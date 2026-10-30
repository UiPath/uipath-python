# Skills

A skill bundle is a versioned group of skills. Each skill is a folder with a `SKILL.md` whose YAML frontmatter has a `name` and a `description`, plus any reference files or scripts the skill needs. Bundles are authored and imported into an Orchestrator folder with the `uip` CLI (UiPath's coding-agent CLI, separate from the `uipath` Python CLI used on this page) and bound to a coded agent like any other resource.
<!-- TODO(PC-5188): link the Orchestrator skill bundles page when published -->

`sdk.skills` resolves the bundles an agent declares, downloads them at run start and exposes their skills to the agent's code: the skill descriptions go into the system prompt, and the full `SKILL.md` is read on demand.

!!! warning "Preview Feature"
    The Orchestrator Skills API is not available yet. Until it ships, `UIPATH_SKILLS_SOURCE` defaults to `local` and bundles are read from `./skills` in the project; see [Local development](#local-development). `orchestrator` is a placeholder today: it skips every bundle as `source_unavailable`. It becomes the default once the API is live.

---

## Declare and Load Bundles

Call `load_all_async` once when the job starts: in your graph factory or your first node, never at import time.

```python
from uipath.platform import UiPath
from uipath.platform.skills import SkillBundleRef

BASE_PROMPT = "You triage supplier invoices."


async def make_graph():
    sdk = UiPath()
    skills = await sdk.skills.load_all_async([
        SkillBundleRef(name="finance", folder_path="Shared/Skills", version_mode="pinned", version="3"),
        SkillBundleRef(name="ops", folder_path="Shared/Skills", version_mode="latest"),
    ])
    system_prompt = BASE_PROMPT + "\n\n" + skills.prompt_section()

    def load_skill(name: str) -> str:
        """Load a skill's full instructions. `name` is `<bundle>/<skill>` from the Skills section."""
        return skills.read(name)   # invoked_by defaults to "model"

    # Bind load_skill to the model as a tool and use system_prompt as the system
    # message; the framework-specific wiring is up to you.
    ...
```

- `version_mode="pinned"` fixes a version; `version` is then required. `version_mode="latest"` takes the newest published version at each call and ignores `version`.
- `folder_path` is optional. Without it the bundle is looked up in the job's folder, taken from `UIPATH_FOLDER_PATH` or `UIPATH_FOLDER_KEY`.
- A bundle that cannot be resolved never fails the run. It is reported in `skills.failures` (a `BundleFailure` with the `ref`, a `reason` and a `detail`) and as an event on the `Skill bundles resolved` trace span, and the agent continues with the bundles that did resolve.
- `skills.names()` lists the resolved skills as `<bundle>/<skill>`. Names are qualified because two bundles may contain a skill with the same name; both stay available.
- `skills.bundles[i].version` is the resolved version; `prompt_section()` also shows it as `(bundle vN)`.
- `skills.prompt_section()` is a `## Skills` markdown section with one line per skill and its description, or an empty string when no bundle has a skill.
- `skills.read(name, path="SKILL.md")` returns a skill file as text. `path` is any file the skill lists (`Skill.files`), relative to the skill folder. Reading a `SKILL.md` records a `Skill load` span; pass `invoked_by="user"` when your own code reads it rather than a tool call made by the model.

### Files on Disk

| `destination` | Where bundles land | Who cleans up |
|---|---|---|
| omitted | a temp folder the set owns | you: call `skills.cleanup()` when the run ends |
| `destination=path` | `path`, **emptied first on every call** | the set leaves the folder in place; `cleanup()` only clears `root` |

`root` is laid out as `<root>/<bundle>/<skill>/...` next to `.uipath-skills-manifest.json`. Pass a `destination` you do not mind losing. `root` is `None` when no bundle resolved and after `cleanup()`; after `cleanup()` a `read()` of a listed skill raises `RuntimeError` (with no bundle resolved there is nothing to read and `read()` raises `KeyError`).

---

## Local Development

Keep a copy of the bundles in the project, one folder per bundle:

```
skills/
├── finance/
│   ├── bundle.json              # optional: {"version": "3"}
│   ├── invoice-triage/
│   │   ├── SKILL.md
│   │   └── reference.md
│   └── vendor-lookup/
│       └── SKILL.md
└── ops/
    └── runbook/
        └── SKILL.md
```

Set the source in `.env` (or in the shell) and run the agent as usual:

```bash
# .env
UIPATH_SKILLS_SOURCE=local
```

```shell
uipath run agent '{"message": "triage invoice 4711"}'
```

`UIPATH_SKILLS_SOURCE` selects where bundles come from:

| Value | Behaviour |
|-------|-----------|
| `local` | Copies `./skills/<bundle>/` (or `UIPATH_SKILLS_LOCAL_ROOT`); a folder holds one version, the one in `bundle.json` or `local` without it. |
| `orchestrator` | The Orchestrator Skills API. A placeholder until the API ships: every bundle is skipped as `source_unavailable` and the agent runs without skills. |

Today the default is `local`; `orchestrator` becomes the default once the Skills API ships. An unknown value falls back to `local` with a warning. A `pinned` reference to a version other than the folder's is loaded anyway, with a warning. The canonical description of the two variables is in [Environment Variables](./environment_variables.md#skill-bundles).

---

## Bindings

`uipath init` writes an empty `bindings.json`. Add one entry per `SkillBundleRef` yourself, or let your coding agent derive it from the code; this is the shape:

```json
{
  "resource": "skillBundle",
  "key": "finance.Shared/Skills",
  "value": {
    "name":        { "defaultValue": "finance",       "isExpression": false, "displayName": "Name" },
    "folderPath":  { "defaultValue": "Shared/Skills", "isExpression": false, "displayName": "Folder Path" },
    "versionMode": { "defaultValue": "pinned",        "isExpression": false, "displayName": "Version Mode" },
    "version":     { "defaultValue": "3",             "isExpression": false, "displayName": "Version" }
  },
  "metadata": { "ActivityName": "load_async", "BindingsVersion": "2.2", "DisplayLabel": "FullName" }
}
```

`ActivityName` names the SDK method that declares the reference; `load_async` covers both `load_async` and `load_all_async`.

`uipath pack` ships the file as `content/bindings_v2.json`. `uipath push` does not import skill-bundle bindings yet and reports each one as skipped, so the bundle must exist in Orchestrator before the solution is deployed.

---

## Overrides per Environment

At deploy time the binding can be overridden per environment. The job receives the override in `uipath.json`, and `load_all_async` applies it before fetching; no code change is needed:

```json
{ "runtime": { "internalArguments": { "resourceOverwrites": {
  "skillBundle.finance": { "name": "finance", "folderPath": "Prod/Skills", "versionMode": "pinned", "version": "7" }
} } } }
```

- An override replaces the whole binding, as for the other bindings: it must give `name`, `folderPath` and `versionMode`, plus `version` when `versionMode` is `pinned`. Nothing is taken from the declared binding.
- A key qualified with the design-time folder, `skillBundle.finance.Shared/Skills`, wins over the bare key `skillBundle.finance`.
- An override's `name` only changes which bundle is fetched. The agent still sees the bundle as `finance`: in `names()`, in the prompt section and on disk.
- An incomplete or invalid override (for instance `pinned` without a `version`) is skipped with a warning, and the declared binding is used.

Locally, put the same object into `__uipath/uipath.json` (the file `uipath run` reads runtime arguments from; create it if it does not exist) and run `uipath run` to test an override.

---

## Traces

Two spans describe skills in a job trace:

- `Skill bundles resolved`: one per `load_all_async` call (and per `load_async` call); none is emitted when no bundle is declared. It carries the source, the bundle and skill counts and the failures. Each resolved bundle is an event with its name, folder, version, version mode and skill count; each failure is a `skill.bundle.failed` event with its reason and detail.
- `Skill load - <bundle>/<skill>`: one per `read()` of a `SKILL.md`, with the bundle version, who asked for it (`skill.invoked_by`) and the size of the text.

Locally, `uipath run agent '{...}' --trace-file trace.jsonl` writes the spans to a JSON Lines file. See [Tracing](./traced.md).

---

## Limits

| Limit | Value |
|-------|-------|
| File size | 512 KiB per file |
| Bundle size | 24 MiB per bundle |
| Time budget | 20 s per bundle; after the first timeout the remaining bundles are skipped |

- A file over the size limit is skipped with a warning. A skill is skipped with a warning when its `SKILL.md` is over the size limit or not valid UTF-8.
- Hidden files and folders are skipped, and a folder without a `SKILL.md` is not a skill. The file name is matched in any case: a `skill.md` is accepted and written to the bundle folder as `SKILL.md`.
- A second reference to the same bundle name is reported as `invalid`; the first one is kept.
- Scripts inside a skill are copied with the rest of its files but never executed by the SDK.

---

## Other Calls

### One Bundle

```python
one = await sdk.skills.load_async(
    "finance", folder_path="Shared/Skills", version_mode="pinned", version="3"
)
```

`load_async` returns a `SkillSet` holding exactly one bundle. Unlike `load_all_async`, it raises when the bundle cannot be resolved: `SkillBundleLoadError`, whose `failure.reason` is one of `not_found`, `version_not_found`, `forbidden`, `invalid`, `too_large` or `source_unavailable`. An unknown `version_mode`, or `pinned` without a `version`, raises `ValueError` before anything is fetched.

### Synchronous Use

`load_all` and `load` are the synchronous twins of `load_all_async` and `load_async`. Prefer the `*_async` methods inside an agent. A synchronous method runs its async twin to completion; when an event loop is already running in the calling thread it runs on a worker thread and blocks the caller for up to 20 s per bundle.

---

## Reference

`SkillsService` is what `sdk.skills` returns. `SkillSet` is what `load_all_async` gives back; `SkillBundle`, `Skill` and `BundleFailure` are its parts; `SkillBundleLoadError` is what `load_async` raises.

::: uipath.platform.skills.SkillsService
    options:
      show_root_heading: true
      show_root_toc_entry: true
      heading_level: 3

::: uipath.platform.skills.SkillBundleRef
    options:
      show_root_heading: true
      show_root_toc_entry: true
      heading_level: 3

::: uipath.platform.skills.SkillSet
    options:
      show_root_heading: true
      show_root_toc_entry: true
      heading_level: 3

::: uipath.platform.skills.SkillBundle
    options:
      show_root_heading: true
      show_root_toc_entry: true
      heading_level: 3

::: uipath.platform.skills.Skill
    options:
      show_root_heading: true
      show_root_toc_entry: true
      heading_level: 3

::: uipath.platform.skills.BundleFailure
    options:
      show_root_heading: true
      show_root_toc_entry: true
      heading_level: 3

::: uipath.platform.skills.SkillBundleLoadError
    options:
      show_root_heading: true
      show_root_toc_entry: true
      heading_level: 3
