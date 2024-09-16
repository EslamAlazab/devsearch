from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator, model_validator
from apis.projects.schemas import CreateProject
from apis.users.validators import password_validator


class CreateUser(BaseModel):
    username: str
    email: str
    password: str
    password_2: str

    @field_validator('username', 'email', mode='before')
    def empty_string_to_none(cls, v):
        if v == '':
            return None
        return v


class MessageSchema(BaseModel):
    name: str = Field(max_length=200)
    email: EmailStr = Field(max_length=200)
    subject: str = Field(max_length=200)
    body: str


class ProjectSchema(CreateProject):
    model_config = ConfigDict(extra='ignore')


class Alert(BaseModel):
    msg: str
    tag: str


class ChangePassword(BaseModel):
    password: str
    password2: str

    @field_validator('password')
    def validate_password(cls, v):
        errors: list[str] = password_validator(v)
        if errors:
            raise ValueError(f"{', '.join(errors)}")
        return v

    @model_validator(mode='after')
    def validate_passwords_match(cls, values):
        print(values)
        if values.password != values.password2:
            raise ValueError("Passwords do not match.")
        return values
