from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Bucket(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    name: str = Field(alias="Name")
    description: Optional[str] = Field(default=None, alias="Description")
    identifier: str = Field(alias="Identifier")
    storage_provider: Optional[str] = Field(default=None, alias="StorageProvider")
    storage_parameters: Optional[str] = Field(default=None, alias="StorageParameters")
    storage_container: Optional[str] = Field(default=None, alias="StorageContainer")
    options: Optional[str] = Field(default=None, alias="Options")
    credential_store_id: Optional[str] = Field(default=None, alias="CredentialStoreId")
    external_name: Optional[str] = Field(default=None, alias="ExternalName")
    password: Optional[str] = Field(default=None, alias="Password")
    folders_count: Optional[int] = Field(default=None, alias="FoldersCount")
    encrypted: Optional[bool] = Field(default=None, alias="Encrypted")
    id: Optional[int] = Field(default=None, alias="Id")
    tags: Optional[List[str]] = Field(default=None, alias="Tags")
