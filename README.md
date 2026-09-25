# CyToolsCore

Socle autonome pour créer des CyTools : standard JSON v1, SDK/runtime Python,
jobs, sessions, isolation des clients, réservation de ressources et adaptateurs
CLI, JSONL, HTTP local et MCP. Version du SDK : **0.9.0** ; schéma : **1** ; protocole : **1.0**.

Chaque Tool embarque ou référence ce SDK. Aucun CyToolsManager, modèle IA,
compte fournisseur ou composant graphique n'est nécessaire.

## Démarrer sous Windows

Depuis ce dossier, avec Python 3.11 ou plus récent :

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --keyring-provider disabled -e '.[mcp,dev]'
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\cytool-test describe
.\.venv\Scripts\cytool-test invoke progress_test
```

Sous Linux/macOS, remplacer `.venv\Scripts\` par `.venv/bin/`.
L'extra `mcp` est optionnel ; `pip install -e .` suffit pour le runtime et la CLI.

## Créer un Tool

```powershell
.\.venv\Scripts\cytools new .\Examples\CyToolSample --name CyToolSample --id cy.tool.sample --desktop
.\.venv\Scripts\cytools validate .\Examples\CyToolSample\app\CyTool.json
.\.venv\Scripts\python .\Examples\CyToolSample\app\tool.py invoke echo --params-file .\Examples\CyToolSample\app\params.json
```

Le mode `--desktop` fournit une racine `app/data/runtime`, une façade ImGui et les sources
du lanceur natif à compiler. Il reste à finaliser l’interface métier, l’installation et
les mises à jour selon [StandaloneDelivery](Docs/StandaloneDelivery.md).
L'onglet Options fournit anglais/francais, theme, taille du texte, licences et sauvegardes
de configurations de generation reutilisables par les clients IA.

Pour un Tool de maillage, ajouter `--mesh-viewer` : aperçu interactif des résultats,
navigation orbitale/libre, zoom rapproché et éclairages studio/soleil. Voir
[Visualisation 3D](Docs/MeshViewer.md) pour l'intégration et les contrôles requis.

Le générateur refuse d'écraser un dossier non vide. Il crée `CyTool.json`, `tool.py`,
`test_tool.py`, `AGENTS.md`, `README.md`, `params.json` et les indications d'installation.
Il fournit aussi `CyToolsGuide.md` et une copie de la documentation du SDK.
`cytools docs` retrouve la documentation complète installée, y compris depuis un wheel.
Le Tool dispose immédiatement des commandes `describe`, `list-operations`, `invoke`,
`diagnose`, `stdio`, `serve`, `create-client` et `mcp`.

**Pour une IA qui doit créer un Tool : commencer par [Docs/AgentGuide.md](Docs/AgentGuide.md).**
Le [prompt prêt à copier](Docs/AgentPrompt.md) fournit un point d'entrée indépendant
du client IA utilisé. Le tutoriel humain est [CreatingYourFirstCyTool](Docs/CreatingYourFirstCyTool.md).

Les standalones disposent d’un journal sélectionnable/copiable et de contrats pour
la résolution vidéo, les modèles dérivés, les LoRA et le choix CPU/GPU : voir
[Journaux et modèles](Docs/StandaloneDiagnosticsAndModels.md).

## Organisation

| Dossier | Rôle |
|---|---|
| `cytools_core/schemas/` | Contrats JSON Schema 2020-12, source de vérité du standard |
| `cytools_core/` | Validation, runtime, stockage, ressources, workers, téléchargements |
| `cytools_core/transports/` | Façades séparées ; même identité et même runtime |
| `cytool_test/` | Tool de référence avec sept opérations sans IA |
| `Tests/` | Tests d'intégration, concurrence, téléchargements, workers, HTTP et MCP réel |
| `Docs/` | Contrat, tutoriel, guide IA, limites et décisions d'architecture |
| `Examples/` | Exemples de clients et de worker portable |

Voir [l'état des fonctionnalités](Docs/ImplementationStatus.md) et
[le compte rendu de validation](Docs/Validation.md) avant une intégration métier.
Les SDK natifs C++/C# ne sont pas livrés : ces langages peuvent déjà utiliser le protocole
JSON ou être exécutés comme workers. Linux/macOS disposent d'une matrice CI ; un test
local Windows ne constitue pas une validation exécutée sur ces plateformes.

## Premier modèle testé : CLAP

[CyToolCLAP](Tools/CyToolCLAP/README.md) est un Tool séparé pour classer sons et musique
avec un modèle local. Quatre extraits publics (chien, pluie, trompette, piano) ont été
testés, ainsi qu'une inférence par MCP. Ses dépendances et poids restent hors du Core.

Stockage local/partagé et CUDA Toolkit : voir [SharedInstallation.md](Docs/SharedInstallation.md).


Accès avancé et orchestration IA : [contrat de couverture](Docs/FullOperationAccess.md).

Plugins Unreal et connecteurs IA : [CyUEMCPSDK et connecteurs intégrés](Docs/UnrealIntegration.md).

## Licence

Copyright (C) 2026 Cyberalien.

CyToolsCore est distribué sous la **GNU General Public License, version 3 uniquement**
(`GPL-3.0-only`). Voir le texte complet dans [LICENSE](LICENSE).

Vous pouvez redistribuer et modifier ce programme selon les termes de cette licence.
Il est fourni sans aucune garantie, notamment sans garantie de qualité marchande ou
d'adéquation à un usage particulier. Les dépendances et modèles tiers conservent
leurs licences respectives.
