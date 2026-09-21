# Stockage des installations et téléchargements

SDK 0.4.0. Python et les bibliothèques propres à chaque moteur restent privés au
Tool. Le pilote NVIDIA est un composant système ; ne pas l'installer, remplacer ou
supprimer automatiquement. Une distribution publique exclut poids, environnements
lourds et caches ; elle livre ses catalogues, installateurs et instructions.

## Options communes

Chaque interface ImGui fournit Options > Installation storage : cache local ou
partagé, dossier partagé configurable, enregistrement d'un CUDA Toolkit existant
et sélection par Tool. Un changement prend effet au prochain lancement, après la
fin des jobs. Aucune migration ni suppression automatique des installations.

Le chemin commun est enregistré sous `%LOCALAPPDATA%/CyTools/installation-storage.json`
sous Windows, `$XDG_CONFIG_HOME/cytools` (sinon `~/.config/cytools`) sous Linux.
`CYTOOLS_SETTINGS_DIR` permet un emplacement explicite. Chaque Tool conserve son
choix dans `data/settings/installation-storage.json`. Aucun registre Windows requis.

## Ce que le SDK implémente

- `InstallationStorage` dans `cytools_core.shared_installation`, import sans effet
  sur l'environnement. `apply_environment()` est appelé explicitement par le Tool.
- Cache pip, Hugging Face Hub et Torch Hub local/partagé via variables de processus.
  `HF_HOME` et les magasins de jetons ne sont pas déplacés. Les installateurs utilisant
  `local_dir`, un cache explicite ou `--no-cache-dir` ne sont pas dédupliqués par magie.
- DownloadManager réutilise automatiquement le cache partagé lorsqu’un SHA256 est fourni ; la copie installée reste privée.
- Téléchargement vérifié `storage.download(url, sha256=..., size=...)`, cache par hash,
  verrou interprocessus et reprise du DownloadManager. Il ne lance pas d'installateur.
- CUDA Toolkit enregistré par chemin, version complète détectée, plateforme et hash
  du compilateur ; sélection explicite par Tool. Au démarrage, CUDA_HOME/CUDA_PATH
  et le PATH du processus pointent vers ce Toolkit. Aucun PATH système n'est modifié.
- `installation_storage_status` expose un état structuré via le runtime CLI/MCP
  existant lorsque `register_operations(runtime, tool_root)` est appelé avant start.
- `app/installation_ui.py` fournit aussi status, configure, register-cuda et select-cuda
  en CLI JSON pour une IA. Ces mutations sont des actions locales explicites.

Le cache partagé économise les transferts, pas nécessairement les copies installées.
Un CUDA Toolkit partagé évite son installation pour chaque Tool. PyTorch conserve
ses propres bibliothèques CUDA ; ne jamais les remplacer par des DLL globales.
Les modèles déjà installés restent à leur emplacement actuel : la mutualisation
des dossiers de poids n'est pas implémentée par cette version.

## Intégration obligatoire

1. Déclarer les composants, versions exactes, tailles, hashes, URLs et licences dans
   le catalogue du Tool. Décrire séparément cache de téléchargement et installation.
2. Appeler `apply_environment()` avant les imports des clients de téléchargement et
   les sous-processus. Les workers héritent de l'environnement. Python reste privé.
3. Pour des téléchargements HTTPS personnalisés, utiliser `storage.download` avec
   SHA256 et traiter ses états ; copier/installer ensuite dans un emplacement privé,
   ou utiliser un adaptateur d'installation partagée explicitement validé.
4. Ne proposer un Toolkit que si sa version est compatible avec le moteur ; les
   templates ne connaissent pas les contraintes de tous les moteurs. Tester les
   extensions qui l'utilisent. Enregistrer un Toolkit ne certifie pas cette compatibilité.
5. Ne pas mettre à jour ni supprimer un composant partagé depuis un Tool. Cette
   version n'expose aucune suppression partagée ni gestion automatique des pilotes.
6. Conserver les installations en cours et les données utilisateur lors des mises à jour.

## Accès aux modèles et premier lancement

Avant génération : diagnostic des composants manquants, choix d'emplacement, taille,
licence, source, téléchargement/reprise explicites, puis validation réelle des fichiers.
L'interface et l'IA doivent recevoir un état distinct pour téléchargement, installation,
échec, connexion nécessaire et action utilisateur nécessaire. Ne pas annoncer Ready
sur la seule présence d'un dossier. Une configuration n'accepte jamais une licence.

`storage.download(..., license_accepted=False)` renvoie LicenseAcceptanceRequired
avec source et action. HTTP 401/403 renvoie AccessRequired : ne pas affirmer qu'un 403
prouve une licence non acceptée. Fournir le lien officiel du modèle, les instructions
de connexion locale Hugging Face et la possibilité de réessayer après intervention.
Le Tool doit distinguer les causes plus précisément lorsque le fournisseur le permet.
Ne jamais écrire un jeton dans configuration, URL, argv, job, cache partagé ou journal.

## Vérifications

Tester chemins configurables, modes indépendants par Tool, verrou concurrent, hashes,
CUDA absent/modifié, états d'accès et absence de déplacement des modèles. Tester le
panneau EN/FR. Distinguer les tests avec faux compilateur d'un vrai moteur CUDA exécuté.

Contrat des préférences : cytools_core/schemas/installation-storage.schema.json.
