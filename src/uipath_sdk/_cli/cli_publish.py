# type: ignore
import os

import click
import requests
from dotenv import load_dotenv


@click.command()
@click.argument("path", type=str, default="")
def publish(path):
    # Search for .nupkg file
    packageToPublish = None
    if not path:
        nupkg_files = [f for f in os.listdir("./") if f.endswith(".nupkg")]
        if not nupkg_files:
            click.echo("No .nupkg file found in current directory")
            return
        click.echo(f"Found package: {nupkg_files[0]}")
        if not click.confirm("Are you sure you want to publish this package?"):
            click.echo("Aborting publish")
            return
        packageToPublish = nupkg_files[0]
    else:
        if not os.path.exists(path):
            click.echo(f"{path} not found")
            return
        packageToPublish = path
    # Check .env file
    if not os.path.exists(".env"):
        click.echo("No .env file found in current directory")
        return

    load_dotenv(os.path.join(os.getcwd(), ".env"))

    if not os.environ.get("UIPATH_TOKEN"):
        click.echo("Invalid .env file - UIPATH_TOKEN not found")
        return

    click.echo("valid")

    base_url = os.environ.get("UIPATH_BASE_URL")
    account = os.environ.get("UIPATH_ACCOUNT_NAME")
    tenant = os.environ.get("UIPATH_TENANT_NAME")
    token = os.environ.get("UIPATH_TOKEN")

    if not all([base_url, account, tenant]):
        click.echo(
            "Missing required environment variables. Please check your .env file contains:"
        )
        click.echo("UIPATH_BASE_URL, UIPATH_ACCOUNT_NAME, UIPATH_TENANT_NAME")
        return

    url = f"https://{base_url}/{account}/{tenant}/orchestrator_/odata/Processes/UiPath.Server.Configuration.OData.UploadPackage()"

    headers = {"Authorization": f"Bearer {token}"}

    with open(packageToPublish, "rb") as f:
        files = {"file": (packageToPublish, f, "application/octet-stream")}
        response = requests.post(url, headers=headers, files=files)

    if response.status_code == 200:
        click.echo("Package published successfully!")
    else:
        click.echo(f"Failed to publish package. Status code: {response.status_code}")
        click.echo(f"Response: {response.text}")
