import click


def environment_options(function):
    function = click.option(
        "--alpha",
        "domain",
        flag_value="alpha",
        default=True,
        help="Use alpha environment",
    )(function)
    function = click.option(
        "--staging",
        "domain",
        flag_value="staging",
        help="Use staging environment",
    )(function)
    function = click.option(
        "--cloud",
        "domain",
        flag_value="cloud",
        help="Use production environment",
    )(function)
    return function
