import os
import re
import shutil


def on_pre_build(config):
    if not os.path.exists("docs/quick_start_images"):
        shutil.copy(
            "docs/plugins/uipath-langchain-python/docs/quick_start.md", "docs/index.md"
        )
        shutil.copytree(
            "docs/plugins/uipath-langchain-python/docs/quick_start_images",
            "docs/quick_start_images",
        )


def on_post_page(output, page, config):
    pattern = r"(<body[^>]*>)"
    replacement = rf"\1\n<noscript><iframe src='https://www.googletagmanager.com/ns.html?id={config['google_tag_manager_id']}' height='0' width='0' style='display:none;visibility:hidden'></iframe></noscript>"
    return re.sub(pattern, replacement, output)
