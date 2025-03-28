# Echo Script

A simple utility script that echoes messages with configurable repetition and prefixing.

## Overview

This script provides a straightforward way to echo messages with the following features:
- Repeat a message multiple times
- Add an optional prefix to each line
- Return the result as a single string with newline separators

## Installation

### Setup Environment

1. Create a new Python virtual environment using UV:
   ```bash
   uv venv -p 3.11 .venv
   ```

2. Activate the virtual environment:
   - On Windows:
     ```bash
     .venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source .venv/bin/activate
     ```

3. Install dependencies:
   ```bash
   uv sync
   ```

## Usage

### Basic Command Structure

Run the script using the UiPath runner with a JSON input:

```bash
uipath run echo.py '{"message": "Hello, world!"}'
```

### Input Parameters

The script accepts the following parameters in JSON format:

- `message` (required): The string message to echo
- `repeat` (optional, default=1): Number of times to repeat the message
- `prefix` (optional, default=None): Prefix to add to each line

### Examples

1. Basic usage (echo once):
   ```bash
   uipath run echo.py '{"message": "Hello, world!"}'
   ```
   Output:
   ```
   {'message': 'Hello, world!'}
   ```

2. Repeat a message multiple times:
   ```bash
   uipath run echo.py '{"message": "Hello, world!", "repeat": 3}'
   ```
   Output:
   ```
   {'message': 'Hello, world!\nHello, world!\nHello, world!'}
   ```

3. Add a prefix to each line:
   ```bash
   uipath run echo.py '{"message": "Hello, world!", "repeat": 2, "prefix": "INFO"}'
   ```
   Output:
   ```
   {'message': 'INFO: Hello, world!\nINFO: Hello, world!'}
   ```

### Orchestrator Deployment

   ```bash
   uipath init
   ```
   ```bash
   uipath auth
   ```
   ```bash
   uipath pack
   ```
   ```bash
   uipath publish
   ```
