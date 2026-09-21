param(
    [string]$AudioFile = 'dog.wav',
    [ValidateSet('general','sounds','music')][string]$Preset = 'general'
)
$ErrorActionPreference = 'Stop'
$toolPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $toolPython)) { throw 'Install this Tool environment first; see README.md.' }
$toolParameters = @{audio_file=$AudioFile; preset=$Preset; top_k=5; max_seconds=30} | ConvertTo-Json
$toolArgumentsPath = Join-Path $PSScriptRoot 'params.last-run.json'
[System.IO.File]::WriteAllText($toolArgumentsPath, $toolParameters, [System.Text.UTF8Encoding]::new($false))
& $toolPython (Join-Path $PSScriptRoot 'tool.py') invoke classify_audio --params-file $toolArgumentsPath --timeout 600
exit $LASTEXITCODE
