# type: ignore
import json

import click
from middlewares import Middlewares


@click.command()
def init(*args, **kwargs):
    should_continue, errorMessage = Middlewares.next("init", *args, **kwargs)

    if errorMessage:
        click.echo(f"{errorMessage}")

    if not should_continue:
        return

    config_path = "config.json"
    config_data = {"entryPoints": []}

    with open(config_path, "w") as config_file:
        json.dump(config_data, config_file, indent=4)
