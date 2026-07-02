Public facade for the Data Fabric entities surface.

:class:`EntitiesService` keeps the existing `sdk.entities.*` API flat and unchanged from a caller's perspective while delegating each operation to the appropriate underlying service:

- :class:`EntitySchemaService` — entity definitions, choice set listings, create / delete / update-metadata lifecycle.
- :class:`EntityDataService` — record CRUD (single and batch), structured queries, attachments, choice-set values, bulk import, and federated SQL queries.

The facade additionally owns cross-cutting concerns such as agent entity-set resolution.

## EntitiesService

Service for managing UiPath Data Service entities.

Entities are database tables in UiPath Data Service that store structured data for automation processes. This service is the unified entry point for every entity operation: schema management, record CRUD, structured and SQL queries, file attachments, choice sets, and bulk import.

See Also

<https://docs.uipath.com/data-service/automation-cloud/latest/user-guide/introduction>

Preview Feature

This service is currently experimental. Behavior and parameters are subject to change in future versions.

### __init__

```
__init__(
    config,
    execution_context,
    folders_service=None,
    folders_map=None,
    entity_name_overrides=None,
    routing_context=None,
)
```

Initialise the facade and its underlying schema and data services.

### create_entity

```
create_entity(name, fields, options=None)
```

Create a new entity with the given schema and return its id.

Parameters:

| Name      | Type                             | Description                                                                                                                                                                      | Default                                                                                                         |
| --------- | -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `name`    | `str`                            | Entity name. Must start with a letter and contain only letters, digits, and underscores (3-100 characters).                                                                      | *required*                                                                                                      |
| `fields`  | `list[EntityCreateFieldOptions]` | Field definitions for the new entity. Each entry declares the field's name, type, and optional constraints such as length_limit, decimal_precision, is_required, is_unique, etc. | *required*                                                                                                      |
| `options` | \`EntityCreateOptions            | None\`                                                                                                                                                                           | Optional entity-level settings such as display name, description, folder placement, and RBAC / analytics flags. |

Returns:

| Name  | Type  | Description                                |
| ----- | ----- | ------------------------------------------ |
| `str` | `str` | The id (UUID) of the newly created entity. |

Raises:

| Type         | Description                                                                                                                                                                                   |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ValueError` | If the entity name or any field name fails the client-side validation (regex / length / reserved names) or if a per-field constraint is not supported for that field type or is out of range. |

Examples:

Create a simple entity::

```
from uipath.platform.entities import (
    EntityCreateFieldOptions,
    EntityCreateOptions,
    EntityFieldDataType,
)

entity_id = entities_service.create_entity(
    "ProductCatalog",
    [
        EntityCreateFieldOptions(
            field_name="product_name",
            type=EntityFieldDataType.STRING,
            is_required=True,
            is_unique=True,
        ),
        EntityCreateFieldOptions(
            field_name="price",
            type=EntityFieldDataType.DECIMAL,
            decimal_precision=2,
        ),
    ],
    options=EntityCreateOptions(
        display_name="Product Catalog",
        description="Inventory of available products",
        is_rbac_enabled=True,
    ),
)
```

### create_entity_async

```
create_entity_async(name, fields, options=None)
```

Asynchronously create a new entity with the given schema.

Parameters:

| Name      | Type                             | Description                                                | Default                         |
| --------- | -------------------------------- | ---------------------------------------------------------- | ------------------------------- |
| `name`    | `str`                            | Entity name; same validation rules as :meth:create_entity. | *required*                      |
| `fields`  | `list[EntityCreateFieldOptions]` | Field definitions.                                         | *required*                      |
| `options` | \`EntityCreateOptions            | None\`                                                     | Optional entity-level settings. |

Returns:

| Name  | Type  | Description                                |
| ----- | ----- | ------------------------------------------ |
| `str` | `str` | The id (UUID) of the newly created entity. |

Raises:

| Type         | Description                          |
| ------------ | ------------------------------------ |
| `ValueError` | For client-side validation failures. |

Examples:

Create a simple entity::

```
from uipath.platform.entities import (
    EntityCreateFieldOptions,
    EntityFieldDataType,
)

entity_id = await entities_service.create_entity_async(
    "ProductCatalog",
    [
        EntityCreateFieldOptions(
            field_name="product_name",
            type=EntityFieldDataType.STRING,
            is_required=True,
        ),
    ],
)
```

### delete_attachment

```
delete_attachment(
    entity_id, record_id, field_name, expansion_level=None
)
```

Remove the file attached to a File-type field on a record.

Parameters:

| Name              | Type  | Description                                                            | Default                                                             |
| ----------------- | ----- | ---------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `entity_id`       | `str` | The unique identifier of the entity.                                   | *required*                                                          |
| `record_id`       | `str` | The unique identifier of the record whose attachment is being removed. | *required*                                                          |
| `field_name`      | `str` | Name of the File-type field on the entity.                             | *required*                                                          |
| `expansion_level` | \`int | None\`                                                                 | Optional FK expansion depth in the response (0 means no expansion). |

Returns:

| Type             | Description                                                                                                                 |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `dict[str, Any]` | Dict\[str, Any\]: The decoded JSON response (typically the updated record), or an empty dict when the response has no body. |

Examples:

Clear an attachment::

```
entities_service.delete_attachment(
    "Customers", "rec-1", "Contract"
)
```

### delete_attachment_async

```
delete_attachment_async(
    entity_id, record_id, field_name, expansion_level=None
)
```

Asynchronously remove the file attached to a File-type field.

Parameters:

| Name              | Type  | Description                                                            | Default                      |
| ----------------- | ----- | ---------------------------------------------------------------------- | ---------------------------- |
| `entity_id`       | `str` | The unique identifier of the entity.                                   | *required*                   |
| `record_id`       | `str` | The unique identifier of the record whose attachment is being removed. | *required*                   |
| `field_name`      | `str` | Name of the File-type field on the entity.                             | *required*                   |
| `expansion_level` | \`int | None\`                                                                 | Optional FK expansion depth. |

Returns:

| Type             | Description                                  |
| ---------------- | -------------------------------------------- |
| `dict[str, Any]` | Dict\[str, Any\]: The decoded JSON response. |

Examples:

Clear an attachment::

```
await entities_service.delete_attachment_async(
    "Customers", "rec-1", "Contract"
)
```

### delete_entity

```
delete_entity(entity_id)
```

Delete an entity and all of its records.

Parameters:

| Name        | Type  | Description                                    | Default    |
| ----------- | ----- | ---------------------------------------------- | ---------- |
| `entity_id` | `str` | The unique identifier of the entity to delete. | *required* |

Examples:

Delete an entity by id::

```
entities_service.delete_entity("a1b2c3d4-...")
```

### delete_entity_async

```
delete_entity_async(entity_id)
```

Asynchronously delete an entity and all of its records.

Parameters:

| Name        | Type  | Description                                    | Default    |
| ----------- | ----- | ---------------------------------------------- | ---------- |
| `entity_id` | `str` | The unique identifier of the entity to delete. | *required* |

Examples:

Delete an entity by id::

```
await entities_service.delete_entity_async("a1b2c3d4-...")
```

### delete_record

```
delete_record(entity_key, record_id)
```

Delete a single record by id.

Note

Unlike :meth:`delete_records` (batch), this single-record endpoint fires Data Fabric trigger events. Use this method when triggers attached to the entity must run on delete.

Parameters:

| Name         | Type  | Description                                    | Default    |
| ------------ | ----- | ---------------------------------------------- | ---------- |
| `entity_key` | `str` | The unique key/identifier of the entity.       | *required* |
| `record_id`  | `str` | The unique identifier of the record to delete. | *required* |

Examples:

Delete by id::

```
entities_service.delete_record("Customers", "rec-1")
```

### delete_record_async

```
delete_record_async(entity_key, record_id)
```

Asynchronously delete a single record by id.

Note

Unlike :meth:`delete_records_async` (batch), this single-record endpoint fires Data Fabric trigger events.

Parameters:

| Name         | Type  | Description                                    | Default    |
| ------------ | ----- | ---------------------------------------------- | ---------- |
| `entity_key` | `str` | The unique key/identifier of the entity.       | *required* |
| `record_id`  | `str` | The unique identifier of the record to delete. | *required* |

Examples:

Delete by id::

```
await entities_service.delete_record_async("Customers", "rec-1")
```

### delete_records

```
delete_records(entity_key, record_ids, fail_on_first=None)
```

Delete multiple records from an entity in a single batch operation.

Parameters:

| Name            | Type        | Description                              | Default                                                                                                                                                                     |
| --------------- | ----------- | ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_key`    | `str`       | The unique key/identifier of the entity. | *required*                                                                                                                                                                  |
| `record_ids`    | `list[str]` | List of record IDs (GUIDs) to delete.    | *required*                                                                                                                                                                  |
| `fail_on_first` | \`bool      | None\`                                   | When True, stop the batch on the first per-record failure. When False (default), all records are attempted and the response lists both success_records and failure_records. |

Returns:

| Name                         | Type                         | Description                                                                                                                                                                                                           |
| ---------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityRecordsBatchResponse` | `EntityRecordsBatchResponse` | Response containing successful and failed record operations. - success_records: List of successfully deleted :class:EntityRecord objects - failure_records: List of :class:FailureRecord describing per-record errors |

