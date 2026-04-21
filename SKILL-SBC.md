---
name: SBC
description: >
  Skill de référence condensé pour SBC (StoryBoard Crafter) — atelier desktop
  Python / PySide6 pour organiser et produire des films IA personnels.
  Utiliser ce skill pour générer du code Python/PySide6 cohérent avec
  l'architecture existante : modèle Block, enums, accesseurs typés, signaux Qt,
  UseCaseService, Clone/Link, workspaces.
  Déclencher aussi pour : bloc, personnage, lieu, shot, asset, prompt,
  librairie, clone, link, provenance, workspace, génération IA.
  Pour la spécification complète, les dettes techniques et l'architecture cible
  → voir SBC-ARCHITECTURE.md
---

# SBC — Skill de référence

Application desktop **Python / PySide6**, stockage **JSON + filesystem local**, macOS et Windows.
Code source dans `/src`. **Tout est Block** — personnage, shot, image, prompt, audio.
**Légende :** ✅ implémenté · 🔧 planifié

---

## Modèle de données — Block ✅

```python
# src/domain/models.py
@dataclass(slots=True)
class Block:
    id: str                          # "blk_<uuid_hex12>" ou ID racine hardcodé
    type: BlockType                  # Nature physique
    profile: str                     # Rôle métier (type × usage)
    name: str
    description: str = ""
    prompt_ref: str = ""
    prompt_generated: str = ""
    comment: str = ""
    shared: bool = False             # ⚠️ DETTE — champ mort, ne pas utiliser
    domain: BlockDomain = BlockDomain.LIB
    access_mode: BlockAccessMode = BlockAccessMode.OWNED
    provenance: dict[str, Any]       # {"kind": BlockProvenanceKind, ...}
    functional_name: str = ""
    tags: list[str]
    content: dict[str, Any]          # Lire via as_media() / as_container()
    contains: list[str]              # IDs enfants (CONTAINER seulement)
    inputs: list[InputConnection]    # Connexions entrantes (non-containers seulement)
    container_paths: dict[str, str]  # {container_id → chemin FreeTree}
    tree: FreeTree | None = None     # Vue arbre (CONTAINER seulement)
    graph: FreeGraph | None = None   # Vue graphe (CONTAINER seulement)

# Méthodes
block.is_container() -> bool
block.is_link()      -> bool
block.is_editable()  -> bool
block.as_media()     -> MediaContent      # Lire storage_path, width, height...
block.as_container() -> ContainerContent  # Lire workspace_role, internal_lib...
```

---

## Enums ✅

```python
class BlockType(str, Enum):
    EMPTY="empty" | CONTAINER="container" | IMAGE="image"
    VIDEO="video" | AUDIO="audio"  | TEXT="text"  | PROMPT="prompt"

class BlockDomain(str, Enum):
    CHARACTERS="characters" | STORY="story" | LIB="lib"
    # LOCATION="location" — DETTE sans infrastructure, ne pas utiliser

class BlockAccessMode(str, Enum):
    OWNED="owned" | LINK="link"

class BlockProvenanceKind(str, Enum):
    LOCAL="local" | LIB_CLONE="lib_clone" | LIB_LINK="lib_link"
    # Seules 3 valeurs — toute autre lève ValueError à la désérialisation

class PortType(str, Enum):
    IN="in" | TOP="top" | BOTTOM="bottom" | OUT="out"
```

---

## Profils — BlockType × usage ✅

| `BlockType` | Profils valides |
|-------------|----------------|
| `CONTAINER` | `workspace_root` · `container` · `shot` · `character` · `character_form` · `location` · `library` · `library_folder` |
| `IMAGE` | `asset` · `reference` · `generated` · `variation` |
| `VIDEO` | `asset` · `generated` · `variation` |
| `AUDIO` | `voice` · `music` · `sfx` · `asset` · `generated` |
| `TEXT` | `note` · `description` · `dialogue` · `preset` |
| `PROMPT` | `prompt` · `preset` |
| `EMPTY` | `internal_lib_empty` · `template_slot` |

**Mutabilité :** le profile d'un `CONTAINER` est fixe à la création. Celui d'un non-container peut changer.

---

## Contenu typé ✅

