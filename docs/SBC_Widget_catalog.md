# SBC_Widget_catalog.md

## Objectif
Ce catalogue sert de référence unique pour éviter de recréer des widgets déjà présents.

Priorité:
1. réutiliser l'existant,
2. extraire un composant générique depuis l'existant,
3. créer un nouveau widget seulement en dernier recours.

Date de mise à jour: 3 avril 2026 (basée sur le code actuel de `UI/Widgets`, `UI/windows`, `UI/themes`, `infrastructure/storage`).

---

## Légende de statut
- `Implémenté`: classe réutilisable déjà disponible.
- `Partiel`: comportement présent mais pas encore extrait en composant générique stable.
- `À créer`: absent du code actuel.

---

## 1) Catalogue réel (source de vérité du code)

| Famille | Widget catalogue (canonique) | Équivalent code existant | Statut | Notes de réutilisation |
|---|---|---|---|---|
| Structure | `AppShell/MainWindow` | `UI/windows/main_window.py::MainWindow` | Implémenté | Shell principal + sidebar + workspace stack. |
| Structure | `SplitWorkspaceWidget` | `QSplitter` dans `UI/windows/thumbnail_list_window.py` | Partiel | Split 2 panneaux présent mais pas extrait en widget générique. |
| Navigation | `SidebarNavigationWidget` | `UI/Widgets/sidebar_menu.py::SidebarMenu` | Implémenté | Navigation latérale cohérente et thémée. |
| Navigation | `TreePanelWidget` | `UI/Widgets/free_tree_widget.py::FreeTreeWidget` | Partiel | Arbre + actions + DnD OK, mais pas de filtre/context menu API générique. |
| Navigation | `SearchBarWidget` | `UI/Widgets/search_bar_widget.py::SearchBarWidget` | Implémenté | Champ de recherche factorisé et réutilisable. |
| Navigation | `FilterBarWidget` | `UI/Widgets/filter_bar_widget.py::FilterBarWidget` | Implémenté | Barre de filtres compacte factorisée. |
| Affichage | `ThumbnailCardWidget` | `UI/Widgets/thumbnail_widget.py::ThumbnailWidget` | Implémenté | Carte vignette complète (canvas + badge + meta). |
| Affichage | `AssetListWidget` | `UI/Widgets/thumbnail_list_view.py::ThumbnailListView` + `thumbnail_model.py` + `thumbnail_delegate.py` | Implémenté | Liste performante via model/delegate. |
| Affichage | `AssetGridWidget` | `UI/Widgets/asset_grid_widget.py::AssetGridWidget` | Implémenté | Vue grille réutilisable basée sur `ThumbnailWidget`. |
| Affichage | `BadgeWidget` | Badge de type via `ThumbnailWidget`/`ThumbnailDelegate` | Partiel | Rendu badge existe, classe dédiée absente. |
| Édition/inspection | `InspectorPanelWidget` | `UI/Widgets/block_property_widget.py::BlockPropertyWidget` | Partiel | Inspecteur bloc structuré, encore spécialisé au domaine Block. |
| Édition/inspection | `InspectorSectionWidget` | `UI/Widgets/inspector_section_widget.py::InspectorSectionWidget` | Implémenté | Section repliable réutilisable pour inspecteurs/panels. |
| Édition/inspection | `PropertiesFormWidget` | `QFormLayout` dans `BlockPropertyWidget` et `ProjectWorkspaceWidget` | Partiel | Structure form présente mais non mutualisée. |
| Édition/inspection | `ProjectInspectorWidget` | `UI/Widgets/project_workspace_widget.py::ProjectWorkspaceWidget` | Implémenté | Métadonnées projet + preview + save. |
| Édition/inspection | `SettingsPanelWidget` | `UI/Widgets/settings_workspace_widget.py::SettingsWorkspaceWidget` | Implémenté | Onglets settings + thème + chemins storage. |
| Preview | `MediaPreviewSupport` | `UI/Widgets/thumbnail_utils.py` | Implémenté | Résolution path + image safe + capture preview vidéo. |
| Preview | `MediaPreviewWidget` | `UI/Widgets/media_preview_widget.py::MediaPreviewWidget` | Implémenté | Preview image/vidéo/texte avec fallback vide. |
| Feedback | `EmptyStateWidget` | `UI/Widgets/empty_state_widget.py::EmptyStateWidget` | Implémenté | État vide factorisé et réutilisable. |
| Support | `UiMetrics/ThemeTokens` | `UI/themes/theme.py`, `theme_loader.py`, `qss/*.qss` | Implémenté | Tokens + QSS centralisés déjà en place. |
| Support | `WidgetPrimitives` | `UI/themes/widget_primitives.py` | Implémenté | Initialisation transversale scroll area/scrollbar. |
| Support | `MountedLibrariesStorage` | `infrastructure/storage/workspace_storage_service.py` (`list/add/remove/save_mounted_libraries`) | Implémenté | Fondations phase A pour les LIBS externes montées via `project.json`. |
| Interaction | `ModeSwitchWidget` | `UI/Widgets/mode_switch_widget.py::ModeSwitchWidget` | Implémenté | Commutation compacte list/grid. |

---

## 2) Matrice anti-réinvention (obligatoire avant tout nouveau widget)

1. Besoin: liste média avec vignettes, clic, double-clic.
Solution: réutiliser `ThumbnailListView` (+ model/delegate existants), ne pas recréer une `QListWidget` custom.

