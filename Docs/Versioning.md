# Versions et compatibilité

Trois versions indépendantes : schemaVersion entier (1), protocolVersion major.minor
(1.0), version métier de chaque Tool. La version du paquet SDK est 0.1.0 : première
implémentation du standard v1, à stabiliser avec les premiers adaptateurs réels.

Le parser conserve les métadonnées inconnues et refuse un major schema/protocol
incompatible. Les opérations et paramètres n'ont pas à accepter des champs inconnus :
un inputSchema fermé est recommandé. Les fichiers JSON Schema livrés sont la source
de vérité ; les scripts bootstrap_schemas/create_test_manifest servent à régénérer
la proposition initiale et doivent évoluer avec les contrats, jamais indépendamment.

Un changement de sens, de champ requis ou de type public nécessite une décision
explicite de compatibilité et des tests de fixtures. Les ajouts optionnels compatibles
peuvent être documentés sans remplacer les IDs d'opération déjà utilisés.

Les schémas utilisent Draft 2020-12 : [spécification officielle](https://json-schema.org/draft/2020-12).
Le choix d'un autre langage ne doit pas changer les unités, noms de champs, états,
erreurs ou garanties d'identité. Porter les fixtures et les tests du protocole.
