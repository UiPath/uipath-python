import json
from typing import Any, Dict, Optional

from uipath_sdk import UiPathSDK  # type: ignore
from uipath_sdk._models.actions import Action  # type: ignore

uipath = UiPathSDK()

class EscalationConfig:
    """
    Class to handle escalation configuration and Action creation.
    """
    def __init__(self, config_path: str = "uipath.json"):
        self.config_path = config_path
        self._config: Optional[Dict[str, Any]] = None

    @property
    def config(self) -> Optional[Dict[str, Any]]:
        """Lazy-load the configuration."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    @property
    def enabled(self) -> bool:
        """
        Check if escalation is enabled.

        Returns True if:
        1. Configuration exists
        2. Contains required appId, data, title
        """
        if not self.config:
            return False

        if "appId" not in self.config:
            return False

        if "data" not in self.config:
            return False

        if "title" not in self.config:
            return False

        return True

    def _load_config(self) -> Optional[Dict[str, Any]]:
        """Load the escalation configuration from the config file."""
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
            return config.get("defaultEscalation")
        except (json.JSONDecodeError, IOError, FileNotFoundError):
            return None

    def process_payload(self, value: Any) -> Dict[str, Any]:
        """
        Process the template by replacing $VALUE placeholders with the provided value.
        """
        template = self.config.get("data", {}) if self.config else {}

        if isinstance(value, str):
            try:
                value_obj = json.loads(value)
            except json.JSONDecodeError:
                value_obj = value
        else:
            value_obj = value

        return self._process_template(template, value_obj)

    def _process_template(self, template: Dict[str, Any], value: Any) -> Dict[str, Any]:
        """Process template with value replacements."""
        def process_value(template_value):
            if isinstance(template_value, dict):
                return {k: process_value(v) for k, v in template_value.items()}
            elif isinstance(template_value, list):
                return [process_value(item) for item in template_value]
            elif isinstance(template_value, str) and template_value.startswith("$VALUE"):
                if template_value == "$VALUE":
                    return value

                path_parts = template_value.replace("$VALUE.", "").split(".")
                current = value

                try:
                    for part in path_parts:
                        if isinstance(current, dict):
                            current = current.get(part)
                        else:
                            return None
                    return current
                except (AttributeError, TypeError):
                    return None
            else:
                return template_value

        return process_value(template)

    async def create_action(self, value: Any) -> Optional[Action]:
        """
        Create an Action with the processed payload.

        Args:
            value: The dynamic value to be processed with the template

        Returns:
            The created Action object or None if configuration is missing or disabled
        """
        if not self.enabled or not self.config:
            return None

        action_data = self.process_payload(value)

        try:
            action = await uipath.actions.create(
                title=self.config.get("title", "Default escalation"),
                app_id=self.config.get("appId"),
                app_version=self.config.get("appVersion", 1),
                data=action_data,
            )
            return action
        except Exception as e:
            print(f"Error creating action: {e}")
            return None
