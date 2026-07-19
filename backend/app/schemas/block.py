from datetime import date, time

from pydantic import BaseModel


class BlockCreate(BaseModel):
    date: date
    start_time: time
    reason: str | None = None


class BlockRead(BaseModel):
    id: int
    date: date
    start_time: time
    reason: str | None = None