Examples:

Delete specific records by ID::

```
# Delete records by their IDs
record_ids = [
    "12345678-1234-1234-1234-123456789012",
    "87654321-4321-4321-4321-210987654321",
]

response = entities_service.delete_records(
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    record_ids
)

print(f"Deleted: {len(response.success_records)}")
print(f"Failed: {len(response.failure_records)}")
```

Delete records matching a condition::

```
# Get all records
records = entities_service.list_records("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# Filter records to delete (e.g., inactive customers)
ids_to_delete = [
    record.id for record in records
    if not getattr(record, 'is_active', True)
]

if ids_to_delete:
    response = entities_service.delete_records(
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        ids_to_delete
    )
    print(f"Deleted {len(response.success_records)} inactive records")
```

### delete_records_async

```
delete_records_async(
    entity_key, record_ids, fail_on_first=None
)
```

Asynchronously delete multiple records from an entity in a single batch operation.

Parameters:

| Name            | Type        | Description                              | Default                                                                                                                                                                     |
| --------------- | ----------- | ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_key`    | `str`       | The unique key/identifier of the entity. | *required*                                                                                                                                                                  |
| `record_ids`    | `list[str]` | List of record IDs (GUIDs) to delete.    | *required*                                                                                                                                                                  |
| `fail_on_first` | \`bool      | None\`                                   | When True, stop the batch on the first per-record failure. When False (default), all records are attempted and the response lists both success_records and failure_records. |

Returns:

| Name                         | Type                         | Description                                                                                                                                                                                                           |
| ---------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityRecordsBatchResponse` | `EntityRecordsBatchResponse` | Response containing successful and failed record operations. - success_records: List of successfully deleted :class:EntityRecord objects - failure_records: List of :class:FailureRecord describing per-record errors |

Examples:

Delete specific records by ID::

```
# Delete records by their IDs
record_ids = [
    "12345678-1234-1234-1234-123456789012",
    "87654321-4321-4321-4321-210987654321",
]

response = await entities_service.delete_records_async(
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    record_ids
)

print(f"Deleted: {len(response.success_records)}")
print(f"Failed: {len(response.failure_records)}")
```

Delete records matching a condition::

```
# Get all records
records = await entities_service.list_records_async("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# Filter records to delete (e.g., inactive customers)
ids_to_delete = [
    record.id for record in records
    if not getattr(record, 'is_active', True)
]

if ids_to_delete:
    response = await entities_service.delete_records_async(
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        ids_to_delete
    )
    print(f"Deleted {len(response.success_records)} inactive records")
```

### download_attachment

```
download_attachment(entity_id, record_id, field_name)
```

Download a file attached to a record and return its raw bytes.

Parameters:

| Name         | Type  | Description                                                    | Default    |
| ------------ | ----- | -------------------------------------------------------------- | ---------- |
| `entity_id`  | `str` | The unique identifier of the entity.                           | *required* |
| `record_id`  | `str` | The unique identifier of the record containing the attachment. | *required* |
| `field_name` | `str` | Name of the File-type field on the entity.                     | *required* |

Returns:

| Name    | Type    | Description           |
| ------- | ------- | --------------------- |
| `bytes` | `bytes` | The raw file content. |

Examples:

Save the downloaded bytes to disk::

```
content = entities_service.download_attachment(
    "Customers", "rec-1", "Contract"
)
with open("downloaded.pdf", "wb") as f:
    f.write(content)
```

### download_attachment_async

```
download_attachment_async(entity_id, record_id, field_name)
```

Asynchronously download a file attached to a record.

Parameters:

| Name         | Type  | Description                                                    | Default    |
| ------------ | ----- | -------------------------------------------------------------- | ---------- |
| `entity_id`  | `str` | The unique identifier of the entity.                           | *required* |
| `record_id`  | `str` | The unique identifier of the record containing the attachment. | *required* |
| `field_name` | `str` | Name of the File-type field on the entity.                     | *required* |

Returns:

| Name    | Type    | Description           |
| ------- | ------- | --------------------- |
| `bytes` | `bytes` | The raw file content. |

Examples:

Save the downloaded bytes to disk::

```
content = await entities_service.download_attachment_async(
    "Customers", "rec-1", "Contract"
)
with open("downloaded.pdf", "wb") as f:
    f.write(content)
```

### get_choiceset_values

```
get_choiceset_values(choiceset_id, start=None, limit=None)
```

Get the values of a choice set by its ID.

Parameters:

| Name           | Type  | Description                              | Default                            |
| -------------- | ----- | ---------------------------------------- | ---------------------------------- |
| `choiceset_id` | `str` | The unique identifier of the choice set. | *required*                         |
| `start`        | \`int | None\`                                   | Optional offset for pagination.    |
| `limit`        | \`int | None\`                                   | Optional page size for pagination. |

Returns:

| Type                   | Description                                                                                                  |
| ---------------------- | ------------------------------------------------------------------------------------------------------------ |
| `list[ChoiceSetValue]` | List\[ChoiceSetValue\]: The values in the choice set, each containing id, name, display_name, and number_id. |

Examples:

Get all values in a choice set::

```
values = entities_service.get_choiceset_values("choiceset-id")
for v in values:
    print(f"{v.number_id}: {v.display_name}")
