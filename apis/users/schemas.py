from pydantic import BaseModel, Field, EmailStr, ConfigDict
from uuid import UUID


class CreateProfile(BaseModel):
    username: str = Field(max_length=100)
    email: str = Field(max_length=200)
    password: str


class UpdateProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    first_name: str | None = Field(max_length=50, default=None)
    last_name: str | None = Field(max_length=50, default=None)
    location: str | None = Field(max_length=200, default=None)
    short_intro: str | None = Field(max_length=200, default=None)
    bio: str | None = Field(default=None)
    github: str | None = Field(max_length=200, default=None)
    x: str | None = Field(max_length=200, default=None)
    linkedin: str | None = Field(max_length=200, default=None)
    youtube: str | None = Field(max_length=200, default=None)
    website: str | None = Field(max_length=200, default=None)


# class SendProfile(BaseModel):
#     profile_id: UUID
#     username: str = Field(max_length=100)
#     email: str = Field(max_length=200)
#     first_name: str | None = Field(max_length=50, default=None)
#     last_name: str | None = Field(max_length=50, default=None)
#     location: str | None = Field(max_length=200, default=None)
#     short_intro: str | None = Field(max_length=200, default=None)
#     bio: str | None = Field(default=None)
#     github: str | None = Field(max_length=200, default=None)
#     x: str | None = Field(max_length=200, default=None)
#     linkedin: str | None = Field(max_length=200, default=None)
#     youtube: str | None = Field(max_length=200, default=None)
#     website: str | None = Field(max_length=200, default=None)
#     skills: list[dict]


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class SkillSchema(BaseModel):
    name: str = Field(max_length=200)
    description: str | None = None


class MessageFromUser(BaseModel):
    subject: str = Field(max_length=200)
    body: str
    recipient: str


class MessageFromNonUser(MessageFromUser):
    name: str = Field(max_length=200)
    email: EmailStr = Field(max_length=200)
