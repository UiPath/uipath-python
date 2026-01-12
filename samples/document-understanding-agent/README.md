# Document Understanding Sample

This sample demonstrates how to use UiPath Document Understanding capabilities with the UiPath Python SDK to classify, extract and validate data from documents.

## Overview

Document Understanding enables automated processing of documents through:

- **Classification**: Identify document types
- **Extraction**: Extract data from classified documents
- **Validation**: Create human-in-the-loop validation actions for review

This sample includes three Document Understanding approaches:

- **IXP (Intelligent Xtraction and Processing)** (`src/ixp.py`) - [IXP documentation](https://docs.uipath.com/ixp/automation-cloud/latest/overview/introduction)
- **Modern Projects** (`src/du_modern.py`) - [Modern DU documentation](https://docs.uipath.com/document-understanding/automation-cloud/latest/user-guide/about-document-understanding)
- **Pretrained Models** (`src/pretrained.py`) - [Pretrained models documentation](https://docs.uipath.com/document-understanding/automation-cloud/latest/user-guide/out-of-the-box-pre-trained-ml-packages)

## Prerequisites

- UiPath Automation Suite or Automation Cloud tenant
- Document Understanding projects deployed with appropriate tags ( [DU Modern publish documentation](https://docs.uipath.com/document-understanding/automation-cloud/latest/user-guide/publish) / [IXP model deployment documentation](https://docs.uipath.com/document-understanding/automation-cloud/latest/user-guide/publish) )
- Action catalog configured for validation actions ( [Actions documentation](https://docs.uipath.com/action-center/automation-cloud/latest/user-guide/about-actions) )
- Storage bucket for validation data ( [Storage buckets documentation](https://docs.uipath.com/orchestrator/automation-cloud/latest/user-guide/about-storage-buckets) )

## Setup

1. **Install dependencies**:

   ```bash
   uv sync
   ```

2. **Configure UiPath credentials and initialize project**:

   ```bash
   uv run uipath auth
   uv run uipath init
   ```

3. **Update sample parameters**:

   Edit the sample files to match your environment:
   - Project names and tags
   - Document type names
   - Action catalog and folder names
   - Storage bucket configuration

## Usage

Run the complete sample workflow:

```bash
uv run uipath run main
```

Or run individual samples:

```python
from src import ixp, du_modern, pretrained

# IXP extraction and validation
ixp.extract_validate()

# Modern project
du_modern.extract_validate()
du_modern.classify_extract_validate()

# Pretrained model
pretrained.extract_validate()
pretrained.classify_extract_validate()
```
