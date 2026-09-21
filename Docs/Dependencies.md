# Dépendances

CyDependencyDescriptor : id, version, required, source, installed, path, executable,
platforms. Les exigences globales sont runtimeRequirements ; chaque backend peut
avoir ses propres dependencies. CanRun contrôle la présence d'un path de fichier ou
d'un executable résolu dans PATH pour les dépendances obligatoires.

Un champ installed:true dans un manifest n'est pas une preuve et ne remplace pas la
détection. La contrainte version documente la version attendue ; le Tool doit vérifier
la version réelle via une commande fiable de son programme. Le Core ne devine pas
la syntaxe de `--version` de tous les exécutables.

Diagnose expose machine et enregistrement des handlers. Appeler CanRun avec les
paramètres exacts pour la vérification opérationnelle des ressources et dépendances.
Un diagnostic métier détaillé (drivers, modèles, comptes) peut être une opération
supplémentaire du Tool, décrite comme les autres.

Aucune installation système automatique. Les éventuels tokens de téléchargement
ou API doivent être fournis par l'hôte, jamais enregistrés dans CyTool.json.
