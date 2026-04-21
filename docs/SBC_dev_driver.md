# SBC Dev Driver

Document court et normatif pour piloter le développement quotidien de SBC.

Ce document ne remplace pas `SBC-ARCHITECTURE.md`.

- `SBC-ARCHITECTURE.md` = vision, modèle cible, dettes, architecture détaillée
- `SBC_dev_driver.md` = règles courtes, opposables, applicables tout de suite

Si une règle n'est ni testable, ni vérifiable par lecture rapide du code, elle ne doit pas figurer ici.

## 1. Portée

Ce driver sert à trancher les décisions de développement courantes sur :

- le modèle métier
- les frontières de couches
- les accès aux données
- les ajouts de features
- les refactorings

Il ne sert pas à décrire toute l'architecture ni la roadmap.

## 2. Principe directeur

SBC optimise d'abord la cohérence du référentiel, pas la sophistication technique.

Conséquences :

- pas de nouvelle abstraction sans doublon ou douleur réelle
- pas de nouvelle couche "au cas où"
- pas de nouveau concept métier si `Block` suffit encore clairement
- pas de feature IA qui casse l'usage offline d'organisation

## 3. Règles dures

### R1. Un seul objet métier central

Tout nouveau contenu manipulé par l'application doit entrer dans le modèle `Block`.

Autorisé :

- ajout d'un `profile`
- ajout de clés documentées dans `content`
- ajout de services autour de `Block`

Interdit :

- créer une seconde entité métier de premier rang pour contourner `Block`
- encoder une feature entière dans des dicts anonymes hors `Block`

Test de décision :

- si l'objet doit vivre, être trié, affiché, relié, persisté ou cloné dans SBC, il doit probablement être un `Block`

### R2. `shared` est gelé

Le champ `shared` existe encore dans le code, mais il est considéré comme dette.

Règle :

- ne pas introduire de nouveau comportement fonctionnel basé sur `block.shared`
- ne pas ajouter de nouvel affichage, filtre ou logique métier utilisant `shared`

Tolérance actuelle :

- compatibilité avec l'existant uniquement

### R3. `BlockDomain.LOCATION` est interdit tant que l'infrastructure n'existe pas

Règle :

- ne pas créer de nouveaux Blocks avec `domain=BlockDomain.LOCATION`

Tant que le root, le panel, le service et le stockage dédiés n'existent pas, les lieux restent dans le flux transitoire déjà documenté.

### R4. La création de Blocks passe par `UseCaseService`

Pour tout nouveau code UI ou applicatif :

- utiliser `UseCaseService.create_block()`
- ou `UseCaseService.create_block_in_container()`

Interdit dans le nouveau code :

- instancier un `Block` à la main pour un flux métier normal
- contourner la génération d'ID et la normalisation faites par `UseCaseService`

### R5. Lecture typée du `content` quand l'accesseur existe

Règle :

- utiliser `as_media()` pour IMAGE, VIDEO, AUDIO
- utiliser `as_container()` pour CONTAINER

Interdit dans le nouveau code UI/applicatif :

- ajouter de nouveaux `block.content.get(...)` pour lire des champs déjà couverts par ces accesseurs

Exception explicite actuelle :

- `src/UI/Widgets/thumbnail_delegate.py` lit encore du texte brut faute d'accesseurs `as_text()` ou `as_prompt()`

### R6. Pas de nouvelle dépendance directe de l'UI vers `services.*`

Règle pour tout nouveau code :

- l'UI parle à `application/*`, pas à `services/*`

Exception explicite actuelle :

- `src/UI/windows/main_window.py` importe encore `BlockService` pour composer l'application

Consigne de refactoring :

- réduire cette exception
- ne pas la propager

### R7. Les documents doivent distinguer `actuel` et `cible`

Toute doc technique nouvelle ou modifiée doit séparer clairement :

- `État actuel`
- `Cible`
- `Dette / écart`

Interdit :

- écrire une règle future comme si elle était déjà vraie dans le code

## 4. Règles de simplicité

### S1. Un problème, un point d'entrée

Avant d'ajouter un service, vérifier si le besoin appartient déjà à :

- `UseCaseService`
- un workspace service existant
- un service de domaine existant

Ne créer un nouveau point d'entrée que si la responsabilité actuelle devient confuse.

### S2. Les widgets réutilisables restent génériques

Un widget de `UI/Widgets/` ne doit pas embarquer de logique métier spécifique à un workspace si cette logique l'empêche d'être réutilisé ailleurs.

### S3. La doc ne doit pas compenser le flou du code

Si une règle importante demande trois paragraphes pour être comprise, elle est soit trop compliquée, soit mal placée.

Préférence :

- simplifier le code
- ou déplacer le détail dans la doc locale du module

## 5. Exceptions admises

Ce driver ne ment pas sur l'état du dépôt.

Exceptions connues à la date du document :

- `src/UI/windows/main_window.py` importe `BlockService`
- `src/UI/Widgets/thumbnail_delegate.py` utilise `block.content.get(...)`
- le champ `shared` existe encore dans le modèle et dans des flux applicatifs
- `BlockDomain.LOCATION` existe dans l'enum mais pas dans l'infrastructure complète

Ces exceptions ne sont pas des précédents. Elles sont tolérées tant qu'elles sont en cours de résorption ou qu'une contrainte technique claire les justifie.

## 6. Checklist avant merge

Avant de valider une modification, vérifier :

1. Est-ce que cette modif ajoute un concept qui aurait pu rester un `Block` ?
2. Est-ce qu'elle propage `shared` ou `LOCATION` au lieu de réduire la dette ?
3. Est-ce qu'elle ajoute un accès direct UI -> `services` ?
4. Est-ce qu'elle ajoute un nouveau `block.content.get(...)` alors qu'un accesseur existe ?
5. Est-ce que la doc décrit honnêtement l'état actuel et l'état cible ?

Si une réponse est "oui", la modif doit être justifiée ou revue.

## 7. Prochaine étape utile

Pour rendre ce driver réellement opposable automatiquement, ajouter ensuite :

1. un contrôle d'import UI -> `services`
2. un contrôle de nouveaux usages interdits de `block.content.get(...)`
3. un contrôle empêchant l'introduction de `BlockDomain.LOCATION` dans les flux de création
