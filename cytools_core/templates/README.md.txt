# __TOOL_NAME__

Generated standalone CyTool. Python 3.11+ required.

This is a development scaffold, not a finished user distribution. Follow
Docs/StandaloneDelivery.md for mandatory ImGui, native launchers, clean layout,
model access/download UI and GitHub updates. Use `cytools new --desktop` for new Tools.

Read Docs/Localization.md and Docs/GenerationConfigurations.md. The standalone UI
must default to English, offer French, and provide an Options tab with persistent
preferences, component licenses, Save/Load configuration and optional generation
autosave. Configuration JSON is reusable through the same runtime by an AI;
loading a configuration must never start a job or restore credentials.

Install the CyToolsCore wheel from the SDK's dist/ directory, or:

```powershell
python -m pip install -e '<SDK_ROOT>[mcp]'
```

Replace that development path with your actual SDK checkout. There is no required
dependency on CyToolsManager, CyAICodex or an AI provider.

```powershell
cytools validate CyTool.json
python -m unittest -v
python tool.py describe
python tool.py invoke echo --params-file params.json
python tool.py --data-dir .cytools/mcp mcp
```

The MCP client launches the last command, with an absolute Python executable and an
absolute tool.py path. Add the optional MCP dependency before using it.
For multiple clients sharing one scheduler, provision credentials with create-client,
launch serve once, then use --connect and CYTOOLS_TOKEN per client (SDK Docs/MultiClient.md).

To implement your tool, replace the echo operation in CyTool.json, its handler in
tool.py and the corresponding tests. Follow AGENTS.md and SDK Docs/AgentGuide.md.
CyToolsGuide.md is a local copy of that guide; `cytools docs` locates the full SDK docs.
The SDK schemas are the protocol source of truth. Unknown metadata is preserved.
