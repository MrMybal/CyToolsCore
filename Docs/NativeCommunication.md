# Native communication — CyToolsCore 0.11.0

CyMCPSDK 0.7.1 owns MCP, the structured CLI, JSONL, HTTP and the native communication
SDK. The Python Tool runtime retains handlers, manifests, JSON Schema 2020-12,
jobs, reservations, downloads and task files. Tool engines, model catalogues,
standalone interfaces and generation settings are not replaced.

## Components

- `Native/`: C++20 integration linked to `CyMCP::Core`, `CyMCP::MCP` and `CyMCP::Http`.
- `CyTools::Communication`: embeddable native host and SDK adapter.
- `cytools-native`: native CLI client of an existing service. It needs no Python
  to communicate; a Python Tool service still needs its Python engine/runtime.
- `cytools_communication.dll` / `libcytools_communication.so` / `.dylib`: C ABI 1.
- `transports/cli.py`, `http.py`, `mcp.py`: compatibility bindings only, loaded lazily.
  There is no fallback to the previous Python transport implementation.
- `transports/api.py`: internal dispatch to the existing authenticated runtime
  Principal, not another public network or MCP implementation.

The Python `mcp` package is a conformance-test client only, never a runtime dependency.
Importing the Core does not load the native library, an interface or an AI provider.

## Build and distribute

Use CMake 3.24+, C++20 and CyMCPSDK 0.7.1 including the checked host extensions.

```powershell
python scripts/build_native.py --cymcp-source ../CyMCPSDK
python -m build --no-isolation
```

An installed CyMCPSDK can be selected with `--prefix PATH_TO_INSTALL` instead.
The build never downloads dependencies. The platform wheel includes the library,
native executable and full licences; a wheel without the native library is refused.
Compile separately per OS/architecture. Windows requires the matching Microsoft
Visual C++ runtime. Linux/macOS validation must run separately.

For a native application, install the CMake build and link:

```cmake
find_package(CyToolsCommunication 0.11 CONFIG REQUIRED)
target_link_libraries(my_tool PRIVATE CyTools::Communication)
```

Include `<cytools/communication.hpp>` and provide a trusted `HostCallback`, or use
CyMCPSDK's Registry directly for a fully native application's operations. Native
C++ consumers require a compatible compiler ABI; the C ABI serves Python bindings.
The private host callback is never exposed as an AI-callable endpoint.

## Existing Tools and clients

Install the **platform wheel** in the Tool's private environment. Existing
`run_cli(create_runtime)` entry points, operation names, request envelopes and
`--connect URL mcp` remain available. Both local and shared-service communication
run through CyMCPSDK. No Tool runtime is copied or replaced.

`cytools new` remains an authoring command, not an AI communication transport.
New scaffolds require Core 0.11.0. Their standalone interface and engines retain
their own Python dependencies. This change does not claim a full C++ Tool runtime.

CLI `invoke` now owns a **temporary task**, like AI/MCP sessions. Returned JSON
preserves the business value snapshot; `artifactsDeleted` describes its internal
files after cleanup. To retain generated files, export before the task finishes:

```powershell
cytool-test invoke generate_file --params-file params.json --export-dir C:/Exports
```

`--export-dir` requires an absolute destination outside the runtime and returns the
ExportJob bundle (`jobId`, `directory`, durable `outputs`) on stdout. Without it,
temporary paths must not be consumed after the process exits. In SDK/MCP workflows,
use ExportJob / `cy_export_job` before FinishTask / `cy_finish_task`. Standalone
UI sessions remain explicitly `temporary=False`. Mutations are never auto-retried.

MCP retains the full `$ref`/`pattern` schemas, asynchronous job envelope and controls.
The existing text result and `{result: ...}` structured output remain compatible.
`cy_share_job` additionally exposes the existing sharing operation. Authenticated
HTTP keeps `POST /v1`; native SDK `describe`/`invoke` requests expose the same
registered operation catalogue. MCP stdio is provided; this adapter does not
advertise a shared MCP HTTP endpoint.

## Identity and ownership

