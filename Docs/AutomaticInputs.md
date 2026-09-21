# Entrées locales automatiques

Une IA ou un utilisateur peut fournir directement le chemin absolu d'un fichier
accessible au processus du Tool. Ne pas exiger de copie manuelle dans data/inputs.
Le Tool importe automatiquement le fichier dans le workspace privé du job via :

```python
snapshot = context.import_input(parameters['image'], base_dir=DATA/'inputs',
                                suffixes=['.png', '.jpg', '.jpeg', '.webp'],
                                max_bytes=32*1024**2)
```

Transmettre uniquement le snapshot au worker. Valider le contenu réel sur ce snapshot
avant son traitement (décodage image, dimensions, etc.). Les noms relatifs déjà utilisés
restent résolus depuis base_dir. Un chemin relatif sortant du dossier est refusé ;
l'appelant peut fournir le chemin absolu explicite du fichier externe.

Le SDK copie par blocs avec contrôle de taille et annulation, impose un fichier régulier,
produit des noms uniques et écrit inputs/imports.json (source, taille, SHA256, snapshot).
Le fichier original reste intact et deux jobs n'écrasent pas leurs entrées. Les entrées
provenant des workspaces de ce runtime respectent la visibilité des jobs authentifiés.
Les permissions de lecture du système d'exploitation continuent de s'appliquer.
Aucun clientId métier ne choisit le propriétaire. Réserver le disque nécessaire aux
copies dans l'estimateur du Tool et prévoir leur rétention avec celle du job.

Une chaîne locale réutilise donc directement le chemin retourné par le Tool précédent.
Un fichier présent seulement sur un autre hôte nécessite un transfert préalable ;
un chemin seul ne transporte pas ses octets. Ne pas télécharger arbitrairement une URL.

Le schéma d'entrée doit décrire les chemins absolus acceptés et l'import automatique.
Le MCP, la CLI et le standalone appellent le même handler. Une fenêtre de sélection de
fichier doit transmettre son chemin sans imposer une copie dans un dossier partagé.
Tester une entrée hors du Tool (espaces/Unicode), des noms identiques, une modification
de l'original, les limites de taille, le contenu invalide et l'isolation entre clients.

Depuis le SDK 0.9.0, utiliser aussi runtime.configure_inputs pour tous les champs de
fichiers : import commun SDK/MCP et gestion de la tâche selon [TaskFiles.md](TaskFiles.md).
Cette intégration couvre les 19 Tools livrés. import_input reste disponible pour les
validations et snapshots privés du handler.

## Durée de vie

Les copies importées sont temporaires par défaut (keep=False), en MCP comme dans
les autres modes. Le Core les supprime après le retour effectif du handler, donc
après l'arrêt de son worker, sur succès, erreur et annulation. La provenance légère
reste dans imports.json avec removed=true. Ce nettoyage de snapshot préserve l'original et les résultats du job. La fin de tâche
supprime ensuite les résultats temporaires selon TaskFiles.md. Un handler ne doit pas retourner une copie temporaire comme résultat durable.

keep=True conserve la copie pendant le job/la tâche pour débogage/reproductibilité ;
cette option ne la protège pas du nettoyage final d’une tâche IA temporaire. LocalMesh
expose keep_input_copies (false par défaut) dans son schéma IA et ses réglages avancés.
Les configurations enregistrent cette option, pas les octets des images.
Le cycle de tâche 0.9.0 ajoute la purge des résultats, la déconnexion, l’expiration
et la récupération au redémarrage ; les workers encore vivants empêchent la purge.


## Task-owned files (SDK 0.9.0)

Read Docs/TaskFiles.md (TaskFiles.md from this Docs directory). Configure input roots and all file fields for automatic imports; AI sessions are temporary by default. FinishTask removes imported copies and generated workspaces after workers stop; export wanted results first. Standalone sessions explicitly use temporary=False.
