# Unreal integration

Core 0.11.0 uses [CyMCPSDK](https://github.com/MrMybal/CyMCPSDK) for native
communication. Read [NativeCommunication.md](NativeCommunication.md). Existing
plugin integrations must explicitly update their bindings and packaged libraries;
this Core migration does not validate a new Unreal engine integration. The legacy
CyUEMCPSDK companion notes below describe its existing architecture, not a required
Python communication dependency for a new native integration.

[CyUEMCPSDK](https://github.com/MrMybal/CyUEMCPSDK) adapts CyToolsCore contracts
to Unreal plugins. Follow its Docs/Integration.md and Docs/UpdateExistingPlugin.md.
For an existing plugin, embed and adapt the C++ sources into its existing modules;
the separate reference plugins are development examples, not mandatory dependencies.
The Python companion uses CyToolsCore without copying its runtime or schemas.

Authentication, jobs, permissions and temporary task files retain the Core contract.
Unreal assets integrated into a project remain persistent project changes.
Provider transports are included in the SDK; CyAIConnectorLab is not a dependency.
External MCP access and embedded assistant tool access require separate integration
and validation. See the SDK validation guide for Windows Editor 5.3–5.8 coverage.

The optional Unreal assistant can ship one offline ZIP containing portable Python,
its official Core wheel and companion dependencies. Follow the SDK's
Docs/AssistantRuntime.md: background detection, explicit first-use installation,
shared user storage by default and optional plugin-local storage. Only immutable,
compatible bundles are shared; plugin sessions, settings and task files stay isolated.
This assistant-specific policy does not change private Python environments for
inference CyTools.


Licence et redistribution commerciale : lire [Licensing.md](Licensing.md).
Conserver les notices MIT du SDK et les licences distinctes des composants tiers.
