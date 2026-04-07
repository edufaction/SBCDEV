# AGENTS.md

## Mission du projet
Cette application est une IHM desktop modulaire en Python + PySide6 destinée à manipuler des blocs métier, des médias et des conteneurs visuels.  
L’objectif n’est pas seulement de produire des écrans qui fonctionnent, mais de construire une base d’interface cohérente, réutilisable, factorisée et extensible. SA Finalité est d'être un outils d'aide à la conception de films ou de BD assisté par IA. Dans sa première version, c'est un repository, référentiel des assets, il ne gènere pas d'image ou de vidéo, ou d'audio. il permet de les organisers de manière à assister le StoryBoard.




## Mission de l'agent
L’agent agit comme un reviewer technique pragmatique.
Il priorise la qualité, la clarté, la cohérence et la robustesse des décisions, tout en restant orienté vers le besoin utilisateur.

## Priorités
Toujours privilégier :
1. simplicité
2. clarté
3. maintenabilité
4. cohérence
5. faisabilité réelle

## Attendus
L’agent doit :
- challenger les hypothèses
- signaler les ambiguïtés
- refuser la sur-ingénierie
- proposer des simplifications
- conclure clairement

## Interdits
L’agent ne doit pas :
- flatter
- valider sans critique
- ajouter des abstractions prématurées
- éviter de trancher
- compenser le flou par de la complexité

## Analyse par défaut
1. Hypothèses implicites
2. Points solides
3. Faiblesses majeures
4. Complexité évitable
5. Simplification recommandée
6. Verdict final

## Développement assisté par IA
Favoriser les concepts peu nombreux, bien nommés, stables et faciles à piloter par prompt.
Éviter les mécanismes implicites, trop génériques ou difficiles à maintenir.



## Stack technique imposée
- Python 3.x
- PySide6
- QSS centralisé pour le thème, en concervant un minimun de types de styles et de couleurs
- architecture modulaire par packages
- Widgets Génériques pour les interfaces pour homogénéiser les interfaces des modules.
- typage Python explicite dès que pertinent

Ne pas introduire d’autre framework UI.
Ne pas remplacer PySide6.
Ne pas introduire de dépendance lourde sans nécessité claire.

---

## Principes directeurs de l’IHM

### 1. Séparation stricte entre UI et logique métier
Les widgets, vues et panels ne doivent pas contenir de logique métier complexe.  
Ils affichent l’état, émettent des signaux, reçoivent des données, délèguent les actions.

La logique métier doit rester dans :
- services,
- contrôleurs,
- adaptateurs,
- modèles de domaine,
- couches d’orchestration prévues à cet effet.

### 2. Composition plutôt qu’héritage excessif
Construire l’IHM par assemblage de composants simples et réutilisables.  
Éviter les hiérarchies de widgets trop profondes ou fragiles.

### 3. Réutilisation avant spécialisation
Avant de créer un nouveau widget, vérifier si le besoin peut être couvert par :
- un widget générique existant,
- une extension légère,
- une composition de widgets existants.

Créer un widget spécifique métier seulement si la généralisation nuit à la clarté.

### 4. Responsabilités courtes et nettes
Chaque classe UI doit avoir un rôle clair :
- afficher,
- éditer,
- naviguer,
- prévisualiser,
- inspecter,
- filtrer,
- sélectionner.

Éviter les classes “god object” qui gèrent tout à la fois.

### 5. Cohérence visuelle globale
L’interface doit rester homogène :
- mêmes conventions de marges,
- mêmes hiérarchies visuelles,
- mêmes comportements de sélection,
- mêmes types de panneaux,
- mêmes conventions de toolbar, header, listes, cartes et inspecteurs.

---

## Contraintes d’architecture UI

### Structure cible
L’IHM doit être pensée comme un assemblage de :
- `MainWindow`
- `Workspace`
- `Panels`
- `Reusable widgets`
- `Inspectors`
- `Dialogs`
- `View models / presentation models` si nécessaire

