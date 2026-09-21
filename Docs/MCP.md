# Adaptateur MCP

Installer l'extra `mcp`. L'implémentation utilise le SDK officiel Python, version 1.30.0
épinglée explicitement. La ligne v2 n'est pas substituable sans migration.
Références : [SDK officiel](https://github.com/modelcontextprotocol/python-sdk),
[documentation v1](https://py.sdk.modelcontextprotocol.io/v1/).

Commande autonome : `cytool-test --data-dir ./mcp-data mcp`.
Le processus expose les opérations sous les noms `op_<operationId>` et un schéma
généré depuis inputSchema. L'enveloppe d'appel est :

```json
{"parameters":{"text":"Bonjour"},"priority":"Normal"}
```

backendId et modelId sont optionnels et restent distincts des paramètres métier.
L'appel retourne immédiatement un job. Interroger cy_get_job avec jobId jusqu'à
Completed, Cancelled ou Failed. Un job Failed est un échec métier, même si la requête
MCP de consultation elle-même réussit.

Contrôles fournis : cy_describe, cy_status, cy_list_jobs, cy_get_job, cy_cancel_job,
cy_events, cy_can_run. Les erreurs de validation/appel MCP sont marquées isError.
Les données sont disponibles comme contenu texte JSON et structuredContent.result.
Progression et événements utilisent le polling CyTools ; les notifications MCP de
progression temps réel ne sont pas encore émises.

Pour plusieurs clients sur une même instance : créer leurs identités, lancer serve,
puis configurer chaque pont avec son CYTOOLS_TOKEN et la commande :

```text
cytool-test --connect http://127.0.0.1:8766/v1 mcp
```

La session est créée par le pont. Aucun clientId/owner arbitraire n'est accepté dans
les arguments d'une opération. Déconnecter le pont d'un service n'annule pas les jobs
du service ; les retrouver par cy_list_jobs à la reconnexion. En mode autonome, l'arrêt
du processus ferme son runtime et demande l'annulation des jobs restants.

La suite de tests initialise un client officiel réel, découvre op_echo, l'appelle,
consulte le résultat et vérifie une entrée invalide. Cela valide l'échange SDK-à-SDK
local ; cela ne prétend pas avoir modifié ni testé la configuration de tous les clients IA.
