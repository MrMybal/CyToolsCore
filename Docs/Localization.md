# Interface multilingue, Options et licences

Depuis le SDK 0.3.0, chaque Tool utilisateur doit fournir une interface anglaise par
defaut et une traduction francaise selectionnable. Cette obligation couvre les Tools
existants lors de leur prochaine correction, ainsi que CyToolsManager.

## Comportement attendu

- Onglet **Options**, toujours accessible, contenant Language, Theme, Text size et Licenses.
- Ajouter Save/Load configuration et Autosave on generation selon [GenerationConfigurations.md](GenerationConfigurations.md).
- Premiere execution en anglais, independamment de la langue Windows/Linux.
- Choix English / Francais applique sans redemarrage et conserve par Tool dans
  `data/settings/ui-preferences.json`. Themes sombre, clair, classique ; texte 80 a 160 %.
- Reinitialiser les preferences ne modifie ni modeles, ni parametres de generation, ni donnees.
- Tous les textes de navigation, boutons, aides, dialogues, erreurs metier et etats visibles
  ont des traductions EN/FR. Les logs bruts tiers et textes originaux des licences restent
  dans leur langue originale, clairement identifies comme tels.
- Ne jamais traduire IDs, chemins, noms de fichiers, schemas, valeurs JSON/MCP, noms de
  modeles, prompts, texte saisi ou genere, jetons, et autres donnees utilisateur.

## Integration fournie par cytools new --desktop

Le generateur livre `app/ui_common.py` et `app/locales/ui.json`. Ce sont des elements de
facade optionnels : aucune importation ImGui ne doit etre ajoutee au Core.
Le module charge les preferences sans importer ImGui ; le rendu le charge a la demande.

```python
from imgui_bundle import hello_imgui
from ui_common import imgui, run, tr

# imgui est une facade de presentation ; les autres attributs sont ceux d ImGui.
# Pour de nouveaux textes, ecrire la source anglaise et ajouter en/fr au catalogue.
if imgui.button('Run'):
    submit_job()

runner.callbacks.show_gui = draw
run(runner)
```

La facade traduit les libelles et conserve une identite ImGui stable avec `###`.
Elle ajoute Options a la barre d'onglets existante. Une interface sans onglets recoit
une navigation Tool / Options. Aucun scheduler ni protocole n'est change.
Les parametres de test `--ui-test-options --ui-test-language=en` (ou fr) ouvrent Options,
ferment apres quelques frames et enregistrent une preuve dans data/reports, sans changer
la preference sauvegardee. Une capture PNG necessite Pillow et NumPy dans le Tool.

Une migration par catalogue de libelles est un point de depart : verifier egalement les
phrases dynamiques, listes de choix, dialogues de fichiers et messages renvoyes par les
handlers. Pour les nouvelles interfaces, utiliser des cles ou textes anglais stables,
avec variables nommees, plutot que concatenations traduites morceau par morceau.
Les choix techniques restent separes de leurs libelles traduits.

## Licences dans Options

Afficher separement l'application, chaque moteur, chaque modele/voix et les dependances.
Le manifeste fournit les declarations existantes ; `app/licenses.json` peut les completer :

```json
[
  {
    "kind": "Engine",
    "name": "Official engine",
    "license": "Not declared",
    "url": "https://example.org/official-license",
    "notes": "Source and revision of the declaration, if known."
  }
]
```

L'exemple de lien est un placeholder documentaire : le remplacer par une source verifiee,
ou laisser vide. Ne jamais inventer une licence, un droit commercial ou un lien officiel.
Les dependances installees utilisent leurs metadonnees License-Expression/License ;
une declaration manquante ou incomplete reste indiquee comme telle. Conserver le texte
juridique original. La traduction des libelles de l'interface n'est pas une traduction
officielle de la licence. Options ne remplace pas l'acceptation personnelle d'une licence
gated dans le parcours Installation.

## Validation

Verifier anglais sans preference, bascule FR, persistance, valeurs invalides, tailles et
themes, identites stables, integrite des entrees utilisateur et presence de la section
Licenses. Executer un rendu EN/FR et verifier que l'onglet Options est effectivement
visible. Un simple chargement du module ne prouve pas la traduction de toute l'interface.
