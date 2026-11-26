# Skills

A skill bundle is a versioned group of skills. Each skill is a folder with a `SKILL.md` whose YAML frontmatter has a `name` and a `description`, plus any reference files or scripts the skill needs. Bundles are authored and imported into an Orchestrator folder with the `uip` CLI (UiPath's coding-agent CLI, separate from the `uipath` Python CLI used on this page) and bound to a coded agent like any other resource.

`sdk.skills` resolves the bundles an agent declares, downloads them at run start and exposes their skills to the agent's code: the skill descriptions go into the system prompt, and the full `SKILL.md` is read on demand.

Preview Feature

The Orchestrator Skills API is not available yet. Until it ships, `UIPATH_SKILLS_SOURCE` defaults to `local` and bundles are read from `./skills` in the project; see [Local development](#local-development). `orchestrator` is a placeholder today: it skips every bundle as `source_unavailable`. It becomes the default once the API is live.

______________________________________________________________________

## Declare and Load Bundles

Call `load_all_async` once when the job starts: in your graph factory or your first node, never at import time.

```
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

| `destination`      | Where bundles land                                                                         | Who cleans up                                                                                         |
| ------------------ | ------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| omitted            | a temp folder the set owns                                                                 | you: call `skills.cleanup()` when the run ends; it removes the folder                                 |
| `destination=path` | `path`: missing, empty, or holding only an earlier load's bundles, which are removed first | `cleanup()` removes the bundle folders and the manifest it wrote; `path` and anything else in it stay |

`root` is laid out as `<root>/<bundle>/<skill>/...` next to `.uipath-skills-manifest.json`. The SDK never removes a file it did not write. A `destination` that holds only what an earlier load wrote there, as its manifest lists, is cleared before the new bundles are written, so a second run into the same folder works even if the first one never called `cleanup()`. When it holds anything else, or is a file or a symbolic link, every bundle fails as `invalid` and the folder is left as it is. With no bundles bound, an earlier load's bundles are cleared too. Pass a `destination` only when something reads the files by path, such as the workspace of an advanced (deepagents) agent; the `read()` path works with the default temp folder. `root` is `None` when no bundle resolved and after `cleanup()`; after `cleanup()` a `read()` of a listed skill raises `RuntimeError` (with no bundle resolved there is nothing to read and `read()` raises `KeyError`).

______________________________________________________________________

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

```
# .env
UIPATH_SKILLS_SOURCE=local
```

```
uipath run agent '{"message": "triage invoice 4711"}'
```

`UIPATH_SKILLS_SOURCE` selects where bundles come from:

| Value          | Behaviour                                                                                                                                          |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `local`        | Copies `./skills/<bundle>/` (or `UIPATH_SKILLS_LOCAL_ROOT`); a folder holds one version, the one in `bundle.json` or `local` without it.           |
| `orchestrator` | The Orchestrator Skills API. A placeholder until the API ships: every bundle is skipped as `source_unavailable` and the agent runs without skills. |

Today the default is `local`; `orchestrator` becomes the default once the Skills API ships. An unknown value falls back to `local` with a warning. A `pinned` reference to a version other than the folder's is loaded anyway, with a warning. The canonical description of the two variables is in [Environment Variables](https://uipath.github.io/uipath-python/core/environment_variables/#skill-bundles).

______________________________________________________________________

## Bindings

`uipath init` writes an empty `bindings.json`. Add one entry per `SkillBundleRef` yourself, or let your coding agent derive it from the code; this is the shape:

```
{
  "resource": "skillBundle",
  "key": "finance.Shared/Skills",
  "value": {
    "name":        { "defaultValue": "finance",       "isExpression": false, "displayName": "Name" },
    "folderPath":  { "defaultValue": "Shared/Skills", "isExpression": false, "displayName": "Folder Path" },
    "versionMode": { "defaultValue": "pinned",        "isExpression": false, "displayName": "Version Mode" },
    "version":     { "defaultValue": "3",             "isExpression": false, "displayName": "Version" }
  },
  "metadata": { "ActivityName": "load_all_async", "BindingsVersion": "2.2", "DisplayLabel": "FullName" }
}
```

`ActivityName` names the SDK method that declares the reference, `load_all_async`.

`uipath pack` ships the file as `content/bindings_v2.json`. `uipath push` does not import skill-bundle bindings yet and reports each one as skipped, so the bundle must exist in Orchestrator before the solution is deployed.

______________________________________________________________________

## Overrides per Environment

At deploy time the binding can be overridden per environment. The job receives the override in `uipath.json`, and `load_all_async` applies it before fetching; no code change is needed:

```
{ "runtime": { "internalArguments": { "resourceOverwrites": {
  "skillBundle.finance": { "name": "finance", "folderPath": "Prod/Skills", "versionMode": "pinned", "version": "7" }
} } } }
```

- An override replaces the whole binding, as for the other bindings: it must give `name`, `folderPath` and `versionMode`, plus `version` when `versionMode` is `pinned`. Nothing is taken from the declared binding.
- A key qualified with the design-time folder, `skillBundle.finance.Shared/Skills`, wins over the bare key `skillBundle.finance`.
- An override's `name` only changes which bundle is fetched. The agent still sees the bundle as `finance`: in `names()`, in the prompt section and on disk.
- An incomplete or invalid override (for instance `pinned` without a `version`) fails that bundle as `invalid`, with the reason in the failure's `detail`; the agent runs without it. The declared binding is not used instead, so a broken pin never loads a different version.

Locally, put the same object into `__uipath/uipath.json` (the file `uipath run` reads runtime arguments from; create it if it does not exist) and run `uipath run` to test an override.

______________________________________________________________________

## Traces

Two spans describe skills in a job trace:

- `Skill bundles resolved`: one per `load_all_async` call; none is emitted when no bundle is declared. It carries the source, the bundle and skill counts and the failures. Each resolved bundle is an event with its name, folder, version, version mode and skill count; each failure is a `skill.bundle.failed` event with its reason and detail.
- `Skill load - <bundle>/<skill>`: one per `read()` of a `SKILL.md`, with the bundle version, who asked for it (`skill.invoked_by`) and the size of the text.

Locally, `uipath run agent '{...}' --trace-file trace.jsonl` writes the spans to a JSON Lines file. See [Tracing](https://uipath.github.io/uipath-python/core/traced/index.md).

______________________________________________________________________

## Limits

| Limit       | Value                                                                                                               |
| ----------- | ------------------------------------------------------------------------------------------------------------------- |
| File size   | 512 KiB per file                                                                                                    |
| Bundle size | 24 MiB per bundle                                                                                                   |
| Time budget | 20 s per bundle; after the first timeout the remaining bundles are skipped. The `local` source is not stopped by it |
| Description | 1024 characters; a longer `description` is cut, one that is not a string is left empty                              |

- A file over the size limit is skipped with a warning. A skill is skipped with a warning when its `SKILL.md` is over the size limit or not valid UTF-8.
- Hidden files and folders are skipped, and a folder without a `SKILL.md` is not a skill. The `local` source does not follow symbolic links: a linked file or skill folder is skipped, and a linked bundle folder is reported as `invalid`. The file name is matched in any case: a `skill.md` is accepted and written to the bundle folder as `SKILL.md`.
- A second reference to the same bundle name is reported as `invalid`; the first one is kept.
- Scripts inside a skill are copied with the rest of its files but never executed by the SDK.

______________________________________________________________________

## Synchronous Use

`load_all` is the synchronous twin of `load_all_async`. Prefer `load_all_async` inside an agent. `load_all` runs it to completion; when an event loop is already running in the calling thread it runs on a worker thread and blocks the caller for up to 20 s per bundle.

______________________________________________________________________

## Reference

`SkillsService` is what `sdk.skills` returns. `SkillSet` is what `load_all_async` gives back; `SkillBundle`, `Skill` and `BundleFailure` are its parts.

### uipath.platform.skills.SkillsService

Resolve the skill bundles an agent is bound to and expose their skills to agent code.

Each bundle is `pinned` to a version or follows the `latest` one. Deploy-time overrides (`skillBundle.<name>` resource overwrites) are applied before fetching. A bundle that cannot be resolved is reported, never raised, by `load_all`.

Where the bundles come from is chosen by `UIPATH_SKILLS_SOURCE`: a local folder (the default) or the Orchestrator Skills API, a placeholder until that API ships. The `*_async` methods are preferred; each synchronous twin runs its async method to completion, on a worker thread when an event loop is already running in the calling thread.

#### __init__

```
__init__(config, execution_context)
```

Create the service.

Parameters:

| Name                | Type                     | Description                                   | Default    |
| ------------------- | ------------------------ | --------------------------------------------- | ---------- |
| `config`            | `UiPathApiConfig`        | Base URL and access token for the Skills API. | *required* |
| `execution_context` | `UiPathExecutionContext` | The job's execution context.                  | *required* |

#### load_all

```
load_all(refs, *, destination=None, source=None)
```

Resolve and download `refs`; see `load_all_async`.

`load_all_async` is preferred. This runs it to completion, on a worker thread when an event loop is already running in this thread; the resource-overwrite context of the calling thread still applies. Called from a running loop, it blocks the caller for up to the per-bundle budget per bundle.

Parameters:

| Name          | Type                       | Description                        | Default                                                                                                     |
| ------------- | -------------------------- | ---------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `refs`        | `Sequence[SkillBundleRef]` | The bundles the agent is bound to. | *required*                                                                                                  |
| `destination` | \`Path                     | None\`                             | The folder to write into, not owned by the set; see load_all_async. By default an owned temp folder.        |
| `source`      | \`SkillBundleSource        | None\`                             | Where bundles come from; by default the one UIPATH_SKILLS_SOURCE selects. It is closed before this returns. |

Returns:

| Type       | Description                            |
| ---------- | -------------------------------------- |
| `SkillSet` | The resolved bundles and the failures. |

#### load_all_async

```
load_all_async(refs, *, destination=None, source=None)
```

Resolve `refs` in order, write each bundle under `<root>/<name>/` and describe the set.

The run's `skillBundle.<name>` resource overwrites are applied to each reference first; an invalid one fails its bundle as `invalid` rather than falling back to the declared reference. Every bundle gets `BUNDLE_RESOLVE_TIMEOUT_SECONDS` of wall clock; after the first timeout the remaining bundles are skipped without being tried. A bundle that fails is reported in `SkillSet.failures` and as a `skill.bundle.failed` event on the `Skill bundles resolved` span; nothing here fails the run, though cancellation still propagates. Nothing the SDK did not write is ever removed. After an error, cancellation included, the bundle folders written so far are removed again, and an owned temp root is removed whole.

Parameters:

| Name          | Type                       | Description                                                                                                                                                                       | Default                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------------- | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `refs`        | `Sequence[SkillBundleRef]` | The bundles the agent is bound to. With none, nothing is fetched, no span is emitted and the set has no root; a destination that holds only an earlier load's bundles is cleared. | *required*                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `destination` | \`Path                     | None\`                                                                                                                                                                            | The folder to write into, which the set does not own. It may be missing, empty, or hold only what an earlier load wrote there, as its manifest lists; that is removed first. When it holds anything else, or is a file or a symbolic link, every bundle fails as invalid and nothing in it changes. SkillSet.cleanup removes only what this call wrote there. By default a temp folder is created that the set owns and cleanup removes. |
| `source`      | \`SkillBundleSource        | None\`                                                                                                                                                                            | Where bundles come from; by default the one UIPATH_SKILLS_SOURCE selects. It is closed before this returns.                                                                                                                                                                                                                                                                                                                              |

Returns:

| Type       | Description                                                           |
| ---------- | --------------------------------------------------------------------- |
| `SkillSet` | The resolved bundles and the failures. root is set only when at       |
| `SkillSet` | least one bundle resolved; an owned temp folder is removed otherwise. |

### uipath.platform.skills.SkillBundleRef

One bound skill bundle: what the agent asks the Skills API for.

#### lookup_name

```
lookup_name
```

The bundle to fetch from Orchestrator or the local folder.

`name` stays the bundle's identity for the agent (bundle folder, prompt label, manifest); a deploy-time binding only changes this.

#### source_name

```
source_name = Field(default=None, alias='sourceName')
```

The deploy-time bundle name, when a binding points `name` elsewhere.

### uipath.platform.skills.SkillSet

The skill bundles resolved for one run, and the bundles that could not be.

`save`/`load` keep the set as `.uipath-skills-manifest.json` inside the folder the bundles were written to; `root` and `owns_root` never land in that manifest.

#### owns_root

```
owns_root = Field(default=False, exclude=True, repr=False)
```

Whether `cleanup` may remove `root`: only for a temp folder this set created.

#### root

```
root = Field(default=None, exclude=True)
```

Folder the bundles were written to; `None` before materializing and after `cleanup`.

#### source

```
source
```

Where the bundles came from, for instance `local` or `orchestrator`.

#### cleanup

```
cleanup()
```

Remove what this set wrote to disk.

An owned temp root is removed whole. In a caller's `destination` only what `load_all` wrote is removed, the bundle folders and the manifest, so the folder can be loaded into again; the folder and anything else in it stay. A set read back with `load` removes nothing.

Afterwards the set has no `root`, so `read` raises `RuntimeError` and a second `cleanup` does nothing. What cannot be removed is logged as a warning.

#### find

```
find(qualified_name)
```

The bundle and skill a qualified `<bundle>/<skill>` name points to.

Parameters:

| Name             | Type  | Description                 | Default    |
| ---------------- | ----- | --------------------------- | ---------- |
| `qualified_name` | `str` | A name as names returns it. | *required* |

Returns:

| Type                        | Description |
| --------------------------- | ----------- |
| \`tuple[SkillBundle, Skill] | None\`      |

#### load

```
load(skills_dir)
```

Read the manifest from `skills_dir`.

The set comes back with `root=skills_dir` and `owns_root=False`, so `read` works right away and `cleanup` leaves the folder alone. A `root` or `owns_root` key inside the file is ignored; `save` never writes them.

Parameters:

| Name         | Type   | Description                             | Default    |
| ------------ | ------ | --------------------------------------- | ---------- |
| `skills_dir` | `Path` | The folder the bundles were written to. | *required* |

Returns:

| Type       | Description |
| ---------- | ----------- |
| \`SkillSet | None\`      |

Raises:

| Type         | Description                                                                                                      |
| ------------ | ---------------------------------------------------------------------------------------------------------------- |
| `ValueError` | If the manifest is not valid JSON (json.JSONDecodeError) or does not match the model (pydantic.ValidationError). |

#### names

```
names()
```

Qualified `<bundle>/<skill>` names in bundle order (D20).

#### prompt_section

```
prompt_section()
```

`## Skills` markdown listing every skill with its description, or `""` when no bundle has a skill.

#### read

```
read(
    qualified_name,
    path=SKILL_FILE_NAME,
    *,
    invoked_by="model",
)
```

A skill file's text. `SKILL.md` is read inside a `Skill load` span.

The span is current during the read, and a read that raises leaves it with an error status.

Parameters:

| Name             | Type        | Description                                                                                                | Default           |
| ---------------- | ----------- | ---------------------------------------------------------------------------------------------------------- | ----------------- |
| `qualified_name` | `str`       | The <bundle>/<skill> name.                                                                                 | *required*        |
| `path`           | `str`       | A file the skill lists, in the POSIX form Skill.files uses, relative to the skill folder.                  | `SKILL_FILE_NAME` |
| `invoked_by`     | `InvokedBy` | Who asked for the file, for the span: "model" for a tool call, "user" when the agent's own code loaded it. | `'model'`         |

Returns:

| Type  | Description                                                         |
| ----- | ------------------------------------------------------------------- |
| `str` | The file text decoded as UTF-8, a BOM dropped. When the file is not |
| `str` | valid UTF-8 a warning is logged and undecodable bytes are replaced. |

Raises:

| Type           | Description                                        |
| -------------- | -------------------------------------------------- |
| `KeyError`     | Unknown skill, or a file the skill does not list.  |
| `RuntimeError` | The set has no root: manifest only, or cleaned up. |

#### save

```
save(skills_dir)
```

Write the manifest into `skills_dir`, creating the folder if needed.

Parameters:

| Name         | Type   | Description                             | Default    |
| ------------ | ------ | --------------------------------------- | ---------- |
| `skills_dir` | `Path` | The folder the bundles were written to. | *required* |

#### skill_at

```
skill_at(virtual_path)
```

The bundle and skill whose `SKILL.md` sits at `virtual_path`.

Parameters:

| Name           | Type  | Description                                                                                                            | Default    |
| -------------- | ----- | ---------------------------------------------------------------------------------------------------------------------- | ---------- |
| `virtual_path` | `str` | A path in the agent's virtual filesystem; a relative path is read from the root, as a virtual filesystem backend does. | *required* |

Returns:

| Type                        | Description |
| --------------------------- | ----------- |
| \`tuple[SkillBundle, Skill] | None\`      |
| \`tuple[SkillBundle, Skill] | None\`      |

### uipath.platform.skills.SkillBundle

A bundle a source resolved to a concrete version and wrote to disk.

#### label

```
label
```

Display name with the resolved version, `<name> v<version>`.

#### virtual_root

```
virtual_root
```

The bundle folder as the agent sees it, `/skills/<name>/`.

### uipath.platform.skills.Skill

One skill a source wrote into its bundle folder.

`name` equals the skill's folder name inside the bundle. `name` and every entry of `files` are checked to stay inside that folder; `SkillSet.read` relies on it.

#### files

```
files = Field(default_factory=list)
```

Paths relative to the skill folder in POSIX form, `SKILL.md` first.

### uipath.platform.skills.BundleFailure

A bound bundle that could not be materialized, and why.
