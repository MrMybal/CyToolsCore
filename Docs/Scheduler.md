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
