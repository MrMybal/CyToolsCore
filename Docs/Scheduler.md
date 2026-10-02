# Scheduler local

Le scheduler trie les jobs admissibles par priorité puis ordre d'arrivée.
Ordre : Interactive, Critical, High, Normal, Background, Low. Il ne préempte pas un
job déjà lancé ; une priorité élevée ne donne pas davantage de droits.

`concurrency.maxWorkers` borne le nombre de handlers actifs. Sequential et Exclusive
limitent à un job. Concurrent, MultiWorker et MultiGPU utilisent ce plafond et les
ressources disponibles ; les workers/devices effectifs sont choisis par le backend.
SharedModelSequential sérialise les jobs du même backend. SharedModelConcurrent et
les autres politiques ne permettent la concurrence d'un même backend que si threadSafe,
concurrentInference et maxConcurrentInference l'autorisent.

Les poids d'un modèle partagé ne sont pas magiquement chargés par une déclaration.
L'adaptateur peut réserver `worker:<id>` pour le coût résident, puis estimer seulement
le coût incrémental de chaque job. Enregistrer le worker dans le runtime pour libérer
sa réservation lors de ReleaseResources(Worker/All).

La réservation de toutes les ressources d'un job est atomique. Si le budget total
est insuffisant, SubmitJob est refusé ; si des jobs utilisent temporairement le budget,
le job devient WaitingForResources. Il n'est pas lancé à découvert.

La priorité stricte peut affamer une file Low si des jobs Interactive arrivent sans fin.
La V1 n'implémente pas d'aging, de préemption ni de coordination entre plusieurs Tools.

## Groupes d'exclusivité par opération (SDK 0.10.0)

Déclarer `exclusiveGroups` dans les opérations qui ne doivent pas se chevaucher,
par exemple la génération, la transcription et le déchargement d'un même moteur GPU.
Extrait de manifeste (les autres champs obligatoires des opérations sont omis ici) :

```json
{
  "concurrency": {"policy": "Concurrent", "maxWorkers": 4},
  "operations": [
    {"id": "generate", "exclusiveGroups": ["gpu"]},
    {"id": "transcribe", "exclusiveGroups": ["gpu"]},
    {"id": "unload_model", "exclusiveGroups": ["gpu"]},
    {"id": "inspect_audio", "exclusiveGroups": []},
    {"id": "generate_on_second_device", "exclusiveGroups": ["gpu_secondary"]}
  ]
}
```

Deux jobs partageant au moins un groupe s'exécutent l'un après l'autre, même si leurs
opérations, backends, sessions ou clients sont différents. Les opérations indépendantes
peuvent continuer dans la limite du nombre de workers, des règles du backend et du budget.
Un tableau absent ou vide n'ajoute aucune contrainte. Les noms sont des IDs sensibles à
la casse, uniques dans le tableau, au format des IDs d'opération (1 à 128 caractères).
Ce sont des noms logiques : `gpu` ne sélectionne pas un device et n'est pas une réservation
VRAM. Les exigences de mémoire et le choix du device restent nécessaires.

Tous les groupes sont acquis ensemble au démarrage effectif sous le verrou du scheduler,
avec la réservation des ressources. Un job bloqué ne démarre aucun handler, ne consomme
aucun slot et ne garde pas une partie de ses groupes. Il reste `Queued` en cas de conflit
de concurrence ; l'attente de mémoire utilise `WaitingForResources`. Les priorités et
`queueTimeout` s'appliquent à cette file. `CanRun` reste vrai pour un job admissible mais
indique `waitingForConcurrency: true` si un groupe, le plafond global ou le backend le
bloque actuellement ; ce diagnostic ne constitue pas une réservation.

Une demande d'annulation ou un délai d'exécution dépassé ne libère pas le groupe :
il reste occupé jusqu'à la sortie du handler et de son nettoyage, y compris l'arrêt
synchrone de ses workers de calcul. Le groupe est libéré sur succès, erreur ou annulation.
Un worker lancé en arrière-plan ne doit pas survivre à son handler avec un calcul actif.
Un modèle simplement résident entre deux jobs conserve sa réservation mémoire séparée ;
les groupes ne chargent ni ne déchargent automatiquement ce modèle.

Pour migrer une file GPU interne, installer le SDK 0.10.0 ou ultérieur, déclarer les
mêmes groupes sur toutes les opérations concernées avant de démarrer le Runtime, puis
soumettre normalement les jobs via SDK/CLI/HTTP/MCP. Vérifier concurrence et annulation
avant de retirer l'ancienne file. Le scaffold 0.10.1 épingle le SDK 0.10.1 dans ses dépendances.
Les anciens SDK peuvent conserver un champ inconnu sans appliquer son comportement :
il ne suffit pas de modifier le manifeste sans mettre à jour le SDK.

La portée est un Runtime. Plusieurs clients doivent utiliser son service partagé pour
partager ces groupes. Des processus autonomes ou des Tools différents ne partagent pas
ce verrou ; conserver les verrous interprocessus nécessaires dans ces intégrations.
