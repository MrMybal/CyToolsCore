# Capacités complètes et orchestration

Un Tool est une API métier complète avec une interface ImGui. Son formulaire simplifié
ne doit jamais déterminer ce qu'une IA peut appeler. Le manifeste et les handlers
forment le contrat commun à MCP, CLI, HTTP, JSONL et standalone.

## Obligation pour la création ou la finalisation d'un Tool

1. Inventorier les fonctions publiques du moteur et de sa version réellement installée :
   tâches, paramètres d'inférence, entrées auxiliaires, sorties, export, ressources,
   modèles, LoRA et installation. Lire les signatures, la CLI et la documentation officielle.
2. Établir `Docs/CapabilityCoverage.md` : capacité native, opération/champ CyTools,
   contrôle standalone, contraintes, preuve de test, ou raison précise d'exclusion.
   Distinguer implémenté/testé, implémenté/non validé, non exposé et non applicable.
   Le nombre de champs JSON ne prouve pas la couverture du moteur.
3. Exposer chaque option métier applicable avec son vrai type, ses unités, défauts,
   bornes, enums, descriptions, dépendances `if/then`, incompatibilités et exemples.
   Préserver la différence entre absent, zéro, false et null. Les presets complètent
   ces paramètres ; ils ne doivent pas masquer ni écraser les valeurs explicites.
4. Relier chaque champ au handler puis au vrai moteur. Pas de paramètres acceptés
   mais ignorés, pas de `kwargs` libre, de code Python, de callback ou de commande shell
   arbitraire. Les tensors/callbacks natifs nécessitent un équivalent métier sérialisable
   ou une exclusion documentée, jamais une fausse prise en charge.
5. Le standalone doit offrir les contrôles métier usuels et un accès avancé à toutes
   les opérations/champs déclarés, y compris listes et objets imbriqués. Le template
   `advanced_ui.py` fournit cet accès JSON, validation/CanRun, priorité, délais,
   contrat copiable, sauvegarde/chargement et résultats copiables. Son exécution
   utilise exactement les valeurs fournies, sans préférences du formulaire simplifié.
6. Tester au moins une valeur non par défaut par famille de réglages, le passage
   jusqu'au moteur, les incompatibilités, et la parité MCP/CLI/standalone. Ne jamais
   déclarer toutes les possibilités du moteur couvertes à partir d'un smoke test UI.

## Client IA / orchestrateur

La CLI fournit aussi `describe-operation ID`, `list-backends`, `list-models`,
`estimate ID --params-file fichier.json` et `can-run ID --params-file fichier.json`.
Les options `--backend` et `--model` s'appliquent aux deux derniers contrôles.

- Découvrir les opérations : `cy_list_operations`, puis `cy_describe_operation` avec
  `operationId`. La réponse inclut inputSchema, outputSchema, backends, permissions,
  ressources et capacités d'annulation. `cy_describe` restitue le Tool complet.
- Découvrir `cy_list_backends`, `cy_list_models` et, si présent,
  `op_model_library_list` pour les références locales, LoRA, formats et périphériques.
  `op_model_library_register` enregistre une référence locale compatible sans copier
  ni télécharger les poids. Le catalogue est partagé par les clients du Tool local.
- Vérifier `cy_estimate` puis `cy_can_run` avec les paramètres et sélections concrets.
  Cela ne remplace pas les contrôles du chargeur ni une validation qualité du modèle.
- Soumettre `op_OPERATION` avec `parameters`, `backendId`, `modelId`, `priority`,
  `queueTimeout` et `executionTimeout` si nécessaire. Les délais sont en secondes.
  Recevoir le jobId ne signifie pas que le travail est terminé.
  Le schéma de sortie MCP décrit le job asynchrone ; les résultats métier finaux
  sont décrits par outputSchema de l'opération et se trouvent dans job.outputs.
- Suivre `cy_get_job` ou `cy_events`. Lire les sorties seulement à l'état Completed.
  Failed/Cancelled doivent brancher vers la gestion d'erreur du workflow. Une relance
  n'est pas automatiquement idempotente. Ne pas relancer un job dont l'arrêt n'est
  pas confirmé. `cy_cancel_job` demande l'annulation ; elle peut être coopérative.
- `cy_release_resources` expose les niveaux déjà implémentés par le Core. Ce contrôle
  ne crée pas de déchargement natif si l'adaptateur n'en dispose pas.

Exemple d'appel MCP (remplacer l'opération et les champs par son contrat réel) :

```json
{
  "parameters": {"prompt": "A small wooden boat", "seed": 42},
  "backendId": "BACKEND_DECLARE",
  "modelId": "MODELE_DECLARE",
  "priority": "Background",
  "queueTimeout": 600,
  "executionTimeout": 1800
}
```

## Composition des tâches

Les sorties doivent annoncer leur signification, type, format/MIME, unités et chemin
de fichier dans outputSchema/outputs. Décrire les entrées attendues par les opérations
suivantes : image, mesh, audio, vidéo, textures, rapport ou paramètres structurés.
Un chemin absolu sur le serveur n'est pas une URL ni un fichier transféré au client.

Pour les fichiers accessibles sur le même hôte, le Tool accepte leur chemin absolu
et crée automatiquement une copie privée avec JobContext.import_input ; aucune copie
manuelle dans data/inputs ne doit être exigée de l'IA. Voir [AutomaticInputs](AutomaticInputs.md).
Entre hôtes, l'orchestrateur transporte les octets. Les outputs restent privés au job.

Les réservations restent propres à chaque runtime. L'orchestrateur doit aussi limiter
les jobs lourds entre plusieurs Tools : il n'y a pas de scheduler GPU distribué dans
le Core. Il doit préserver les identités, les droits et les workspaces des clients.

Sous Windows, le Core restaure uniquement pour le sous-processus NVIDIA la valeur
ProgramFiles issue du registre système si le client MCP l'a omise. Il préserve les
variables explicitement fournies et ne modifie ni l'environnement global ni le pilote.

## Portée de la livraison 0.7.0

Accès avancé à toutes les opérations déjà déclarées, contrôles MCP supplémentaires
issus du schéma portable et bibliothèque locale accessible aux IA. Les inventaires
générés dans les Tools recensent ces contrats ; ils ne certifient pas l'exposition de
chaque argument des bibliothèques natives. Toute capacité native supplémentaire doit
suivre la matrice et les tests ci-dessus avant d'être annoncée comme disponible.


## Task-owned files (SDK 0.9.0)

Read Docs/TaskFiles.md (TaskFiles.md from this Docs directory). Configure input roots and all file fields for automatic imports; AI sessions are temporary by default. FinishTask removes imported copies and generated workspaces after workers stop; export wanted results first. Standalone sessions explicitly use temporary=False.
