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
    Name: str = Field(alias="name")
    Description: Optional[str] = Field(default=None, alias="description")
    Identifier: str = Field(alias="identifier")
    StorageProvider: Optional[str] = Field(default=None, alias="storageProvider")
    StorageParameters: Optional[str] = Field(default=None, alias="storageParameters")
    StorageContainer: Optional[str] = Field(default=None, alias="storageContainer")
    Options: Optional[str] = Field(default=None, alias="options")
    CredentialStoreId: Optional[str] = Field(default=None, alias="credentialStoreId")
    ExternalName: Optional[str] = Field(default=None, alias="externalName")
    Password: Optional[str] = Field(default=None, alias="password")
    FoldersCount: Optional[int] = Field(default=None, alias="foldersCount")
    Encrypted: Optional[bool] = Field(default=None, alias="encrypted")
    Id: Optional[int] = Field(default=None, alias="id")
    Tags: Optional[List[str]] = Field(default=None, alias="tags")
