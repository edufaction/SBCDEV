# domain_views.md

## Objectif
Ce document définit les règles d’interface spécifiques aux grands domaines fonctionnels :

- Characters
- Story
- Library
- Universe (Location)

Il garantit que :
- chaque domaine garde une identité utile,
- tout en respectant une grammaire UI commune,
- et en évitant la divergence ergonomique.

Ce document complète :
- AGENTS.md → architecture & règles de code
- ui_guidelines.md → ergonomie globale
- widget_catalog.md → composants réutilisables

---

## Règle fondamentale

Tous les domaines doivent respecter la structure de base :

- gauche → navigation / arbre / organisation
- centre → vue principale de travail
- droite → inspecteur / propriétés / liens

Aucun domaine ne doit casser cette structure sans justification forte.

---

# 1. CHARACTER VIEW

## Objectif métier
Gérer des entités visuelles riches (personnages) avec :
- références visuelles
- variantes
- descriptions
- relations
- médias générés

## Layout

### Gauche
- `TreePanelWidget`
- organisation libre des personnages
- groupes / dossiers
- possibilité de drag & drop

### Centre
Vue principale orientée VISUEL

Modes possibles :
- grid (par défaut)
- list enrichie
- preview focus

Utiliser :
- `AssetGridWidget`
- `ThumbnailCardWidget`

### Droite
Inspecteur (`InspectorPanelWidget`) avec sections :

- General
- Visual References
- Generated Assets
- Metadata
- Links
- Notes

## Comportements clés

- sélection d’un personnage → met à jour inspecteur
- double clic → ouvre vue détaillée / fenêtre flottante
- drag & drop → réorganisation dans l’arbre
- preview rapide possible

## Spécificités UI

- importance forte des thumbnails
- possibilité de comparer visuellement plusieurs variantes
- accès rapide aux images de référence

## Widgets spécifiques autorisés

- `CharacterReferenceStripWidget`
- `CharacterVariantSelectorWidget`

---

# 2. STORY VIEW

## Objectif métier
Construire une narration structurée à partir de blocs (shots, scènes, storyblocks).

## Layout

### Gauche
- `TreePanelWidget`
- structure narrative :
  - story
  - storyblocks
  - shots

### Centre
Vue STRUCTURELLE ou VISUELLE selon mode

Modes :
- tree narratif enrichi
- grid de shots
- vue séquentielle
- (optionnel) vue graphe

Utiliser :
- `AssetGridWidget`
- `AssetListWidget`
- éventuellement un widget dédié de séquence

### Droite
Inspecteur avec sections :

- General
- Narrative Content
- Media (start frame, end frame, video)
- Dialogue
- Links
- Notes

## Comportements clés

- sélection → met à jour inspecteur
- double clic → ouvre détail du shot
- navigation fluide entre blocs
- cohérence entre structure et contenu

## Spécificités UI

- importance de la lecture séquentielle
- possibilité de visualiser rapidement une séquence
- éviter les écrans trop techniques

## Widgets spécifiques autorisés

- `ShotSequenceWidget`
- `StoryTimelineMiniWidget`

---

# 3. LIBRARY VIEW

## Objectif métier
Gérer un ensemble d’assets (images, vidéos, textes, références).
Le domaine `LIB` couvre:
- la librairie projet (`Library Root`),
- la librairie interne (`INTERNALLIB`),
- et, à terme, les libs externes montées.

## Layout

### Gauche
- `TreePanelWidget`
- organisation libre
- dossiers, collections, tags

### Centre
Vue principale orientée EXPLORATION

Modes :
- grid (principal)
- list
- résultats de recherche

Utiliser :
- `AssetGridWidget`
- `ThumbnailCardWidget`

### Droite
Inspecteur avec :

- General
- Media info
- Metadata
- Usage / Links
- Notes

## Comportements clés

- recherche rapide
- filtres
- sélection multiple
- drag & drop vers d’autres domaines

## Spécificités UI

- densité visuelle importante
- priorité à la vitesse de navigation
- preview rapide essentielle

## Widgets spécifiques autorisés

- `AssetUsageWidget`
- `MetadataCompactWidget`

## Contraintes de stockage associées

- Le conteneur racine `PROJET` contient les sous-racines de domaine, dont `Library Root` et `INTERNALLIB`.
- Les blocs finaux ne doivent pas être attachés directement à la racine absolue.
- `INTERNALLIB` contient un bloc `EMPTY` dédié au drop/import (`internal_lib_empty`).
- Les blocs sont persistés par workspace dans `workspaces/<workspace_key>/blocks.json`.

