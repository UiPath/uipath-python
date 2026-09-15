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
    version=None,
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
| `version`      | `int`         | Version of the published project. It can be used instead of tag.                                      | `None`     |
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
    version=None,
    project_name=None,
    file=None,
    file_path=None,
)
```

Asynchronously version of the classify method.

### create_validate_classification_action

```
create_validate_classification_action(
    classification_results,
    action_title,
    action_priority=None,
    action_catalog=None,
    action_folder=None,
    storage_bucket_name=None,
    storage_bucket_directory_path=None,
)
```

Create a validate classification action for a document based on the classification results. More details about validation actions can be found in the [official documentation](https://docs.uipath.com/ixp/automation-cloud/latest/user-guide/validating-classifications).

Parameters:

| Name                            | Type                         | Description                                                                              | Default    |
| ------------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------- | ---------- |
| `classification_results`        | `list[ClassificationResult]` | The classification results to be validated, typically obtained from the classify method. | *required* |
| `action_title`                  | `str`                        | Title of the action.                                                                     | *required* |
| `action_priority`               | `ActionPriority`             | Priority of the action.                                                                  | `None`     |
| `action_catalog`                | `str`                        | Catalog of the action.                                                                   | `None`     |
| `action_folder`                 | `str`                        | Folder of the action.                                                                    | `None`     |
| `storage_bucket_name`           | `str`                        | Name of the storage bucket.                                                              | `None`     |
| `storage_bucket_directory_path` | `str`                        | Directory path in the storage bucket.                                                    | `None`     |

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
    classification_results,
    action_title,
    action_priority=None,
    action_catalog=None,
    action_folder=None,
    storage_bucket_name=None,
    storage_bucket_directory_path=None,
)
```

Asynchronous version of the create_validation_action method.

### create_validate_extraction_action

```
create_validate_extraction_action(
    extraction_response,
    action_title,
    action_priority=None,
    action_catalog=None,
    action_folder=None,
    storage_bucket_name=None,
    storage_bucket_directory_path=None,
)
```

