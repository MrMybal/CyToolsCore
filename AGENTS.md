# CyToolsCore — règles de développement

Lire README.md, Docs/AgentGuide.md, Docs/Architecture.md et Docs/ImplementationStatus.md.
Pour créer un nouveau Tool, utiliser `cytools new`; ne pas copier le runtime.

- Les fichiers cytools_core/schemas/*.schema.json définissent le contrat portable.
- Le SDK Python est l'implémentation de référence ; aucun contrat différent pour C++/C#.
- Toute opération déclare ses entrées, sorties, plateformes, permissions et ressources.
- Les identités viennent du transport authentifié. Ne jamais prendre le clientId d'un paramètre métier.
- Conserver les réservations jusqu'à l'arrêt réel du handler/worker, même après une demande d'annulation.
- Ne pas écrire les outputs dans un dossier partagé : utiliser JobContext.path.
- Le Core ne charge ni UI, ni runtime IA, ni serveur MCP par simple import.
- Réserver stdout aux sorties structurées en mode CLI/JSONL/MCP ; diagnostics sur stderr.
- Ne pas déclarer supporté ce qui est inconnu ou seulement décrit par un schéma.
- Tests : `.venv/Scripts/python -m pytest -q` (Windows), `.venv/bin/python -m pytest -q` (Unix).
- Distribution : `python -m build --no-isolation`; vérifier les schémas et templates dans le wheel.
- Mettre à jour les docs et la version si un contrat public change.

## Livraison des nouveaux Tools

Tout Tool de maillage suit Docs/MeshViewer.md et utilise `--desktop --mesh-viewer` :
viewport 3D interactif, ouverture du résultat, navigation souris/clavier, orbite/libre,
zoom rapproché, scènes et lumières. Aucune dépendance graphique importée par le Core.

Lire Docs/Localization.md. Anglais par defaut, francais selectionnable. Onglet Options
obligatoire : langue persistante, theme, taille du texte et licences par composant.

Lire Docs/GenerationConfigurations.md. Options doit permettre de sauvegarder et
charger la configuration courante en JSON versionne, reutilisable par une IA,
avec autosave facultative a la generation. Exclure les secrets ; charger ne lance
aucun traitement. Utiliser les callbacks explicites du scaffold pour le formulaire.
Modifier les Tools existants uniquement lorsque leur migration est demandee.
Lire Docs/SharedInstallation.md. Distinguer cache partagé et installation partagée.
Python reste privé ; ne jamais déplacer les modèles, modifier le pilote système ni
remplacer les bibliothèques CUDA de PyTorch lors d'un changement de stockage.

Lire Docs/StandaloneDelivery.md. Utiliser `cytools new --desktop`. Interface Dear ImGui obligatoire dans le Tool, jamais importée par le Core. Livrer un lanceur Windows .exe, un lanceur Linux adapté, une racine app/data/runtime rangée, l’installation guidée des modèles et les mises à jour GitHub avec restauration. Le squelette CLI/MCP seul ne constitue pas une livraison terminée.
# Standalone diagnostics and models

Lire Docs/StandaloneDiagnosticsAndModels.md. Préserver les journaux sélectionnables et
copiables, la résolution vidéo prévue/réelle, les modèles locaux/LoRA compatibles et le
choix CPU/GPU réellement appliqué. Aucun poids ni secret dans les configurations.


Lire [Docs/FullOperationAccess.md](Docs/FullOperationAccess.md) : inventaire des capacités natives, parité complète des options métier entre IA et standalone, contrats de sorties composables et preuves de validation. Un formulaire simplifié ne limite pas le contrat du Tool.

Lire Docs/AutomaticInputs.md (AutomaticInputs.md depuis Docs) : chemins absolus acceptés pour les entrées locales, copie automatique privée par job, aucune copie manuelle exigée de l’IA.


## Task-owned files (SDK 0.9.0)

Read Docs/TaskFiles.md (TaskFiles.md from this Docs directory). Configure input roots and all file fields for automatic imports; AI sessions are temporary by default. FinishTask removes imported copies and generated workspaces after workers stop; export wanted results first. Standalone sessions explicitly use temporary=False.
