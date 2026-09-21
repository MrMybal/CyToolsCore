# Livraison obligatoire d'un CyTool autonome

Pour les maillages, appliquer [MeshViewer.md](MeshViewer.md) : vue 3D interactive
obligatoire après génération/remesh/PBR/UV/rig, commandes souris/clavier, inspection
rapprochée, scènes et éclairages. Les aperçus fixes seuls ne suffisent pas.

Appliquer [SharedInstallation.md](SharedInstallation.md) : choix cache local/partagé,
référencement des CUDA Toolkits compatibles, Python privé et distribution sans poids
ni gros environnements. L'installation guidée traite connexion et licences requises.

Ces exigences s'appliquent aux nouveaux Tools utilisateur. Le Core reste indépendant
de l'UI : Dear ImGui est une dépendance de la façade du Tool, jamais du runtime importé.
Un squelette CLI/MCP fonctionnel n'est pas une livraison terminée.

## 1. Dossier utilisateur propre

Créer avec `cytools new CHEMIN --name NOM --id ID --desktop`. Le mode historique sans
`--desktop` reste disponible pour les intégrations existantes, mais n'est pas le choix
de livraison d'un nouveau Tool autonome.

```text
NOM/
  NOM.exe                  # Windows : ouvre directement ImGui
  NOM.sh                   # Linux : lanceur exécutable simple
  LISEZ-MOI.md              # guide utilisateur court
  app/                     # code, UI, manifest, docs, tests, scripts, métadonnées de release
  data/                    # inputs, models, jobs, settings, logs, reports
  runtime/                 # Python/runtime privé, backends, builds, downloads, versions
```

Après validation, ranger scripts temporaires, logs, paramètres de test, roues, rapports
et fichiers de build dans les sous-dossiers appropriés. Ne pas laisser vingt fichiers
techniques à la racine. Garder un seul point d'entrée principal clairement nommé.
Ne jamais supprimer les données utilisateur pour « nettoyer ».

Créer l'environnement Python à son emplacement final. Un venv n'est pas présumé
déplaçable : ses scripts contiennent des chemins absolus. Toute migration doit être
réversible, préserver les poids/résultats, adapter références persistées et points
d'entrée, puis être retestée depuis un répertoire de travail différent.

## 2. Une vraie interface Dear ImGui

**Anglais par defaut, francais en option, pour toute l'interface.** Appliquer
[Localization.md](Localization.md). Fournir l'onglet Options : langue persistante,
theme, taille du texte et licences distinctes du Tool, du moteur, des modeles et des
dependances, avec sources officielles et inconnues explicites.
Ajouter sauvegarde/chargement de la configuration courante et autosave optionnelle
a chaque generation selon [GenerationConfigurations.md](GenerationConfigurations.md).

Le lanceur doit ouvrir ImGui directement, sans terminal à configurer, sans JSON à
éditer pour les opérations courantes. Toutes les capacités annoncées doivent être
utilisables : sélection du modèle/backend si pertinente, fichiers, textes, paramètres,
options avancées, exécution, progression réelle, erreurs compréhensibles, annulation,
consultation/export des résultats et diagnostic.

Le scaffold fournit une façade ImGui minimale ; adapter ses widgets au métier.
Une zone JSON générique ne remplace pas une interface utilisable pour les fonctions
principales. Ajouter un aperçu quand il aide réellement à exploiter la sortie.
Ne pas figer la fenêtre pendant un téléchargement ou une inférence.

La façade soumet des jobs au même Runtime/transport authentifié que la CLI/MCP.
Elle ne crée pas un deuxième scheduler, protocole, registre de jobs ou modèle chargé
dans le processus UI. La fermeture et l'annulation attendent l'arrêt réel des workers.

## 3. Installer un modèle depuis l'interface

Afficher état d'installation, espace estimé, source officielle, licence, prérequis,
et boutons Télécharger / Reprendre / Réparer / Annuler adaptés au backend.
Ne pas présenter un modèle absent comme disponible.

Pour un modèle soumis à autorisation :

1. Fournir un bouton vers la page officielle du modèle et les instructions d'accès.
2. Expliquer que l'utilisateur accepte personnellement les conditions sur le site.
3. Proposer la connexion locale au fournisseur (OAuth/device flow si disponible,
   sinon champ de jeton masqué avec lien vers sa création et droits minimaux).
