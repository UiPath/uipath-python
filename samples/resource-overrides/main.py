from typing import Any
from uipath import UiPath
from pydantic import BaseModel


class Resource(BaseModel):
    name: str
    value: Any

class Response(BaseModel):
    resources: list[Resource] = []

async def main() -> Response:

    uipath = UiPath()

    response = Response()

    # Assets - retrieve asset value
    asset = await uipath.assets.retrieve_async("asset_name", folder_path="folder_key")
    response.resources.append(Resource(name="asset", value=str(asset.model_dump())))

    # Connections - retrieve connection
    connection = await uipath.connections.retrieve_async("connection_key")
    response.resources.append(Resource(name="connection", value=connection.model_dump()))

    # Actions (Apps) - create action
    action = await uipath.actions.create_async(
        title="Action Title",
        data={"key": "value"},
        app_name="app_name",
        app_folder_path="app_folder_path"
    )
    response.resources.append(Resource(name="action", value=str(action.model_dump())))

    # Context Grounding (Indexes) - add to index
    await uipath.context_grounding.retrieve_async(
        name="index_name",
        folder_path="folder_path"
    )

    # Buckets - retrieve bucket
    bucket = await uipath.buckets.retrieve_async(
        name="bucket_name",
        folder_path="folder_path"
    )
    response.resources.append(Resource(name="bucket", value=str(bucket.model_dump())))

    # Processes - invoke process
    process_result = await uipath.processes.invoke_async(
        name="process_name",
        input_arguments={"arg1": "value1"},
        folder_path="folder_path"
    )
    response.resources.append(Resource(name="process_result", value=str(process_result.model_dump())))

    return response
