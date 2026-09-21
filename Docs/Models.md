# Backends et modèles

Un backend a id/name, une liste models et éventuellement version, plateformes,
dépendances et exigences de ressources. Il déclare explicitement shareableModelInstance,
threadSafe, concurrentInference et maxConcurrentInference.

Un modèle a id/name/version, source, licence, fichiers, tailles de téléchargement et
d'installation, plateformes, computeBackends, précisions, quantizations, profils de
ressources et capacités. Local, Remote et Hybrid décrivent son emplacement ;
runsLocally précise l'exécution et networkRequired le besoin de connexion.

Les fichiers possèdent path, url, sha256, sizeBytes, et éventuellement etag/revision.
Ils sont des métadonnées, pas une autorisation d'installer des exécutables automatiquement.
L'adaptateur appelle DownloadManager après les décisions de licence/authentification
requises par sa source, puis met à jour l'état installé fourni au runtime.

ListModels retourne les modèles déclarés avec backendId. Une sélection modelId
inconnue ou un modèle local non installé donne MissingModel. Les modèles distants
ne requièrent pas un fichier local ; le backend doit vérifier son authentification.

CyToolsCore ne télécharge pas un modèle sur la seule base d'une requête de génération
et n'embarque pas de chargeur PyTorch. La notion de modèle reste facultative.
