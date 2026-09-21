# __TOOL_NAME__

Projet de développement généré, à finaliser avant livraison.

- app/ : code, manifeste, UI ImGui, tests, documentation et scripts.
- data/ : entrées, modèles, résultats isolés, réglages et logs.
- runtime/ : Python privé, dépendances, versions et mises à jour préparées.

Créer l'environnement dans runtime/python et y installer le wheel CyToolsCore fourni
ainsi que les dépendances app/requirements.txt. Le SDK n'est pas supposé publié sur PyPI.
Lancer.cmd démarre la façade ImGui pendant le développement.
Sous Windows, exécuter app/build_launcher.ps1 dans un terminal de compilation Visual C++,
puis livrer __TOOL_NAME__.exe et retirer Lancer.cmd de la racine finale.
Sous Linux, le lanceur est __TOOL_NAME__.sh ; un runtime Linux distinct doit être préparé et testé.

L'interface générée est un point de départ : ajouter les widgets et aperçus métier,
le parcours de modèle sous licence et les mises à jour GitHub selon app/Docs/StandaloneDelivery.md.
Ne pas déclarer le Tool fini parce que le squelette se lance.
