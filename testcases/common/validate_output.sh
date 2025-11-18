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

# Run assertions from the testcase's src directory
run_assertions() {
    echo "Running assertions..."
    if [ -f "src/assert.py" ]; then
        # Use the Python from the virtual environment
        # Prepend the common directory to the python path so it can be resolved
        PYTHONPATH="../common:$PYTHONPATH" python src/assert.py
    else
        echo "assert.py not found in src directory!"
        exit 1
    fi
}

debug_print_uipath_output
run_assertions