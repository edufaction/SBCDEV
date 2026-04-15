# SBC Properties Editor Spec

## 1. Scope

This document defines a `QTreeView`-based properties editor for SBCDEV, aligned with the current codebase in `src/`.

The objective is:

- keep the editor generic enough for several `Block` types,
- stay compatible with the current PySide6 architecture,
- preserve the existing split between generic property editing and specialized editors,
- avoid unnecessary framework complexity.

---

## 2. Product Goal

The properties editor is a right-side inspector/editor for one selected `Block`.

It must:

- display block properties grouped by UI logic,
- allow inline editing for a limited safe subset,
- expose structural and technical fields as read-only,
- handle contextual editing such as `container_paths`,
- work in graph, tree and thumbnail contexts,
- emit explicit change requests to the application layer.

It must not:

- replace specialized domain editors,
- become a full JSON editor,
- edit complex relations directly,
- absorb business validation rules.

---

## 3. Alignment With Current Code

### 3.1 Current domain model

Source: `src/domain/models.py`

The real `Block` fields relevant to the editor are:

- `id`
- `type`
- `profile`
- `name`
- `description`
- `prompt_ref`
- `prompt_generated`
- `comment`
- `shared`
- `domain`
- `access_mode`
- `provenance`
- `container_paths`
- `functional_name`
- `tags`
- `content`
- `contains`
- `inputs`

The spec must use those names, not abstract alternatives like `children` or `links`.

### 3.2 Existing editing split

The app already contains specialized editors:

- story shot editor:
  - `src/UI/Widgets/story_shot_workspace_widget.py`
- character quick editing in workspace toolbar:
  - `src/UI/Frames/workspaces/character_workspace_panel.py`
- project metadata editor:
  - `src/UI/Widgets/project_workspace_widget.py`

The treeview properties editor must complement those editors, not replace them.

### 3.3 Existing generic inspector

Current generic inspector:

- `src/UI/Widgets/block_property_widget.py`

Current behavior already established:

- read-only metadata display,
- contextual `container_paths` edition,
- read-only `content` preview.

The treeview editor should be the evolution of that role, not a detached framework.

---

## 4. Target Component

### 4.1 Main widget

Recommended public widget:

```python
class BlockPropertiesEditor(QWidget):
    ...
```

It contains:

- an optional `SearchBarWidget`
- a `QTreeView`
- a lightweight model
- a `QStyledItemDelegate`
- an optional footer/status row

### 4.2 Migration strategy

Near-term implementation may:

- introduce `BlockPropertiesEditor`,
- then replace `BlockPropertyWidget` usage progressively,
- or make `BlockPropertyWidget` a wrapper around the new treeview editor.

This avoids a brutal refactor of all current parents.

---

## 5. TreeView UI Structure

### 5.1 Hierarchy

The `QTreeView` displays:

- level 1: groups
- level 2: properties

Example:

```text
General
    Name                Ariane
    Type                container
    Profile             character
    Domain              characters

Text
    Description         Main protagonist...
    Comment             silhouette to refine
    Functional Name     hero_main

Prompt
    Prompt Ref          ...
    Prompt Generated    ...

Context
    Container Path      Principaux/Heros

Relations
    Contains            3
    Inputs              1

Content
    JSON Preview        { ... }
```

### 5.2 Columns

Use 2 columns only:

- `Property`
- `Value`

No third status column in phase 1.

### 5.3 Visual behavior

Groups should:

- be expandable/collapsible,
- be expanded by default,
- not be editable,
- use a stronger visual style than property rows.

Properties should:

- only edit in the `Value` column,
- show read-only values clearly,
- support multiline display when needed.

---

## 6. Recommended Architecture

## 6.1 View

```python
BlockPropertiesEditor(QWidget)
└── QTreeView
```

## 6.2 Model

For SBCDEV, start with:

```python
QStandardItemModel
```

not `QAbstractItemModel`.

Reason:

- faster to implement,
- easier to maintain,
- enough for grouped property rows,
- lower risk than a full custom tree model.

If the editor later needs virtualization, very large schemas, or heavy dynamic behavior, a custom model can be introduced then.

## 6.3 Delegate

Use:

```python
class PropertyValueDelegate(QStyledItemDelegate):
    ...
```

The delegate is only responsible for the `Value` column.

## 6.4 Lightweight configuration

Use lightweight specs instead of a heavy registry framework.

```python
@dataclass(frozen=True)
class PropertyFieldSpec:
    key: str
    label: str
    group: str
    editor_type: str
    editable: bool = False
    multiline: bool = False
    technical: bool = False
    choices: tuple[str, ...] = ()
```

```python
@dataclass(frozen=True)
class PropertyGroupSpec:
    id: str
    label: str
    order: int = 100
    expanded: bool = True
```

This is enough for SBCDEV phase 1.

---

## 7. Data Model for Rows

Each property row should carry metadata through item data roles.

Recommended internal row metadata:

```python
@dataclass
class PropertyRowState:
    key: str
    label: str
    editor_type: str
    editable: bool
    multiline: bool
    technical: bool
    container_scoped: bool = False
    choices: tuple[str, ...] = ()
```

Stored on the `QStandardItem` using custom Qt roles.

This avoids a separate property-node class in phase 1.

---

## 8. Supported Editor Types

Phase 1 editor types:

- `readonly`
- `string`
- `text`
- `tags`
- `path`
- `enum`

Mapping:

- `string` -> `QLineEdit`
- `text` -> `QPlainTextEdit`
- `tags` -> `QLineEdit`
- `path` -> `QLineEdit`
- `enum` -> `QComboBox`
- `readonly` -> no editor

No generic handler registry is required in phase 1.

A simple delegate switch on `editor_type` is sufficient.

---

## 9. Supported Property Keys

### 9.1 Phase 1 editable keys

Editable only when `block.is_editable()` is true:

- `name`
- `description`
- `functional_name`
- `comment`
- `tags`
- `prompt_ref`
- `prompt_generated`

### 9.2 Contextual editable key

Editable only with a valid selected container context:

- `container_path`

This row maps to:

- `block.container_paths[current_container_id]`

The UI key may be `container_path`, even though the domain storage is `container_paths[container_id]`.

### 9.3 Read-only keys

Always read-only in the generic editor:

- `id`
- `type`
- `profile`
- `domain`
- `access_mode`
- `provenance`
- `shared`
- `contains`
- `inputs`
- `content_json`

### 9.4 Deferred keys

Do not generically edit in phase 1:

- arbitrary `content.*`
- graph payload
- tree payload
- `inputs` relations
- `contains` relations

---

## 10. Property Groups

Recommended group structure:

### `general`

- `id`
- `name`
- `type`
- `profile`
- `domain`
- `access_mode`
- `shared`
- `source`

### `text`

- `description`
- `comment`
- `functional_name`
- `tags`

### `prompt`

- `prompt_ref`
- `prompt_generated`

### `context`

- `container_path`

### `relations`

- `contains`
- `inputs`

### `content`

- `content_json`

These groups are UI groups.
They must not mirror raw Python structure mechanically.

---

## 11. Value Resolution Rules

### 11.1 Direct field resolution

For top-level fields, read directly from `Block`.

Examples:

- `block.name`
- `block.comment`
- `block.functional_name`

### 11.2 Computed display fields

Some rows are computed for display:

- `source` from `block.provenance`
- `contains` as summary text or count
- `inputs` as summary text or count
- `content_json` as pretty-printed JSON

### 11.3 Contextual path field

`container_path` is resolved using:

- selected `container_id`
- `block.container_paths.get(container_id, "")`

If no valid `container_id` is provided:

- the row remains visible,
- the value is empty,
- the row is read-only.

---

## 12. Read-Only Policy

### 12.1 Linked blocks

When `block.is_link()` is true:

- all editable rows become read-only,
- `container_path` becomes read-only,
- the editor should expose a visible read-only hint.

