# CyTools protocol 1.0

Sources normatives : schemas/request.schema.json et response.schema.json.
Les mêmes objets s'utilisent sur JSONL stdio et HTTP POST /v1.
HTTP exige Content-Length et un corps JSON UTF-8 (pas de requête chunked dans ce serveur V1).

```json
{"protocolVersion":"1.0","id":1,"method":"DescribeTool","params":{}}
```

```json
{"protocolVersion":"1.0","id":1,"result":{"id":"cy.tool.test"}}
```

La seconde réponse illustre seulement l'enveloppe ; DescribeTool retourne le manifest
complet. Une réponse contient exactement result ou error. id est recopié ; les clients
doivent corréler les IDs. JSONL traite les commandes dans l'ordre ; les jobs lancés
restent concurrents. Pas de batch JSON-RPC implicite : c'est le protocole CyTools.

| Méthode | params | Résultat |
|---|---|---|
| DescribeTool | {} | manifest |
| GetCapabilities | {} | liste |
| ListOperations | {} | descripteurs |
| DescribeOperation | operationId | descripteur |
| ListBackends | {} | descripteurs |
| ListModels | backendId optionnel | modèles avec backendId |
| GetRuntimeStatus | {} | métriques et budget |
| GetSystemResources | {} | mesures système |
| EstimateResources | operationId, parameters, backendId?, modelId? | estimation |
| CanRun | mêmes champs | canRun, status, estimate, waitingForResources |
| Diagnose | {} | système et handlers |
| CreateSession | temporary? (true), retentionSeconds? (3600) | sessionId, clientId, createdAt, closed, temporary, expiresAt |
| CloseSession | sessionId | session fermée ; Busy si jobs actifs |
| SubmitJob | sessionId, operationId, parameters, backendId?, modelId?, priority?, queueTimeout?, executionTimeout? | job |
| GetJob | jobId | job autorisé |
| ListJobs | {} | jobs autorisés |
| CancelJob | jobId | job après demande d'annulation |
| ShareJob | jobId, visibility, sharedWith? | job |
| GetEvents | after optionnel, défaut 0 | events, cursor, gap |
| ReleaseResources | level | résultat ; permission manageResources |

Les noms de champs réseau utilisent camelCase. L'API Python emploie snake_case pour
les arguments des méthodes Runtime ; LocalClient.call conserve les noms réseau.
Un code C++/C# peut sérialiser ces objets avec son propre parseur JSON ; aucune
représentation binaire ou import Python n'est nécessaire.

Les IDs clients ne sont pas des credentials. HTTP utilise Authorization: Bearer TOKEN.
Les sessions sont créées après authentification, les workspaces uniquement par le serveur.
Un client ne fournit ni chemin de workspace ni identité propriétaire dans SubmitJob.


## Temporary tasks (SDK 0.9.0)

See [TaskFiles.md](TaskFiles.md). ImportFile(sessionId, source, companions?) returns an automatically staged path. ExportJob(jobId, destination) preserves a bundle outside the runtime. FinishTask(sessionId, cancelRunning?) removes task artifacts after workers stop; KeepTaskAlive(sessionId) renews idle retention. CloseSession also cleans temporary tasks. MCP exposes cy_import_file, cy_export_job, cy_finish_task, cy_begin_task and cy_keep_task_alive.