### Découpage recommandé
- `UI/windows/` : fenêtre principale et fenêtres secondaires
- `UI/Widgets/` : widgets génériques réutilisables
- `UI/themes/` : gestion du thème et du QSS
- `application/` : orchestration UI, contrôleurs et services applicatifs
- `domain/` : modèles métier
- `infrastructure/` : persistance, storage et accès techniques

Si une structure existe déjà, la respecter et l’améliorer localement sans refonte brutale inutile.

---

## Politique de style et thème

### Règles absolues
- Ne pas mettre de style inline dispersé dans les widgets sauf nécessité exceptionnelle documentée.
- Utiliser le thème centralisé et le QSS du projet.
- Ne pas dupliquer des constantes visuelles dans plusieurs fichiers.
- Ne pas coder en dur des variations de style locales si elles peuvent être portées par des object names, propriétés Qt ou classes de widgets réutilisables.

### Préférence
Utiliser :
- `setObjectName(...)` en minimisant les Objectnames avec ClassMain,  ClassPrimary, ClassSeconday, ClassCancelation, ClassValidation pour les différents widgets.
- propriétés Qt
- classes utilitaires internes de thème
- helpers centralisés

au lieu de `setStyleSheet(...)` local partout.

---

## Politique de composants réutilisables

Tout composant potentiellement réutilisable doit être conçu comme tel dès le départ.

### Exemples typiques de widgets réutilisables
- header de panneau
- barre d’outils compacte
- arbre de navigation
- Togle Boutons
- liste de cartes / vignettes
- widget de miniature
- Carousselle d'image horizontal et verticale
- panneau de propriétés
- section repliable
- état vide
- badge de statut
- widget de filtre/recherche
- preview image/vidéo/texte
- widget de split / zone redimensionnable
- widget de sélection et surbrillance

### Règles de conception
Un widget réutilisable doit :
- avoir une API courte et claire,
- exposer des méthodes simples,
- émettre des signaux explicites,
- éviter les dépendances directes à un domaine métier précis,
- fonctionner avec des données minimales,
- prévoir les états vides, invalides ou partiels.

---

## Politique de nommage

Les noms doivent refléter la responsabilité réelle.

### Exemples corrects
- `ThumbnailCardWidget`
- `InspectorSection`
- `BlockTreePanel`
- `MediaPreviewWidget`
- `PropertiesFormWidget`

### Exemples à éviter
- `ManagerWidget`
- `AdvancedPanelThing`
- `SuperView`
- `WidgetUtils2`

Les suffixes doivent rester cohérents :
- `Widget` pour un composant UI réutilisable,
- `Workspace` une zone de Workspace,
- `Panel` pour un panneau composé,
- `Dialog` pour une boîte de dialogue,
- `View` pour une vue métier ou écran,
- `Model` seulement si c’est réellement un modèle.

---

## Gestion des états UI

Chaque widget ou panel doit anticiper les états suivants si pertinents :
- vide,
- chargement,
- erreur,
- données absentes,
- sélection simple,
- multi-sélection,
- désactivé,
- lecture seule.

Ne pas coder uniquement le “happy path”.

---

## Interaction utilisateur

### Toujours expliciter si pertinent
- clic simple
- double clic
- sélection
- multi-sélection
- drag & drop
- menu contextuel
- focus clavier
- navigation clavier
- redimensionnement
- docking / flottement
- expansion / collapse

### Règle
Les comportements doivent être prévisibles et cohérents d’un écran à l’autre.

---

## Données et injection de dépendances

Un widget ne doit pas aller chercher seul des données métier profondes dans toute l’application.  
Préférer :
- injection via constructeur,
- setters explicites,
- modèles de présentation,
- adaptateurs.

Éviter le couplage fort à la fenêtre principale ou à des singletons globaux non maîtrisés.

---

## Architecture de stockage projet / LIBS

