# Adaptateur MCP

La communication utilise CyMCPSDK C++ 0.7.1. Installer le wheel natif du Core,
ou compiler Native/ avant une installation source. Aucun SDK MCP Python n’est
chargé par le serveur ; il sert uniquement de client de test. Voir
[NativeCommunication.md](NativeCommunication.md).

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
les arguments d'une opération. Déconnecter le pont termine ses propres tâches temporaires et demande leur
annulation/nettoyage ; cela ne termine pas les tâches des autres clients. En mode autonome, l'arrêt
du processus ferme son runtime et demande l'annulation des jobs restants.

La suite de tests initialise un client officiel réel, découvre op_echo, l'appelle,
consulte le résultat et vérifie une entrée invalide. Cela valide l'échange SDK-à-SDK
local ; cela ne prétend pas avoir modifié ni testé la configuration de tous les clients IA.
