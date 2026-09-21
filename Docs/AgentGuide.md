# Créer un CyTool avec une IA

Ce document est le contrat de travail à fournir à une IA chargée de créer un Tool.
Il s'applique à Codex, Claude, OpenCode ou tout autre assistant, sans dépendance au client.

## Résultat attendu

Lire [StandaloneDiagnosticsAndModels.md](StandaloneDiagnosticsAndModels.md) : journal
sélectionnable/copiable, pixels vidéo visibles, bibliothèque de dérivés, LoRA compatibles
et sélection CPU/GPU réelle, enregistrés dans les configurations de génération.

Pour les Tools de maillage (génération, remesh, PBR, UV, rig), lire
[MeshViewer.md](MeshViewer.md) : utiliser `--desktop --mesh-viewer` et fournir le
viewport interactif avec résultat automatique, caméra libre/orbitale et éclairage.

Interface anglaise par defaut, francaise en option. Lire [Localization.md](Localization.md) :
onglet Options, preferences persistantes, theme/taille du texte et licences de chaque composant.
Lire [SharedInstallation.md](SharedInstallation.md) : cache local/partagé configurable,
CUDA Toolkit enregistré et sélectionné explicitement, Python privé et installation
guidée des composants absents, avec états d'accès structurés utilisables par une IA.

Une application autonome avec interface **Dear ImGui obligatoire**, un vrai lanceur
Windows `.exe`, un lanceur Linux adapté et une racine rangée `app/data/runtime`.
Le manifeste et les sources résident dans `app/`. Les modèles et résultats sont dans
`data/`. La CLI et le MCP complètent l'interface. Lire et appliquer intégralement
[StandaloneDelivery.md](StandaloneDelivery.md) : installation guidée des modèles,
autorisations/licences, mises à jour GitHub, restauration et contrôles de livraison.
Ne pas créer CyToolsManager et ne pas ajouter une dépendance UI au Core.

## Informations à déterminer avant l'implémentation

| Information | Exemple | Emplacement |
|---|---|---|
| Nom et ID stable | CyToolExample / cy.tool.example | name / id |
| Version métier | 0.1.0 | version |
| Opérations | echo, convert, inspect | operations |
| Entrées et contraintes | text requis, steps entre 1 et 100 | inputSchema |
| Sorties exactes | objet avec file et mimeType | outputSchema + outputs |
| Exécutable externe | python, ffmpeg, programme natif | runtimeRequirements |
| Plateformes | Windows x64 Supported ; macOS Unknown | platforms |
| Backends / modèles | moteur, versions, fichiers, licences | backends[].models[] |
| Budget par job | RAM, VRAM par device, disque, threads CPU | resourceRequirements / estimate |
| Parallélisme sûr | Sequential par défaut | concurrency |
| Effets et accès nécessaires | network, filesystemExternal | permissions |
| Répertoire de données | chemin dédié au Tool/service | --data-dir |
| Transport | CLI seule, service partagé, pont MCP | commandes de lancement |

Si une valeur est inconnue, l'écrire comme telle. Ne pas inventer une consommation
VRAM, une compatibilité GPU ou un modèle installé. Les booléens de capacité décrivent
le code livré, pas un objectif futur. Toutes les tailles sont en **octets**, les durées
en **secondes**, la progression entre **0 et 100**.

## Procédure reproductible

1. Installer le SDK depuis le dépôt local ou le wheel fourni ; Python >= 3.11.
2. Exécuter `cytools new CHEMIN --name CyToolExample --id cy.tool.example --desktop`.
3. Lire les fichiers générés et conserver le point d'entrée `run_cli(create_runtime)`.
4. Remplacer l'opération echo par les opérations du Tool dans `CyTool.json`.
5. Implémenter un handler par opération et les enregistrer dans `create_runtime`.
6. Déclarer les ressources fixes ; ajouter un estimateur si elles dépendent des paramètres.
7. Isoler un runtime lourd dans `ProcessWorker` ; définir son protocole de sortie JSON.
8. Ajouter des tests du comportement réel, des entrées invalides, de l'annulation,
   de l'échec métier, des sorties et de l'isolation de deux clients.
9. Exécuter validation du manifest, tests du Tool, CLI describe/invoke et test MCP.
10. Finaliser ImGui, le parcours d'installation des modèles et les mises à jour GitHub.
11. Compiler/packager les lanceurs ; ranger la distribution et tester le lancement réel.
12. Documenter installation, configuration, dépendances, modèles, preuves et limites.

## Contrat Python exact

```python
from pathlib import Path
from cytools_core import Runtime, load_manifest, CyToolError
from cytools_core.transports.cli import run_cli

def create_runtime(data_dir, **options):
    runtime = Runtime(load_manifest(Path(__file__).with_name('CyTool.json')),
                      data_dir, **options)

    def write_report(context, parameters):
        context.cancellation.check()
        path = context.path('outputs/report.txt')
        path.write_text(parameters['text'], encoding='utf-8')
        context.progress(100, currentStep='Written', currentStepIndex=1, stepCount=1)
        return {'file': str(path), 'mimeType': 'text/plain'}

    def estimate(parameters, backend, model):
        # Remplacer cet exemple par une estimation conservatrice du vrai traitement.
        return {'ramBytes': 1048576,
                'diskBytes': len(parameters['text'].encode('utf-8'))}

    runtime.register('write_report', write_report, estimate=estimate)
    return runtime

if __name__ == '__main__':
    raise SystemExit(run_cli(create_runtime))
```

