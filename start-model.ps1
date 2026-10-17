param(
    [string]$OllamaDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'tools\ollama'),
    [string]$LogDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'run-logs')
)
$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot 'backend\.venv\Scripts\python.exe'
$ollamaPath = Join-Path $OllamaDirectory 'ollama.exe'
if (!(Test-Path -LiteralPath $pythonPath) -or !(Test-Path -LiteralPath $ollamaPath)) {
    throw 'Backend Python ortamı veya yerel Ollama kurulumu bulunamadı.'
}
New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
$env:OLLAMA_MODELS = Join-Path $OllamaDirectory 'models'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_CONTEXT_LENGTH = '8192'
$processIds = @{}
$savedProcesses = Join-Path $LogDirectory 'model-processes.json'
if (Test-Path -LiteralPath $savedProcesses) {
    foreach ($property in (Get-Content -LiteralPath $savedProcesses | ConvertFrom-Json).PSObject.Properties) {
        $processIds[$property.Name] = $property.Value
    }
}
try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 }
catch {
    $server = Start-Process -FilePath $ollamaPath -ArgumentList @('serve') -WorkingDirectory $OllamaDirectory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $LogDirectory 'ollama.out.log') -RedirectStandardError (Join-Path $LogDirectory 'ollama.err.log')
    $processIds.Ollama = $server.Id
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2; $ready = $true; break }
        catch { Start-Sleep -Seconds 1 }
    }
    if (!$ready) { throw 'Ollama başlatılamadı; ollama.err.log dosyasına bakın.' }
}
try { $null = Invoke-RestMethod 'http://127.0.0.1:8100/v1/health' -TimeoutSec 2 }
catch {
    $service = Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8100', '--env-file', (Join-Path $PSScriptRoot '.env')) -WorkingDirectory (Join-Path $PSScriptRoot 'model-service') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $LogDirectory 'model.out.log') -RedirectStandardError (Join-Path $LogDirectory 'model.err.log')
    $processIds.ModelService = $service.Id
}
if ($processIds.Count) { $processIds | ConvertTo-Json | Set-Content (Join-Path $LogDirectory 'model-processes.json') }
Write-Output 'Yerel model servisleri başlatıldı. Hazır olma durumu: http://127.0.0.1:8100/v1/health'
