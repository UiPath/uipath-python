import re


def on_post_page(output, page, config):
    pattern = r"(<body[^>]*>)"
    replacement = rf"\1\n<noscript><iframe src='https://www.googletagmanager.com/ns.html?id={config['google_tag_manager_id']}' height='0' width='0' style='display:none;visibility:hidden'></iframe></noscript>"
    return re.sub(pattern, replacement, output)
