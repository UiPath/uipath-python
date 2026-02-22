## EntitiesService

Service for managing UiPath Data Service entities.

Entities are database tables in UiPath Data Service that can store structured data for automation processes.

See Also

<https://docs.uipath.com/data-service/automation-cloud/latest/user-guide/introduction>

### delete_records

```
delete_records(entity_key, record_ids)
```

Delete multiple records from an entity in a single batch operation.

Parameters:

| Name         | Type        | Description                              | Default    |
| ------------ | ----------- | ---------------------------------------- | ---------- |
| `entity_key` | `str`       | The unique key/identifier of the entity. | *required* |
| `record_ids` | `list[str]` | List of record IDs (GUIDs) to delete.    | *required* |

Returns:

| Name                         | Type                         | Description                                                                                                                                                                                             |
| ---------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityRecordsBatchResponse` | `EntityRecordsBatchResponse` | Response containing successful and failed record operations. - success_records: List of successfully deleted EntityRecord objects - failure_records: List of EntityRecord objects that failed to delete |

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
delete_records_async(entity_key, record_ids)
```

Asynchronously delete multiple records from an entity in a single batch operation.

Parameters:

| Name         | Type        | Description                              | Default    |
| ------------ | ----------- | ---------------------------------------- | ---------- |
| `entity_key` | `str`       | The unique key/identifier of the entity. | *required* |
| `record_ids` | `list[str]` | List of record IDs (GUIDs) to delete.    | *required* |

Returns:

| Name                         | Type                         | Description                                                                                                                                                                                             |
| ---------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityRecordsBatchResponse` | `EntityRecordsBatchResponse` | Response containing successful and failed record operations. - success_records: List of successfully deleted EntityRecord objects - failure_records: List of EntityRecord objects that failed to delete |

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

### insert_records

```
insert_records(entity_key, records, schema=None)
```

Insert multiple records into an entity in a single batch operation.

Parameters:

| Name         | Type        | Description                                                                                                   | Default                                                                                                                       |
| ------------ | ----------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `entity_key` | `str`       | The unique key/identifier of the entity.                                                                      | *required*                                                                                                                    |
| `records`    | `list[Any]` | List of records to insert. Each record should be an object with attributes matching the entity's field names. | *required*                                                                                                                    |
| `schema`     | \`Type[Any] | None\`                                                                                                        | Optional schema class for validation. When provided, validates that each record in the response matches the schema structure. |

Returns:

| Name                         | Type                         | Description                                                                                                                                                                                              |
| ---------------------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityRecordsBatchResponse` | `EntityRecordsBatchResponse` | Response containing successful and failed record operations. - success_records: List of successfully inserted EntityRecord objects - failure_records: List of EntityRecord objects that failed to insert |

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
insert_records_async(entity_key, records, schema=None)
```

Asynchronously insert multiple records into an entity in a single batch operation.

Parameters:

| Name         | Type        | Description                                                                                                   | Default                                                                                                                       |
| ------------ | ----------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `entity_key` | `str`       | The unique key/identifier of the entity.                                                                      | *required*                                                                                                                    |
| `records`    | `list[Any]` | List of records to insert. Each record should be an object with attributes matching the entity's field names. | *required*                                                                                                                    |
| `schema`     | \`Type[Any] | None\`                                                                                                        | Optional schema class for validation. When provided, validates that each record in the response matches the schema structure. |

Returns:

| Name                         | Type                         | Description                                                                                                                                                                                              |
| ---------------------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityRecordsBatchResponse` | `EntityRecordsBatchResponse` | Response containing successful and failed record operations. - success_records: List of successfully inserted EntityRecord objects - failure_records: List of EntityRecord objects that failed to insert |

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
    entity_key, schema=None, start=None, limit=None
)
```

List records from an entity with optional pagination and schema validation.

The schema parameter enables type-safe access to entity records by validating the data against a user-defined class with type annotations. When provided, each record is validated against the schema's field definitions before being returned.

Parameters:

| Name         | Type        | Description                              | Default                                                                                                                                                                                                                                                                                                               |
| ------------ | ----------- | ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_key` | `str`       | The unique key/identifier of the entity. | *required*                                                                                                                                                                                                                                                                                                            |
| `schema`     | \`Type[Any] | None\`                                   | Optional schema class for validation. This should be a Python class with type-annotated fields that match the entity's structure. Field Validation Rules: - Required fields: Use standard type annotations (e.g., name: str) - Optional fields: Use Optional or union with None (e.g., age: Optional[int] or age: int |
| `start`      | \`int       | None\`                                   | Starting index for pagination (0-based).                                                                                                                                                                                                                                                                              |
| `limit`      | \`int       | None\`                                   | Maximum number of records to return.                                                                                                                                                                                                                                                                                  |

Returns:

| Type                 | Description                                                                                                                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `list[EntityRecord]` | List\[EntityRecord\]: A list of entity records. Each record contains an 'id' field and all other fields from the entity. Fields can be accessed as attributes or dictionary keys on the EntityRecord object. |

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
    entity_key, schema=None, start=None, limit=None
)
```

