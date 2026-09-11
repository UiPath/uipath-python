"""Project types scaffolded by `uipath new`.

Framework integrations (uipath-langchain and the packages in
UiPath/uipath-integrations-python) import this to decide whether a
`uipath new` invocation is theirs to handle.
"""

from enum import StrEnum


class ProjectType(StrEnum):
    """What `uipath new` scaffolds.

    AUTO (the default) lets an installed agent framework claim the scaffold
    and falls back to a function project; FUNCTION and AGENT request one
    explicitly.
    """

    AUTO = "auto"
    FUNCTION = "function"
    AGENT = "agent"