Ce code exige une opération `write_report` dans le manifest. Son `inputSchema`
doit contenir `text` string requis ; son `outputSchema` doit contenir `file` et
`mimeType` string requis. Déclarer `supportsProgress: true`, `canCancel: true`,
`canRunAsync: true`. `file` peut porter `x-cy-kind: File` pour une future UI.

Le handler reçoit une copie validée des paramètres, avec les valeurs par défaut
appliquées. Il retourne un objet JSON conforme à outputSchema. Un retour invalide
fait échouer le job avec `InvalidOutput`. Pour un échec attendu, lever
`CyToolError('MissingDependency', 'Message utile', recoverable=True)`.

Ne pas appeler `runtime.start()` dans la factory : le lanceur et les tests gèrent
le cycle de vie. Ne pas imprimer sur stdout depuis les handlers ; utiliser
`context.log(message, level='Info')`. Les opérations natives longues doivent appeler
`context.cancellation.check()` régulièrement. Le Core ne peut pas interrompre de force
un thread Python ; un programme non coopératif doit être isolé dans un worker.

## Paramètres conditionnels et UI

Employer JSON Schema 2020-12 : type, properties, required, default, enum, minimum,
maximum, multipleOf, items, $defs/$ref locaux et if/then/else. Ne pas créer de dialecte
de validation concurrent. Utiliser `x-cy-kind` et `x-cy-ui` pour les informations visuelles.
Exemple complet dans [Parameters.md](Parameters.md). Le format file est une annotation,
pas une permission automatique de lecture d'un fichier arbitraire.

## Backends et modèles

Une opération sans backend utilise `supportedBackends: []` et n'a pas besoin de modèle.
Si un seul backend est déclaré pour l'opération, il est sélectionné par défaut.
Avec plusieurs backends, fournir backendId explicitement. modelId est facultatif mais,
si fourni, doit appartenir au backend et être installé pour une exécution locale.
L'estimateur reçoit `(parameters, backend_descriptor_or_None, model_descriptor_or_None)`.
Les métadonnées d'un modèle ne constituent pas son implémentation : son installation,
son chargement et son exécution appartiennent à l'adaptateur du Tool.

Pour 10 Gio de VRAM : `{'vramBytes': {'auto': 10 * 1024**3}}` choisit un GPU admissible ;
`{'vramBytes': {'0': 6 * 1024**3, '1': 6 * 1024**3}}` réserve deux GPU.
Le backend doit effectivement savoir répartir le calcul. Ne pas mettre `simulation`
dans un vrai Tool : ce device appartient aux tests.

## Partage entre plusieurs clients

Pour partager une file et un modèle, démarrer **un service** et connecter les clients
avec des jetons distincts. Voir [MultiClient.md](MultiClient.md). Plusieurs processus
MCP autonomes lancés dans des dossiers différents ont des runtimes différents.
Ne pas prétendre qu'ils partagent automatiquement leur VRAM ou leurs modèles.

## Définition de terminé

Appliquer aussi tous les critères de [StandaloneDelivery.md](StandaloneDelivery.md).
La génération d'un squelette ou une commande CLI réussie ne suffit pas.

L'interface Dear ImGui doit respecter [Localization.md](Localization.md) : anglais
par défaut, français sélectionnable et onglet Options avec préférences et licences.
Appliquer [GenerationConfigurations.md](GenerationConfigurations.md) : sauvegarde et
chargement du formulaire, autosave optionnelle des paramètres soumis, JSON versionné
réutilisable par une IA et exclusion des secrets. Vérifier un aller-retour réel du
formulaire et un rejeu via le runtime. Le chargement ne démarre jamais la génération.

- `cytools validate CyTool.json` réussit.
- La CLI décrit toutes les opérations implémentées et exécute un cas réel.
- Les sorties valident outputSchema ; les chemins créés restent dans le workspace.
- Un client B ne lit ni n'annule un job privé du client A.
- L'annulation libère réellement le worker avant les réservations.
- Un paramètre incorrect et une dépendance absente donnent un code d'erreur utile.
- Le catalogue MCP est dérivé du manifest et l'appel crée un job consultable.
- README donne des commandes testées et les variables d'environnement exactes.
- Les plateformes testées sont distinguées des plateformes simplement déclarées.

Pour un SDK natif C++/C#, reproduire le protocole et les mêmes fixtures de conformité.
Une première intégration peut déjà utiliser le service HTTP ou un worker JSON stdin/stdout.
Ne pas réécrire le scheduler dans chaque Tool.


Lire [FullOperationAccess.md](FullOperationAccess.md) : inventaire des capacités natives, parité complète des options métier entre IA et standalone, contrats de sorties composables et preuves de validation. Un formulaire simplifié ne limite pas le contrat du Tool.

Lire Docs/AutomaticInputs.md (AutomaticInputs.md depuis Docs) : chemins absolus acceptés pour les entrées locales, copie automatique privée par job, aucune copie manuelle exigée de l’IA.


## Task-owned files (SDK 0.9.0)

Read Docs/TaskFiles.md (TaskFiles.md from this Docs directory). Configure input roots and all file fields for automatic imports; AI sessions are temporary by default. FinishTask removes imported copies and generated workspaces after workers stop; export wanted results first. Standalone sessions explicitly use temporary=False.
