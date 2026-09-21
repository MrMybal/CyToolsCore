# Architecture

```text
Façade ImGui du Tool / CLI / JSONL / HTTP / MCP
          |
      LocalClient -- contexte authentifié (Principal)
          |
       Runtime -- validation -- descripteurs JSON
          |
       Scheduler -- ResourceLedger -- mesures psutil / NVIDIA optionnel
          |
       Handler(context, parameters)
          |
       Python métier / ProcessWorker / adaptateur distant
```

## Choix initiaux

Le SDK de référence utilise Python >= 3.11 pour les wrappers et workers.
Le protocole JSON ne contient aucun type Python sérialisé ni dépendance UI.
`jsonschema` valide Draft 2020-12 ; `psutil` fournit les mesures système.
Le SDK officiel MCP est épinglé à 1.30.0 : sa ligne v2 nécessite une migration.
Les transports, contrats et cycles de vie restent séparés ; une capacité déclarée
ne constitue pas une capacité validée.

## Propriété et synchronisation

Chaque runtime possède son stockage SQLite, ses sessions, ses handlers, sa file,
son ledger et ses workers enregistrés. Il n'existe pas de singleton global.
Une Condition/RLock protège les mutations et un seul scheduler attribue les réservations.
Le code métier s'exécute hors du verrou. Un verrou SQLite exclusif distinct interdit
deux runtimes utilisant le même répertoire de données ; sa libération suit le processus.

Les handlers sont enregistrés avant start. Le serveur HTTP traite plusieurs requêtes
et partage ce même runtime. Les workers sont possédés explicitement et arrêtés sans
tuer tous les processus portant le même nom.

## Persistance

SQLite conserve clients (empreintes SHA256 de jetons aléatoires), sessions, métadonnées
de jobs et observations de ressources. Les fichiers restent dans les workspaces.
Au redémarrage, les jobs non terminaux deviennent Failed/Interrupted. Ils ne sont pas
relancés automatiquement : un effet externe pourrait sinon être exécuté deux fois.
Les réservations sont reconstruites vides ; les modèles persistants doivent être
réenregistrés par leurs adaptateurs. Les événements sont un buffer borné en mémoire.
