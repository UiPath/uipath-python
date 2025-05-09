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
    storageProvider: Optional[str] = Field(default=None, alias="StorageProvider")
    storageParameters: Optional[str] = Field(default=None, alias="StorageParameters")
    storageContainer: Optional[str] = Field(default=None, alias="StorageContainer")
    options: Optional[str] = Field(default=None, alias="Options")
    credentialStoreId: Optional[str] = Field(default=None, alias="CredentialStoreId")
    externalName: Optional[str] = Field(default=None, alias="ExternalName")
    password: Optional[str] = Field(default=None, alias="Password")
    foldersCount: Optional[int] = Field(default=None, alias="FoldersCount")
    encrypted: Optional[bool] = Field(default=None, alias="Encrypted")
    id: Optional[int] = Field(default=None, alias="Id")
    tags: Optional[List[str]] = Field(default=None, alias="Tags")
