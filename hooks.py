import os
import shutil


def redirect_index(*args, **kwargs):
    if not os.path.exists("docs/quick_start_images"):
        shutil.copy(
            "docs/plugins/uipath-langchain-python/docs/quick_start.md", "docs/index.md"
        )
        shutil.copytree(
            "docs/plugins/uipath-langchain-python/docs/quick_start_images",
            "docs/quick_start_images",
        )
