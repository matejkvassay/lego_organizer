from typing import Literal

from pydantic import BaseModel, Field


class SetOut(BaseModel):
    set_id: int
    number: str
    number_variant: int
    name: str
    year: int | None
    theme: str | None
    subtheme: str | None
    pieces: int | None
    minifigs: int | None
    image_url: str | None
    thumbnail_url: str | None
    brickset_url: str | None

    model_config = {"from_attributes": True}


class ItemOut(BaseModel):
    id: int
    type: Literal["set", "other"]
    title: str
    description: str | None
    box: str
    notes: str
    tags: list[str]
    set: SetOut | None


class ItemCreate(BaseModel):
    type: Literal["set", "other"]
    brickset_set_id: int | None = None
    title: str | None = None
    description: str | None = None
    box: str = ""
    notes: str = ""
    tags: list[str] = Field(default_factory=list)


class ItemUpdate(BaseModel):
    box: str | None = None
    notes: str | None = None
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class Candidate(BaseModel):
    set_id: int
    number: str
    name: str
    year: int | None = None
    theme: str | None = None
    image_url: str | None = None
    reason: str = ""


class Candidates(BaseModel):
    """Structured output of the add-a-set agent."""

    candidates: list[Candidate] = Field(default_factory=list, max_length=6)
