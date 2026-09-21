# Ressources

Source : `schemas/resources.schema.json`. Les champs exécutables sont ramBytes,
vramBytes (map deviceId → octets), diskBytes, temporaryDiskBytes, cpuThreads.
Le ledger additionne disque permanent et temporaire. Tous les montants sont >= 0.
Une réservation propriétaire est unique, et libérée seulement lorsque son travail cesse.

Les métadonnées CPU/GPU, networkRequired, durationSeconds, preferredDevice,
fallbackOptions, ram et vram décrivent les besoins plus fins. RAM/VRAM peuvent préciser
minimum, recommended, estimatedLoaded, estimatedRuntime, estimatedPeak, observedPeak.
Dans cette version, les adaptateurs doivent convertir ces profils en budgets scalaires
effectifs ; le scheduler ne devine pas une correspondance entre profil et hardware.
Les minimums de cœurs/threads CPU, instructions requises, GPU obligatoire, vendors et
computeBackends déclarés font l'objet de contrôles explicites dans CanRun.

`EstimateResources` combine les valeurs backend, modèle, opération, puis les valeurs
renvoyées par l'estimateur, dans cet ordre de priorité. Les maps VRAM sont remplacées,
pas additionnées implicitement. `CanRun` valide les paramètres, la sélection, les plateformes,
les dépendances obligatoires et la capacité totale. Il indique séparément si le job
doit attendre des ressources déjà réservées. Un mode offload ou reducedSettings doit
être implémenté par le backend ; le Core ne réduit jamais silencieusement la demande.

`GetSystemResources` mesure RAM et CPU via psutil, disque libre, OS et architecture.
NVIDIA est découvert via nvidia-smi si présent. La découverte GPU n'est pas exhaustive :
AMD, Intel, Metal, DirectML et les instructions CPU spécialisées nécessitent un provider.
`gpuDiscoveryComplete: false` empêche de présenter une absence de détection comme une
preuve d'absence de GPU.

Le budget par défaut est capturé au démarrage. Un hôte peut injecter `capacity` et
`system` pour tests, politique de quota ou provider externe. Les réservations coordonnent
un runtime, pas les autres programmes de l'OS ; prévoir une marge pour ces programmes.
Elles ne sont pas une limite matérielle de mémoire imposée au backend.

`context.observe_resources(usage, profile)` persiste une mesure observée avec jobId,
timestamp et profil libre. Les profils peuvent indexer version du Tool, backend, modèle,
plateforme, compute backend, précision, quantization et profil de paramètres.
Le Core ne prétend pas mesurer automatiquement la VRAM propre à un job.
