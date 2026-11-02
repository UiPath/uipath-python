# Federated credentials in CI

Run tests against UiPath Orchestrator from a CI pipeline without storing a client secret. The pipeline gets a short-lived OIDC token from its provider (GitHub Actions here) and exchanges it for a UiPath access token.

## How it works

1. UiPath Identity holds a federated credential on an external application: "accept tokens from this issuer, with this audience and subject".
2. The CI job asks its provider for an OIDC token and passes it as the client assertion.
3. Identity checks the token signature against the issuer's public keys, checks the claims against the federated credential, and issues an access token with the application's scopes.

## Setup

Create an external application without a secret and register a federated credential that trusts your repository, using the [uip CLI](https://docs.uipath.com/uipath-cli/standalone/latest/user-guide/authentication#flow-3-%E2%80%94-federated-credentials-(workload-identity)):

```bash
uip admin external-apps create "my-ci-app" --no-secret --app-scope "OR.Folders.Read"
uip admin external-apps federated-credentials create <client-id> \
  --name "GitHub Actions main" \
  --issuer "https://token.actions.githubusercontent.com" \
  --audience "https://uipath/<client-id>" \
  --subject "repo:<owner>/<repo>:ref:refs/heads/main"
```

Copy [github-workflow.yml](github-workflow.yml) to `.github/workflows/` in that repository and fill in `UIPATH_URL` and `UIPATH_CLIENT_ID`.

## Usage

From code, pass the token to the SDK:

```python
UiPath(
    base_url=os.environ["UIPATH_URL"],
    client_id=os.environ["UIPATH_CLIENT_ID"],
    client_assertion=os.environ["UIPATH_CLIENT_ASSERTION"],
    scope="OR.Folders.Read",
)
```

From the CLI, `uipath auth` reads the token from `UIPATH_CLIENT_ASSERTION` (or `--client-assertion`) and writes the session to `.env` for the commands that follow (`uipath run`, `uipath eval`, `uipath pack`):

```bash
uipath auth --base-url "$UIPATH_URL" --client-id "$UIPATH_CLIENT_ID" --scope OR.Folders.Read
```
