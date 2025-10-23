#!/bin/bash

# Common utility to print UiPath output file
# Usage: source /app/testcases/common/validate_output.sh

debug_print_uipath_output() {
    echo "Printing output file..."
    if [ -f "__uipath/output.json" ]; then
        echo "=== OUTPUT FILE CONTENT ==="
        cat __uipath/output.json
        echo "=== END OUTPUT FILE CONTENT ==="
    else
        echo "ERROR: __uipath/output.json not found!"
        echo "Checking directory contents:"
        ls -la
        if [ -d "__uipath" ]; then
            echo "Contents of __uipath directory:"
            ls -la __uipath/
        else
            echo "__uipath directory does not exist!"
        fi
    fi
}

validate_output() {
    echo "Printing output file for validation..."
    debug_print_uipath_output

    echo "Validating output..."
    python src/assert.py || { echo "Validation failed!"; exit 1; }

    echo "Testcase completed successfully."
}

validate_output
