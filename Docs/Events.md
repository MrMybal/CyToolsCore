# Événements et logs

Les événements contiennent sequence, type, timestamp, toolId, data et les identités
clientId/sessionId/jobId lorsqu'elles s'appliquent. Le compteur est local à l'exécution
du runtime ; il repart à zéro après redémarrage.

GetEvents(after) retourne les événements autorisés, cursor à transmettre au prochain
appel et gap lorsque des événements demandés ont été évincés du buffer borné.
Le client doit aussi réinitialiser son curseur si cursor devient inférieur au précédent.
L'état de job persistant est la référence après perte d'événements.

Émissions V1 : ToolStarted/ToolStopping, SessionCreated/SessionClosed, JobCreated,
JobQueued, JobWaitingForResources, JobPreparing, JobStarted, JobProgress, JobCancelling,
JobCancelled, JobCompleted, JobFailed, ResourceReservationCreated/Released, Log.
Les événements de modèles, previews, téléchargements ou connexions persistantes
peuvent être ajoutés par leurs adaptateurs ; ils ne sont pas simulés comme preuves.

`context.log(message, level)` ajoute un log corrélé au job. Conventions de niveau :
Trace, Debug, Info, Warning, Error, Critical. Le buffer en mémoire n'est pas une
archive de logs durable ; un hôte peut exporter les événements dans son journal.
