# Transports

Les modules transports n'ajoutent aucune logique de job. LocalClient est le dispatcher
commun, lié à un Principal. La factory du Tool crée son runtime ; la façade démarre
et ferme les ressources qu'elle possède.

| Transport | Implémentation V1 | Utilisation |
|---|---|---|
| Native | Runtime et LocalClient | Client Python dans le processus |
| Structured CLI | run_cli | Commande invoke avec résultat JSON |
| JSONL stdio | commande stdio | Une requête/réponse JSON par ligne, processus persistant |
| HTTP local | commande serve | POST /v1 avec Bearer token, runtime partagé |
| MCP stdio | extra mcp | Catalogue dynamique d'opérations + contrôles jobs |
| MCP vers service partagé | --connect URL mcp | Pont stdio/HTTP, identité par token |
| IPC natif / WebSocket | contrat d'adaptateur | Pas de serveur livré |
| HTTP distant | HTTPClient HTTPS | Gateway TLS/auth et transfert d'artefacts à fournir |

Les messages JSONL utilisent le protocole CyTools, pas MCP. `mcp` utilise le protocole
MCP géré par le SDK officiel. Ne pas relier un client MCP à la commande `stdio`.

Le serveur livré écoute uniquement 127.0.0.1. Il refuse les Origins de navigateur,
exige un Bearer, limite les requêtes à 1 MiB et impose un délai de lecture. Il n'est
pas un serveur Internet public : ajouter quotas, TLS, supervision et politique réseau
avant une exposition distante. La CLI ne modifie aucune configuration de client IA.