Create a validate extraction action for a document based on the extraction response. More details about validation actions can be found in the [official documentation](https://docs.uipath.com/ixp/automation-cloud/latest/user-guide/validating-extractions).

Parameters:

| Name                            | Type                 | Description                                                                        | Default    |
| ------------------------------- | -------------------- | ---------------------------------------------------------------------------------- | ---------- |
| `extraction_response`           | `ExtractionResponse` | The extraction result to be validated, typically obtained from the extract method. | *required* |
| `action_title`                  | `str`                | Title of the action.                                                               | *required* |
| `action_priority`               | `ActionPriority`     | Priority of the action.                                                            | `None`     |
| `action_catalog`                | `str`                | Catalog of the action.                                                             | `None`     |
| `action_folder`                 | `str`                | Folder of the action.                                                              | `None`     |
| `storage_bucket_name`           | `str`                | Name of the storage bucket.                                                        | `None`     |
| `storage_bucket_directory_path` | `str`                | Directory path in the storage bucket.                                              | `None`     |

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
    extraction_response,
    action_title,
    action_priority=None,
    action_catalog=None,
    action_folder=None,
    storage_bucket_name=None,
    storage_bucket_directory_path=None,
)
```

Asynchronous version of the create_validation_action method.

### extract

```
extract(
    tag=None,
    version=None,
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
| `version`               | `int`                  | Version of the published project. It can be used instead of tag.                                                                                                               | `None`  |
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
    version=None,
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

### retrieve_ixp_extraction_result

```
retrieve_ixp_extraction_result(
    project_id, tag, operation_id
)
```

Retrieve the result of an IXP extraction operation (single-shot, non-blocking).

This method retrieves the result of an IXP extraction that was previously started with `start_ixp_extraction`. It does not poll - it makes a single request and returns the result if available, or raises an exception if not complete.

Parameters:

| Name           | Type  | Description                                          | Default    |
| -------------- | ----- | ---------------------------------------------------- | ---------- |
| `project_id`   | `str` | The ID of the IXP project.                           | *required* |
| `tag`          | `str` | The tag of the published project version.            | *required* |
| `operation_id` | `str` | The operation ID returned from start_ixp_extraction. | *required* |

Returns:

| Name                    | Type                    | Description                                            |
| ----------------------- | ----------------------- | ------------------------------------------------------ |
| `ExtractionResponseIXP` | `ExtractionResponseIXP` | The extraction response containing the extracted data. |

Raises:

| Type                            | Description                            |
| ------------------------------- | -------------------------------------- |
| `OperationNotCompleteException` | If the extraction is not yet complete. |
| `OperationFailedException`      | If the extraction operation failed.    |

Examples:

```
# After receiving a callback/webhook that extraction is complete:
result = service.retrieve_ixp_extraction_result(
    project_id=start_response.project_id,
    tag=start_response.tag,
    operation_id=start_response.operation_id,
)
```

### retrieve_ixp_extraction_result_async

```
retrieve_ixp_extraction_result_async(
    project_id, tag, operation_id
)
```

Asynchronous version of the retrieve_ixp_extraction_result method.

### retrieve_ixp_extraction_validation_result

```
retrieve_ixp_extraction_validation_result(
    project_id, tag, operation_id
)
```

Retrieve the result of an IXP create validate extraction action operation (single-shot, non-blocking).

This method retrieves the result of an IXP create validate extraction action that was previously started with `start_ixp_extraction_validation`. It does not poll - it makes a single request and returns the result if available, or raises an exception if not complete.

Parameters:

| Name           | Type  | Description                                                     | Default    |
| -------------- | ----- | --------------------------------------------------------------- | ---------- |
| `operation_id` | `str` | The operation ID returned from start_ixp_extraction_validation. | *required* |
| `project_id`   | `str` | The ID of the IXP project.                                      | *required* |
| `tag`          | `str` | The tag of the published project version.                       | *required* |

Returns:

| Name                       | Type                       | Description           |
| -------------------------- | -------------------------- | --------------------- |
| `ValidateExtractionAction` | `ValidateExtractionAction` | The validation action |

Raises:

| Type                            | Description                                   |
| ------------------------------- | --------------------------------------------- |
| `OperationNotCompleteException` | If the validation action is not yet complete. |
| `OperationFailedException`      | If the validation action has failed.          |

Examples:

```
# After receiving a callback/webhook that validation is complete:
validation_result = service.retrieve_ixp_extraction_validation_result(
    operation_id=start_operation_response.operation_id,
    project_id=start_operation_response.project_id,
    tag=start_operation_response.tag,
)
```

### retrieve_ixp_extraction_validation_result_async

```
retrieve_ixp_extraction_validation_result_async(
    project_id, tag, operation_id
)
```

Asynchronous version of the retrieve_ixp_extraction_validation_result method.

### start_ixp_extraction

```
start_ixp_extraction(
    project_name, tag, file=None, file_path=None
)
```

Start an IXP extraction process without waiting for results (non-blocking).

This method uploads the file as an attachment and starts the extraction process, returning immediately without waiting for the extraction to complete. Use this for async workflows where you want to receive results via callback/webhook.

Parameters:

| Name           | Type          | Description                                             | Default    |
| -------------- | ------------- | ------------------------------------------------------- | ---------- |
| `project_name` | `str`         | Name of the IXP project.                                | *required* |
| `tag`          | `str`         | Tag of the published project version (e.g., "staging"). | *required* |
| `file`         | `FileContent` | The document file to be processed.                      | `None`     |
| `file_path`    | `str`         | Path to the document file to be processed.              | `None`     |

Note

Either `file` or `file_path` must be provided, but not both.

Returns:

| Name                      | Type                      | Description                                                 |
| ------------------------- | ------------------------- | ----------------------------------------------------------- |
| `ExtractionStartResponse` | `StartExtractionResponse` | Contains the operation_id, document_id, project_id, and tag |

Examples:

```
start_response = uipath.documents.start_ixp_extraction(
    project_name="MyIXPProjectName",
    tag="staging",
    file_path="path/to/document.pdf",
)
# start_response.operation_id can be used to poll for results later
```

### start_ixp_extraction_async

```
start_ixp_extraction_async(
    project_name, tag, file=None, file_path=None
)
```

Asynchronous version of the start_ixp_extraction method.

### start_ixp_extraction_validation

```
start_ixp_extraction_validation(
    extraction_response,
    action_title,
    action_catalog=None,
    action_priority=None,
    action_folder=None,
    storage_bucket_name=None,
    storage_bucket_directory_path=None,
)
```

Start an IXP extraction validation action without waiting for results (non-blocking).

Parameters:

| Name                            | Type                    | Description                                                          | Default    |
| ------------------------------- | ----------------------- | -------------------------------------------------------------------- | ---------- |
| `extraction_response`           | `ExtractionResponseIXP` | The extraction response from the IXP extraction process.             | *required* |
| `action_title`                  | `str`                   | The title of the validation action.                                  | *required* |
| `action_catalog`                | `str`                   | The catalog of the validation action.                                | `None`     |
| `action_priority`               | `ActionPriority`        | The priority of the validation action.                               | `None`     |
| `action_folder`                 | `str`                   | The folder of the validation action.                                 | `None`     |
| `storage_bucket_name`           | `str`                   | The name of the storage bucket where validation data will be stored. | `None`     |
| `storage_bucket_directory_path` | `str`                   | The directory path within the storage bucket.                        | `None`     |

Returns:

| Name                                | Type                                | Description                                                  |
| ----------------------------------- | ----------------------------------- | ------------------------------------------------------------ |
| `StartExtractionValidationResponse` | `StartExtractionValidationResponse` | Contains the operation_id, document_id, project_id, and tag. |

Examples:

```
start_operation_response = service.start_ixp_extraction_validation(
    action_title="Validate IXP Extraction",
    action_priority=ActionPriority.HIGH,
    action_catalog="DefaultCatalog",
    action_folder="Validations",
    storage_bucket_name="my-storage-bucket",
    storage_bucket_directory_path="validations/ixp",
    extraction_response=extraction_response,
)
# start_operation_response can be used to poll for validation results later
```

### start_ixp_extraction_validation_async

```
start_ixp_extraction_validation_async(
    extraction_response,
    action_title,
    action_catalog=None,
    action_priority=None,
    action_folder=None,
    storage_bucket_name=None,
    storage_bucket_directory_path=None,
)
```

Asynchronous version of the start_ixp_extraction_validation method.