Asynchronously list records from an entity with optional pagination and schema validation.

The schema parameter enables type-safe access to entity records by validating the data against a user-defined class with type annotations. When provided, each record is validated against the schema's field definitions before being returned.

Parameters:

| Name         | Type        | Description                              | Default                                                                                                                                                                                                                                                                                                               |
| ------------ | ----------- | ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_key` | `str`       | The unique key/identifier of the entity. | *required*                                                                                                                                                                                                                                                                                                            |
| `schema`     | \`Type[Any] | None\`                                   | Optional schema class for validation. This should be a Python class with type-annotated fields that match the entity's structure. Field Validation Rules: - Required fields: Use standard type annotations (e.g., name: str) - Optional fields: Use Optional or union with None (e.g., age: Optional[int] or age: int |
| `start`      | \`int       | None\`                                   | Starting index for pagination (0-based).                                                                                                                                                                                                                                                                              |
| `limit`      | \`int       | None\`                                   | Maximum number of records to return.                                                                                                                                                                                                                                                                                  |

Returns:

| Type                 | Description                                                                                                                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `list[EntityRecord]` | List\[EntityRecord\]: A list of entity records. Each record contains an 'id' field and all other fields from the entity. Fields can be accessed as attributes or dictionary keys on the EntityRecord object. |

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

### update_records

```
update_records(entity_key, records, schema=None)
```

Update multiple records in an entity in a single batch operation.

Parameters:

| Name         | Type        | Description                                                                                                                               | Default                                                                                                                                   |
| ------------ | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_key` | `str`       | The unique key/identifier of the entity.                                                                                                  | *required*                                                                                                                                |
| `records`    | `list[Any]` | List of records to update. Each record must have an 'Id' field and should be a Pydantic model with model_dump() method or similar object. | *required*                                                                                                                                |
| `schema`     | \`Type[Any] | None\`                                                                                                                                    | Optional schema class for validation. When provided, validates that each record in the request and response matches the schema structure. |

Returns:

| Name                         | Type                         | Description                                                                                                                                                                                             |
| ---------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityRecordsBatchResponse` | `EntityRecordsBatchResponse` | Response containing successful and failed record operations. - success_records: List of successfully updated EntityRecord objects - failure_records: List of EntityRecord objects that failed to update |

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
update_records_async(entity_key, records, schema=None)
```

Asynchronously update multiple records in an entity in a single batch operation.

Parameters:

| Name         | Type        | Description                                                                                                                               | Default                                                                                                                                   |
| ------------ | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_key` | `str`       | The unique key/identifier of the entity.                                                                                                  | *required*                                                                                                                                |
| `records`    | `list[Any]` | List of records to update. Each record must have an 'Id' field and should be a Pydantic model with model_dump() method or similar object. | *required*                                                                                                                                |
| `schema`     | \`Type[Any] | None\`                                                                                                                                    | Optional schema class for validation. When provided, validates that each record in the request and response matches the schema structure. |

Returns:

| Name                         | Type                         | Description                                                                                                                                                                                             |
| ---------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityRecordsBatchResponse` | `EntityRecordsBatchResponse` | Response containing successful and failed record operations. - success_records: List of successfully updated EntityRecord objects - failure_records: List of EntityRecord objects that failed to update |

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
