# État de l'implémentation 0.9.0

Le schéma CyTools v1 est la base portable ; le SDK 0.9.0 est son implémentation
de référence. Ce fichier distingue ce qui fonctionne de ce qu'un backend doit fournir.

| Domaine | Livré et exécutable |
|---|---|
| Standard | JSON Schema 2020-12 versionné : Tool, paramètres, jobs, événements, ressources, workers, requêtes/réponses |
| Validation | Manifest, IDs/références, paramètres conditionnels, defaults, sorties ; métadonnées extensibles |
| Runtime | Handlers enregistrés, jobs async, priorités, états, progression, erreurs, annulation coopérative, délais queue/exécution |
| Clients | Jetons aléatoires persistés en empreinte, sessions, workspaces distincts, Owner/Shared/Global et filtrage des événements |
| Scheduler | Concurrence bornée, politiques de sérialisation, réservation atomique RAM/VRAM/disque/CPU, attente et libération |
| Ressources | Détection OS/CPU/RAM/disque, NVIDIA optionnel, estimation personnalisable, CanRun, observations persistées |
| Backends/modèles | Descripteurs, sélection, catalogues, contrôles de présence et compatibilité ; profils de ressources |
| Workers | Processus one-shot JSON, arrêt, tentative d'arrêt des descendants, détection de crash, relance, release |
| Downloads | HTTPS, partials persistants, pause/reprise, ETag/Range, SHA256/taille, verify/remove, cache lié à la source |
| Stockage | SQLite, historique des jobs, sessions/clients, settings d'identité, observations, récupération Interrupted |
| Transports | Native Python, CLI JSON, JSONL, HTTP loopback authentifié, MCP stdio officiel et pont vers service partagé |
| Création de Tool | Générateur avec option --desktop, structure app/data/runtime, façade ImGui optionnelle, source du lanceur Windows, script Linux, tests et contrat de livraison |
| Options autonomes | Templates Dear ImGui : anglais par défaut, français, préférences persistantes et informations de licence ; intégration et traductions métier à finaliser dans chaque Tool |
| Diagnostics autonomes | Journal tournant, champ multiligne sélectionnable, copie intégrale, exceptions et événements authentifiés ; stderr des workers conservé dans leur workspace |
| Modèles locaux et exécution | Bibliothèque de références locales versionnée, profils par job, LoRA/intensités et sélections CPU/GPU selon les adaptateurs réellement déclarés ; aucune compatibilité universelle ni distillation générique |
| Visualisation de maillage | Option --desktop --mesh-viewer : panneau ImGui, rendu OpenGL/PBR, résultat automatique, caméra orbitale/libre, scènes et lumières ; dépendances graphiques confinées au Tool |
| Configurations de génération | Schéma JSON versionné, Save/Load, autosave facultative après soumission, exclusion des secrets et rejeu par le runtime ; callbacks explicites de formulaire dans le scaffold |
| Entrées locales automatiques | JobContext.import_input : chemin absolu ou relatif, copie privée bornée/annulable, provenance SHA256, nettoyage après arrêt du handler sur succès/échec/annulation, conservation explicite ; intégré à LocalMesh |
| Fichiers des tâches IA | Import commun automatique sur les champs déclarés des 19 Tools, bundles OBJ/GLTF, export explicite, purge de session/MCP/expiration après arrêt effectif, récupération au redémarrage |
| Interopérabilité | Client C# .NET 8 via contrat HTTP ; worker indépendant du SDK |
| Accès complet aux opérations | Onglet ImGui avancé pour tous les paramètres déclarés ; découverte MCP/CLI détaillée, estimation, backend/modèle, priorités/délais, schéma de job asynchrone et bibliothèque de modèles accessible par opérations |

## Limites explicites

- Pas de SDK natif C++ ou C# complet : wire protocol commun et exemples disponibles.
- Pas de GUI chargée dans le Core. Le scaffold desktop fournit une façade ImGui à finaliser dans le Tool ; pas de CyToolsManager, découverte réseau ou registre global.
- Le Core ne fournit pas un updater GitHub universel : le contrat de livraison impose son implémentation dans le Tool, avec un exemple concret SPAR3D. Le scaffold ne prétend pas télécharger un modèle ou gérer une licence tout seul.
- Pas de scheduler distribué ni de limite OS matérielle ; les réservations sont locales
  au runtime et reposent sur les estimations. Le budget par défaut est capturé au démarrage.
- Chargement de modèle, partage réel des poids, offload, precision/quantization et
  multi-GPU réel nécessitent un backend ; les descriptors seuls ne les exécutent pas.
- Workers persistants avec handshake, heartbeat, pause/reprise, idle unload programmé
  et protocole de déchargement sont des points d'extension, pas simulés comme implémentés.
- Temporary/Job/Model n'ont rien de résident à libérer dans le worker one-shot.
- Les downloads génériques sont disponibles ; un adaptateur de catalogue/compte est
  requis pour l'authentification interactive et la gestion métier d'un dépôt de modèles.
- Le diagnostic des versions de dépendances, des drivers non NVIDIA et des instructions
  CPU requiert un provider. Des instructions CPU requises mais non vérifiées sont refusées.
- Pas de SSE/WebSocket, transport IPC natif, transfert distant de fichiers, OAuth ou
  serveur MCP HTTP direct. MCP stdio peut néanmoins partager le service local via le pont.
- Les événements sont bornés et non persistés ; historique de jobs et observations
  sont persistés. La rétention/purge de gros outputs reste à configurer dans le Tool.
- Annulation native coopérative. Un handler non coopératif garde sa réservation jusqu'à
  son arrêt ; le Core ne libère pas artificiellement son budget.
- Windows x64 testé localement. Les résultats Linux/macOS de la CI restent à exécuter.

Ces limites sont aussi indiquées dans les pages concernées. Les premiers Tools peuvent
déjà utiliser le runtime sans réimplémenter validation, jobs, sessions ou transports.

## Installation partagée (0.4.0)

Cache pip/HF/Torch configurable et cache SHA256 du DownloadManager, verrou interprocessus, référencement de CUDA Toolkit existant avec sélection par Tool et état CLI/MCP. Python et bibliothèques PyTorch restent privés. Aucun installateur CUDA automatique ni migration des poids existants. Voir SharedInstallation.md.
