# Mettre à jour les logiciels et plugins qui utilisent les SDK Cy

Ce guide s'applique à un produit existant : logiciel, CyTool ou plugin Unreal.
Le projet cible est celui indiqué par l'utilisateur ou ouvert dans l'espace de travail.
Les dépôts SDK sont des références de développement ; leur présence n'est pas une
condition de fonctionnement chez l'utilisateur final.

## 1. Sauvegarder avant toute modification

Lire les AGENTS.md applicables, examiner l'état Git et les différences existantes.
Faire un commit local de sauvegarde du périmètre cible avant la migration, après
vérification des données à inclure. Préserver le travail existant et exclure secrets,
poids, caches, venvs, journaux et fichiers générés inutiles. Ne pas ajouter sans examen
tout le dépôt parent. Sans Git, faire une sauvegarde datée vérifiable et le signaler.
Consigner le hash ou la sauvegarde. Ne pas réinitialiser le projet ou réécrire son historique.

Ce guide autorise la migration du projet cible uniquement. Pour une série de produits,
l'appliquer séparément à chaque produit autorisé, avec ses propres preuves. Ne pas
modifier tous les dossiers voisins ni publier/pousser sans instruction couvrant cela.

## 2. Identifier l'intégration et les versions réellement utilisées

Inventorier sources incluses, dépendances, versions installées, manifestes,
requirements/contraintes/locks, roues Python, ZIP, installateurs, bibliothèques gelées,
lanceurs et chemins de runtime. Vérifier le processus réellement lancé ; la version
affichée dans un README ou un environnement de développement ne prouve pas celle du produit.

Classer le projet :
- CyToolsCore seul : suivre les sections 3, 4, 6 et 7.
- CyUEMCPSDK intégré : suivre toutes les sections applicables, dont la section 5.
- Les deux : une migration coordonnée, avec des versions compatibles.

Références MIT vérifiées à la rédaction :
- CyToolsCore 0.10.1 : https://github.com/MrMybal/CyToolsCore
- CyUEMCPSDK 0.1.8 : https://github.com/MrMybal/CyUEMCPSDK

Pour une version ultérieure, vérifier sa licence, ses changements et sa compatibilité ;
ne pas supposer qu'un numéro supérieur suffit. Épingler les versions réellement
sélectionnées et validées. Ne pas utiliser automatiquement la dernière version d'une
dépendance tierce pour une migration de licence.

Lire README.md, Docs/Architecture.md, Docs/ImplementationStatus.md,
Docs/Versioning.md et Docs/Licensing.md du Core. Pour Unreal, lire aussi son README,
AGENTS.md, Docs/Architecture.md, Docs/Licensing.md et Docs/UpdateExistingPlugin.md.

La migration 0.10.0 vers 0.10.1 ne change ni le schéma 1, ni le protocole 1.0,
ni le comportement du runtime. Une intégration plus ancienne peut demander des
adaptations fonctionnelles ; comparer les différences avant de remplacer du code.

## 3. Mettre à jour le Core dans le logiciel

Installer le wheel officiel MIT dans l'environnement privé prévu par le logiciel,
ou le construire depuis le dépôt MIT sélectionné avec python -m build --no-isolation.
Utiliser le Python du produit et son gestionnaire de dépendances existant. Mettre à
jour requirements, contraintes, locks, configuration de build et métadonnées cohérentes.
L'extra MCP est nécessaire seulement si le produit utilise ce transport.

Ne pas copier ou réimplémenter le runtime, le scheduler ou les schémas dans le logiciel.
Les intégrations C++/C# doivent conserver le même contrat portable. Conserver les
opérations publiques, leurs IDs, entrées/sorties, profils et adaptations métier.
Réutiliser l'UI et l'installateur du produit ; ne pas ajouter l'assistant Unreal à un
logiciel qui utilise seulement le Core.

