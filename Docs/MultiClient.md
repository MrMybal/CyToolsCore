# Plusieurs clients sur un même Tool

Pour partager jobs, modèle et budget de ressources, tous les clients doivent joindre
le **même runtime**. Le mode service HTTP local fournit ce point commun.

Provisionner les clients depuis le poste de confiance avant de démarrer le service :

```powershell
cytool-test --data-dir ./service-data create-client --name ClientA
cytool-test --data-dir ./service-data create-client --name ClientB
cytool-test --data-dir ./service-data serve --port 8766
```

Chaque commande create-client affiche une seule fois `{clientId, token}`. Conserver
les jetons dans la configuration privée du client. La base conserve leur empreinte,
pas leur valeur. Ne pas provisionner pendant qu'un service possède ce data-dir.

Dans le terminal de chaque client, utiliser son propre token :

```powershell
$env:CYTOOLS_TOKEN = '<jeton-du-client>'
cytool-test --connect http://127.0.0.1:8766/v1 describe
cytool-test --connect http://127.0.0.1:8766/v1 invoke echo --params-file params.json
```

Un client MCP lance la même commande avec `mcp` au lieu de invoke. Ce pont stdio
parle au service existant ; il ne crée pas un second scheduler. La variable CYTOOLS_TOKEN
appartient au processus du pont. Voir [MCP.md](MCP.md).

Chaque client crée ses sessions. Un identifiant de session ne remplace jamais le jeton.
Un job Owner est privé ; Shared permet les clientIds de sharedWith ; Global autorise
la lecture à tous les clients authentifiés. Seul le propriétaire peut annuler ou modifier
le partage. Les événements de jobs respectent la même règle. Les statistiques agrégées
du service sont visibles, sans liste des réservations d'autres clients.

`--permission NAME` lors du provisionnement donne une permission d'opération.
`manageResources` permet ReleaseResources. Les clients ne peuvent pas augmenter leurs
permissions par une requête API. Le code natif chargé dans le même processus est de confiance.
