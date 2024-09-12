from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum


class CreateProject(BaseModel):
    title: str = Field(min_length=2)
    description: str | None = None
    demo_link: str | None = None
    source_code: str | None = None


class UpdateProject(CreateProject):
    title: str | None = None


class ReviewSchema(BaseModel):
    class Value(Enum):
        up_vote = 'up'
        down_vote = 'down'

    model_config = ConfigDict(use_enum_values=True)
    body: str | None = None
    value: Value

    # @field_validator('value')
    # def value_validator(cls, value):
    #     """
    #     Validator to ensure the value is either 'up' or 'down'.
    #     """
    #     if value not in ('up', 'down'):
    #         raise ValueError("Value must be 'up' or 'down'.")
    #     return value


class SendProject(CreateProject):
    featured_image: str
    vote_total: int
    vote_ratio: float
    created: datetime
