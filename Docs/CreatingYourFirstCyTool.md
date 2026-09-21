# Créer son premier CyTool

Installer le SDK comme indiqué dans le README. Les commandes suivantes supposent
que l'environnement virtuel contenant le SDK est activé (`.venv/Scripts/Activate.ps1`
sous PowerShell ou `source .venv/bin/activate` sous Linux/macOS).

```powershell
cytools new ./CyToolExample --name CyToolExample --id cy.tool.example
cd CyToolExample
cytools validate CyTool.json
python -m unittest -v
python tool.py describe
python tool.py list-operations
python tool.py invoke echo --params-file params.json
```

Le générateur crée un Tool fonctionnel. `params.json` contient `{"text":"Hello CyTools"}`.
L'invocation retourne un objet job avec `state: Completed` et `outputs.text`.
Les paramètres passés dans un fichier évitent les différences d'échappement entre shells.

## Ajouter une opération

Dans `CyTool.json`, ajouter un objet dans operations avec id/name/description,
inputSchema/outputSchema. Employer `additionalProperties: false` pour détecter les
fautes de frappe dans les paramètres. Le manifest lui-même accepte des métadonnées
inconnues pour permettre l'évolution du standard.

Dans `create_runtime`, écrire `def operation(context, parameters)` puis appeler
`runtime.register('operation_id', operation)`. Toute opération déclarée doit avoir un
handler : le runtime refuse de démarrer sinon. La CLI et le catalogue MCP se mettent à
jour automatiquement, sans écrire un outil MCP supplémentaire.

Consulter le handler `write_report` du guide IA pour produire un fichier, et les sept
opérations de `cytool_test/__init__.py` pour l'annulation, la progression et les erreurs.

## Lancer en MCP

Installer `cytools-core[mcp]` depuis le checkout ou le wheel. Configurer un client MCP
stdio pour lancer l'interpréteur Python du Tool avec les arguments absolus :

```json
{
  "mcpServers": {
    "cytool-example": {
      "command": "C:/path/to/venv/Scripts/python.exe",
      "args": ["C:/path/to/CyToolExample/tool.py", "--data-dir", "C:/path/to/data/mcp", "mcp"]
    }
  }
}
```

Ce bloc illustre le format courant `mcpServers` ; l'emplacement et la syntaxe de la
configuration dépendent du client. Ne pas écraser sa configuration existante.
Le client découvre `op_echo`, appelle `{"parameters":{"text":"Hello"}}`, puis
consulte `cy_get_job` avec le jobId retourné. Voir [MCP.md](MCP.md).

## Livrer

Installer le wheel de CyToolsCore avec le Tool, ou référencer une version précise.
Ne pas dépendre d'un chemin de développement privé dans la distribution finale.
Le SDK livre des scripts console Python ; produire un `.exe` autonome avec son outil
de packaging est une étape propre au Tool, à tester avec ses dépendances.
La génération ne choisit pas de licence à la place du propriétaire du projet.