4. Ne jamais mettre le jeton dans argv, manifest, params, jobs, captures ou logs.
   Le passer par stdin/IPC et utiliser le magasin d'identifiants du fournisseur/OS.
5. Distinguer erreur réseau, espace insuffisant, jeton invalide et accès 401/403.
6. Télécharger avec reprise, version/révision épinglée, taille et empreinte lorsqu'elles
   existent ; vérifier avant de marquer installé. Inclure les modèles auxiliaires.

L'utilisateur doit pouvoir terminer cette installation sans retourner dans le terminal.
Les dépendances lourdes restent privées au Tool ; ne pas les installer dans le Core.

## 4. GitHub : application, moteur et poids sont distincts

Configurer des sources explicites. Ne pas inventer de dépôt du Tool s'il n'existe pas :
proposer sa configuration dans ImGui et indiquer la limite. Le dépôt du moteur ne
constitue pas automatiquement le dépôt de l'application CyTools.

Implémenter vérification et téléchargement depuis GitHub : releases/archives pour
l'application, ou git fetch/checkout sur une révision précise pour le moteur.
L'option de vérification/téléchargement automatique doit être visible et enregistrée.
Le changement des poids suit son propre catalogue/versionnement/licence.

Préparer la mise à jour dans runtime/updates ; contrôler provenance configurée,
identité du Tool, plateforme/ABI, taille, hash disponible et confinement des archives.
Refuser traversées de chemins et liens dangereux. Ne pas exécuter une commande fournie
par une chaîne distante ni faire de git reset --hard sur un dossier utilisateur.

Les dépendances nouvelles vont dans un environnement séparé. Tester avant activation.
Ne jamais écraser une application pendant une génération. Activer au redémarrage ou
sous verrou, conserver la version précédente et fournir une restauration. data/ ne
fait jamais partie du remplacement. Écrire le format de release attendu et ses limites.
Un checksum publié avec une release n'est pas une signature indépendante de l'auteur.

## 5. Lanceurs et distribution

Windows : livrer un vrai `.exe` ou un exécutable empaqueté qui ouvre ImGui. Un `.cmd`
provisoire de développement ne suffit pas pour déclarer la livraison terminée.
Linux : fournir un script exécutable ou une AppImage avec instructions minimales ;
ne pas réutiliser un environnement Windows. Un lanceur ne prouve pas la compatibilité.

Distinguer clairement : installation autonome sur la machine testée, application
portable avec runtime redistribuable, et installeur complet. Ne pas annoncer « sans
Python installé » si le venv dépend encore du Python système. Respecter les licences
de redistribution des runtimes et des modèles ; ne pas incorporer des poids gated
dans une release publique par défaut.

## 6. Vérifications de livraison

- Racine conforme ; modèles et anciens résultats conservés après migration/mise à jour.
- Lancement réel de l'exécutable depuis un autre cwd, rendu ImGui et opération réelle.
- Toutes les opérations annoncées accessibles par des contrôles utilisables.
- Installation de modèle testée ; accès refusé géré sans fuite de secrets ni contournement.
- Annulation d'inférence et de maintenance ; aucune libération prématurée de ressources.
- Mises à jour : vérification, téléchargement, rejet d'une archive invalide, activation,
  restauration et préservation des données. Décrire les tests avec fixtures si aucune
  release distante réelle n'existe ; ne pas prétendre à une mise à jour publique testée.
- Tests du Tool, manifeste, CLI et vrai appel MCP ; plateformes exécutées séparées des suppositions.
- Guide utilisateur court à la racine, documentation développeur dans app/, preuves dans data/reports.

Adapter les chemins, licences, opérations et mises à jour au Tool cible.
Ne pas copier le runtime CyToolsCore, les modèles ou un environnement existant.

# Journaux et modèles

Appliquer [StandaloneDiagnosticsAndModels](StandaloneDiagnosticsAndModels.md) avant
livraison : logs copiables, résolution vidéo explicite, catalogue local de modèles/LoRA
compatibles et choix de périphérique effectivement utilisé par le worker.


Lire [FullOperationAccess.md](FullOperationAccess.md) : inventaire des capacités natives, parité complète des options métier entre IA et standalone, contrats de sorties composables et preuves de validation. Un formulaire simplifié ne limite pas le contrat du Tool.

Lire Docs/AutomaticInputs.md (AutomaticInputs.md depuis Docs) : chemins absolus acceptés pour les entrées locales, copie automatique privée par job, aucune copie manuelle exigée de l’IA.
