# Jobs

Source normative : `schemas/job.schema.json`. Un job possède jobId, clientId,
sessionId, workspaceId, toolId, operationId, backendId, modelId, parameters, priority,
createdAt, startedAt, finishedAt, state, progress, outputs, error et resourceEstimate.
Les identifiants sont des UUID aléatoires. Les dates sont UTC ISO 8601.

Cycle implémenté : Created → Queued → éventuellement WaitingForResources → Preparing
→ Running → Completed ou Failed. Une annulation en attente va directement à Cancelled ;
en exécution elle passe par Cancelling, puis Cancelled lorsque le handler s'arrête.
Une expiration d'exécution donne Failed avec code Timeout après arrêt effectif.
LoadingModel et Paused sont réservés pour les adaptateurs futurs, pas des commandes
de pause universelles déjà disponibles.

`runtime.submit(principal, session_id, operation_id, parameters, ...)` retourne le job.
`runtime.wait(principal, job_id, timeout)` attend sans annuler à l'expiration de ce délai
de consultation. `queue_timeout` et `execution_timeout` sont des délais de job distincts.

La progression peut contenir percent, currentStep, currentStepIndex, stepCount,
etaSeconds, currentFile, previewAvailable, statusMessage. Le Core transporte ces
données ; il ne calcule pas une ETA fiable à la place du backend.

La reprise du processus marque Interrupted les jobs restés non terminaux. Historique
et sorties demeurent consultables avec le même jeton client. Aucune relance automatique.
