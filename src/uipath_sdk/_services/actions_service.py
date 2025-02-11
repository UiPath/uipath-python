import json
from typing import cast

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import Action
from ._base_service import BaseService


class ActionsService(FolderContext, BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def create(self, title: str, task_catalog: str) -> Action:
        endpoint = "/orchestrator_/forms/TaskForms/CreateFormTask"
        content = json.dumps(
            {
                "formLayout": {
                    "components": [
                        {
                            "mask": False,
                            "customClass": "uipath-button-container",
                            "tableView": True,
                            "alwaysEnabled": False,
                            "type": "table",
                            "input": False,
                            "key": "key",
                            "label": "label",
                            "rows": [
                                [
                                    {"components": []},
                                    {"components": []},
                                    {"components": []},
                                    {"components": []},
                                    {"components": []},
                                    {"components": []},
                                ]
                            ],
                            "numRows": 1,
                            "numCols": 6,
                            "reorder": False,
                        },
                        {
                            "label": "JIRA Description",
                            "disabled": True,
                            "tableView": True,
                            "defaultValue": "JIRA Description",
                            "key": "jiraDescription",
                            "type": "textfield",
                            "input": True,
                        },
                        {
                            "label": "LLM Classification",
                            "disabled": True,
                            "tableView": True,
                            "defaultValue": "LLM Classification",
                            "key": "llmClassification",
                            "type": "textarea",
                            "input": True,
                        },
                        {
                            "type": "button",
                            "label": "Approve",
                            "key": "submit",
                            "disableOnInvalid": True,
                            "input": True,
                            "alwaysEnabled": False,
                            "tableView": True,
                        },
                    ],
                    "version": 1,
                },
                "title": title,
                "priority": "Low",
                "taskCatalogName": task_catalog,
            }
        )

        return cast(
            "Action",
            self.request(
                "POST",
                endpoint,
                content=content,
            ).json(),
        )

    @property
    def custom_headers(self) -> dict[str, str]:
        return self.folder_headers
