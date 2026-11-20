UiPath Documents Models.

This module contains models related to UiPath Document Understanding service.

## ActionPriority

Bases: `str`, `Enum`

Priority levels for validation actions. More details can be found in the [official documentation](https://docs.uipath.com/action-center/automation-cloud/latest/user-guide/create-document-validation-action#configuration).

### CRITICAL

```
CRITICAL = 'Critical'
```

Critical priority

### HIGH

```
HIGH = 'High'
```

High priority

### LOW

```
LOW = 'Low'
```

Low priority

### MEDIUM

```
MEDIUM = 'Medium'
```

Medium priority

### from_str

```
from_str(value)
```

Creates an ActionPriority from a string.

## ClassificationResponse

Bases: `BaseModel`

A model representing the response from a document classification process.

## ClassificationResult

Bases: `BaseModel`

A model representing the result of a document classification.

Attributes:

| Name               | Type             | Description                                               |
| ------------------ | ---------------- | --------------------------------------------------------- |
| `document_id`      | `str`            | The ID of the classified document.                        |
| `document_type_id` | `str`            | The ID of the predicted document type.                    |
| `confidence`       | `float`          | The confidence score of the classification.               |
| `ocr_confidence`   | `float`          | The OCR confidence score of the document.                 |
| `reference`        | `Reference`      | The reference information for the classified document.    |
| `document_bounds`  | `DocumentBounds` | The bounds of the document in terms of pages and text.    |
| `classifier_name`  | `str`            | The name of the classifier used.                          |
| `project_id`       | `str`            | The ID of the project associated with the classification. |

## DocumentBounds

Bases: `BaseModel`

A model representing the bounds of a document in terms of pages and text.

## DocumentsService

Bases: `_DocumentsServiceBase`

Service for managing UiPath DocumentUnderstanding Document Operations.

This service provides methods to extract data from documents using UiPath's Document Understanding capabilities.

It calls DU Framework API v1.1. `DocumentsServiceV2` has the same methods and calls API v2.

Preview Feature

This function is currently experimental. Behavior and parameters are subject to change in future versions.

## DocumentsServiceV2

Bases: `_DocumentsServiceBase`

Service for managing UiPath DocumentUnderstanding Document Operations on DU Framework API v2.

It has the same methods as `DocumentsService`, which calls API v1.1. API v2 results differ:

- field IDs are prefixed with their document type and field group, e.g. `Default.Invoice.Total`
- IXP results group fields in `FieldGroup` fields instead of `Table` fields, and their fields are typed, e.g. `MonetaryQuantity`
- validation tasks open in the Compact view

Preview Feature

This function is currently experimental. Behavior and parameters are subject to change in future versions.

## ExtractionResponse

Bases: `BaseModel`

A model representing the response from a document extraction process.

Attributes:

| Name                | Type               | Description                                                        |
| ------------------- | ------------------ | ------------------------------------------------------------------ |
| `extraction_result` | `ExtractionResult` | The result of the extraction process.                              |
| `project_id`        | `str`              | The ID of the project associated with the extraction.              |
| `tag`               | `str`              | The tag associated with the published model version.               |
| `document_type_id`  | `str`              | The ID of the document type associated with the extraction.        |
| `api_version`       | `str`              | The DU Framework API version that produced the result, 1.1 or 2.0. |

## ExtractionResponseIXP

Bases: `ExtractionResponse`

A model representing the response from a document extraction process for IXP projects.

Attributes:

| Name              | Type                              | Description                                                                                                             |
| ----------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `data_projection` | `list[FieldGroupValueProjection]` | A simplified projection of the extracted data, with one entry per row of each table (API v1.1) or field group (API v2). |

## ExtractionResult

Bases: `BaseModel`

A model representing the result of a document extraction process.

## FieldGroupValueProjection

Bases: `BaseModel`

A model representing a projection of a field group value in a document extraction result.

## FieldType

Bases: `str`, `Enum`

Field types supported by Document Understanding service.

## FieldValueProjection

Bases: `BaseModel`

A model representing a projection of a field value in a document extraction result.

Attributes:

| Name   | Type  | Description                                                                                                                                                          |
| ------ | ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`   | `str` | The field ID. In API v1.1 it is the plain field ID (e.g. Total). In API v2 it is prefixed by its document type and field group, if any (e.g. Default.Invoice.Total). |
| `name` | `str` | The field display name.                                                                                                                                              |

## ProjectType

Bases: `str`, `Enum`

Project types available and supported by Documents Service.

### IXP

```
IXP = 'IXP'
```

Represents an [IXP](https://docs.uipath.com/ixp/automation-cloud/latest/overview/managing-projects#creating-a-new-project) project type.

### MODERN

```
MODERN = 'Modern'
```

Represents a [DU Modern](https://docs.uipath.com/document-understanding/automation-cloud/latest/user-guide/about-document-understanding) project type.

### PRETRAINED

```
PRETRAINED = 'Pretrained'
```

Represents a [Pretrained](https://docs.uipath.com/document-understanding/automation-cloud/latest/user-guide/out-of-the-box-pre-trained-ml-packages) project type.

## Reference

Bases: `BaseModel`

A model representing a reference within a document.

## StartExtractionResponse

Bases: `StartOperationResponse`

A model representing the response from starting an extraction operation.

## StartExtractionValidationResponse

Bases: `StartOperationResponse`

A model representing the response from starting an extraction validation operation.

## StartOperationResponse

Bases: `BaseModel`

A model representing the response from starting an operation.

Attributes:

| Name           | Type  | Description                                                          |
| -------------- | ----- | -------------------------------------------------------------------- |
| `operation_id` | `str` | The ID of the extraction operation, used to poll for results.        |
| `document_id`  | `str` | The ID of the digitized document.                                    |
| `project_id`   | `str` | The ID of the project.                                               |
| `tag`          | `str` | The tag of the published project version.                            |
| `api_version`  | `str` | The DU Framework API version that started the operation, 1.1 or 2.0. |

## ValidateClassificationAction

Bases: `ValidationAction`

A model representing a validation action for document classification.

## ValidateExtractionAction

Bases: `ValidationAction`

A model representing a validation action for document extraction.

## ValidationAction

Bases: `BaseModel`

A model representing a validation action for a document.

Attributes:

| Name            | Type   | Description                                                                                      |
| --------------- | ------ | ------------------------------------------------------------------------------------------------ |
| `action_data`   | `dict` | The data associated with the validation action.                                                  |
| `action_status` | `str`  | The status of the validation action. Possible values can be found in the official documentation. |
| `project_id`    | `str`  | The ID of the project associated with the validation action.                                     |
| `tag`           | `str`  | The tag associated with the published model version.                                             |
| `operation_id`  | `str`  | The operation ID associated with the validation action.                                          |