```

### get_choiceset_values_async

```
get_choiceset_values_async(
    choiceset_id, start=None, limit=None
)
```

Asynchronously get the values of a choice set by its ID.

Parameters:

| Name           | Type  | Description                              | Default                            |
| -------------- | ----- | ---------------------------------------- | ---------------------------------- |
| `choiceset_id` | `str` | The unique identifier of the choice set. | *required*                         |
| `start`        | \`int | None\`                                   | Optional offset for pagination.    |
| `limit`        | \`int | None\`                                   | Optional page size for pagination. |

Returns:

| Type                   | Description                                           |
| ---------------------- | ----------------------------------------------------- |
| `list[ChoiceSetValue]` | List\[ChoiceSetValue\]: The values in the choice set. |

### get_record

```
get_record(entity_key, record_id, expansion_level=None)
```

Fetch a single entity record by its id.

Parameters:

| Name              | Type  | Description                                   | Default                                                                |
| ----------------- | ----- | --------------------------------------------- | ---------------------------------------------------------------------- |
| `entity_key`      | `str` | The unique key/identifier of the entity.      | *required*                                                             |
| `record_id`       | `str` | The unique identifier of the record to fetch. | *required*                                                             |
| `expansion_level` | \`int | None\`                                        | Depth of foreign-key expansion in the response (0 means no expansion). |

Returns:

| Name           | Type           | Description                                       |
| -------------- | -------------- | ------------------------------------------------- |
| `EntityRecord` | `EntityRecord` | The record, with optional expanded relationships. |

Examples:

Basic usage::

```
record = entities_service.get_record("Customers", "rec-1")
print(record.id, record.name)
```

With FK expansion::

```
# Inline the related Company record on the returned Customer
record = entities_service.get_record(
    "Customers", "rec-1", expansion_level=1
)
```

### get_record_async

```
get_record_async(
    entity_key, record_id, expansion_level=None
)
```

Asynchronously fetch a single entity record by its id.

Parameters:

| Name              | Type  | Description                                   | Default                                                                |
| ----------------- | ----- | --------------------------------------------- | ---------------------------------------------------------------------- |
| `entity_key`      | `str` | The unique key/identifier of the entity.      | *required*                                                             |
| `record_id`       | `str` | The unique identifier of the record to fetch. | *required*                                                             |
| `expansion_level` | \`int | None\`                                        | Depth of foreign-key expansion in the response (0 means no expansion). |

Returns:

| Name           | Type           | Description |
| -------------- | -------------- | ----------- |
| `EntityRecord` | `EntityRecord` | The record. |

Examples:

Basic usage::

```
record = await entities_service.get_record_async("Customers", "rec-1")
print(record.id, record.name)
```

### import_records

```
import_records(entity_id, file=None, file_path=None)
```

Bulk-import records into an entity from a CSV file.

Provide exactly one of `file` (raw bytes) or `file_path` (path on disk).

Parameters:

| Name        | Type          | Description                          | Default                                                     |
| ----------- | ------------- | ------------------------------------ | ----------------------------------------------------------- |
| `entity_id` | `str`         | The unique identifier of the entity. | *required*                                                  |
| `file`      | \`FileContent | None\`                               | Raw bytes of a CSV file. Mutually exclusive with file_path. |
| `file_path` | \`str         | None\`                               | Path to a local CSV file. Mutually exclusive with file.     |

Returns:

| Name                          | Type                          | Description                                                                                                                                                  |
| ----------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `EntityImportRecordsResponse` | `EntityImportRecordsResponse` | Reports the total rows in the file, the number successfully inserted, and an optional error_file_link pointing to a CSV listing rows that failed validation. |

Examples:

Import from a path on disk::

```
result = entities_service.import_records(
    "Customers", file_path="./customers.csv"
)
print(
    f"Inserted {result.inserted_records} of "
    f"{result.total_records} rows"
)
if result.error_file_link:
    print(f"Errors: {result.error_file_link}")
```

### import_records_async

```
import_records_async(entity_id, file=None, file_path=None)
```

Asynchronously bulk-import records into an entity from a CSV file.

Provide exactly one of `file` (raw bytes) or `file_path` (path on disk).

Parameters:

| Name        | Type          | Description                          | Default                   |
| ----------- | ------------- | ------------------------------------ | ------------------------- |
| `entity_id` | `str`         | The unique identifier of the entity. | *required*                |
| `file`      | \`FileContent | None\`                               | Raw bytes of a CSV file.  |
| `file_path` | \`str         | None\`                               | Path to a local CSV file. |

Returns:

| Name                          | Type                          | Description                                                       |
| ----------------------------- | ----------------------------- | ----------------------------------------------------------------- |
| `EntityImportRecordsResponse` | `EntityImportRecordsResponse` | Reports the total, inserted, and error_file_link for failed rows. |

Examples:

Import from a path on disk::

```
result = await entities_service.import_records_async(
    "Customers", file_path="./customers.csv"
)
print(
    f"Inserted {result.inserted_records} of "
    f"{result.total_records} rows"
)
```

### insert_record

```
insert_record(entity_key, data, expansion_level=None)
```

Insert a single record into an entity and return the inserted row.

Note

Unlike :meth:`insert_records` (batch), this single-record endpoint fires Data Fabric trigger events. Use this method when triggers attached to the entity must run.

Parameters:

| Name              | Type  | Description                                                                                         | Default                                                                |
| ----------------- | ----- | --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `entity_key`      | `str` | The unique key/identifier of the entity.                                                            | *required*                                                             |
| `data`            | `Any` | Record payload — a dict, a Pydantic model, an :class:EntityRecord, or any object exposing __dict__. | *required*                                                             |
| `expansion_level` | \`int | None\`                                                                                              | Depth of foreign-key expansion in the response (0 means no expansion). |

Returns:

| Name           | Type           | Description                                                                      |
| -------------- | -------------- | -------------------------------------------------------------------------------- |
| `EntityRecord` | `EntityRecord` | The inserted record with its server-assigned Id plus any expanded relationships. |

Examples:

Insert from a dict::

```
record = entities_service.insert_record(
    "Customers",
    {"name": "Alice", "email": "alice@example.com"},
)
print(record.id)
```

Insert from a Pydantic model::

```
class CustomerInput(BaseModel):
    name: str
    email: str

record = entities_service.insert_record(
    "Customers",
    CustomerInput(name="Bob", email="bob@example.com"),
    expansion_level=1,
)
```

### insert_record_async

```
insert_record_async(entity_key, data, expansion_level=None)
```

Asynchronously insert a single record into an entity.

Note

Unlike :meth:`insert_records_async` (batch), this single-record endpoint fires Data Fabric trigger events. Use this method when triggers attached to the entity must run.

Parameters:

| Name              | Type  | Description                                                                                         | Default                                                                |
| ----------------- | ----- | --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `entity_key`      | `str` | The unique key/identifier of the entity.                                                            | *required*                                                             |
| `data`            | `Any` | Record payload — a dict, a Pydantic model, an :class:EntityRecord, or any object exposing __dict__. | *required*                                                             |
| `expansion_level` | \`int | None\`                                                                                              | Depth of foreign-key expansion in the response (0 means no expansion). |

Returns:

| Name           | Type           | Description                                      |
| -------------- | -------------- | ------------------------------------------------ |
| `EntityRecord` | `EntityRecord` | The inserted record with its server-assigned Id. |

Examples:

Insert from a dict::

```
record = await entities_service.insert_record_async(
    "Customers",
    {"name": "Alice", "email": "alice@example.com"},
)
print(record.id)
```

### insert_records

```
insert_records(
    entity_key,
    records,
    schema=None,
    expansion_level=None,
    fail_on_first=None,
)
```

Insert multiple records into an entity in a single batch operation.

Parameters:

| Name              | Type        | Description                                                                                                                      | Default                                                                                                                                                                     |
| ----------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_key`      | `str`       | The unique key/identifier of the entity.                                                                                         | *required*                                                                                                                                                                  |
| `records`         | `list[Any]` | List of records to insert. Each record may be a dict, a Pydantic model, an :class:EntityRecord, or any object exposing __dict__. | *required*                                                                                                                                                                  |
| `schema`          | \`Type[Any] | None\`                                                                                                                           | Optional schema class for validation. When provided, validates that each record in the response matches the schema structure.                                               |
| `expansion_level` | \`int       | None\`                                                                                                                           | Depth of foreign-key expansion in the response (0 means no expansion).                                                                                                      |
| `fail_on_first`   | \`bool      | None\`                                                                                                                           | When True, stop the batch on the first per-record failure. When False (default), all records are attempted and the response lists both success_records and failure_records. |

Returns:

| Name                         | Type                         | Description                                                                                                                                                                                                            |
| ---------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityRecordsBatchResponse` | `EntityRecordsBatchResponse` | Response containing successful and failed record operations. - success_records: List of successfully inserted :class:EntityRecord objects - failure_records: List of :class:FailureRecord describing per-record errors |

