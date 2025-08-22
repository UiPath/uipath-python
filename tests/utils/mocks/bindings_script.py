from uipath import UiPath

uipath = UiPath()


async def async_function() -> None:
    await uipath.assets.retrieve_async("asset_from_retrieve_async")
    await uipath.buckets.retrieve_async("bucket_from_retrieve_async")
    await uipath.context_grounding.retrieve_async("index_from_retrieve_async")
    await uipath.processes.invoke_async("process_name_from_invoke_async")


def include_folder_path() -> None:
    uipath.assets.retrieve("asset_with_folder_path", folder_path="asset_folder_path")
    uipath.buckets.retrieve("bucket_with_folder_path", folder_path="bucket_folder_path")
    uipath.context_grounding.retrieve(
        "index_with_folder_path", folder_path="index_folder_path"
    )
    uipath.processes.invoke(
        "process_with_folder_path", folder_path="process_folder_path"
    )


def main() -> None:
    uipath.assets.retrieve("asset_from_retrieve")
    uipath.buckets.retrieve("bucket_from_retrieve")
    uipath.context_grounding.retrieve("index_from_retrieve")
    uipath.processes.invoke("process_name_from_invoke")
