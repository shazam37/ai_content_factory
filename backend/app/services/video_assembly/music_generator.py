"""
Generates per-topic ambient background music via FFmpeg lavfi synthesis.

Each topic gets uniquely parameterized music:
- 8 mood profiles detected from topic title keywords
- Per-topic chorus detune (2-4 Hz) creates a beating effect unique to each title
- Cached per topic_id so reruns reuse the same track
"""
import asyncio
import logging
import os
import subprocess
from dataclasses import dataclass

from app.core import storage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MusicProfile:
    name: str
    f0: float        # root note (Hz)
    f1: float        # third
    f2: float        # fifth
    echo_ms: int     # reverb delay — long = spacious / cosmic feel
    echo_decay: float
    lowpass: int     # Hz — lower = darker/heavier
    tremolo: float   # pulsing Hz (0 = none) — adds rhythmic energy
    noise: float     # pink noise volume — warmth/texture
    gain: float


# ── 8 mood profiles ──────────────────────────────────────────────────────────
_PROFILES: dict[str, MusicProfile] = {
    # Dark, uneasy — quantum, brain, unknown
    "mysterious": MusicProfile("mysterious",    220.0, 261.6, 329.6, 1200, 0.55,  700, 0.0, 0.05, 0.85),
    # Deep, threatening — death, extinction, black holes
    "ominous":    MusicProfile("ominous",       174.6, 207.7, 261.6, 1900, 0.65,  320, 0.0, 0.08, 0.78),
    # Tense, building — wars, battles, revolutions
    "dramatic":   MusicProfile("dramatic",      155.6, 185.0, 233.1,  900, 0.50,  750, 0.9, 0.04, 0.88),
    # Electronic, cold — AI, robots, algorithms, cyber
    "futuristic": MusicProfile("futuristic",    138.6, 174.6, 220.0,  480, 0.38, 1100, 2.2, 0.02, 0.90),
    # Bright, uplifting — discoveries, breakthroughs, firsts
    "wonder":     MusicProfile("wonder",        196.0, 246.9, 293.7,  850, 0.40, 1050, 0.4, 0.03, 0.92),
    # Vast, meditative — space, universe, philosophy
    "contemplative": MusicProfile("contemplative", 130.8, 164.8, 196.0, 1700, 0.62, 520, 0.0, 0.06, 0.78),
    # Grand, powerful — ancient civilisations, empires, history
    "epic":       MusicProfile("epic",          196.0, 233.1, 293.7, 1050, 0.48,  820, 0.6, 0.04, 0.88),
    # Urgent, kinetic — speed, extremes, explosive reactions
    "energetic":  MusicProfile("energetic",     146.8, 185.0, 220.0,  550, 0.36, 1250, 3.2, 0.02, 0.94),
}

# ── Keyword → profile lookup (first match wins) ───────────────────────────────
_KEYWORD_RULES: list[tuple[list[str], str]] = [
    (["extinction", "apocalypse", "collapse", "black hole", "death of", "doom",
      "plague", "destroy", "dark matter", "void", "silent killer"], "ominous"),
    (["war", "battle", "siege", "invasion", "conquest", "massacre",
      "civil war", "world war", "genocide"], "dramatic"),
    (["revolution", "empire", "dynasty", "rise of", "fall of", "ancient",
      "pyramid", "rome", "egypt", "viking", "mongol", "roman", "greek",
      "medieval", "civilization", "century", "kingdom"], "epic"),
    (["artificial intelligence", " ai ", "robot", "cyber", "algorithm",
      "machine learning", "neural network", "singularity", "computer"], "futuristic"),
    (["quantum", "particle", "neuron", "electricity", "brain",
      "consciousness", "dna", "synapse", "dark web", "mystery", "enigma"], "mysterious"),
    (["space", "galaxy", "universe", "cosmic", "nebula", "supernova",
      "orbit", "telescope", "cosmos", "philosophy", "time travel",
      "multiverse", "reality", "perception"], "contemplative"),
    (["discover", "breakthrough", "first ever", "incredible", "amazing",
      "never before", "solved", "proof", "secret", "hidden truth"], "wonder"),
    (["fastest", "most powerful", "biggest", "extreme", "record",
      "impossible", "lightning", "explosion", "chain reaction", "nuclear",
      "big bang", "speed of light"], "energetic"),
]

