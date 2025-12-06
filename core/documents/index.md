## DocumentsService

Service for managing UiPath DocumentUnderstanding Document Operations.

This service provides methods to extract data from documents using UiPath's Document Understanding capabilities.

Preview Feature

This function is currently experimental. Behavior and parameters are subject to change in future versions.

### classify

```
classify(
    project_type,
    tag=None,
    project_name=None,
    file=None,
    file_path=None,
)
```

Classify a document using a DU Modern project.

Parameters:

| Name           | Type          | Description                                                                                           | Default    |
| -------------- | ------------- | ----------------------------------------------------------------------------------------------------- | ---------- |
| `project_type` | `ProjectType` | Type of the project.                                                                                  | *required* |
| `project_name` | `str`         | Name of the DU Modern project. Must be provided if project_type is not ProjectType.PRETRAINED.        | `None`     |
| `tag`          | `str`         | Tag of the published project version. Must be provided if project_type is not ProjectType.PRETRAINED. | `None`     |
| `file`         | `FileContent` | The document file to be classified.                                                                   | `None`     |
| `file_path`    | `str`         | Path to the document file to be classified.                                                           | `None`     |

Note

Either `file` or `file_path` must be provided, but not both.

Returns:

| Type                         | Description                                                     |
| ---------------------------- | --------------------------------------------------------------- |
| `list[ClassificationResult]` | List\[ClassificationResult\]: A list of classification results. |

Examples:

```
Modern DU project:
with open("path/to/document.pdf", "rb") as file:
    classification_results = service.classify(
        project_name="MyModernProjectName",
        tag="Production",
        file=file,
    )

Pretrained project:
with open("path/to/document.pdf", "rb") as file:
    classification_results = service.classify(
        project_type=ProjectType.PRETRAINED,
        file=file,
    )
```

### classify_async

```
classify_async(
    project_type,
    tag=None,
    project_name=None,
    file=None,
    file_path=None,
)
```

Asynchronously version of the classify method.

### create_validate_classification_action

```
create_validate_classification_action(
    action_title,
    action_priority,
    action_catalog,
    action_folder,
    storage_bucket_name,
    storage_bucket_directory_path,
    classification_results,
)
```

