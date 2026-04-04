# SBCDEV

SBCDEV is a modular desktop application (Python + PySide6) for organizing creative assets and structured blocks used in AI-assisted film and comic (BD) preproduction.

At this stage, the app is a **repository and storyboard organization tool**.
It does **not** generate images, videos, or audio.

## Key Goals

- Keep UI architecture modular, reusable, and maintainable
- Organize media assets (images, videos, prompts) through block/container structures
- Support creative workflows with consistent tree, thumbnail, inspector, and workspace patterns
- Provide a stable foundation for future AI-assisted authoring features

## Current Scope

- Multi-workspace desktop shell
- Project tree + free tree workflows
- Thumbnail list/grid exploration
- Media preview and block inspection panels
- Drag & drop import flows
- Internal library branch (`INTERNALLIB`)
- Mounted external library metadata support (`kind = "LIB"`, phase A storage)

## Repository Structure

- `src/` — application source code
  - `UI/` — windows, reusable widgets, theme, icons
  - `application/` — use cases and orchestration
  - `domain/` — domain models and rules
  - `infrastructure/` — persistence and storage services
  - `services/` — application-level services
- `tests/` — automated test suite
- `docs/` — UI/domain/widget reference documentation
- `BuildAPP/` — macOS `.app` packaging setup (`py2app`)
- `DataProject/` — project seed/sample data files

## Requirements

- Python `>= 3.11` (currently tested with Python `3.14`)
- `PySide6`
- `platformdirs`

## Quick Start (Dev)

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install PySide6 platformdirs pytest py2app
```

Run the app:

```bash
cd src
../.venv/bin/python main.py
```

## Run Tests

From the repository root:

```bash
.venv/bin/pytest -q
```

`pyproject.toml` is configured so tests resolve imports from `src/` automatically.

## Build macOS App

From the repository root:

```bash
python BuildAPP/setup.py py2app
```

The generated app bundle is produced in `dist/` (default `py2app` behavior).

## Storage Notes (Current Architecture)

- Workspace block data is stored in:
  - `workspaces/<workspace_key>/blocks.json`
- Workspace/project metadata (including mounted libraries) is stored in:
  - `project.json`
- Mounted libraries are tracked through `mounted_libraries` entries.

## Documentation

- `docs/SBC_UI_guidelines.md`
- `docs/SBC_Widget_catalog.md`
- `docs/SBC_domain_views.md`
- `AGENTS.md` (project engineering and UI architecture rules)

## License

See [LICENSE](LICENSE).
