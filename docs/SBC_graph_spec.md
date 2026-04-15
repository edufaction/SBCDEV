# SBC Graph Specification (Aligned with SBCDEV)

## 1. Scope

This document defines the graph model and UI behavior for SBCDEV, aligned with the current codebase and storage rules.

Goals:
- keep domain as source of truth
- keep graph UI as a projection
- preserve compatibility with current `Block` model, storage layout, and workspaces

---

## 2. Gap Analysis (what was missing in previous spec)

Previous version was not fully aligned with the app. Main gaps were:

1. Domain mismatch:
- previous spec used `Block + Link`
- SBCDEV uses a single `Block` model with:
  - `inputs` (`InputConnection`) for port-based links
  - `graph` (`FreeGraph`) for visual nodes/edges inside a container

2. Graph scope mismatch:
- graph is not global
- graph is embedded per container block (`container.graph`)

3. Persistence mismatch:
- previous spec suggested one flat JSON
- SBCDEV stores:
  - `project.json`
  - `ui_state.json`
  - `workspaces/<workspace_key>/blocks.json`

4. Workspace constraints missing:
- graph must respect workspace roots (`PROJET`, `Characters Root`, `Story Root`, `Library Root`, `INTERNALLIB`)
- no final block directly under absolute root

5. Visual sizing rules missing:
- no explicit GraphBlock sizing per content type
- required for consistent UI

---

## 3. Domain Model (actual SBCDEV)

Source: `src/domain/models.py`.

### 3.1 Block (single business entity)

Key fields used by graph:
- `id: str`
- `type: BlockType` (`empty`, `container`, `image`, `video`, `audio`, `text`, `prompt`)
- `profile: str` (includes `preset` for compact textual blocks)
- `name: str`
- `access_mode: BlockAccessMode` (`owned` or `link`)
- `provenance: dict`
- `contains: list[str]`
- `inputs: list[InputConnection]`
- `tree: FreeTree | None`
- `graph: FreeGraph | None`

### 3.2 InputConnection (logical link)

- `source_block_id: str`
- `port: PortType` (`in`, `top`, `bottom`, `out`)
- `name: str`
- `enabled: bool`
- `order: int`
- `metadata: dict`

### 3.3 FreeGraph (visual projection per container)

- `nodes: dict[str, FreeGraphNode]`
- `edges: dict[str, FreeGraphEdge]`

Node:
- `id`
- `block_id`
- `x`, `y`

Edge:
- `id`
- `source_node_id`
- `target_node_id`
- `label`

---

## 4. UI Projection Objects

### 4.1 GraphBlock

UI node bound to one domain `Block`.

Constraints:
- no business logic in UI node
- all updates go through controller/services
- must reflect block `access_mode` (read-only visuals for linked blocks)

### 4.2 GraphLink

UI connection bound to domain relation:
- visual edge from `FreeGraphEdge`
- semantic relation from `inputs` on target block

Important:
- a visual edge alone is not enough for business semantics
- port semantics must come from `InputConnection`

---

## 5. Graph Boundary Rules

1. Graph exists only for container blocks.
2. A graph node can be added only if `block_id in container.contains`.
3. Deleting a node removes connected graph edges.
4. Domain objects remain independent from widget internals.

These rules match current `FreeGraphService` and `UseCaseService`.

---

## 6. Port Model and Connection Rules

Port types:
- `OUT`
- `IN`
- `TOP`
- `BOTTOM`

Port reservation (business semantics):
- `TOP` is reserved for `preset` blocks.
- `BOTTOM` is reserved for `prompt` blocks.

Allowed:
- `OUT -> IN`
- `OUT -> TOP`
- `OUT -> BOTTOM`

Forbidden:
- `IN -> IN`
- `TOP -> TOP`
- `BOTTOM -> BOTTOM`
- `* -> OUT` (except source origin semantics)

Multiplicity target:
- `OUT`: multiple
- `IN`: multiple
- `TOP`: single
- `BOTTOM`: single

Content constraints by target port:
- target `TOP` accepts only blocks with `profile == "preset"` (or equivalent preset semantic profile).
- target `BOTTOM` accepts only blocks with `type == "prompt"` or `profile == "prompt"`.

Validation must be centralized in controller/service layer (not in widget-only code).

---

## 7. Visual Layout and Node Sizing

### 7.1 Port layout (stable convention)

- left side center: `IN`
-  top side center : `TOP`
- right side center : `OUT`
- bottom side center: `BOTTOM`

### 7.1.b Connector rendering and colors (required)

Connectors must be rendered as circular handles placed on GraphBlock borders.

Color mapping:
- `IN`: green
- `OUT`: red
- `TOP`: blue
- `BOTTOM`: yellow

Each connector must remain visually distinct in default, hover, and active drag states.

### 7.2 GraphBlock size policy (required)

Define base media size:
- `GRAPH_BLOCK_MEDIA_SIZE = (320, 180)`  # width, height

