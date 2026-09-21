# Validation

Run from the repository root with Python 3.11 or newer:

```powershell
python -m pip install -e ".[mcp,dev]"
python -m pytest -q
python -m build --no-isolation
```

The automated suite covers schemas, authentication and ownership, concurrent scheduling,
worker cancellation, resource reservations, HTTP/MCP, automatic input staging,
temporary task cleanup, export, shared downloads, configuration and desktop scaffolding.
Inspect wheel and source archive contents; schemas, templates and guides are required.

Optional .NET interoperability: `dotnet build Examples/DotNetClient`, followed by
`python scripts/validate_dotnet.py`. The GitHub workflow defines Windows/Linux/macOS
and Python 3.11/3.12 jobs. A local Windows pass does not certify the other platforms.
Resource-capacity tests use fixtures; they do not establish model inference quality
or GPU capacity for third-party Tools. Those need their own delivery evidence.
