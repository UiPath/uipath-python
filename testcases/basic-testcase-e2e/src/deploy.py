from uipath import UiPath
from dotenv import load_dotenv
load_dotenv()

def main():
    uipath = UiPath()

    uipath.processes.create_release(
        name="basic-testcase-e2e",
        package_name="basic-testcase-e2e",
        package_version="0.0.1",
        input_json='{"message": "Hello from E2E", "repeat": 3, "prefix": "E2E"}',
        retention_action="Delete",
        retention_period=20,
        stale_retention_period=30,
    )

    print("Deployed basic-testcase-e2e process.")

if __name__ == "__main__":
    main()


# {
#     "Name": "langchain-agent-no-llm",
#     "Description": "simple langchain agent with no llm",
#     "ProcessKey": "langchain-agent-no-llm",
#     "ProcessVersion": "0.0.1",
#     "EntryPointId": 596116,
#     "EnvironmentVariables": "",
#     "InputArguments": "{}",
#     "SpecificPriorityValue": 45,
#     "JobPriority": null,
#     "RobotSize": null,
#     "HiddenForAttendedUser": false,
#     "ResourceOverwrites": [],
#     "RemoteControlAccess": "None",
#     "RetentionAction": "Delete",
#     "RetentionPeriod": 20,
#     "StaleRetentionAction": "Delete",
#     "StaleRetentionPeriod": 30,
#     "Tags": []
# }