2. Besoin: carte vignette unitaire (miniature + titre + badge type).
Solution: réutiliser `ThumbnailWidget`.

3. Besoin: navigation arborescente projet/blocs.
Solution: partir de `FreeTreeWidget` et l'étendre, ne pas créer une nouvelle tree view métier.

4. Besoin: inspecteur de bloc à droite.
Solution: partir de `BlockPropertyWidget` puis extraire des sections communes si nécessaire.

5. Besoin: shell applicatif avec navigation latérale.
Solution: réutiliser `MainWindow` + `SidebarMenu`; spécialiser les pages du workspace.

6. Besoin: thème / couleurs / spacing.
Solution: passer par `UI/themes/*` et propriétés Qt (`panel`, `panelAlt`, etc.), jamais via styles inline dispersés.

---

## 3) Plan de factorisation recommandé (depuis l'existant)

Objectif: extraire seulement ce qui est déjà dupliqué, sans refonte brutale.

### Phase A (priorité haute)
1. Extraire `PanelHeaderWidget`.
Source: en-têtes répétés dans `FreeTreeWidget`, `ProjectWorkspaceWidget`, `SettingsWorkspaceWidget`.

2. Extraire `PanelContainerWidget`.
Source: structures `panel/panelAlt + layout + marges` répétées dans plusieurs fenêtres/workspaces.

3. Extraire `SearchBarWidget`.
Source: `QLineEdit` de `ThumbnailListWindow` avec API standard (`text_changed`, clear, placeholder).

4. Extraire `FilterBarWidget`.
Source: barre type/profile de `ThumbnailListWindow`.

### Phase B (priorité moyenne)
1. `InspectorSectionWidget`: fait.
Source: intégré dans `BlockPropertyWidget`.

2. `EmptyStateWidget`: fait.
Source: intégré dans `BlockPropertyWidget` et `MediaPreviewWidget`.

3. `MediaPreviewWidget` autonome: fait.
Source: intégré dans `ProjectWorkspaceWidget`.

### Phase C (à la demande métier)
- `BreadcrumbWidget`, `LinkListWidget`, `TagEditorWidget`, `NotesEditorWidget`, `SelectionToolbarWidget`.
Règle: implémenter uniquement si un besoin réel est confirmé sur au moins 2 écrans.

État actuel:
- `AssetGridWidget`: fait (intégré à `ThumbnailListWindow`).
- `ModeSwitchWidget`: fait (intégré à `ThumbnailListWindow`).
- autres items: en backlog.

---

## 4) Widgets Inexistants (issus du texte de référence)

Widgets présents dans ton référentiel cible mais **absents du code actuel** (ou non extraits en classe dédiée stable):

### Structure
- `SplitWorkspaceWidget` (classe dédiée absente, usage `QSplitter` ad hoc)
- `SectionCardWidget`

### Navigation
- `BreadcrumbWidget`
- `TreePanelWidget` (version générique dédiée absente, `FreeTreeWidget` reste spécialisé)

### Affichage synthétique
- `SummaryTileWidget`
- `BadgeWidget` (classe dédiée absente)

### Édition / inspection
- `LabeledFieldWidget`
- `TagEditorWidget`
- `NotesEditorWidget`
- `PropertiesFormWidget` (classe dédiée absente, structure seulement via `QFormLayout`)
- `InspectorPanelWidget` (classe dédiée absente, comportement réparti)

### Preview
- `ImagePreviewWidget`
- `VideoPreviewWidget`
- `TextPreviewWidget`

### Interaction / sélection
- `SelectionToolbarWidget`
- `LinkListWidget`
- `ReferenceInputWidget`
- `DropZoneWidget`

### Feedback / état
- `LoadingStateWidget`
- `ErrorStateWidget`
- `StatusMessageWidget`

### Support / utilitaires UI
- `CollapsibleContainerWidget`
- `IconTextButtonWidget`
- `ContextActionMenuBuilder`
- `ThumbnailPlaceholderFactory`
- `UiSpacing / UiMetrics` (classe/helper dédié manquant; seulement tokens de thème aujourd'hui)

---

## 5) Convention d'implémentation

Quand un nouveau widget est réellement nécessaire:
1. documenter pourquoi l'existant ne suffit pas,
2. définir une API publique courte,
3. ajouter l'export dans `UI/Widgets/__init__.py` si réutilisable,
4. brancher le style via thème/QSS centralisé,
5. prévoir les états `vide`, `erreur`, `désactivé` si pertinents.

---

## 6) Règle de gouvernance du catalogue

Ce document doit être mis à jour à chaque extraction de widget générique.

Format attendu pour chaque entrée:
- nom canonique,
- classe/fichier réel,
- statut (`Implémenté`, `Partiel`, `À créer`),
- décision de réutilisation.

Ce catalogue est prioritaire sur les intentions théoriques: le code existant fait foi.

---

## 7) Règles liées à la nouvelle architecture LIBS

1. `INTERNALLIB` remplace `VIRTUAL` comme branche interne de projet.
2. Les libs externes ne sont pas copiées dans le projet en phase A: elles sont référencées par montage (`mounted_libraries`).
3. Les blocs projet sont stockés dans `workspaces/<workspace_key>/blocks.json` (format racine `blocks.json` supprimé).
4. Avant de créer un widget de gestion des libs externes, réutiliser l’API de `WorkspaceStorageService` existante.
5. Toute future UI LIBS (phase B) doit consommer cette source de vérité, pas une structure ad hoc locale.
