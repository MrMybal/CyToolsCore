# Sauvegarder et recharger une configuration de generation

Chaque interface autonome doit fournir **Save configuration**, **Load configuration**
et **Autosave on generation** dans Options. La sauvegarde manuelle conserve le formulaire
courant, meme avant une generation. Un formulaire incomplet peut etre sauvegarde comme
brouillon, avec `validParameters: false` et son erreur de validation.

L'autosave est optionnelle, desactivee par defaut. Apres acceptation d'une soumission par
le runtime, elle conserve les parametres reels, le modele/backend et le jobId dans
`data/configurations/autosave/<jobId>.json`. Elle n'annonce pas la reussite de la generation.
Pour une seed tiree au hasard par le modele, la configuration enregistre la demande ;
une reproduction identique exige la seed resolue et les memes poids/runtime, si le Tool
les fournit. Ne pas promettre une reproduction bit a bit.

Les sauvegardes manuelles vont dans `data/configurations/`, sous un nom unique, sans
ecrasement implicite. Le chargement verifie format, version et toolId, restaure le formulaire
sans executer de code ni demarrer un job. Les champs de connexion, tokens et mots de passe
sont exclus. Les prompts/textes saisis font partie des parametres sauvegardes.
Les fichiers d'entree sont references par leur chemin ou nom ; ils ne sont pas copies dans
le JSON. Pour partager une configuration, fournir aussi les entrees necessaires.

## Format portable versionne

Source de verite : `cytools_core/schemas/generation-config.schema.json`. Le generateur
copie ce contrat dans app/ pour permettre la validation avec un runtime Core plus ancien.

```json
{
  "format": "cytools-generation-config",
  "schemaVersion": 1,
  "toolId": "cy.tool.example",
  "toolVersion": "0.1.0",
  "operationId": "generate",
  "parameters": {"prompt": "Example", "seed": 42},
  "backendId": "",
  "modelId": "",
  "validParameters": true,
  "uiState": {},
  "jobId": null
}
```

`parameters` utilise exactement le schema de l'operation CyTools. `uiState` conserve
les controles pour le rechargement visuel ; une IA n'a pas besoin de cette section pour
executer le traitement. Les valeurs de protocole ne sont jamais traduites.
Une nouvelle version du Tool revalide les parametres contre son schema courant.

## Reutilisation par une IA

1. Lire toolId, operationId, parameters, backendId et modelId.
2. Via MCP, appeler l'operation correspondante avec ces valeurs, puis suivre le job.
3. Ou executer depuis la racine du Tool :

```powershell
.\runtime\python\Scripts\python.exe .\app\generation_config.py .\data\configurations\exemple.json --data-dir .\data\replay-jobs
```

Ce helper utilise le runtime du Tool et ses controles habituels. Il n'execute aucun
script ou commande defini dans le JSON. Les permissions de l'identite restent celles
du runtime ; un Tool exigeant une permission explicite doit fournir son integration
authentifiee appropriee, sans contourner le controle.

## Integration et tests

Le scaffold 0.3.0 fournit generation_config.py, la facade UI et la documentation.
Pour une nouvelle interface, enregistrer explicitement
`ui_common.configure_generation(runtime, capture_config, restore_config)` : le getter
retourne operationId/parameters et eventuellement backendId/modelId, le loader restaure
les champs du formulaire. La migration des anciennes interfaces contient des adaptateurs
pour leurs fermetures Python ; les nouvelles interfaces doivent utiliser ces callbacks
explicites pour eviter une dependance aux noms internes de leurs variables.
La migration des interfaces existantes reutilise leurs constructeurs de parametres.
Pour tout nouveau Tool, verifier que Save configuration exporte exactement les valeurs
du formulaire et la bonne operation, y compris les conversions de listes, modeles et
parametres conditionnels. Tester les allers-retours avec les vrais champs metier.
Les autosaves doivent utiliser les parametres soumis, pas un formulaire pouvant avoir
change pendant l'execution. Un echec de sauvegarde doit etre visible sans masquer un job
deja lance. Ne pas inclure de secrets dans uiState non plus.
