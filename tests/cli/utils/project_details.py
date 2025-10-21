import toml


class ProjectDetails:
    def __init__(
        self,
        name=None,
        version=None,
        description=None,
        authors=None,
        dependencies=None,
        requires_python=None,
    ):
        self.name = name
        self.version = version
        self.description = description
        self.authors = authors if authors else []
        self.dependencies = dependencies if dependencies else []
        self.requires_python = requires_python

    @classmethod
    def from_toml(cls, toml_str):
        data = toml.loads(toml_str)
        project_data = data.get("project")
        if project_data:
            name = project_data.get("name")
            version = project_data.get("version")
            description = project_data.get("description")
            authors = project_data.get("authors")
            dependencies = project_data.get("dependencies")
            requires_python = project_data.get("requires-python")
            return cls(
                name, version, description, authors, dependencies, requires_python
            )
        else:
            return None

    def to_toml(self):
        data = {
            "project": {
                "name": self.name,
                "version": self.version,
                "description": self.description,
                "authors": self.authors,
                "dependencies": self.dependencies,
                "requires-python": self.requires_python,
            }
        }
        return toml.dumps(data)
