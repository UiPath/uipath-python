# Classifier evaluator end-to-end demo

A minimal intent-classification agent that exercises the new
`ClassifierEvaluator` end-to-end. Use this as the test fixture for both
SDK-only validation (Path A below) and Studio Web full-stack validation
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
        ├── intent_match.json     # per-datapoint ExactMatch on agent_output.intent
        └── intent_classifier.json # the new uipath-classifier (pure metadata)
```

The eval set is wired so that for every datapoint both evaluators run:
- `intent_match` produces a 1.0/0.0 score with `{"expected": "...", "actual": "..."}` justification.
- `intent_classifier` produces a sentinel 0.0 score with `{"classes": [...], "source_evaluator": "intent_match"}` justification.

Downstream (the C# layer in Studio Web) reads both to compute precision /
recall / F-score across the dataset.

> Heads-up — every datapoint must have an entry for the classifier in
> `evaluationCriterias` (even an empty `{}`). The runtime currently skips
> evaluators that aren't keyed in `evaluationCriterias` for a datapoint, so
> omitting them silently drops the classifier results.

## Path A — SDK only (real run, ~30 seconds)

```bash
cd packages/uipath
uv sync --all-extras

cd samples/classifier_demo
uv run --project ../.. uipath eval main main.json --no-report --output-file /tmp/out.json
```

Expected: a results table with two columns (`intent_classifier`, `intent_match`).
`intent_match` averages to 0.7 (6/9 correct). `intent_classifier` shows 0.0 per
row by design — its real work is to ship the classes list to the backend.

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

You should see something like:

```
intent_classifier  {'expected': '', 'actual': '', 'classes': ['book', 'cancel', 'reschedule'], 'source_evaluator': 'intent_match'}
intent_match       {'expected': 'book', 'actual': 'book'}
```

## Path B — Full Studio Web stack (real UI, click Run, see panel)

Currently blocked on environment that I (the assistant who built this) didn't
have available locally. The pieces:

### Prereqs (per `Agents/LOCAL_DEVELOPMENT.md`)
- Docker installed and running
- `make` available
- Azure CLI authenticated session (`az login`)
- Azure DevOps PAT exported as `AZURE_DEVOPS_PAT`
- GitHub NPM registry token exported as `GH_NPM_REGISTRY_TOKEN`
- Azure access token exported as `AZURE_ACCESS_TOKEN` (for the python worker build)
- `cloud-provider-kind` binary (used for the local KinD cluster)

### Steps

1. **Point python-eval-worker at the local SDK branch.** The published
   `uipath` package on PyPI doesn't yet have `ClassifierEvaluator`. Edit
   `Agents/python-eval-worker/pyproject.toml`:

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
   author them in the UI — the picker now shows a "Classifier" entry under
   the AGGREGATION section), and click Run.

6. **Verify** the Aggregations panel renders between the run header and the
   datapoint table, with the confusion matrix matching what Path A's Python
   shim computes (macro F1 ≈ 0.667 on this fixture).

### Open questions for the team owning local dev

- Does the existing PAT / token set get refreshed automatically by the dev tooling, or do contributors need to rotate them periodically?
- Is there a simpler "local-only" path that bypasses the KinD cluster (e.g. docker-compose) for changes that don't touch K8s manifests?
- What's the standard pattern for pointing the python worker at a non-PyPI uipath build? The `[tool.uv.sources]` override above is the standard uv path — confirm there's no Helm/skaffold complication.

## Companion PRs

| Repo | Branch | PR | What |
|---|---|---|---|
| uipath-python | `feat/eval-classifier-evaluator` | [#1674](https://github.com/UiPath/uipath-python/pull/1674) | SDK `ClassifierEvaluator` |
| Agents | `feat/eval-classifier-backend` | [#5313](https://github.com/UiPath/Agents/pull/5313) | C# math + activity + envelope storage |
| Agents | `feat/eval-dataset-evaluators-ui` | [#5306](https://github.com/UiPath/Agents/pull/5306) | Frontend picker + Aggregations panel |