## LIBS externes montées (phase A)

En phase A, le montage des libs externes est une responsabilité de stockage.

Source de vérité:
- `project.json` → `mounted_libraries`

Format normalisé:
- `id`
- `kind=LIB`
- `path`
- `label`
- `enabled`
- `read_only`
- `mounted_at` (optionnel)

En phase A, cette donnée est persistée et normalisée, sans imposer encore une UI de navigation dédiée.

---

# 4. UNIVERSE / LOCATION VIEW

## Objectif métier
Gérer les lieux, environnements, décors.

## Layout

### Gauche
- `TreePanelWidget`
- organisation des lieux
- hiérarchie possible

### Centre
Vue VISUELLE + STRUCTURE

Modes :
- grid de lieux
- preview enrichie
- vue interne d’un lieu (conteneur)

Utiliser :
- `AssetGridWidget`
- `ThumbnailCardWidget`

### Droite
Inspecteur avec :

- General
- Environment Description
- Visual References
- Associated Elements
- Links
- Notes

## Comportements clés

- ouverture d’un lieu → vue interne
- navigation hiérarchique
- cohérence visuelle des environnements

## Spécificités UI

- importance des références visuelles
- continuité visuelle entre lieux
- accès rapide aux éléments liés

## Widgets spécifiques autorisés

- `LocationReferenceBoardWidget`
- `EnvironmentPreviewWidget`

---

# 5. RÈGLES TRANSVERSES

## 5.1 Sélection unique globale

La sélection doit être cohérente :
- arbre → centre → inspecteur synchronisés
- une sélection claire à tout moment

---

## 5.2 Inspecteur unique

Même logique d’inspecteur pour tous les domaines :
- sections repliables
- même structure visuelle
- mêmes composants de base

---

## 5.3 Thumbnails cohérents

Toutes les vues visuelles doivent utiliser :
- `ThumbnailCardWidget`

Pas de variation graphique sauvage.

---

## 5.4 États vides homogènes

Tous les domaines doivent utiliser :
- `EmptyStateWidget`

---

## 5.5 Drag & Drop unifié

Le drag & drop doit fonctionner de manière cohérente :
- entre domaines
- entre panneaux
- entre arbres et vues

---

## 5.6 Ouverture d’un élément

Deux modes standards :
- inline (centre)
- fenêtre flottante

Ne pas multiplier les comportements différents.

---

## 5.7 Liens et références

Tous les domaines doivent afficher les liens via :
- `LinkListWidget`

---

## 5.8 Navigation cohérente

- double clic = ouvrir
- simple clic = sélectionner
- clic droit = menu contextuel

---

## 5.9 Modes d’affichage

Quand pertinent, proposer :
- grid
- list
- preview

via `ModeSwitchWidget`

---

## 5.10 Performance perçue

- affichage rapide
- placeholders propres
- chargement progressif si nécessaire

---

## 5.11 Cohérence LIB / INTERNALLIB

- `LIB` est le domaine logique unique pour la gestion des bibliothèques.
- `INTERNALLIB` est la branche de partage interne au projet.
- Les libs externes sont des workspaces séparés (kind `library`) référencés par montage, pas dupliqués dans les données projet.

---

# 6. MATRICE DE COHÉRENCE

| Élément              | Characters | Story | Library | Universe |
|---------------------|----------|-------|--------|---------|
| Tree gauche         | ✔        | ✔     | ✔      | ✔       |
| Grid centrale       | ✔        | ✔     | ✔      | ✔       |
| Inspecteur droite   | ✔        | ✔     | ✔      | ✔       |
| Thumbnails          | ✔        | ✔     | ✔      | ✔       |
| Drag & Drop         | ✔        | ✔     | ✔      | ✔       |
| Liens visibles      | ✔        | ✔     | ✔      | ✔       |
| Preview média       | ✔        | ✔     | ✔      | ✔       |

---

# 7. RÈGLE D’EXTENSION

Quand un nouveau domaine apparaît :

1. reprendre la structure standard
2. réutiliser les widgets existants
3. définir uniquement les sections spécifiques
4. éviter toute rupture ergonomique

---

# 8. RÉSUMÉ

Chaque domaine :
- a sa logique métier propre,
- mais partage une même grammaire UI.

Les différences doivent porter sur :
- le contenu,
- les sections,
- les interactions métier,

et NON sur :
- la structure globale,
- les composants de base,
- les comportements fondamentaux.

L’objectif est une application cohérente, prévisible et maîtrisée, même en croissance.
