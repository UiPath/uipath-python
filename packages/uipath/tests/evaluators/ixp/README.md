# IXP Measure scoring — golden parity tests

Parity suite for the ported scoring core in
`src/uipath/eval/evaluators/ixp/`. The source of truth is ixp-platform's own
test suite:

- `data/*.json` — byte-for-byte copies of ixp-platform
  `backend/mls/user-model-store/uipath_mls_user_model_store/tests/data/`
  (29 `ixp_metrics_test_case_*` + 28 `from_moon_ixp_metrics_test_case_*`).
- `ixp_utils.py` — port of the upstream fixture builders (pydantic v2).
- `run_golden_tests.py` — replicates `test_ixp_metrics.py` (both golden
  paths), the `test_ranged_value.py` numeric table, the typed-normalizer
  cases from user-model `test_data_type.py`, and a differential test of the
  pure-Python assignment solver against scipy.
- `demo.py` — sample runs: the design wiki's worked example (asserts
  F1 = 5/7, project score 0.70 → GOOD) plus a few golden fixtures printed
  as metric grids.

## Run

```bash
cd packages/uipath/tests/evaluators/ixp

# full parity suite (85 checks)
uv run --no-project --python 3.12 --with pydantic --with python-dateutil \
    --with scipy --with numpy python run_golden_tests.py

# sample runs / worked example
uv run --no-project --python 3.12 --with pydantic --with python-dateutil \
    python demo.py
```

scipy/numpy are test-only (differential check; skipped if absent). The
ported module itself needs only stdlib + python-dateutil.

## Refreshing goldens

If the ML team changes the math in ixp-platform, re-copy `tests/data/*.json`
from ixp-platform and re-run. Any intentional logic change must land in both
places (upstream pins this with a metrics-cache version bump — see the note
at the top of upstream `metrics/ixp.py`).
