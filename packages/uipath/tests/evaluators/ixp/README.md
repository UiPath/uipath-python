# IXP Measure scoring — golden parity tests

Parity suite for the ported scoring core in
`src/uipath/eval/evaluators/ixp/`. The source of truth is ixp-platform's own
test suite:

- `data/*.json` — byte-for-byte copies of ixp-platform
  `backend/mls/user-model-store/uipath_mls_user_model_store/tests/data/`
  (29 `ixp_metrics_test_case_*` + 28 `from_moon_ixp_metrics_test_case_*`).
- `ixp_utils.py` — port of the upstream fixture builders (pydantic v2).
- `test_golden_parity.py` — replicates upstream `test_ixp_metrics.py` (both
  golden paths), the `test_ranged_value.py` numeric table, the
  typed-normalizer cases from user-model `test_data_type.py`, a differential
  test of the pure-Python assignment solver against scipy (skipped when
  scipy is absent), and the design wiki's worked example.
- `demo.py` — sample runs: the wiki worked example (F1 = 5/7, project score
  0.70 → GOOD) plus a few golden fixtures printed as metric grids.

## Run

```bash
cd packages/uipath

pytest tests/evaluators/ixp              # the parity suite (runs in CI)
uv run python -m tests.evaluators.ixp.demo   # sample runs / worked example
```

To also exercise the scipy differential test locally:

```bash
uv run --with scipy --with numpy pytest tests/evaluators/ixp
```

## Refreshing goldens

If the ML team changes the math in ixp-platform, re-copy `tests/data/*.json`
from ixp-platform and re-run. Any intentional logic change must land in both
places (upstream pins this with a metrics-cache version bump — see the note
at the top of upstream `metrics/ixp.py`). The ported files
`ixp.py`/`ranged_value.py`/`data_type_utils.py`/`moon.py` are excluded from
ruff lint/format in `pyproject.toml` to keep them byte-comparable with
upstream — do not reformat them.
