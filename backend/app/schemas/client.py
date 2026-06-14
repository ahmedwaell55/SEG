from pydantic import BaseModel, ConfigDict, Field


class ClientBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    phone: str = Field(min_length=3, max_length=50)


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    phone: str | None = Field(default=None, min_length=3, max_length=50)


class ClientOut(ClientBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