Examples:

Insert records without schema::

```
class Customer:
    def __init__(self, name, email, age):
        self.name = name
        self.email = email
        self.age = age

customers = [
    Customer("John Doe", "john@example.com", 30),
    Customer("Jane Smith", "jane@example.com", 25),
]

response = entities_service.insert_records(
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    customers
)

print(f"Inserted: {len(response.success_records)}")
print(f"Failed: {len(response.failure_records)}")
```

Insert with FK expansion and fail-fast::

```
response = entities_service.insert_records(
    "Orders",
    [{"product_id": "p-1", "qty": 3}, {"product_id": "p-2", "qty": 1}],
    expansion_level=1,    # inline the related Product on each response record
    fail_on_first=True,   # abort the batch at the first error
)
```

Insert with schema validation::

```
class CustomerSchema:
    name: str
    email: str
    age: int

class Customer:
    def __init__(self, name, email, age):
        self.name = name
        self.email = email
        self.age = age

customers = [Customer("Alice Brown", "alice@example.com", 28)]

response = entities_service.insert_records(
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    customers,
    schema=CustomerSchema
)

# Access inserted records with validated structure
for record in response.success_records:
    print(f"Inserted: {record.name} (ID: {record.id})")
```

### insert_records_async

```
insert_records_async(
    entity_key,
    records,
    schema=None,
    expansion_level=None,
    fail_on_first=None,
)
```

Asynchronously insert multiple records into an entity in a single batch operation.

Parameters:

| Name              | Type        | Description                                                                                                                      | Default                                                                                                                                                                     |
| ----------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_key`      | `str`       | The unique key/identifier of the entity.                                                                                         | *required*                                                                                                                                                                  |
| `records`         | `list[Any]` | List of records to insert. Each record may be a dict, a Pydantic model, an :class:EntityRecord, or any object exposing __dict__. | *required*                                                                                                                                                                  |
| `schema`          | \`Type[Any] | None\`                                                                                                                           | Optional schema class for validation. When provided, validates that each record in the response matches the schema structure.                                               |
| `expansion_level` | \`int       | None\`                                                                                                                           | Depth of foreign-key expansion in the response (0 means no expansion).                                                                                                      |
| `fail_on_first`   | \`bool      | None\`                                                                                                                           | When True, stop the batch on the first per-record failure. When False (default), all records are attempted and the response lists both success_records and failure_records. |

Returns:

| Name                         | Type                         | Description                                                                                                                                                                                                            |
| ---------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityRecordsBatchResponse` | `EntityRecordsBatchResponse` | Response containing successful and failed record operations. - success_records: List of successfully inserted :class:EntityRecord objects - failure_records: List of :class:FailureRecord describing per-record errors |

Examples:

Insert records without schema::

```
class Customer:
    def __init__(self, name, email, age):
        self.name = name
        self.email = email
        self.age = age

customers = [
    Customer("John Doe", "john@example.com", 30),
    Customer("Jane Smith", "jane@example.com", 25),
]

response = await entities_service.insert_records_async(
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    customers
)

print(f"Inserted: {len(response.success_records)}")
print(f"Failed: {len(response.failure_records)}")
```

Insert with schema validation::

```
class CustomerSchema:
    name: str
    email: str
    age: int

class Customer:
    def __init__(self, name, email, age):
        self.name = name
        self.email = email
        self.age = age

customers = [Customer("Alice Brown", "alice@example.com", 28)]

response = await entities_service.insert_records_async(
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    customers,
    schema=CustomerSchema
)

# Access inserted records with validated structure
for record in response.success_records:
    print(f"Inserted: {record.name} (ID: {record.id})")
```

### list_choicesets

```
list_choicesets()
```

List all choice sets in Data Service.

Returns:

| Type           | Description                                        |
| -------------- | -------------------------------------------------- |
| `list[Entity]` | List\[Entity\]: A list of all choice set entities. |

Examples:

List all choice sets::

```
choicesets = entities_service.list_choicesets()
for cs in choicesets:
    print(f"{cs.display_name} ({cs.id})")
```

### list_choicesets_async

```
list_choicesets_async()
```

Asynchronously list all choice sets in Data Service.

Returns:

| Type           | Description                                        |
| -------------- | -------------------------------------------------- |
| `list[Entity]` | List\[Entity\]: A list of all choice set entities. |

### list_entities

```
list_entities()
```

List all entities in Data Service.

Returns:

| Type           | Description                                                                                                                                                               |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `list[Entity]` | List\[Entity\]: A list of all entities with their metadata and field definitions. Each entity includes name, display name, fields, record count, and storage information. |

Examples:

List all entities::

```
# Get all entities in the Data Service
entities = entities_service.list_entities()
for entity in entities:
    print(f"{entity.display_name} ({entity.name})")
```

Find entities with RBAC enabled::

```
entities = entities_service.list_entities()

# Filter to entities with row-based access control
rbac_entities = [
    e for e in entities
    if e.is_rbac_enabled
]
```

Summary report::

```
entities = entities_service.list_entities()

total_records = sum(e.record_count or 0 for e in entities)
total_storage = sum(e.storage_size_in_mb or 0 for e in entities)

print(f"Total entities: {len(entities)}")
print(f"Total records: {total_records}")
print(f"Total storage: {total_storage:.2f} MB")
```

### list_entities_async

```
list_entities_async()
```

Asynchronously list all entities in the Data Service.

Returns:

| Type           | Description                                                                                                                                                               |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `list[Entity]` | List\[Entity\]: A list of all entities with their metadata and field definitions. Each entity includes name, display name, fields, record count, and storage information. |

Examples:

List all entities::

```
# Get all entities in the Data Service
entities = await entities_service.list_entities_async()
for entity in entities:
    print(f"{entity.display_name} ({entity.name})")
```

Find entities with RBAC enabled::

```
entities = await entities_service.list_entities_async()

# Filter to entities with row-based access control
rbac_entities = [
    e for e in entities
    if e.is_rbac_enabled
]
```

Summary report::

```
entities = await entities_service.list_entities_async()

total_records = sum(e.record_count or 0 for e in entities)
total_storage = sum(e.storage_size_in_mb or 0 for e in entities)

print(f"Total entities: {len(entities)}")
print(f"Total records: {total_records}")
print(f"Total storage: {total_storage:.2f} MB")
```

### list_records

```
list_records(
    entity_key,
    schema=None,
    start=None,
    limit=None,
    expansion_level=None,
    filter=None,
    orderby=None,
    select=None,
    expand=None,
)
```

List records from an entity with optional pagination and schema validation.

The schema parameter enables type-safe access to entity records by validating the data against a user-defined class with type annotations. When provided, each record is validated against the schema's field definitions before being returned.

Parameters:

