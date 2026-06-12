from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class DiscoveredTrend:
    keyword: str
    niche: str
    source: str
    score: float = 0.0
    url: str | None = None
    raw_data: dict = field(default_factory=dict)


class BaseTrendDiscoverer(ABC):
    """Abstract base for all trend discovery sources."""

    @abstractmethod
    async def discover(self, niches: list[str]) -> list[DiscoveredTrend]:
        """Return a list of discovered trends for the given niches."""
        ...

    def name(self) -> str:
        return self.__class__.__name__