Create a validate classification action for a document based on the classification results. More details about validation actions can be found in the [official documentation](https://docs.uipath.com/ixp/automation-cloud/latest/user-guide/validating-classifications).

Parameters:

| Name                            | Type                         | Description                                                                              | Default    |
| ------------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------- | ---------- |
| `action_title`                  | `str`                        | Title of the action.                                                                     | *required* |
| `action_priority`               | `ActionPriority`             | Priority of the action.                                                                  | *required* |
| `action_catalog`                | `str`                        | Catalog of the action.                                                                   | *required* |
| `action_folder`                 | `str`                        | Folder of the action.                                                                    | *required* |
| `storage_bucket_name`           | `str`                        | Name of the storage bucket.                                                              | *required* |
| `storage_bucket_directory_path` | `str`                        | Directory path in the storage bucket.                                                    | *required* |
| `classification_results`        | `list[ClassificationResult]` | The classification results to be validated, typically obtained from the classify method. | *required* |

Returns:

| Name                           | Type                           | Description                                 |
| ------------------------------ | ------------------------------ | ------------------------------------------- |
| `ValidateClassificationAction` | `ValidateClassificationAction` | The created validate classification action. |

Examples:

```
validation_action = service.create_validate_classification_action(
    action_title="Test Validation Action",
    action_priority=ActionPriority.MEDIUM,
    action_catalog="default_du_actions",
    action_folder="Shared",
    storage_bucket_name="du_storage_bucket",
    storage_bucket_directory_path="TestDirectory",
    classification_results=classification_results,
)
```

### create_validate_classification_action_async

```
create_validate_classification_action_async(
    action_title,
    action_priority,
    action_catalog,
    action_folder,
    storage_bucket_name,
    storage_bucket_directory_path,
    classification_results,
)
```

Asynchronous version of the create_validation_action method.

### create_validate_extraction_action

```
create_validate_extraction_action(
    action_title,
    action_priority,
    action_catalog,
    action_folder,
    storage_bucket_name,
    storage_bucket_directory_path,
    extraction_response,
)
```

Create a validate extraction action for a document based on the extraction response. More details about validation actions can be found in the [official documentation](https://docs.uipath.com/ixp/automation-cloud/latest/user-guide/validating-extractions).

Parameters:

| Name                            | Type                 | Description                                                                        | Default    |
| ------------------------------- | -------------------- | ---------------------------------------------------------------------------------- | ---------- |
| `action_title`                  | `str`                | Title of the action.                                                               | *required* |
| `action_priority`               | `ActionPriority`     | Priority of the action.                                                            | *required* |
| `action_catalog`                | `str`                | Catalog of the action.                                                             | *required* |
| `action_folder`                 | `str`                | Folder of the action.                                                              | *required* |
| `storage_bucket_name`           | `str`                | Name of the storage bucket.                                                        | *required* |
| `storage_bucket_directory_path` | `str`                | Directory path in the storage bucket.                                              | *required* |
| `extraction_response`           | `ExtractionResponse` | The extraction result to be validated, typically obtained from the extract method. | *required* |

Returns:

| Name                           | Type                       | Description                    |
| ------------------------------ | -------------------------- | ------------------------------ |
| `ValidateClassificationAction` | `ValidateExtractionAction` | The created validation action. |

Examples:

```
validation_action = service.create_validate_extraction_action(
    action_title="Test Validation Action",
    action_priority=ActionPriority.MEDIUM,
    action_catalog="default_du_actions",
    action_folder="Shared",
    storage_bucket_name="du_storage_bucket",
    storage_bucket_directory_path="TestDirectory",
    extraction_response=extraction_response,
)
```

### create_validate_extraction_action_async

```
create_validate_extraction_action_async(
    action_title,
    action_priority,
    action_catalog,
    action_folder,
    storage_bucket_name,
    storage_bucket_directory_path,
    extraction_response,
)
```

Asynchronous version of the create_validation_action method.

### extract

```
extract(
    tag=None,
    project_name=None,
    file=None,
    file_path=None,
    classification_result=None,
    project_type=None,
    document_type_name=None,
)
```

Extract predicted data from a document using an DU Modern/IXP project.

Parameters:

| Name                    | Type                   | Description                                                                                                                                                                    | Default |
| ----------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------- |
| `project_name`          | `str`                  | Name of the IXP/DU Modern project. Must be provided if classification_result is not provided.                                                                                  | `None`  |
| `tag`                   | `str`                  | Tag of the published project version. Must be provided if classification_result is not provided and project_type is not ProjectType.PRETRAINED.                                | `None`  |
| `file`                  | `FileContent`          | The document file to be processed. Must be provided if classification_result is not provided.                                                                                  | `None`  |
| `file_path`             | `str`                  | Path to the document file to be processed. Must be provided if classification_result is not provided.                                                                          | `None`  |
| `project_type`          | `ProjectType`          | Type of the project. Must be provided if project_name is provided.                                                                                                             | `None`  |
| `document_type_name`    | `str`                  | Document type name associated with the extractor to be used for extraction. Required if project_type is ProjectType.MODERN and project_name is provided.                       | `None`  |
| `classification_result` | `ClassificationResult` | The classification result obtained from a previous classification step. If provided, project_name, project_type, file, file_path, and document_type_name must not be provided. | `None`  |

Note

Either `file` or `file_path` must be provided, but not both.

Returns:

| Type                 | Description             |
| -------------------- | ----------------------- |
| \`ExtractionResponse | ExtractionResponseIXP\` |

Examples:

IXP projects:

```
with open("path/to/document.pdf", "rb") as file:
    extraction_response = service.extract(
        project_name="MyIXPProjectName",
        tag="live",
        file=file,
    )
```

DU Modern projects (providing document type name):

```
with open("path/to/document.pdf", "rb") as file:
    extraction_response = service.extract(
        project_name="MyModernProjectName",
        tag="Production",
        file=file,
        project_type=ProjectType.MODERN,
        document_type_name="Receipts",
    )
```

DU Modern projects (using existing classification result):

```
with open("path/to/document.pdf", "rb") as file:
    classification_results = uipath.documents.classify(
        tag="Production",
        project_name="MyModernProjectName",
        file=file,
    )

extraction_result = uipath.documents.extract(
    classification_result=max(classification_results, key=lambda result: result.confidence),
)
```

### extract_async

```
extract_async(
    tag=None,
    project_name=None,
    file=None,
    file_path=None,
    classification_result=None,
    project_type=None,
    document_type_name=None,
)
```

Asynchronously version of the extract method.

### get_validate_classification_result

```
get_validate_classification_result(validation_action)
```

Get the result of a validate classification action.

Note

This method will block until the validation action is completed, meaning the user has completed the validation in UiPath Action Center.

Parameters:

| Name                | Type                           | Description                                                                                                            | Default    |
| ------------------- | ------------------------------ | ---------------------------------------------------------------------------------------------------------------------- | ---------- |
| `validation_action` | `ValidateClassificationAction` | The validation action to get the result for, typically obtained from the create_validate_classification_action method. | *required* |

Returns:

| Type                         | Description                                                         |
| ---------------------------- | ------------------------------------------------------------------- |
| `list[ClassificationResult]` | List\[ClassificationResult\]: The validated classification results. |

Examples:

```
validated_results = service.get_validate_classification_result(validate_classification_action)
```

### get_validate_classification_result_async

```
get_validate_classification_result_async(validation_action)
```

Asynchronous version of the get_validation_result method.

### get_validate_extraction_result

```
get_validate_extraction_result(validation_action)
```

Get the result of a validate extraction action.

Note

This method will block until the validation action is completed, meaning the user has completed the validation in UiPath Action Center.

Parameters:

| Name                | Type                           | Description                                                                                                        | Default    |
| ------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------ | ---------- |
| `validation_action` | `ValidateClassificationAction` | The validation action to get the result for, typically obtained from the create_validate_extraction_action method. | *required* |

Returns:

| Type                 | Description             |
| -------------------- | ----------------------- |
| \`ExtractionResponse | ExtractionResponseIXP\` |

Examples:

```
validated_result = service.get_validate_extraction_result(validate_extraction_action)
```

### get_validate_extraction_result_async

```
get_validate_extraction_result_async(validation_action)
```

Asynchronous version of the get_validation_result method.