| Name              | Type        | Description                              | Default                                                                                                                                                                                                                                                                                                               |
| ----------------- | ----------- | ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_key`      | `str`       | The unique key/identifier of the entity. | *required*                                                                                                                                                                                                                                                                                                            |
| `schema`          | \`Type[Any] | None\`                                   | Optional schema class for validation. This should be a Python class with type-annotated fields that match the entity's structure. Field Validation Rules: - Required fields: Use standard type annotations (e.g., name: str) - Optional fields: Use Optional or union with None (e.g., age: Optional[int] or age: int |
| `start`           | \`int       | None\`                                   | Starting index for pagination (0-based).                                                                                                                                                                                                                                                                              |
| `limit`           | \`int       | None\`                                   | Maximum number of records to return.                                                                                                                                                                                                                                                                                  |
| `expansion_level` | \`int       | None\`                                   | Depth of foreign-key expansion in the response (0 means no expansion). Higher values inline related records up to that many hops.                                                                                                                                                                                     |
| `filter`          | \`str       | None\`                                   | OData $filter expression (e.g. "status eq 'active'").                                                                                                                                                                                                                                                                 |
| `orderby`         | \`str       | None\`                                   | OData $orderby expression (e.g. "created_at desc").                                                                                                                                                                                                                                                                   |
| `select`          | \`list[str] | None\`                                   | Column projection — field names to include (rendered as $select).                                                                                                                                                                                                                                                     |
| `expand`          | \`list[str] | None\`                                   | Relationship names to expand inline (rendered as $expand).                                                                                                                                                                                                                                                            |

Returns:

| Name                        | Type                        | Description                                                                                                                                                                               |
| --------------------------- | --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityRecordsListResponse` | `EntityRecordsListResponse` | A list-compatible response with total_count, has_next_page and next_cursor pagination metadata. Iteration, indexing, and len() continue to work like a plain list of :class:EntityRecord. |

Raises:

| Type         | Description                                                                                                                         |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| `ValueError` | If schema validation fails for any record, including cases where required fields are missing or field types don't match the schema. |

Examples:

Basic usage without schema::

```
# Retrieve all records from an entity
records = entities_service.list_records("Customers")
for record in records:
    print(record.id)
```

With pagination::

```
# Get first 50 records
records = entities_service.list_records("Customers", start=0, limit=50)
print(f"Showing {len(records)} of {records.total_count} total")
if records.has_next_page:
    next_page = entities_service.list_records(
        "Customers", start=50, limit=50
    )
```

With OData filter, sorting, projection, and expansion::

```
records = entities_service.list_records(
    "Customers",
    filter="status eq 'active'",
    orderby="created_at desc",
    select=["name", "email", "status"],
    expand=["company"],
    expansion_level=1,
)
```

With schema validation::

```
class CustomerRecord:
    name: str
    email: str
    age: Optional[int]
    is_active: bool

# Records are validated against CustomerRecord schema
records = entities_service.list_records(
    "Customers",
    schema=CustomerRecord
)

# Safe to access fields knowing they match the schema
for record in records:
    print(f"{record.name}: {record.email}")
```

### list_records_async

```
list_records_async(
    entity_key,
    schema=None,
    start=None,
    limit=None,
    expansion_level=None,
    filter=None,
    orderby=None,
    select=None,
    expand=None,
)
```

Asynchronously list records from an entity with optional pagination and schema validation.

The schema parameter enables type-safe access to entity records by validating the data against a user-defined class with type annotations. When provided, each record is validated against the schema's field definitions before being returned.

Parameters:

| Name              | Type        | Description                              | Default                                                                                                                                                                                                                                                                                                               |
| ----------------- | ----------- | ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_key`      | `str`       | The unique key/identifier of the entity. | *required*                                                                                                                                                                                                                                                                                                            |
| `schema`          | \`Type[Any] | None\`                                   | Optional schema class for validation. This should be a Python class with type-annotated fields that match the entity's structure. Field Validation Rules: - Required fields: Use standard type annotations (e.g., name: str) - Optional fields: Use Optional or union with None (e.g., age: Optional[int] or age: int |
| `start`           | \`int       | None\`                                   | Starting index for pagination (0-based).                                                                                                                                                                                                                                                                              |
| `limit`           | \`int       | None\`                                   | Maximum number of records to return.                                                                                                                                                                                                                                                                                  |
| `expansion_level` | \`int       | None\`                                   | Depth of foreign-key expansion in the response (0 means no expansion). Higher values inline related records up to that many hops.                                                                                                                                                                                     |
| `filter`          | \`str       | None\`                                   | OData $filter expression (e.g. "status eq 'active'").                                                                                                                                                                                                                                                                 |
| `orderby`         | \`str       | None\`                                   | OData $orderby expression (e.g. "created_at desc").                                                                                                                                                                                                                                                                   |
| `select`          | \`list[str] | None\`                                   | Column projection — field names to include (rendered as $select).                                                                                                                                                                                                                                                     |
| `expand`          | \`list[str] | None\`                                   | Relationship names to expand inline (rendered as $expand).                                                                                                                                                                                                                                                            |

Returns:

| Name                        | Type                        | Description                                                                                                                                                                               |
| --------------------------- | --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityRecordsListResponse` | `EntityRecordsListResponse` | A list-compatible response with total_count, has_next_page and next_cursor pagination metadata. Iteration, indexing, and len() continue to work like a plain list of :class:EntityRecord. |

Raises:

| Type         | Description                                                                                                                         |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| `ValueError` | If schema validation fails for any record, including cases where required fields are missing or field types don't match the schema. |

Examples:

Basic usage without schema::

```
# Retrieve all records from an entity
records = await entities_service.list_records_async("Customers")
for record in records:
    print(record.id)
```

With pagination::

```
# Get first 50 records
records = await entities_service.list_records_async("Customers", start=0, limit=50)
print(f"Showing {len(records)} of {records.total_count} total")
if records.has_next_page:
    next_page = await entities_service.list_records_async(
        "Customers", start=50, limit=50
    )
```

With OData filter, sorting, projection, and expansion::

```
records = await entities_service.list_records_async(
    "Customers",
    filter="status eq 'active'",
    orderby="created_at desc",
    select=["name", "email", "status"],
    expand=["company"],
    expansion_level=1,
)
```

With schema validation::

```
class CustomerRecord:
    name: str
    email: str
    age: Optional[int]
    is_active: bool

# Records are validated against CustomerRecord schema
records = await entities_service.list_records_async(
    "Customers",
    schema=CustomerRecord
)

# Safe to access fields knowing they match the schema
for record in records:
    print(f"{record.name}: {record.email}")
```

### query_entity_records

```
query_entity_records(sql_query)
```

Query entity records using a validated SQL query.

PREVIEW: This method is in preview and may change in future releases.

Parameters:

| Name        | Type  | Description                                                                                                                                                                                                   | Default    |
| ----------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| `sql_query` | `str` | A SQL SELECT query to execute against Data Service entities. Only SELECT statements are allowed. Queries without WHERE must include a LIMIT clause. Subqueries and multi-statement queries are not permitted. | *required* |

Notes

A routing context is always derived from the configured `folders_map` when present and included in the request body.

Returns:

| Type                   | Description                                                       |
| ---------------------- | ----------------------------------------------------------------- |
| `list[dict[str, Any]]` | List\[Dict[str, Any]\]: A list of result records as dictionaries. |

Raises:

| Type         | Description                                                                                                |
| ------------ | ---------------------------------------------------------------------------------------------------------- |
| `ValueError` | If the SQL query fails validation (e.g., non-SELECT, missing WHERE/LIMIT, forbidden keywords, subqueries). |

### query_entity_records_async

```
query_entity_records_async(sql_query)
```

Asynchronously query entity records using a validated SQL query.

PREVIEW: This method is in preview and may change in future releases.

Parameters:

| Name        | Type  | Description                                                                                                                                                                                                   | Default    |
| ----------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| `sql_query` | `str` | A SQL SELECT query to execute against Data Service entities. Only SELECT statements are allowed. Queries without WHERE must include a LIMIT clause. Subqueries and multi-statement queries are not permitted. | *required* |

Notes

A routing context is always derived from the configured `folders_map` when present and included in the request body.