Si le logiciel embarque une distribution gelée, un installateur ou un environnement
préparé, le reconstruire avec le vrai paquet MIT. Une modification de LICENSE, d'un
champ JSON ou d'un README ne transforme pas un ancien paquet GPL en paquet MIT.
Repérer les anciens ZIP/wheels toujours sélectionnés par les lanceurs ; remplacer
les références dans la distribution à livrer, sans supprimer des données utilisateur.

Pour une intégration qui migre depuis un ancien Core, vérifier les conventions de :
- Docs/AutomaticInputs.md et Docs/TaskFiles.md : chemins externes importés automatiquement,
  champs fichiers configurés, sorties via JobContext.path, export des résultats voulus,
  FinishTask après arrêt réel, sessions IA temporaires et standalone temporary=False.
  Ne jamais purger modèles, caches, fichiers sources ou sauvegardes utilisateur.
- Docs/Scheduler.md : GetRuntimeStatus et exclusiveGroups pour les opérations
  réellement incompatibles ; conserver les réservations jusqu'à l'arrêt des workers.
  Les groupes ne coordonnent pas des runtimes distincts.
- Docs/FullOperationAccess.md : options métier réellement appliquées, contrat composable
  et accès IA/standalone cohérent pour les CyTools concernés.

Les exigences UI des CyTools se lisent dans leurs guides de livraison. Le Core n'impose
pas Dear ImGui à un logiciel généraliste qui l'intègre ; une migration de dépendance
n'autorise pas à remplacer son interface ou retirer ses fonctions existantes.

## 4. Livrer les licences et sources dans LICENCES

Créer LICENCES directement à la racine du produit ou du plugin livré, pas seulement
dans le dépôt de développement. Conserver la licence propre du produit et les
attributions tierces. La licence du SDK n'impose pas MIT au code propre du produit.

Inclure selon les composants réellement distribués :
- LICENCES/CyToolsCore-MIT.txt : copie complète et inchangée du LICENSE du Core MIT.
- LICENCES/CyUEMCPSDK-MIT.txt : copie complète et inchangée du LICENSE Unreal SDK.
  Obligatoire pour ses sources intégrées, même sans assistant.
- LICENCES/SOURCES.txt : liens vers les deux dépôts ci-dessus, les guides de création/
  intégration et les références nécessaires aux autres composants inclus.
- LICENCES/AssistantRuntime-Notices.txt : index actuel du bundle quand il est distribué.
  Garder aussi les textes complets des licences Python et des dépendances dans le ZIP.
- Notices/licences des autres composants inclus, selon leurs propres obligations.

Conserver Copyright (c) 2026 Cyberalien avec les textes MIT. Un lien ou le mot MIT ne
remplace pas le texte complet. Les CyTools générés conservent également la notice
LICENSE-CyToolsCore.txt fournie par le scaffold ; la copier dans LICENCES si nécessaire.
Ne pas faire de remplacement global de GPL par MIT dans les dépendances, modèles ou
sources tierces. Les copies déjà reçues sous GPL conservent leurs droits.

Inclure LICENCES dans les règles de packaging, archives, installateurs et ressources
déployées. Pour Unreal, adapter FilterPlugin.ini et NonUFS si nécessaire. Examiner
l'archive finale : la présence des notices dans les seules sources n'est pas suffisante.
La licence MIT n'est pas une preuve d'approbation Fab/Unreal ou des licences des modèles.

## 5. Adapter CyUEMCPSDK à chaque plugin Unreal

Appliquer les guides de référence :
- https://github.com/MrMybal/CyUEMCPSDK/blob/main/Docs/UpdateExistingPlugin.md
- https://github.com/MrMybal/CyUEMCPSDK/blob/main/Docs/UpdateAssistantRuntime.md
- https://github.com/MrMybal/CyUEMCPSDK/blob/main/Docs/Licensing.md

Adapter les fonctions du projet existant. Inclure l'intégration dans ses modules
existants, sans installer un plugin/module SDK séparé chez le client. Ne pas ajouter
de dépendance à CyAIConnectorLab. Préserver les fonctionnalités spécifiques au plugin.

