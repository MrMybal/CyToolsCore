# Creating and maintaining CyToolCLAP

Read README.md, CyTool.json and tool.py before modifying this tool.
Read CyToolsGuide.md (local copy) or CyToolsCore Docs/AgentGuide.md as the implementation contract.
Run `cytools docs` to locate the complete documentation installed with the SDK.

1. Declare every operation in CyTool.json: inputSchema, outputSchema, supportedBackends,
   permissions, resourceRequirements and actual platform support.
2. Register one handler per declared operation in create_runtime().
3. Handler signature: handler(context, parameters) -> JSON-serializable outputs.
4. Check context.cancellation during loops; use context.cancellation.sleep() for waits.
5. Create outputs using context.path('outputs/name.ext'). Never share a fixed output path.
6. Use context.progress(percent, currentStep='...') when supportsProgress is true.
7. Use runtime.register(id, handler, estimate=...) for parameter-dependent RAM/VRAM.
8. Do not implement a second scheduler, job registry, authentication system or MCP parser.
9. No UI, specific AI model or external CLI is required by the core.
10. Treat external files and executable arguments as untrusted; use argv, never shell interpolation.
11. Add real operation tests (invalid inputs, failure, cancellation, output validity).
12. Run: cytools validate CyTool.json; python -m unittest -v; python tool.py describe;
    python tool.py invoke classify_audio --params-file params.json.
    Run validate_public.py separately for real CLAP and MCP inference.
13. Document dependencies, model licenses, platform verification and limitations honestly.
14. A descriptor does not implement a backend. Do not claim a capability without code and tests.

User operation parameters cannot choose clientId, owner or a different session.
Permissions belong to the authenticated transport context. Heavy/untrusted runtimes
belong in ProcessWorker; in-process cancellation is cooperative, not forcible.