```python
# LECTURE — toujours via accesseurs, jamais block.content.get() directement
media = block.as_media()         # IMAGE / VIDEO / AUDIO
media.storage_path               # str
media.thumbnail_path             # str
media.preview_path               # str (vidéo)
media.width                      # int px
media.height                     # int px
media.duration_ms                # int
media.candidate_paths()          # tuple[str,...] — non-vides par priorité

ctn = block.as_container()       # CONTAINER
ctn.workspace_role               # str lowercase — "story_root", "characters_root"...
ctn.internal_lib                 # bool
ctn.drop_target                  # bool

# ÉCRITURE — directement dans le dict avec les clés canoniques de block_content.py
block.content["storage_path"]   = str(destination)
block.content["workspace_role"] = "story_root"
```

---

## InputConnection ✅

```python
@dataclass(slots=True)
class InputConnection:
    source_block_id: str   # Block non-container source
    port: PortType
    name: str = ""
    enabled: bool = True
    order: int = 0
    metadata: dict[str, Any]
```

Connexions uniquement entre Blocks **non-containers** (IMAGE, VIDEO, AUDIO, TEXT, PROMPT).
Les `CONTAINER` n'ont pas de `inputs`.

---

## Couches d'édition structurelles — FreeTree et FreeGraph ✅

Un `CONTAINER` embarque deux couches d'édition UI **indépendantes** de son architecture :

- **`block.tree` / FreeTree** — couche **architecture** : l'utilisateur organise ses
  Blocks en hiérarchie avec des dossiers virtuels, indépendamment de `block.contains`
- **`block.graph` / FreeGraph** — couche **liens** : l'utilisateur visualise et édite
  spatialement les connexions entre Blocks, indépendamment des containers

Ces couches sont initialisées et maintenues par `FreeTreeService` / `FreeGraphService`.
**Ne jamais instancier `FreeTree()` / `FreeGraph()` directement dans le code applicatif.**

```python
class FreeTree:
    root_ids: list[str]             # IDs nœuds racine
    nodes: dict[str, FreeTreeNode]  # node_id → nœud

class FreeTreeNode:
    id: str; kind: str              # "folder" | "block_ref"
    name: str; block_id: str | None; children: list[str]

class FreeGraph:
    nodes: dict[str, FreeGraphNode]
    edges: dict[str, FreeGraphEdge]

class FreeGraphNode:
    id: str; block_id: str; x: float; y: float

class FreeGraphEdge:
    id: str; source_node_id: str; target_node_id: str; label: str = ""
```

**Règles clés :**
- `block.contains` est la source de vérité — `tree` et `graph` sont des couches éditables indépendantes
- `FreeGraph.add_node()` exige `block_id ∈ container.contains` — sinon `ValidationError`
- Supprimer un enfant de `contains` ne nettoie pas `tree`/`graph` automatiquement — cascade manuelle via les services

---

## Provenance ✅

| Origine | `access_mode` | `provenance.kind` | Éditable |
|---------|-------------|-------------------|----------|
| Créé localement | `OWNED` | `"local"` | ✅ |
| Clone depuis LIB externe | `OWNED` | `"lib_clone"` | ✅ |
| Link depuis LIB externe | `LINK` | `"lib_link"` | ❌ |
| Clone depuis LIB interne | `OWNED` | `"local"` + `source_block_id` | ✅ |
| Link depuis LIB interne | `LINK` | `"local"` + `source_block_id` | ❌ |

---

## Système Clone / Link — flux en deux étapes ✅

```
LIB externe (.sbcprj)
    │  Étape 1 — create_block_from_library_source()
    ▼
LIB interne (blk_internal_lib_root)   ← point de passage obligatoire
    │
    ├── Étape 2 Clone → Block OWNED / "local" dans workspace domaine
    └── Étape 2 Link  → Block LINK  / "local" dans workspace domaine
```

---

## Architecture en couches ✅

```
src/
├── domain/          models.py · block_content.py · exceptions.py
├── infrastructure/  repositories/ · storage/
├── services/        block_service.py · free_tree_service.py · free_graph_service.py · container_rules.py
├── application/     use_case_service.py · container_resolver.py · workspaces/
└── UI/              windows/ · Frames/workspaces/ · Widgets/ · themes/
```

---

## UseCaseService — façade unique ✅

**L'UI n'appelle jamais `BlockService` directement.**  
Cette règle est vérifiée mécaniquement par `import-linter` (voir SBC-ARCHITECTURE.md — "Enforcement de l'architecture en couches").