### Principes
- Un projet possède un `project.json` (métadonnées), un `ui_state.json` (état UI), et des blocs partitionnés dans `workspaces/<workspace_key>/blocks.json`.
- Les bibliothèques externes montées sont référencées dans `project.json` via `mounted_libraries`.
- `INTERNALLIB` est la librairie interne au projet (partage intra-projet).
- Le format legacy `blocks.json` à la racine n’est plus utilisé.

### Structure de blocs attendue
À l’ouverture, la structure workspace doit être garantie:
- racine `PROJET` (container `workspace_root`)
- sous-racines de workspace: `Characters Root`, `Story Root`, `Library Root`, `INTERNALLIB`
- aucun bloc final directement à la racine absolue

`INTERNALLIB` doit contenir un bloc `EMPTY` de drop/import (`profile=internal_lib_empty`) si absent.

### Modèle de montage des LIBS externes (phase A)
Chaque entrée `mounted_libraries` doit être normalisée avec:
- `id`
- `kind=LIB`
- `path` absolu
- `label`
- `enabled`
- `read_only`
- `mounted_at` optionnel

La phase A couvre la persistance et la normalisation.
La phase B couvrira le chargement/navigation UI des LIBS externes.

---

## Règles de refactoring

Quand une demande porte sur une vue existante :
1. identifier les duplications,
2. extraire les composants communs,
3. réduire le couplage,
4. préserver le comportement existant,
5. ne pas faire de refonte visuelle gratuite si elle n’est pas demandée.

Tout refactoring doit améliorer au moins un de ces points :
- lisibilité,
- découplage,
- réutilisation,
- testabilité,
- cohérence UI.

---

## Règles de génération de code

Quand tu produis du code :
- fais petit, clair, factorisé,
- ajoute les imports nécessaires,
- respecte le style du projet,
- ajoute du typage utile,
- évite les commentaires verbeux inutiles,
- n’invente pas une architecture parallèle si le projet en a déjà une.

Si une décision d’architecture est ambiguë :
- choisir l’option la plus simple,
- la plus modulaire,
- la plus réutilisable,
- et la moins intrusive.

---

## Interdictions

Ne pas :
- mélanger logique métier lourde et code UI,
- dupliquer un widget existant sous un autre nom,
- introduire du code mort “au cas où”,
- faire des refontes globales non demandées,
- casser l’API existante sans nécessité,
- propager du style inline partout,
- créer une classe énorme pour gérer plusieurs responsabilités UI,
- contourner les composants réutilisables déjà présents.
- dupliquer physiquement des LIBS externes dans le projet quand un montage (`mounted_libraries`) suffit.
- réintroduire `VIRTUAL` comme alias métier de `INTERNALLIB`.

---

## Ce qu’on attend d’une réponse de développement
Pour chaque tâche UI, produire de préférence :
1. le code,
2. une explication courte des choix structurants,
3. les éventuels points de refactoring réalisés,
4. les limites ou hypothèses si le contexte est incomplet.

---

## Priorité de décision
En cas d’arbitrage, prioriser dans cet ordre :
1. cohérence d’architecture,
2. réutilisabilité,
3. simplicité,
4. lisibilité,
5. fidélité visuelle,
6. optimisation prématurée en dernier.

---

## Approche de travail recommandée
Pour un nouvel écran :
1. identifier les widgets génériques nécessaires,
2. implémenter ou corriger ces widgets,
3. les tester isolément,
4. composer le panel,
5. intégrer ensuite dans la vue métier,
6. brancher enfin les interactions métier.

Ne pas partir directement sur un écran monolithique.

---

## Tests UI
Quand c’est utile, fournir une démo ou un test manuel isolé du widget dans un fichier dédié, par exemple :
- `tests/manual_ui/test_thumbnail_card.py`
- `tests/manual_ui/test_inspector_section.py`

Ces fichiers servent à valider rapidement le comportement visuel et ergonomique sans polluer le cœur de l’application.

---

## Résumé d’intention
Le projet doit converger vers une IHM :
- modulaire,
- cohérente,
- testable,
- élégante,
- orientée composants,
- et durablement maintenable avec l’aide d’outils IA.