Chaque plugin possède ses propres noms de classes/types/services/spawners,
configurations, profils, connexions, sessions, logs, fichiers de tâches et processus
possédés. Ne pas importer les namespaces génériques de la référence sans adaptation.
Vérifier la coexistence avec d'autres plugins intégrés : pas de symboles doublés,
de paramètres écrasés, de session partagée par erreur ou d'arrêt d'un processus voisin.

Quand l'assistant existe ou doit être inclus, appliquer AssistantUI.md, Providers.md,
AssistantContexts.md et UpdateAssistantInterface.md : instances contextualisées,
profils et modèle visibles, permissions effectives, assistant optionnel et anglais
par défaut. Le point d'entrée appartient au plugin/toolkit ; pas d'entrée globale
Window > Assistant ou de spawner générique ajouté par défaut.

Pour son runtime Python, appliquer AssistantRuntime.md :
- Fournir le bundle MIT compatible, avec ZIP, bundle.json, SetupRuntime.ps1,
  Licenses.txt et LICENSE-CyUEMCPSDK.txt cohérents.
- Réutiliser un installateur conforme déjà présent ; vérification à l'ouverture,
  choix explicite Install / repair ou Later, stockage utilisateur partagé par défaut.
- Mutualiser uniquement des bundles immuables identiques. Un contenu différent change
  l'empreinte et le dossier. Ne pas modifier un runtime partagé actif ni ses notices.
- Garder isolés paramètres, tokens, conversations, uploads et tâches par intégration.
  Le Python privé des CyTools d'inférence ne devient pas partagé à cause de cette règle.
- Remplacer le bundle livré ; une installation locale de développement mise à jour
  ne remplace pas le ZIP dans les plugins déjà distribués. Garder la migration et le
  retour à l'ancienne version compatibles avec les installations encore utilisées.

Quand les adaptations modifient le compagnon ou ses dépendances, reconstruire avec
Scripts/PackageAssistantRuntime.py et les versions choisies, en conservant les notices.
Ne pas embarquer poids, CUDA, CLIs fournisseurs ou secrets simplement pour cette migration.

## 6. Vérifier la livraison réelle

Adapter les contrôles au produit, sans prétendre tester tous les moteurs ou modèles
si le changement ne les affecte pas. Tester dans le runtime du produit livré :
- version CyToolsCore et License-Expression MIT dans les métadonnées installées ;
- version du compagnon et notices MIT lorsqu'il est inclus ;
- lancement depuis le lanceur réel, lecture d'une configuration existante et une
  opération représentative via les transports effectivement utilisés ;
- import d'un fichier externe, export puis nettoyage d'une tâche IA, si applicable ;
- erreurs, annulation et isolation lorsque l'adaptation change leur chemin d'exécution ;
- présence de LICENCES/SOURCES.txt, des textes complets et des notices tierces dans
  l'archive/installation finale, sans ancien paquet Core GPL encore sélectionné.

Pour Unreal avec assistant, vérifier installation/réutilisation du bundle, profils et
permissions, ouverture de plusieurs contextes, arrêt et coexistence de plugins.
Pour du code natif modifié, compiler les versions Unreal annoncées par le plugin.
Commencer les changements UI par UE 5.3 conformément au guide ; ne pas annoncer validées
les versions non exécutées. Ne pas distribuer un vieux binaire renommé comme nouveau.

Consigner les limites concrètes (SDK indisponible, version UE absente, dépendance
incompatible) et les validations non exécutées. Ne pas conclure seulement sur une
compilation du SDK de référence ou sur les tests d'un autre produit.

## 7. Livrer la migration

Mettre à jour la documentation du produit avec versions et composants inclus, sources,
licences, installation, mise à jour et retour à la version précédente.
Présenter le résultat : sauvegarde initiale, modifications adaptées, versions réellement
chargées, preuves des tests et contenu vérifié du paquet final. Ne pas enregistrer de
secrets, modèles, caches ou rapports privés dans le commit.

Un commit final est possible dans le périmètre autorisé après vérification. Push,
publication Fab, release ou réécriture d'historique nécessitent l'autorisation
correspondante ; ce guide ne l'accorde pas à lui seul.