Returns:

| Type                   | Description                                                       |
| ---------------------- | ----------------------------------------------------------------- |
| `list[dict[str, Any]]` | List\[Dict[str, Any]\]: A list of result records as dictionaries. |

Raises:

| Type         | Description                                                                                                |
| ------------ | ---------------------------------------------------------------------------------------------------------- |
| `ValueError` | If the SQL query fails validation (e.g., non-SELECT, missing WHERE/LIMIT, forbidden keywords, subqueries). |

### resolve_entity_set

```
resolve_entity_set(items)
```

Resolve an agent entity set, applying resource overwrites.

### resolve_entity_set_async

```
resolve_entity_set_async(items)
```

Resolve an agent entity set, applying resource overwrites.

### retrieve

```
retrieve(entity_key)
```

Retrieve an entity by its key.

Parameters:

| Name         | Type  | Description                              | Default    |
| ------------ | ----- | ---------------------------------------- | ---------- |
| `entity_key` | `str` | The unique key/identifier of the entity. | *required* |

Returns:

| Name     | Type     | Description                                                                                                                                                                                                                                                                                                 |
| -------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Entity` | `Entity` | The entity with all its metadata and field definitions, including: - name: Entity name - display_name: Human-readable display name - fields: List of field metadata (field names, types, constraints) - record_count: Number of records in the entity - storage_size_in_mb: Storage size used by the entity |

Examples:

Basic usage::

```
# Retrieve entity metadata
entity = entities_service.retrieve("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
print(f"Entity: {entity.display_name}")
print(f"Records: {entity.record_count}")
```

Inspecting entity fields::

```
entity = entities_service.retrieve("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# List all fields and their types
for field in entity.fields:
    print(f"{field.name} ({field.sql_type.name})")
    print(f"  Required: {field.is_required}")
    print(f"  Primary Key: {field.is_primary_key}")
```

### retrieve_async

```
retrieve_async(entity_key)
```

Asynchronously retrieve an entity by its key.

Parameters:

| Name         | Type  | Description                              | Default    |
| ------------ | ----- | ---------------------------------------- | ---------- |
| `entity_key` | `str` | The unique key/identifier of the entity. | *required* |

Returns:

| Name     | Type     | Description                                                                                                                                                                                                                                                                                                 |
| -------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Entity` | `Entity` | The entity with all its metadata and field definitions, including: - name: Entity name - display_name: Human-readable display name - fields: List of field metadata (field names, types, constraints) - record_count: Number of records in the entity - storage_size_in_mb: Storage size used by the entity |

Examples:

Basic usage::

```
# Retrieve entity metadata
entity = await entities_service.retrieve_async("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
print(f"Entity: {entity.display_name}")
print(f"Records: {entity.record_count}")
```

Inspecting entity fields::

```
entity = await entities_service.retrieve_async("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# List all fields and their types
for field in entity.fields:
    print(f"{field.name} ({field.sql_type.name})")
    print(f"  Required: {field.is_required}")
    print(f"  Primary Key: {field.is_primary_key}")
```

### retrieve_by_name

```
retrieve_by_name(entity_name, folder_key=None)
```

Retrieve an entity by its name.

The server resolves the entity within the folder identified by `folder_key`. When omitted the default folder from the execution context is used.

Parameters:

| Name          | Type  | Description             | Default                                 |
| ------------- | ----- | ----------------------- | --------------------------------------- |
| `entity_name` | `str` | The name of the entity. | *required*                              |
| `folder_key`  | \`str | None\`                  | Optional folder key for disambiguation. |

### retrieve_by_name_async

```
retrieve_by_name_async(entity_name, folder_key=None)
```

Asynchronously retrieve an entity by its name.

The server resolves the entity within the folder identified by `folder_key`. When omitted the default folder from the execution context is used.

Parameters:

| Name          | Type  | Description             | Default                                 |
| ------------- | ----- | ----------------------- | --------------------------------------- |
| `entity_name` | `str` | The name of the entity. | *required*                              |
| `folder_key`  | \`str | None\`                  | Optional folder key for disambiguation. |

### retrieve_records

```
retrieve_records(
    entity_key,
    filter_group=None,
    sort_options=None,
    selected_fields=None,
    expansions=None,
    expansion_level=None,
    aggregates=None,
    group_by=None,
    joins=None,
    binnings=None,
    start=None,
    limit=None,
)
```

Retrieve records with structured filters, sorting, expansion, joins, and aggregates.

Routes to the V2 endpoint when `binnings` is provided (numeric/date binning is gated by the `enable-binning-on-query` feature flag on the backend).

Parameters:

| Name              | Type                          | Description                              | Default                                                                                                          |
| ----------------- | ----------------------------- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `entity_key`      | `str`                         | The unique key/identifier of the entity. | *required*                                                                                                       |
| `filter_group`    | \`EntityQueryFilterGroup      | None\`                                   | Nested filter conditions combined with AND/OR.                                                                   |
| `sort_options`    | \`list[EntityQuerySortOption] | None\`                                   | Sort fields and direction.                                                                                       |
| `selected_fields` | \`list[str]                   | None\`                                   | Column projection — field names to include; omit to return all fields.                                           |
| `expansions`      | \`list[Any]                   | None\`                                   | Foreign-key relationships to expand inline on each result record.                                                |
| `expansion_level` | \`int                         | None\`                                   | Depth of expansion (sent as a URL query param).                                                                  |
| `aggregates`      | \`list[EntityAggregate]       | None\`                                   | Aggregate expressions (COUNT / SUM / AVG / MIN / MAX). Maximum 5 per query.                                      |
| `group_by`        | \`list[str]                   | None\`                                   | Fields to group aggregate results by. Maximum 5; required when both aggregates and selected_fields are supplied. |
| `joins`           | \`list[EntityJoin]            | None\`                                   | Cross-entity joins. Maximum 3, all of the same type.                                                             |
| `binnings`        | \`list[EntityBinning]         | None\`                                   | Bucket numeric or date group-by fields. Each entry's field must also appear in group_by.                         |
| `start`           | \`int                         | None\`                                   | Records to skip (pagination offset).                                                                             |
| `limit`           | \`int                         | None\`                                   | Maximum number of records to return.                                                                             |

Returns:

| Name                            | Type                            | Description                                                                                                                                                                                                                                                                                                     |
| ------------------------------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `RetrieveEntityRecordsResponse` | `RetrieveEntityRecordsResponse` | A response with items, total_count, has_next_page, and next_cursor. items is a list of :class:EntityRecord for plain queries, or :class:AggregateRow when aggregates, group_by, or binnings are used. next_cursor is populated only when the backend returns one; otherwise paginate by passing the next start. |

Examples:

Filter + sort + projection::

```
from uipath.platform.entities import (
    EntityQueryFilter,
    EntityQueryFilterGroup,
    EntityQuerySortOption,
    LogicalOperator,
    QueryFilterOperator,
)

result = entities_service.retrieve_records(
    "Customers",
    filter_group=EntityQueryFilterGroup(
        logical_operator=LogicalOperator.And,
        query_filters=[
            EntityQueryFilter(
                field_name="status",
                operator=QueryFilterOperator.Equals,
                value="active",
            )
        ],
    ),
    sort_options=[
        EntityQuerySortOption(field_name="created_at", is_descending=True)
    ],
    selected_fields=["Id", "name", "email"],
    start=0,
    limit=50,
)
print(f"Found {result.total_count} customers")
```

Aggregates and group-by (counts per status)::

```
from uipath.platform.entities import (
    EntityAggregate,
    EntityAggregateFunction,
)

result = entities_service.retrieve_records(
    "Customers",
    selected_fields=["status"],
    group_by=["status"],
    aggregates=[
        EntityAggregate(
            function=EntityAggregateFunction.Count,
            field="Id",
            alias="total",
        )
    ],
)
for row in result.items:
    print(row.status, row.total)
```

### retrieve_records_async

```
retrieve_records_async(
    entity_key,
    filter_group=None,
    sort_options=None,
    selected_fields=None,
    expansions=None,
    expansion_level=None,
    aggregates=None,
    group_by=None,
    joins=None,
    binnings=None,
    start=None,
    limit=None,
)
```

Asynchronously retrieve records with structured filters, sorting, expansion, joins, and aggregates.

Routes to the V2 endpoint when `binnings` is provided (numeric/date binning is gated by the `enable-binning-on-query` feature flag on the backend).

Parameters:

| Name              | Type                          | Description                              | Default                                                                                                          |
| ----------------- | ----------------------------- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `entity_key`      | `str`                         | The unique key/identifier of the entity. | *required*                                                                                                       |
| `filter_group`    | \`EntityQueryFilterGroup      | None\`                                   | Nested filter conditions combined with AND/OR.                                                                   |
| `sort_options`    | \`list[EntityQuerySortOption] | None\`                                   | Sort fields and direction.                                                                                       |
| `selected_fields` | \`list[str]                   | None\`                                   | Column projection — field names to include; omit to return all fields.                                           |
| `expansions`      | \`list[Any]                   | None\`                                   | Foreign-key relationships to expand inline on each result record.                                                |
| `expansion_level` | \`int                         | None\`                                   | Depth of expansion.                                                                                              |
| `aggregates`      | \`list[EntityAggregate]       | None\`                                   | Aggregate expressions. Maximum 5 per query.                                                                      |
| `group_by`        | \`list[str]                   | None\`                                   | Fields to group aggregate results by. Maximum 5; required when both aggregates and selected_fields are supplied. |
| `joins`           | \`list[EntityJoin]            | None\`                                   | Cross-entity joins. Maximum 3, all of the same type.                                                             |
| `binnings`        | \`list[EntityBinning]         | None\`                                   | Bucket numeric or date group-by fields.                                                                          |
| `start`           | \`int                         | None\`                                   | Records to skip (pagination offset).                                                                             |
| `limit`           | \`int                         | None\`                                   | Maximum number of records to return.                                                                             |

Returns:

| Name                            | Type                            | Description                                                         |
| ------------------------------- | ------------------------------- | ------------------------------------------------------------------- |
| `RetrieveEntityRecordsResponse` | `RetrieveEntityRecordsResponse` | A response with items, total_count, has_next_page, and next_cursor. |

Examples:

Filter + sort + pagination::

```
from uipath.platform.entities import (
    EntityQueryFilter,
    EntityQueryFilterGroup,
    QueryFilterOperator,
)

result = await entities_service.retrieve_records_async(
    "Customers",
    filter_group=EntityQueryFilterGroup(
        query_filters=[
            EntityQueryFilter(
                field_name="status",
                operator=QueryFilterOperator.Equals,
                value="active",
            )
        ],
    ),
    start=0,
    limit=25,
)
print(f"{len(result.items)} of {result.total_count} customers")
```

### update_entity_metadata

```
update_entity_metadata(entity_id, metadata)
```

Update an entity's display name, description, and/or RBAC flag.

Parameters:

| Name        | Type                          | Description                          | Default                                                                                                                                                                                                                      |
| ----------- | ----------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_id` | `str`                         | The unique identifier of the entity. | *required*                                                                                                                                                                                                                   |
| `metadata`  | \`EntityMetadataUpdateOptions | Dict[str, Any]\`                     | An :class:EntityMetadataUpdateOptions instance or a dict with any of display_name, description, is_rbac_enabled. Dict keys may be snake_case (display_name) or camelCase (displayName); both serialize correctly to the API. |

Examples:

Rename and update description::

```
from uipath.platform.entities import EntityMetadataUpdateOptions

entities_service.update_entity_metadata(
    "a1b2c3d4-...",
    EntityMetadataUpdateOptions(
        display_name="New Display Name",
        description="Refreshed description",
    ),
)
```

From a plain dict::

```
entities_service.update_entity_metadata(
    "a1b2c3d4-...",
    {"display_name": "X", "is_rbac_enabled": True},
)
```

### update_entity_metadata_async

```
update_entity_metadata_async(entity_id, metadata)
```

Asynchronously update an entity's display name, description, and/or RBAC flag.

Parameters:

| Name        | Type                          | Description                          | Default                                                                                                          |
| ----------- | ----------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| `entity_id` | `str`                         | The unique identifier of the entity. | *required*                                                                                                       |
| `metadata`  | \`EntityMetadataUpdateOptions | Dict[str, Any]\`                     | An :class:EntityMetadataUpdateOptions instance or a dict with any of display_name, description, is_rbac_enabled. |

Examples:

Rename::

```
from uipath.platform.entities import EntityMetadataUpdateOptions

await entities_service.update_entity_metadata_async(
    "a1b2c3d4-...",
    EntityMetadataUpdateOptions(display_name="Renamed Entity"),
)
```

### update_record

```
update_record(
    entity_key, record_id, data, expansion_level=None
)
```

Update a single record by id and return the updated row.

Note

Unlike :meth:`update_records` (batch), this single-record endpoint fires Data Fabric trigger events. Use this method when triggers attached to the entity must run.

Parameters:

| Name              | Type  | Description                                                                                                                                             | Default                                                                |
| ----------------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `entity_key`      | `str` | The unique key/identifier of the entity.                                                                                                                | *required*                                                             |
| `record_id`       | `str` | The unique identifier of the record to update.                                                                                                          | *required*                                                             |
| `data`            | `Any` | Fields to update — a dict, a Pydantic model, or any object exposing __dict__. Fields explicitly set to None are sent through; unset fields are omitted. | *required*                                                             |
| `expansion_level` | \`int | None\`                                                                                                                                                  | Depth of foreign-key expansion in the response (0 means no expansion). |

Returns:

| Name           | Type           | Description         |
| -------------- | -------------- | ------------------- |
| `EntityRecord` | `EntityRecord` | The updated record. |

Examples:

Partial update from a dict::

```
record = entities_service.update_record(
    "Customers",
    "rec-1",
    {"email": "alice.new@example.com"},
)
```

Clear a field by passing an explicit `None`::

```
# Note: unset fields are omitted; explicit None values are sent.
record = entities_service.update_record(
    "Customers",
    "rec-1",
    {"middle_name": None},
)
```

### update_record_async

```
update_record_async(
    entity_key, record_id, data, expansion_level=None
)
```

Asynchronously update a single record by id.

Note

Unlike :meth:`update_records_async` (batch), this single-record endpoint fires Data Fabric trigger events.

Parameters:

| Name              | Type  | Description                                                                   | Default                         |
| ----------------- | ----- | ----------------------------------------------------------------------------- | ------------------------------- |
| `entity_key`      | `str` | The unique key/identifier of the entity.                                      | *required*                      |
| `record_id`       | `str` | The unique identifier of the record to update.                                | *required*                      |
| `data`            | `Any` | Fields to update — a dict, a Pydantic model, or any object exposing __dict__. | *required*                      |
| `expansion_level` | \`int | None\`                                                                        | Depth of foreign-key expansion. |

Returns:

| Name           | Type           | Description         |
| -------------- | -------------- | ------------------- |
| `EntityRecord` | `EntityRecord` | The updated record. |

Examples:

Partial update::

```
record = await entities_service.update_record_async(
    "Customers",
    "rec-1",
    {"email": "alice.new@example.com"},
)
```

### update_records

```
update_records(
    entity_key,
    records,
    schema=None,
    expansion_level=None,
    fail_on_first=None,
)
```

Update multiple records in an entity in a single batch operation.

Parameters:

| Name              | Type        | Description                                                                                                                                                          | Default                                                                                                                                                                     |
| ----------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_key`      | `str`       | The unique key/identifier of the entity.                                                                                                                             | *required*                                                                                                                                                                  |
| `records`         | `list[Any]` | List of records to update. Each record must include its Id field. A record may be a dict, a Pydantic model, an :class:EntityRecord, or any object exposing __dict__. | *required*                                                                                                                                                                  |
| `schema`          | \`Type[Any] | None\`                                                                                                                                                               | Optional schema class for validation. When provided, validates that each record in the request and response matches the schema structure.                                   |
| `expansion_level` | \`int       | None\`                                                                                                                                                               | Depth of foreign-key expansion in the response (0 means no expansion).                                                                                                      |
| `fail_on_first`   | \`bool      | None\`                                                                                                                                                               | When True, stop the batch on the first per-record failure. When False (default), all records are attempted and the response lists both success_records and failure_records. |

Returns:

| Name                         | Type                         | Description                                                                                                                                                                                                           |
| ---------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityRecordsBatchResponse` | `EntityRecordsBatchResponse` | Response containing successful and failed record operations. - success_records: List of successfully updated :class:EntityRecord objects - failure_records: List of :class:FailureRecord describing per-record errors |

Examples:

Update records::

```
# First, retrieve records to update
records = entities_service.list_records("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# Modify the records
for record in records:
    if record.name == "John Doe":
        record.age = 31

# Update the modified records
response = entities_service.update_records(
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    records
)

print(f"Updated: {len(response.success_records)}")
print(f"Failed: {len(response.failure_records)}")
```

Update with schema validation::

```
class CustomerSchema:
    name: str
    email: str
    age: int

# Retrieve and update
records = entities_service.list_records(
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    schema=CustomerSchema
)

# Modify specific records
for record in records:
    if record.age < 30:
        record.is_active = True

response = entities_service.update_records(
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    records,
    schema=CustomerSchema
)

for record in response.success_records:
    print(f"Updated: {record.name}")
```

### update_records_async

```
update_records_async(
    entity_key,
    records,
    schema=None,
    expansion_level=None,
    fail_on_first=None,
)
```

Asynchronously update multiple records in an entity in a single batch operation.

Parameters:

| Name              | Type        | Description                                                                                                                                                          | Default                                                                                                                                                                     |
| ----------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_key`      | `str`       | The unique key/identifier of the entity.                                                                                                                             | *required*                                                                                                                                                                  |
| `records`         | `list[Any]` | List of records to update. Each record must include its Id field. A record may be a dict, a Pydantic model, an :class:EntityRecord, or any object exposing __dict__. | *required*                                                                                                                                                                  |
| `schema`          | \`Type[Any] | None\`                                                                                                                                                               | Optional schema class for validation. When provided, validates that each record in the request and response matches the schema structure.                                   |
| `expansion_level` | \`int       | None\`                                                                                                                                                               | Depth of foreign-key expansion in the response (0 means no expansion).                                                                                                      |
| `fail_on_first`   | \`bool      | None\`                                                                                                                                                               | When True, stop the batch on the first per-record failure. When False (default), all records are attempted and the response lists both success_records and failure_records. |

Returns:

| Name                         | Type                         | Description                                                                                                                                                                                                           |
| ---------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityRecordsBatchResponse` | `EntityRecordsBatchResponse` | Response containing successful and failed record operations. - success_records: List of successfully updated :class:EntityRecord objects - failure_records: List of :class:FailureRecord describing per-record errors |

Examples:

Update records::

```
# First, retrieve records to update
records = await entities_service.list_records_async("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# Modify the records
for record in records:
    if record.name == "John Doe":
        record.age = 31

# Update the modified records
response = await entities_service.update_records_async(
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    records
)

print(f"Updated: {len(response.success_records)}")
print(f"Failed: {len(response.failure_records)}")
```

Update with schema validation::

```
class CustomerSchema:
    name: str
    email: str
    age: int

# Retrieve and update
records = await entities_service.list_records_async(
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    schema=CustomerSchema
)

# Modify specific records
for record in records:
    if record.age < 30:
        record.is_active = True

response = await entities_service.update_records_async(
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    records,
    schema=CustomerSchema
)

for record in response.success_records:
    print(f"Updated: {record.name}")
```

### upload_attachment

```
upload_attachment(
    entity_id,
    record_id,
    field_name,
    file=None,
    file_path=None,
    expansion_level=None,
)
```

Upload a file attachment to a File-type field on a record.

Provide exactly one of `file` (raw bytes) or `file_path` (path on disk).

Parameters:

| Name              | Type          | Description                                                              | Default                                                                                              |
| ----------------- | ------------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| `entity_id`       | `str`         | The unique identifier of the entity.                                     | *required*                                                                                           |
| `record_id`       | `str`         | The unique identifier of the record whose attachment field is being set. | *required*                                                                                           |
| `field_name`      | `str`         | Name of the File-type field on the entity.                               | *required*                                                                                           |
| `file`            | \`FileContent | None\`                                                                   | Raw bytes (bytes / bytearray / memoryview) of the file to upload. Mutually exclusive with file_path. |
| `file_path`       | \`str         | None\`                                                                   | Path to a local file to upload. Mutually exclusive with file.                                        |
| `expansion_level` | \`int         | None\`                                                                   | Optional FK expansion depth in the response (0 means no expansion).                                  |

Returns:

| Type             | Description                                                                                                                 |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `dict[str, Any]` | Dict\[str, Any\]: The decoded JSON response (typically the updated record), or an empty dict when the response has no body. |

Examples:

Upload from raw bytes::

```
with open("contract.pdf", "rb") as f:
    data = f.read()
entities_service.upload_attachment(
    "Customers", "rec-1", "Contract", file=data
)
```

Upload from a path on disk::

```
entities_service.upload_attachment(
    "Customers", "rec-1", "Contract", file_path="./contract.pdf"
)
```

### upload_attachment_async

```
upload_attachment_async(
    entity_id,
    record_id,
    field_name,
    file=None,
    file_path=None,
    expansion_level=None,
)
```

Asynchronously upload a file attachment to a File-type field on a record.

Provide exactly one of `file` (raw bytes) or `file_path` (path on disk).

Parameters:

| Name              | Type          | Description                                                              | Default                                                             |
| ----------------- | ------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| `entity_id`       | `str`         | The unique identifier of the entity.                                     | *required*                                                          |
| `record_id`       | `str`         | The unique identifier of the record whose attachment field is being set. | *required*                                                          |
| `field_name`      | `str`         | Name of the File-type field on the entity.                               | *required*                                                          |
| `file`            | \`FileContent | None\`                                                                   | Raw bytes of the file to upload. Mutually exclusive with file_path. |
| `file_path`       | \`str         | None\`                                                                   | Path to a local file to upload. Mutually exclusive with file.       |
| `expansion_level` | \`int         | None\`                                                                   | Optional FK expansion depth in the response.                        |

Returns:

| Type             | Description                                  |
| ---------------- | -------------------------------------------- |
| `dict[str, Any]` | Dict\[str, Any\]: The decoded JSON response. |

Examples:

Upload from a path on disk::

```
await entities_service.upload_attachment_async(
    "Customers", "rec-1", "Contract", file_path="./contract.pdf"
)
```

### validate_entity_batch

```
validate_entity_batch(batch_response, schema=None)
```

Parse a batch response, optionally validating success records against `schema`.

Failure records are returned as :class:`FailureRecord` instances and are not validated against the user schema.
