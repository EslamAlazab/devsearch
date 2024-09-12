from pydantic import BaseModel, Field, EmailStr, ConfigDict
from projects.schemas import CreateProject


class MessageSchema(BaseModel):
    name: str = Field(max_length=200)
    email: EmailStr = Field(max_length=200)
    subject: str = Field(max_length=200)
    body: str


class ProjectSchema(CreateProject):
    model_config = ConfigDict(extra='ignore')