For media-like blocks:
- `type in {image, video, audio}` -> use `GRAPH_BLOCK_MEDIA_SIZE`

For compact textual blocks:
- `type in {prompt, text}` OR `profile == "preset"` ->
  - width = media width / 2
  - height = media height / 2
  - default compact size: `(160, 90)`

Rule required by product:
- prompt/preset/text blocks are 2x smaller in width and 2x smaller in height than image/video/audio blocks.

### 7.3 GraphBlock content widget (required)

GraphBlock must display the block thumbnail widget (same visual component family as thumbnail preview used elsewhere in app).

Expected behavior:
- if media preview is available, show block thumbnail
- if no media preview is available, show consistent empty-state thumbnail placeholder
- linked/read-only blocks keep same thumbnail rendering with read-only visual hint

---

## 8. Persistence Contract (SBCDEV)

### 8.1 Files

- `project.json`: metadata + mounted libraries
- `ui_state.json`: transient UI state
- `workspaces/<workspace_key>/blocks.json`: partitioned blocks

### 8.2 Serialized graph data

`Block` payload includes:
- `inputs`
- `graph.nodes`
- `graph.edges`

No raw widget dump is persisted.

### 8.3 Viewport state per graph (required)

For each container graph, UI viewport state must be persisted and restored:
- block positions (`x`, `y`) for all graph nodes
- zoom level
- focus/center position (graph camera center)

Persistence granularity:
- one viewport state per container graph
- no global shared zoom across containers

---

## 9. Mounted Libraries and Read-only Behavior

Mounted libraries are normalized in `project.json` with:
- `id`
- `kind = "LIB"`
- `path` (absolute)
- `label`
- `enabled`
- `read_only`
- `mounted_at` (optional)

Graph/inspector UI must surface read-only state when `access_mode == "link"` and prevent forbidden edits.

---

## 10. Controller Responsibilities

Graph controller (or equivalent orchestration layer) must:

1. load blocks and build graph projection per container
2. apply connection validation rules
3. sync UI actions to domain through services
4. persist through storage services
5. never bypass domain/service validation

Suggested service integration:
- `UseCaseService`
- `FreeGraphService`
- `BlockService`
- storage services in `infrastructure/storage`

Default graph bootstrap:
- if selected container has no `graph`, controller/service must create a default empty graph payload for this container.
- bootstrap should then place all blocks contained in this container into graph nodes (default auto-layout strategy).
- each container owns its own graph; never share one graph across containers.

Interaction model (required):
- link creation starts with click+drag from a source connector
- a connection is created only when dropped on a compatible target connector
- dropping outside a compatible connector cancels link creation
- during drag-over, target connector/node must display explicit visual feedback to show valid selection

Viewport interaction model (required):
- use standard graph UX interactions for focus navigation (pan/move focus)
- support zoom in
- support zoom out
- support reset zoom / fit-to-view behavior
- after reload, viewport should restore persisted zoom and focus for the selected container graph

---

## 11. Acceptance Criteria

1. Graph is always container-scoped.
2. Nodes map to existing contained blocks only.
3. Connection rules are enforced (`IN` multi allowed).
4. `TOP` accepts presets only, `BOTTOM` accepts prompts only.
5. If selected container has no graph, a default graph is created and initialized from its contained blocks.
6. Reload from storage restores positions and links consistently.
7. Read-only linked blocks are correctly protected.
8. Visual sizing rule is respected:
- image/video/audio = media size
- prompt/preset/text = half media size on both axes
9. Connectors are circular and color-coded: `IN` green, `OUT` red, `TOP` blue, `BOTTOM` yellow.
10. Link interaction works with click+drag and drop on connector; invalid drop does not create connection.
11. Drag-over feedback clearly indicates selectable/compatible target.
12. GraphBlock displays block thumbnail widget (or defined placeholder).
13. Positions and zoom are persisted per container graph and restored on reload.
14. Standard viewport interactions are available (focus pan, zoom in, zoom out, reset/fit view).
15. Domain remains source of truth.

---

## 12. Implementation Checklist

- [ ] Graph widget enforces size policy from section 7.2
- [ ] Graph widget enforces connection validation from section 6
- [ ] Domain sync for edge semantics (`inputs`) is complete
- [ ] Read-only linked block behavior is enforced in graph interactions
- [ ] Circular connector rendering implemented with port color mapping
- [ ] Click+drag/drop link creation implemented on connectors
- [ ] Drag-over visual feedback implemented for valid/invalid targets
- [ ] GraphBlock embeds block thumbnail widget (with placeholder fallback)
- [ ] Per-container graph viewport persistence implemented (node positions + zoom + focus center)
- [ ] Standard viewport interactions implemented (pan/focus, zoom in, zoom out, reset/fit)
- [ ] Manual UI validation added (recommended under `tests/manual_ui/`)