### 12.2 Global read-only mode

Optional support:

```python
def set_read_only(self, value: bool) -> None: ...
```

This mode forces the whole editor to non-editable state.

### 12.3 Specialized ownership

If a block belongs to a workflow already edited by a dedicated widget, the generic editor may still display overlapping values, but the application should avoid contradictory simultaneous editing flows in the same screen.

---

## 13. Model and Delegate Behavior

### 13.1 Model responsibilities

The model must:

- build grouped rows from the current block,
- expose 2 columns,
- mark group rows non-editable,
- mark only the `Value` column editable when allowed,
- refresh when a new block is selected.

### 13.2 Delegate responsibilities

The delegate must:

- create the correct editor widget for the row,
- set editor data from the row value,
- read editor value back,
- emit the normalized value to the editor widget logic.

### 13.3 Widget responsibilities

The widget must:

- manage current block and container context,
- build the tree model from field specs,
- collect edits into explicit payloads,
- emit change requests upward.

It must not:

- persist directly,
- enforce business rules,
- mutate unrelated domain structures.

---

## 14. Signals

Recommended signals:

```python
property_change_requested = Signal(dict)
relative_path_changed = Signal(str, str, str)
```

Recommended payload for generic changes:

```python
{
    "block_id": "...",
    "key": "name",
    "value": "Ariane"
}
```

For tags:

```python
{
    "block_id": "...",
    "key": "tags",
    "value": ["hero", "lead"]
}
```

For `container_path`, keep a dedicated compatibility signal:

```python
relative_path_changed(block_id, container_id, relative_path)
```

This matches the existing application flow and avoids mixing path context into every generic payload.

---

## 15. Filtering

The editor may provide a filter line.

Filter scope:

- group label
- property label

Filtering is UI-only.

It must not:

- alter the selected block,
- alter property ordering,
- mutate the underlying model permanently.

`QSortFilterProxyModel` is acceptable if needed, but a simple hide/show strategy is enough in phase 1.

---

## 16. Integration With Existing App

### 16.1 Expected parents

The editor must be embeddable in:

- graph workspace panels,
- tree windows,
- thumbnail list windows.

### 16.2 Existing flows to preserve

The editor must preserve:

- tree selection -> inspector refresh
- graph selection -> inspector refresh
- contextual path editing using container context

### 16.3 Specialized editors remain valid

Specialized widgets keep ownership of:

- rich story shot editing
- quick character editing
- project metadata editing

The treeview editor is the generic inspector, not the whole editing system.

---

## 17. Implementation Plan

### Phase 1

Create `BlockPropertiesEditor` with:

- `QTreeView`
- `QStandardItemModel`
- lightweight field/group specs
- read-only metadata rows
- editable rows for:
  - `name`
  - `description`
  - `functional_name`
  - `comment`
  - `tags`
  - `prompt_ref`
  - `prompt_generated`
  - `container_path`

### Phase 2

Integrate into one parent context first:

- `CharacterWorkspacePanel` or `FreeTreeWindow`

### Phase 3

Add generic `property_change_requested` handling in the application layer.

### Phase 4

Replace the old form-based inspector progressively where it is beneficial.

### Phase 5

Only if the property matrix becomes much larger:

- extract a richer schema layer,
- consider a custom model,
- consider a true handler registry.

---

## 18. Non-Goals

This spec does not include:

- full arbitrary nested `content.*` edition,
- input relation editing,
- child relation editing,
- generic graph editing,
- generic tree editing,
- undo/redo framework,
- a universal editor replacing every specialized widget.

---

## 19. Final Direction

The correct treeview solution for SBCDEV is:

- a pragmatic `QTreeView` inspector,
- based on `QStandardItemModel`,
- with a small `QStyledItemDelegate`,
- editing a narrow safe subset of real `Block` fields,
- preserving the current split between generic inspector and specialized editors,
- and fitting the current architecture instead of replacing it wholesale.
