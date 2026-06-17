# Classifier aggregator end-to-end demo

A minimal intent-classification agent that exercises the new
classification **aggregator** end-to-end. Use this as the test fixture for
both SDK-only validation (Path A below) and Studio Web full-stack validation
(Path B).

## What's here

```
classifier_demo/
├── main.py                       # 3-class keyword classifier
├── uipath.json
├── pyproject.toml
├── bindings.json
└── evaluations/
    ├── eval-sets/
    │   └── main.json             # 9 datapoints, 3 per class, some intentionally wrong
    └── evaluators/
        └── intent_match.json     # ExactMatch on agent_output.intent + classification aggregator
```

There is **one** evaluator. `intent_match` is an `ExactMatchEvaluator` whose
`evaluatorConfig` carries an `aggregators: [{ name: "classification", classes: [...] }]`
entry. Per datapoint, the evaluator emits a 1.0/0.0 score and an
`ExactMatchJustification` whose `aggregators` field round-trips the config
through to the downstream consumer (the C# layer in Studio Web), which builds
a confusion matrix and precision / recall / F-score across the dataset.

## Path A — SDK only (real run, ~30 seconds)

```bash
cd packages/uipath
uv sync --all-extras

cd samples/classifier_demo
uv run --project ../.. uipath eval main main.json --no-report --output-file /tmp/out.json
```

Expected: a results table with a single `intent_match` column averaging 0.667
(6/9 correct).

To see the metadata payload that lands in the backend's
`CodedEvaluatorScore.Justification`:

```bash
python3 -c "
import json
with open('/tmp/out.json') as f: d = json.load(f)
for r in d['evaluationSetResults'][0]['evaluationRunResults']:
    print(r['evaluatorName'], r['result'].get('details'))
"
```

You should see entries like:

```
intent_match  {'expected': 'book', 'actual': 'book', 'aggregators': [{'name': 'classification', 'classes': ['book', 'cancel', 'reschedule']}]}
```

The `aggregators` list is identical on every datapoint by design — it's the
mechanism by which the per-datapoint records carry the class set to the C#
post-pass without requiring a separate evaluator-snapshot lookup.

## Path B — Full Studio Web stack (real UI, click Run, see panel)

The pieces below assume you have a local KinD cluster running per
`Agents/LOCAL_DEVELOPMENT.md`.

### Prereqs
- Docker installed and running
- `make` available
- Azure CLI authenticated session (`az login`)
- Azure DevOps PAT exported as `AZURE_DEVOPS_PAT`
- GitHub NPM registry token exported as `GH_NPM_REGISTRY_TOKEN`
- Azure access token exported as `AZURE_ACCESS_TOKEN` (for the python worker build)
- `cloud-provider-kind` binary (used for the local KinD cluster)

### Steps

1. **Point python-eval-worker at the local SDK branch.** The published
   `uipath` package on PyPI doesn't yet have the classification aggregator.
   Edit `Agents/python-eval-worker/pyproject.toml`:

   ```toml
   [tool.uv.sources]
   uipath = { path = "../../uipath-python/packages/uipath", editable = true }
   ```

   Then `cd python-eval-worker && uv lock && uv sync`.

2. **Bring up the local KinD cluster** (from `Agents/`):
   ```bash
   make create-kind-cluster
   kubectl get nodes
   sudo ./bin/cloud-provider-kind &      # in a separate shell or background
   make up
   make deploy
   ```

3. **Build the backend with the classifier changes:**
   ```bash
   git checkout feat/eval-classifier-backend       # in Agents repo
   # Re-trigger the helm/skaffold deploy for the backend
   make deploy
   ```

4. **Build the frontend with the UI changes:**
   ```bash
   git checkout feat/eval-dataset-evaluators-ui    # in Agents repo
   # Same deploy command rebuilds frontend image
   ```

5. **Open Studio Web** (URL surfaced by the deploy output), create an agent
   project, upload the eval-set + evaluator JSONs from this directory (or
   author them in the UI — the evaluator picker exposes an
   "Aggregators" section on ExactMatch where the classification aggregator
   can be attached with its class list), and click Run.

6. **Verify** the Aggregations panel renders between the run header and the
   datapoint table, with the confusion matrix matching what Path A's Python
   payload encodes (macro F1 ≈ 0.667 on this fixture).

### Open questions for the team owning local dev

- Does the existing PAT / token set get refreshed automatically by the dev tooling, or do contributors need to rotate them periodically?
- Is there a simpler "local-only" path that bypasses the KinD cluster (e.g. docker-compose) for changes that don't touch K8s manifests?
- What's the standard pattern for pointing the python worker at a non-PyPI uipath build? The `[tool.uv.sources]` override above is the standard uv path — confirm there's no Helm/skaffold complication.

## Companion PRs

| Repo | Branch | PR | What |
|---|---|---|---|
| uipath-python | `feat/eval-classifier-evaluator` | [#1674](https://github.com/UiPath/uipath-python/pull/1674) | SDK `ExactMatch.aggregators` + `LegacyExactMatch.aggregators` |
| Agents | `feat/eval-classifier-backend` | [#5313](https://github.com/UiPath/Agents/pull/5313) | C# math + activity + envelope storage |
| Agents | `feat/eval-dataset-evaluators-ui` | [#5306](https://github.com/UiPath/Agents/pull/5306) | Frontend picker + Aggregations panel |
