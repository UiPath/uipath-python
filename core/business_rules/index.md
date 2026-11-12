Business Rules service for UiPath Platform.

Runs business rules: a rule deployed to Orchestrator, or, inside a debug session, the undeployed rule from the Studio project being debugged.

## BusinessRulesService

Service for running UiPath Business Rules.

Each call runs one input against a business rule, named like any other resource, and returns the decisions it produced. The service picks the endpoint from the run itself, so the caller never chooses one: inside a debug session the undeployed rule from the project being debugged runs, and otherwise the rule deployed to Orchestrator runs.

### run

```
run(
    name,
    input_arguments,
    *,
    version=None,
    decision_names=None,
    folder_key=None,
    folder_path=None,
    caller=None,
    trace_context=None,
)
```

Run a business rule against one input.

Parameters:

| Name              | Type                       | Description                                                                                     | Default                                                                                                                               |
| ----------------- | -------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `name`            | `str`                      | The name of the business rule.                                                                  | *required*                                                                                                                            |
| `input_arguments` | `dict[str, Any]`           | The input to run, keyed by the rule's input names. Declared inputs absent from it bind to null. | *required*                                                                                                                            |
| `version`         | \`str                      | None\`                                                                                          | The rule version to run; defaults to the active version. Ignored on a debug run.                                                      |
| `decision_names`  | \`list[str]                | None\`                                                                                          | The decisions to evaluate; defaults to the whole model.                                                                               |
| `folder_key`      | \`str                      | None\`                                                                                          | The key of the folder the rule is deployed in.                                                                                        |
| `folder_path`     | \`str                      | None\`                                                                                          | The path of the folder the rule is deployed in. Looked up and sent as its key.                                                        |
| `caller`          | \`BusinessRuleCaller       | None\`                                                                                          | Who is running the rule, for the deployed run's audit. Fields left unset default to the current job's values. Ignored on a debug run. |
| `trace_context`   | \`BusinessRuleTraceContext | None\`                                                                                          | The trace to file the run's spans under. Defaults to the ambient trace: UIPATH_TRACE_ID and the current span.                         |

Which rule runs is decided in this order, first match winning:

1. `folder_key` or `folder_path` given: the rule deployed in that folder.
1. Inside a debug session (`UIPATH_PROJECT_ID` is set, or the job is rooted to a debug job) with a job key in `UIPATH_JOB_KEY`: the undeployed rule from the project being debugged. The service finds the project and its folders from the job's lineage.
1. Otherwise: the rule deployed in `UIPATH_FOLDER_KEY`, or else `UIPATH_FOLDER_PATH`.

A deployed run needs a folder key: `folder_key` is sent as is, and `folder_path` is looked up and sent as its key; the two are exclusive. A `businessRule` binding can remap `name` and the folder per environment; its folder then replaces `folder_key` or `folder_path`.

Returns:

| Name                    | Type                    | Description                           |
| ----------------------- | ----------------------- | ------------------------------------- |
| `BusinessRuleRunResult` | `BusinessRuleRunResult` | The decisions produced for the input. |

Raises:

| Type                      | Description                                                |
| ------------------------- | ---------------------------------------------------------- |
| `ValueError`              | If the request is invalid or a required folder is missing. |
| `FolderNotFoundException` | If no folder matches folder_path.                          |
| `EnrichedException`       | If the service rejects the request.                        |

Examples:

```
from uipath.platform import UiPath

client = UiPath()

# In a debug session this runs the rule from the project being
# debugged; deployed, the rule in the job's folder.
result = client.business_rules.run(
    "Loan Pricing", {"creditScore": 740, "age": 34}
)
for decision in result.decisions:
    print(decision.decision_name, decision.outputs)

# Always the rule deployed in a given folder
result = client.business_rules.run(
    "Loan Pricing", {"creditScore": 740}, folder_path="Finance"
)
```

### run_async

```
run_async(
    name,
    input_arguments,
    *,
    version=None,
    decision_names=None,
    folder_key=None,
    folder_path=None,
    caller=None,
    trace_context=None,
)
```

Asynchronously run a business rule against one input.

Parameters:

| Name              | Type                       | Description                                                                                     | Default                                                                                                                               |
| ----------------- | -------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `name`            | `str`                      | The name of the business rule.                                                                  | *required*                                                                                                                            |
| `input_arguments` | `dict[str, Any]`           | The input to run, keyed by the rule's input names. Declared inputs absent from it bind to null. | *required*                                                                                                                            |
| `version`         | \`str                      | None\`                                                                                          | The rule version to run; defaults to the active version. Ignored on a debug run.                                                      |
| `decision_names`  | \`list[str]                | None\`                                                                                          | The decisions to evaluate; defaults to the whole model.                                                                               |
| `folder_key`      | \`str                      | None\`                                                                                          | The key of the folder the rule is deployed in.                                                                                        |
| `folder_path`     | \`str                      | None\`                                                                                          | The path of the folder the rule is deployed in. Looked up and sent as its key.                                                        |
| `caller`          | \`BusinessRuleCaller       | None\`                                                                                          | Who is running the rule, for the deployed run's audit. Fields left unset default to the current job's values. Ignored on a debug run. |
| `trace_context`   | \`BusinessRuleTraceContext | None\`                                                                                          | The trace to file the run's spans under. Defaults to the ambient trace: UIPATH_TRACE_ID and the current span.                         |

Returns:

| Name                    | Type                    | Description                           |
| ----------------------- | ----------------------- | ------------------------------------- |
| `BusinessRuleRunResult` | `BusinessRuleRunResult` | The decisions produced for the input. |

Raises:

| Type                      | Description                                                |
| ------------------------- | ---------------------------------------------------------- |
| `ValueError`              | If the request is invalid or a required folder is missing. |
| `FolderNotFoundException` | If no folder matches folder_path.                          |
| `EnrichedException`       | If the service rejects the request.                        |
