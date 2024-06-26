from pydantic import BaseModel, field_validator
from datetime import datetime


class CreateProject(BaseModel):
    title: str
    description: str | None = None
    demo_link: str | None = None
    source_code: str | None = None


class UpdateProject(CreateProject):
    title: str | None = None


class ReviewSchema(BaseModel):

    body: str | None = None
    value: str

    @field_validator('value')
    def value_validator(cls, value):
        """
        Validator to ensure the value is either 'up' or 'down'.
        """
        if value not in ('up', 'down'):
            raise ValueError("Value must be 'up' or 'down'.")
        return value


class SendProject(CreateProject):
    featured_image: str
    vote_total: int
    vote_ratio: float
    created: datetime