The native HTTP authenticator derives identity from the Bearer credential. Its
trusted callback maps to a runtime Principal; business `clientId` or `principal`
fields cannot choose the identity. MCP connections own separate task sets.
Disconnect requests cleanup through the existing runtime; files and reservations
remain owned until handlers/workers actually stop.

CyMCPSDK's default schema profile stays fail-closed. This integration explicitly
supplies a checked Draft 2020-12 validator, preserving full Tool schemas without
stripping constraints. Only local schema references are allowed. HTTP is loopback
only, rejects browser Origins and bounds request bodies to 1 MiB. stdout is reserved
for structured results and protocols; diagnostics use stderr.

Keep callbacks and native workers alive until requests finish. Close the native
host before its owned runtime. Do not destroy a host during an active embedding call.

## Validation

```powershell
python -m pytest -q
python -m build --no-isolation
```

Conformance covers a real MCP client, two identities, advanced schemas, cancellation,
disconnect cleanup, UTF-8/BOM inputs, durable exports and the executable with Python
absent from PATH. Provider authentication, inference and model quality are not
established by these transport tests.

## Licences and sources

Retain root `LICENCES/` and the notices packaged with the native library.

- Core (MIT): https://github.com/MrMybal/CyToolsCore
- Communication (MIT): https://github.com/MrMybal/CyMCPSDK

Models, providers and Tool applications retain their own terms. No model is bundled.


## Native host callback (ABI 1)

Each callback accepts a private JSON object and returns `{result: value}` or
`{error: {code, message, ...}}`. The adapter supplies the authenticated identity.
Never expose these envelopes as untrusted business arguments.

| Private method | Host responsibility |
| --- | --- |
| `$bootstrap` | Start/reuse the Tool runtime from `params.dataDir`; return an opaque `principal`. |
| `$authenticate` | Authenticate transport `token`; return an opaque principal. |
| `$request` | Dispatch portable `request` using the separately supplied authenticated `principal`. |
| `$schemas` | Return `requests` (method to parameter schema) and `job` from portable Core schemas. |
| `$check_schema` | Check the full schema declaration and reject nonlocal references. |
| `$validate` | Validate `value` against the complete `schema`; no defaults at this boundary. |
| `$create_client` | CLI bootstrap/admin creation only; return a runtime-issued credential. |

The standalone native MCP bridge fetches contracts and delegates full validation
to the authenticated service. `cytools.host` management requests allow only schema
discovery and validation of already registered schemas. They cannot bootstrap,
authenticate another identity, or evaluate arbitrary client-supplied schemas.
Generations are never used as validation probes.

[Examples/NativeClient](../Examples/NativeClient/README.md) contains real installed
C++ and plain-C consumers. Install the CMake build, build these examples, then use
`CYTOOLS_TOKEN` with the actual service URL for a native call.


## Reproduce the dependency source snapshot

The accompanying `Native/patches/CyMCPSDK-0.7.1-host.patch` contains the native
host extensions against CyMCPSDK commit
`791d4d7d7680213b282ec8529d248a10f8494d77`. The supplied local CyMCPSDK checkout
already contains them; do not apply the patch twice. For a clean checkout at that
exact commit, apply the patch with `git apply PATH_TO_PATCH` from its SDK directory,
then build the Core against it. CI uses this pinned base plus patch, never a moving
branch. These local changes do not imply that a 0.7.1 SDK release has been published.


Full portable operation IDs remain accepted. If adding the MCP `op_` prefix would
exceed the native tool-name bound, discovery supplies a stable bounded alias and
the description retains the original ID. `cy_submit_job` always accepts the exact
portable operationId, including 128-character IDs, with the same task envelope.
Existing valid `op_` names are unchanged.


## Effective AI capability discovery (0.11.0)

Before starting the runtime, call `cytools_core.communication.register_operations(runtime)`.
The read-only `ai_communication_status` operation reports the actually loaded native
Core/CyMCPSDK versions, lifecycle rules and, with `includeOperations: true`, the
complete effective operation schemas, permissions and resources. It does not start
a server, call a provider or grant permissions. The scaffold includes this registration.
MCP catalogues are paginated: follow `nextCursor` to inspect every operation.
