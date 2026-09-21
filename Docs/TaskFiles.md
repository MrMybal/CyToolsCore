# Task files — SDK 0.9.0

SDK sessions are temporary by default. A task can contain several jobs; completion of
one producer must not delete results needed by consumers. Models, application code,
shared installation caches and the original source files are never task artifacts.

## Tool implementation (mandatory)

Configure the accepted input root once in create_runtime, before starting:

```python
runtime.configure_inputs(DATA / 'inputs', fields={
    'image_to_mesh': ['image_file'],
    'synthesize': ['references.*.audio'],
})
```

Use the same root as the existing input resolver (including any configured environment
variable). Declare every input-file field, including nested array fields. These fields
accept absolute external paths; the SDK copies the source into a unique task-owned
subdirectory of the accepted input root before calling the handler. Existing relative
paths are also copied. A model path, LoRA, export destination or executable is NOT an
input artifact: do not declare these in fields. Keep file format/size validation in the
handler. The shared import bundle limit defaults to 8 GiB, configurable by the Tool.
All generated files, intermediate files and worker diagnostics MUST use JobContext.path.
Never write generated media into a global directory. Explicit user saves (profiles,
model registration, installation) remain persistent operations.

## AI / MCP use

- Call operations with an absolute input path directly; no shell copy is required.
- Or call `cy_import_file({"source":"D:/project/image.png"})`. The Tool process copies
  it and returns `path` (absolute), `relativePath`, SHA256 and size. Supply path to the
  operation. OBJ/MTL/textures and GLTF/BIN references are copied automatically. Additional
  files can be passed as `companions`, relative paths from
  the source directory; directory structure is preserved. Import the bundle before
  submitting it. This never downloads a model.
- Poll `cy_get_job`; read/consume the results while the task remains open.
- To preserve a result, use `cy_export_job({"jobId":"...","destination":"D:/project/results"})`.
  This copies the job bundle, including supporting files, into a unique destination
  directory outside the runtime; returned output paths point to the exported copy.
- Call `cy_finish_task({})` after all consumers finish. It removes imported copies AND
  whole job workspaces: generated results, intermediates and logs. It never removes
  the original files or the explicit exported bundle. An active worker returns Busy;
  `cancelRunning:true` requests cancellation and defers deletion until workers stop.
- Disconnect also finishes all connection-owned tasks. A forgotten idle task expires
  after 3600 seconds by default. `cy_keep_task_alive` renews it; active workers are
  never removed by expiration. `cy_begin_task` accepts retentionSeconds (1..86400).
  Its returned sessionId can be passed to operation envelopes and task controls for
  concurrent task graphs. Finish each Tool's task only after downstream consumers
  have imported or consumed its output. Paths between machines require a transfer
  transport; a local path refers to the Tool's host.

SDK equivalents: CreateSession, ImportFile, SubmitJob, ExportJob, FinishTask,
KeepTaskAlive; same authenticated ownership in JSONL and HTTP. Native Python:

```python
with runtime.task(actor) as session_id:
    job = runtime.submit(actor, session_id, 'image_to_mesh', {'image_file': source})
    result = runtime.wait(actor, job['jobId'], timeout=300)
    saved = runtime.export_job(actor, job['jobId'], destination)
```

The context manager closes on exceptions as well. Normal runtime shutdown cleans
remaining temporary tasks. On restart, recorded temporary tasks are recovered for
cleanup; recorded live worker processes block deletion. A redirected workspace or a
locked file produces cleanupError and retries, never an unsafe recursive deletion.
Do not claim that an OS-denied source can be read: the MCP must return a useful error.

## Standalone and compatibility

Interactive UI sessions MUST explicitly use `temporary=False`; their generated results
remain available after closing the UI. Imported working copies still disappear on
session/runtime close. CLI `invoke` and saved-configuration replay remain persistent
for backwards compatibility. AI automation should use task sessions via SDK/MCP.
Pre-0.9 sessions have no temporary flag and are preserved; there is no destructive
migration of old inputs/results. Small SQLite job/session history remains, with the
parameters and output payload removed for purged jobs (`artifactsDeleted:true`).
Model weights and secrets must not be put into a job workspace or export bundle.

## Verification required before delivery

Test external image/audio/video/mesh inputs without manually placing them under the
Tool; assert the real resolver accepts the staged path. Test bundles, failed/cancelled
jobs, disconnect, expiration, exports, client isolation and a worker still running.
Verify every configured file field, not only one selected Tool. A transport test is
not proof of a new full AI inference run; report the distinction explicitly.
