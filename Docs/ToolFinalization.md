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
