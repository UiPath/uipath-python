import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

from uipath import UiPath
from uipath.models.actions import Action

logger = logging.getLogger(__name__)


class Escalation:
    """Class to handle default escalation."""

    def __init__(self, config_path: Union[str, Path] = "uipath.json"):
        """Initialize the escalation with a config file path.

        Args:
            config_path: Path to the configuration file (string or Path object)
        """
        self.config_path = Path(config_path)
        self._config = None
        self._enabled = False
        self._load_config()

    def _load_config(self) -> None:
        """Load and validate the default escalation from the config file.

        If the 'defaultEscalation' section exists, validates required fields.
        Raises error if required fields are missing.
        """
        try:
            config_data = json.loads(self.config_path.read_text(encoding="utf-8"))
            escalation_config = config_data.get("defaultEscalation")

            if escalation_config:
                required_fields = {"request", "title"}
                missing_fields = [
                    field for field in required_fields if field not in escalation_config
                ]

                if not any(key in escalation_config for key in ("appName", "appKey")):
                    missing_fields.append("appName or appKey")

                if missing_fields:
                    raise ValueError(
                        f"Missing required fields in configuration: {', '.join(missing_fields)}"
                    )

                self._config = escalation_config
                self._enabled = True
                logger.debug("Escalation configuration loaded successfully")
            else:
                self._enabled = False

        except FileNotFoundError:
            logger.debug(f"Config file not found: {self.config_path}")
            self._enabled = False

        except json.JSONDecodeError:
            logger.warning(
                f"Failed to parse config file {self.config_path}: Invalid JSON"
            )
            self._enabled = False

        except ValueError as e:
            logger.error(str(e))
            raise

        except Exception as e:
            logger.error(f"Unexpected error loading config {self.config_path}: {e}")
            self._enabled = False

    @property
    def enabled(self) -> bool:
        """Check if escalation is enabled.

        Returns:
            True if configuration is valid and loaded
        """
        return self._enabled

    def prepare_data(self, value: Any) -> Dict[str, Any]:
        """Prepare action data by replacing $VALUE placeholders with the provided value.

        Args:
            value: The value to substitute into the template

        Returns:
            Prepared data dictionary with substitutions applied
        """
        if not self.enabled or not self._config:
            return {}

        template = self._config.get("request", {})

        if isinstance(value, str):
            try:
                value_obj = json.loads(value)
            except json.JSONDecodeError:
                value_obj = value
        else:
            value_obj = value

        return self._substitute_values(template, value_obj)

    def _substitute_values(
        self, template: Dict[str, Any], value: Any
    ) -> Dict[str, Any]:
        """Replace template placeholders with actual values.

        Args:
            template: Template dictionary containing placeholders
            value: Values to substitute into the template

        Returns:
            Template with values substituted
        """

        def process_value(template_value):
            if isinstance(template_value, dict):
                return {k: process_value(v) for k, v in template_value.items()}
            elif isinstance(template_value, list):
                return [process_value(item) for item in template_value]
            elif isinstance(template_value, str):
                if template_value == "$VALUE":
                    return value
                elif template_value.startswith("$VALUE."):
                    return self._resolve_value_path(template_value, value)

            return template_value

        return process_value(template)

    def _resolve_value_path(self, path_expr: str, value: Any) -> Any:
        """Resolve a dot-notation path expression against a value.

        Args:
            path_expr: Path expression (e.g. "$VALUE.user.name")
            value: Value object to extract data from

        Returns:
            Extracted value or None if path doesn't exist
        """
        path_parts = path_expr.replace("$VALUE.", "").split(".")
        current = value

        for part in path_parts:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current.get(part)

        return current

    def extract_response_value(self, action_data: Dict[str, Any]) -> Any:
        if not self._config:
            return ""

        response_template = self._config.get("response")
        if not response_template:
            return ""

        for key, template_value in response_template.items():
            if key in action_data:
                extracted_value = None

                if template_value == "$VALUE":
                    extracted_value = action_data[key]
                elif isinstance(template_value, str) and template_value.startswith(
                    "$VALUE."
                ):
                    path_parts = template_value.replace("$VALUE.", "").split(".")
                    current = action_data[key]

                    valid_path = True
                    for part in path_parts:
                        if not isinstance(current, dict) or part not in current:
                            valid_path = False
                            break
                        current = current.get(part)

                    if valid_path:
                        extracted_value = current

                if extracted_value is not None:
                    if isinstance(extracted_value, str):
                        if extracted_value.lower() == "true":
                            return True
                        elif extracted_value.lower() == "false":
                            return False

                        try:
                            if "." in extracted_value:
                                return float(extracted_value)
                            else:
                                return int(extracted_value)
                        except ValueError:
                            pass

                    return extracted_value

        return action_data

    async def create(self, value: Any) -> Optional[Action]:
        """Create an escalation Action with the prepared data.

        Args:
            value: The dynamic value to be substituted into the template

        Returns:
            The created Action object or None if creation fails
        """
        if not self.enabled or not self._config:
            return None

        action_data = self.prepare_data(value)

        if not action_data:
            logger.warning("Action creation skipped: empty data after preparation")
            return None

        try:
            uipath = UiPath()
            action = uipath.actions.create(
                title=self._config.get("title", "Default escalation"),
                app_name=self._config.get("appName"),
                app_key=self._config.get("appKey"),
                app_version=self._config.get("appVersion", 1),
                data=action_data,
            )
            logger.info(f"Action created successfully: {action.key}")
            return action
        except Exception as e:
            logger.error(f"Error creating action: {e}")
            return None