_NICHE_DEFAULTS: dict[str, str] = {
    "science": "mysterious", "history": "epic",
    "programming": "futuristic", "ai": "futuristic", "trivia": "wonder",
}


def _pick_profile(topic_title: str, niche: str) -> MusicProfile:
    tl = " " + topic_title.lower() + " "
    for keywords, name in _KEYWORD_RULES:
        if any(kw in tl for kw in keywords):
            return _PROFILES[name]
    return _PROFILES[_NICHE_DEFAULTS.get(niche.lower(), "mysterious")]


def _generate_music_sync(
    output_path: str,
    gen_dur: float,
    profile: MusicProfile,
    detune: float,
) -> None:
    """
    FFmpeg command that synthesises a 3-voice chorus pad:
      voices 0-5 : three sine pairs (clean + detuned) → beating/chorus effect
      voice  6   : pink noise → warmth
    """
    f0, f1, f2 = profile.f0, profile.f1, profile.f2
    # Slightly different detune per voice for a richer stereo spread
    d0, d1, d2 = detune, detune * 1.3, detune * 0.7

    eg, oc = 0.80, 0.90
    ms, dc = profile.echo_ms, profile.echo_decay

    def seg(ia: int, ib: int, vol: float, ms_scale: float) -> str:
        return (
            f"[{ia}:a][{ib}:a]amix=inputs=2:duration=longest,"
            f"aecho={eg}:{oc}:{max(150, int(ms * ms_scale))}:{dc},"
            f"volume={vol}"
        )

    tremolo_f = f"tremolo=f={profile.tremolo}:d={min(0.28, 0.12 + profile.tremolo * 0.03):.2f}," \
        if profile.tremolo > 0 else ""

    fc = (
        f"{seg(0, 1, 0.13, 1.00)}[s0];"
        f"{seg(2, 3, 0.11, 0.85)}[s1];"
        f"{seg(4, 5, 0.11, 0.70)}[s2];"
        f"[6:a]lowpass=f=380,volume={profile.noise:.2f}[noise];"
        f"[s0][s1][s2][noise]amix=inputs=4:duration=longest,"
        f"lowpass=f={profile.lowpass},"
        f"{tremolo_f}"
        f"afade=t=in:st=0:d=4,"
        f"volume={profile.gain}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=f={f0:.2f}:sample_rate=44100",
        "-f", "lavfi", "-i", f"sine=f={f0 + d0:.2f}:sample_rate=44100",
        "-f", "lavfi", "-i", f"sine=f={f1:.2f}:sample_rate=44100",
        "-f", "lavfi", "-i", f"sine=f={f1 + d1:.2f}:sample_rate=44100",
        "-f", "lavfi", "-i", f"sine=f={f2:.2f}:sample_rate=44100",
        "-f", "lavfi", "-i", f"sine=f={f2 + d2:.2f}:sample_rate=44100",
        "-f", "lavfi", "-i", "anoisesrc=c=pink:a=0.04:sample_rate=44100",
        "-filter_complex", fc,
        "-t", str(gen_dur),
        "-c:a", "libmp3lame", "-q:a", "4",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=90)
    if result.returncode != 0:
        raise RuntimeError(f"Music gen failed: {result.stderr.decode()[:400]}")
    logger.info(
        "Music ready: %s  profile=%s detune=%.1fHz",
        output_path, profile.name, detune,
    )


async def get_background_music(
    video_duration: float,
    topic_id: int,
    topic_title: str,
    niche: str = "science",
) -> str | None:
    """
    Return path to per-topic ambient music.
    Generates on first call, cached to /storage/audio/_bg_music_{topic_id}.mp3.
    """
    cache_path = storage.audio_path(f"_bg_music_{topic_id}.mp3")
    if os.path.exists(cache_path):
        logger.debug("Reusing cached music: %s", cache_path)
        return cache_path

    profile = _pick_profile(topic_title, niche)
    # detune: 2.0, 2.5, or 3.0 Hz based on title hash — unique per topic
    detune = 2.0 + (abs(hash(topic_title)) % 3) * 0.5
    gen_dur = max(video_duration + 15.0, 180.0)

    logger.info(
        "Generating music for topic %d (%r)  profile=%s detune=%.1fHz",
        topic_id, topic_title[:50], profile.name, detune,
    )
    try:
        await asyncio.to_thread(_generate_music_sync, cache_path, gen_dur, profile, detune)
        return cache_path
    except Exception as exc:
        logger.warning("Background music failed: %s", exc)
        return None
