from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=72)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class PermissionRead(BaseModel):
    id: int
    code: str
    label: str
    module: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RoleBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=100)
    description: str | None = None
    permission_ids: list[int] = []


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    permission_ids: list[int] | None = None


class RoleRead(BaseModel):
    id: int
    name: str
    label: str
    description: str | None = None
    system: bool
    permission_ids: list[int]
    permissions: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    full_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    is_active: bool = True
    role_ids: list[int] = []
    project_ids: list[int] = []
    center_ids: list[int] = []


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)
    role_ids: list[int] | None = None
    project_ids: list[int] | None = None
    center_ids: list[int] | None = None


class UserRead(BaseModel):
    id: int
    username: str
    full_name: str | None = None
    email: str | None = None
    is_active: bool
    role_ids: list[int]
    roles: list[str]
    permissions: list[str]
    project_ids: list[int]
    center_ids: list[int]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CurrentUserRead(UserRead):
    is_admin: bool
