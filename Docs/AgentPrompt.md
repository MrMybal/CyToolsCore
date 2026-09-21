# Prompt prêt à fournir à une IA

## Prompt court pour un nouveau Tool

```text
Crée CyTools_<NOM> dans un nouveau sous-dossier <TOOLS_ROOT>/CyTools_<NOM>.
Fonction : <DESCRIPTION COURTE>.
Suis toutes les instructions de <SDK_ROOT>\Docs\AgentPrompt.md,
ainsi que les documents qu'il référence. Ne modifie pas les autres Tools.
```

## Instructions complètes de création

Remplacer les champs entre chevrons. Les documents cités sont obligatoires.

```text
Crée une application CyTools autonome nommée <NOM>, ID <ID>, dans <TOOLS_ROOT>/<NOM>.
Fonction attendue : <DESCRIPTION DU MODÈLE/OUTIL, ENTRÉES, SORTIES ET OPTIONS>.
Sources officielles : <URL DU MOTEUR, PAGE DU MODÈLE, DÉPÔT GITHUB DU TOOL SI DISPONIBLE>.

SDK local : <SDK_ROOT>. Lis d’abord AGENTS.md, README.md,
Docs/AgentGuide.md, Docs/StandaloneDelivery.md, Docs/Architecture.md et
Docs/ImplementationStatus.md. Utilise cytools new --desktop ; ne copie jamais le runtime.

Livre une racine épurée : <NOM>.exe, lanceur Linux, LISEZ-MOI.md, app/, data/, runtime/.
Range code, manifeste, tests et scripts dans app ; modèles, entrées, jobs, réglages et
logs dans data ; environnements privés, sources de moteurs, téléchargements et versions
dans runtime. Nettoie les artefacts de développement avant livraison sans supprimer de données.

L’exécutable Windows doit ouvrir directement une vraie interface Dear ImGui.
L'interface est en anglais par defaut et entierement disponible en francais.
Applique Docs/Localization.md : onglet Options avec langue persistante, theme,
taille du texte et licences du Tool, du moteur, des modeles et des dependances,
avec liens officiels. Ne suppose aucun droit pour une licence non renseignee.
Ajoute Save/Load configuration et Autosave on generation dans Options, en appliquant
Docs/GenerationConfigurations.md : JSON versionne, parametres exacts reutilisables
par une IA, aucun secret, chargement sans execution automatique.
Applique Docs/SharedInstallation.md : cache local/partagé configurable, Python privé,
CUDA Toolkit partagé explicitement sélectionné et version vérifiée, états structurés
pour l'IA en cas de connexion/licence nécessaire. Ne déplace aucun modèle existant.
Distribue sans poids, caches et gros environnements ; guide leur installation au premier lancement.
Toutes les capacités annoncées doivent être utilisables dans cette interface : sélection
entrée/modèle/backend, réglages usuels et avancés, génération, progression réelle,
annulation, erreurs, diagnostic et accès/aperçu des résultats. Pas de JSON à éditer pour
l’usage normal. CLI et MCP utilisent le même runtime et les mêmes schémas.
Pour tout Tool qui produit/modifie un mesh, applique Docs/MeshViewer.md et utilise
--desktop --mesh-viewer : vrai viewport 3D, ouverture automatique du résultat, navigation
souris/clavier en orbite et libre, inspection rapprochée, scènes, studio trois points
et soleil, matériaux PBR. Une image fixe ou un lanceur externe ne suffit pas.

Ajoute un écran d’installation des modèles : état, taille, source, licence, boutons
Télécharger/Reprendre/Réparer/Annuler. Si autorisation requise, fournir instructions et
liens officiels, puis une connexion locale sécurisée. L’utilisateur accepte lui-même la
licence. Aucun jeton dans argv, paramètres de jobs, manifeste ou logs. Vérifie les fichiers
et prépare les modèles auxiliaires ; n’annonce pas un modèle installé avant contrôle.

Ajoute les mises à jour GitHub de l’application et du moteur en les distinguant des poids.
Source configurée, vérification et téléchargement automatiques optionnels, staging,
contrôles de version/hash/ABI/archives, activation hors génération, sauvegarde et retour
arrière. Préserve data. Si le dépôt du Tool n’existe pas, rends-le configurable et indique
cette limite ; n’invente ni URL, ni release, ni test réussi.

Conserve jobs, identités authentifiées, workspaces, réservations et annulation du SDK.
Isole le modèle dans un worker ; libère les ressources seulement après son arrêt réel.
Aucune dépendance ImGui ou IA dans le Core. Crée les environnements à leur chemin final.

Teste le lanceur et les écrans ImGui, un traitement réel et ses sorties, l’installation,
les erreurs d’accès, l’annulation, l’isolation, le MCP, les mises à jour et leur rollback.
Distingue Windows/Linux exécutés, tests avec fixtures et fonctions encore non vérifiées.
Un scaffold CLI/MCP n’est pas une livraison terminée. Livre le dossier rangé, un guide
court et les preuves dans data/reports. Décris honnêtement les prérequis du runtime.
```
# Exigences complémentaires obligatoires

Appliquer `Docs/StandaloneDiagnosticsAndModels.md` : journal intégré sélectionnable
et copiable, résolution vidéo prévue/réelle visible, ajout de modèles locaux compatibles,
LoRA avec intensités lorsque le moteur sait les charger, et sélection CPU/GPU/Auto
avec ressources et exécution cohérentes. Conserver ces sélections dans Save/Load/Autosave.


Lire [FullOperationAccess.md](FullOperationAccess.md) : inventaire des capacités natives, parité complète des options métier entre IA et standalone, contrats de sorties composables et preuves de validation. Un formulaire simplifié ne limite pas le contrat du Tool.
