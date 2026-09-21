# Opérations

Une opération décrit une capacité, pas un transport. Elle expose id, name, description,
inputSchema et outputSchema. Elle peut préciser supportedBackends, outputs,
resourceRequirements, permissions, platforms, estimatedDurationSeconds et les booléens
canRunAsync, canCancel, supportsProgress, supportsPreview, supportsStreaming.

Enregistrer `runtime.register(id, handler, estimate=None)` avant `start()`.
Le handler reçoit `JobContext` et un dictionnaire validé. Il renvoie une valeur JSON
validée par outputSchema. L'estimateur optionnel reçoit paramètres/backend/modèle ;
il doit être rapide, sans effets de bord, déterministe pour les mêmes données.

Toutes les soumissions du runtime actuel sont des jobs asynchrones. `invoke` constitue
une façade synchrone qui attend un état terminal. `canCancel` autorise la demande
utilisateur ; l'arrêt du runtime peut toujours demander une annulation.

Une permission déclarée doit être présente dans le Principal. Ce contrôle décide si
l'opération peut être lancée ; ce n'est pas une sandbox de code Python. Le handler
reste responsable de contrôler les accès aux chemins et programmes qu'il utilise.
