# Workers et libération

`ProcessWorker(command: list[str], cwd=None, startup_timeout=10, idle_timeout=60)`
possède un processus lancé sans shell. Entrée sur stdin :

```json
{"protocolVersion":"1.0","parameters":{"text":"hello"},"workspace":"/job/workspace"}
```

Le programme lit cette valeur JSON jusqu'à EOF et retourne **une valeur JSON** sur
stdout, puis termine avec code 0. Ses diagnostics vont sur stderr. Un code non nul
donne WorkerCrashed ; une sortie non JSON donne ProtocolError. La sortie est ensuite
validée contre l'outputSchema de l'opération. Voir `Examples/worker_echo.py`.

Usage : `runtime.register('operation', worker.run)`. Le worker est one-shot et peut
être relancé après un crash. Sa durée de réponse est bornée par idle_timeout et le
deadline du job. Il ne possède pas encore de handshake ready ni heartbeat actif ;
startup_timeout est réservé au contrat d'adaptateurs persistants. health() retourne
état, PID, vivant et dernière réponse observée, avec heartbeatSupported:false.

Les états utilisés sont Stopped, Starting, Busy, Stopping et Failed. Idle, Loading,
Ready et Unloading sont des états prévus pour un adaptateur persistant. Un modèle
partagé et son protocole de commandes doivent être implémentés par cet adaptateur.

ReleaseResources accepte Temporary, Job, Model, Worker, All. Sur le worker one-shot,
les trois premiers n'ont pas de cache résident à libérer ; Worker/All arrêtent le process.
Le runtime refuse cette opération globale pendant un job actif et exige manageResources.
Les workers enregistrés peuvent conserver une réservation `worker:<id>` ; elle est
retirée après leur arrêt. Un adaptateur personnalisé implémente release(level).

L'arrêt tente de terminer les descendants encore rattachés via psutil, attend puis
force ceux qui persistent. Un processus qui se détache volontairement, ou un service
extérieur, demande un contrôle spécifique au backend/OS. Le Core ne garantit pas
la libération d'un contexte GPU appartenant à un processus qu'il ne possède pas.

Pour les modèles persistants, Never/AfterJob/After1Minute/After5Minutes/After15Minutes/
WhenResourcesNeeded/Custom sont des politiques décrites dans le manifest, dont
l'application temporelle relève de l'adaptateur. La V1 ne prétend pas les appliquer
à un modèle arbitraire sans son code de déchargement.