```python
# Créer
use_case.create_block(type=BlockType.IMAGE, domain=BlockDomain.CHARACTERS,
                      profile="generated", name="Hulk Rage")
use_case.create_block_in_container(parent_container_id="blk_characters_root", ...)

# Clone / Link depuis LIB externe → LIB interne
use_case.create_block_from_library_source(
    source_block=lib_block, mount_id="lib_mount_ff1a",
    source_workspace_id="library_a1b2",
    source_workspace_path="/path/to/lib.sbcprj",
    as_link=False,   # False=clone, True=link
    parent_container_id="blk_internal_lib_root",
)

# Connecter deux Blocks non-containers
use_case.connect_input(
    target_block_id="blk_image_yyyy",
    source_block_id="blk_prompt_xxxx",
    port=PortType.IN, name="prompt_source",
)
```

---

## Workspaces — Navigation UI ✅

```
[ Dashboard ] | [ Projet ] [ Personnages ] [ Scénario ] [ Librairie ] [ Paramètres ]
```

### IDs des Blocks racine (hardcodés)

```python
PROJECT_ROOT_BLOCK_ID       = "blk_project_root"        # Racine Master principale
INTERNAL_LIB_ROOT_BLOCK_ID  = "blk_internal_lib_root"   # LIB interne du projet
CHARACTERS_ROOT_BLOCK_ID    = "blk_characters_root"
STORY_ROOT_BLOCK_ID         = "blk_story_root"
LIB_ROOT_BLOCK_ID           = "blk_lib_root"
INTERNAL_LIB_EMPTY_BLOCK_ID = "blk_internal_lib_empty"  # Drop zone EMPTY
```

Tous : `CONTAINER` / `profile="workspace_root"`.
Rôle sémantique lu via `block.as_container().workspace_role`.

---

## Signaux Qt — règle fondamentale ✅

```
Bottom-up : Widget → Signal → Panel → Signal → MainWindow._handler() → UseCaseService
Top-down  : MainWindow._refresh_project_workspace()
                → panel.set_blocks(self._blocks)  ← TOUS les panels sans exception
```

Tout composant affichant des données de Block **DOIT se rafraîchir intégralement**
sur `set_blocks()`. Aucun composant ne garde une copie locale stale.

### Contrat pour tout nouveau widget

```python
class MonWidget(QWidget):
    block_update_requested = Signal(dict)   # intention de mutation — jamais mutation directe
    block_selected = Signal(object)

    def set_blocks(self, blocks: list[Block], project_root: str = "") -> None:
        self._blocks = blocks       # remplace toujours, jamais de merge partiel
        self._project_root = project_root
        self._refresh()             # redessine tout depuis self._blocks

    def _on_user_edit(self, block_id: str, new_name: str) -> None:
        self.block_update_requested.emit({"block_id": block_id, "name": new_name})
        # Ne PAS modifier self._blocks ici — attendre set_blocks() en retour
```

Ne jamais câbler un signal de widget directement vers un autre widget — tout passe par `MainWindow`.

---

## Règles de codage

1. **Import domaine** — depuis le package `domain`, pas `domain.models` directement.
   ```python
   from domain import Block, BlockType, BlockDomain, MediaContent, ContainerContent
   ```

2. **Lecture de content** — accesseurs obligatoires, jamais `block.content.get()` dans l'UI/services.
   ```python
   role = block.as_container().workspace_role   # ✅
   role = block.content.get("workspace_role")   # ❌
   ```

3. **Écriture de content** — clés canoniques de `block_content.py` uniquement, ne pas en inventer.
   ```python
   block.content["storage_path"] = str(destination)   # ✅
   ```

4. **Création** — toujours via `UseCaseService.create_block()` ou `create_block_in_container()`.

5. **Nouveau profil** — l'ajouter dans le set `PROFILES` de `domain/models.py`.

6. **Nouveaux champs de content** — les documenter dans `domain/block_content.py`.

7. **IDs** — format `blk_<uuid4().hex[:12]>`, généré automatiquement par `UseCaseService`.

8. **Erreurs** — `ValidationError` et `NotFoundError` remontent jusqu'à l'UI.
   Logger avec `logger = logging.getLogger(__name__)`.

9. **LOCATION** — ne pas créer de blocks avec `domain=BlockDomain.LOCATION`.
   Utiliser `domain=CHARACTERS` + `profile="location"` (infrastructure non implémentée).

10. **`shared`** — ne pas utiliser, toujours `False`, champ mort en attente de suppression.
