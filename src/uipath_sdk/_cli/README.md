# parse

`parse-ast.py` will extract names and types of resources to prepare for bindings. currently it's hardcoded to run on `dummy-main.py`

# init

asks for project name, type (process/agent) description and target directory where to init the project. it inits a script, a requirements.txt for the user to install, and a config.json file that we'll use at packing time.

# pack

asks for target directory of the package files and the version and will create a nupkg file
