# Tool delivery checklist

Follow [StandaloneDelivery](StandaloneDelivery.md), [FullOperationAccess](FullOperationAccess.md)
and [TaskFiles](TaskFiles.md) before delivering a Tool.

- Validate the manifest and execute its automated tests.
- Launch the standalone from outside its installation folder; verify English/French,
  configuration persistence, copyable logs and every exposed business operation.
- Exercise CLI and real MCP calls, including external inputs, result export,
  cancellation and task cleanup after workers stop.
- Validate real model inference separately from synthetic transport tests.
- Record the executed platform, model revision, output format and resource measurements.
- Keep machine-specific reports under the Tool's data/reports directory.
- State untested platforms and operations explicitly. A scaffold alone is not a delivery.


## Native communication (Core 0.11.0)

Read [NativeCommunication.md](NativeCommunication.md). Use the platform Core wheel
containing CyMCPSDK C++ communication; source builds must compile Native/ first.
Do not add the Python MCP runtime or copy an old CLI/HTTP/MCP implementation.
Keep the Tool handlers, manifest, task files and standalone UI integration.
CLI `invoke` tasks are temporary; export wanted files with `--export-dir` or ExportJob.
