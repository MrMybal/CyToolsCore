# Paramètres et génération d'UI

Les valeurs suivent JSON Schema Draft 2020-12. Utiliser les types JSON standards,
pas `type: file` ou `type: float`. Les spécialités CyTools sont des annotations :

| Besoin | Validation JSON | x-cy-kind |
|---|---|---|
| Texte / texte long | string | String / MultilineString |
| Case à cocher | boolean | Boolean |
| Entier / réel / seed | integer / number / integer | Integer / Float / Seed |
| Choix | enum | Enum |
| Fichier / dossier | string | File / Directory |
| Plusieurs fichiers | array de strings | Files |
| Image / audio / vidéo | string ou objet documenté | Image / Audio / Video |
| Structure / liste | object / array | Object / Array |
| Référence | string/objet avec contrat ou $ref local | Reference |

`x-cy-ui` accepte help, advanced, hidden, runtimeGenerated, step et visibleWhen.
Ces propriétés sont destinées aux vues ; une contrainte de sécurité ou de validité
doit être exprimée dans le schéma ou vérifiée par le handler. `multipleOf` impose
un pas validé ; `x-cy-ui.step` est seulement une suggestion visuelle.

```json
{
  "type": "object",
  "properties": {
    "backend": {"enum": ["native", "external"], "default": "native", "x-cy-kind": "Enum"},
    "precision": {"enum": ["fp16", "fp32"], "x-cy-ui": {"advanced": true}},
    "codec": {"type": "string"}
  },
  "required": ["backend"],
  "additionalProperties": false,
  "allOf": [
    {
      "if": {"properties": {"backend": {"const": "native"}}, "required": ["backend"]},
      "then": {"properties": {"precision": {"default": "fp32"}}, "required": ["precision"]},
      "else": {"required": ["codec"]}
    }
  ]
}
```

Le champ backend de cet exemple est un paramètre métier illustratif. Pour sélectionner
un véritable backend déclaré, utiliser backendId dans SubmitJob ; éviter deux sélecteurs
contradictoires dans un Tool réel.

Les defaults sont copiés dans properties/items/allOf et la branche if sélectionnée,
avant validation. Aucun default n'est choisi arbitrairement entre anyOf/oneOf.
Les références distantes sont refusées ; embarquer les définitions avec $defs.
Les format JSON Schema sont des annotations dans cette V1 (pas de validation de date,
d'URL ou d'existence d'un fichier par le seul mot-clé format).
