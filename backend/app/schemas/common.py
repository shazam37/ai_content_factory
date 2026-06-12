from pydantic import BaseModel


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list


class MessageResponse(BaseModel):
    message: str


class TaskResponse(BaseModel):
    task_id: str
    message: str
