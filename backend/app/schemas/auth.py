from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=4, max_length=128)


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=6, max_length=128)
    full_name: str | None = Field(default=None, max_length=150)
    role: str = Field(default="staff", pattern="^(admin|staff)$")
    is_active: bool = True


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=80)
    password: str | None = Field(default=None, min_length=6, max_length=128)
    full_name: str | None = Field(default=None, max_length=150)
    role: str | None = Field(default=None, pattern="^(admin|staff)$")
    is_active: bool | None = None
