param(
    [string]$OllamaPath = (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'tools\ollama\ollama.exe'),
    [string]$BaseModel = 'gemma4:e2b',
    [string]$TargetModel = 'gemma4-e2b-text'
)
$ErrorActionPreference = 'Stop'
# İndirilmiş gerçek modelin üretim şablonunu ve lisansını korur.
$definition = & $OllamaPath show $BaseModel --modelfile
if ($LASTEXITCODE -ne 0) { throw 'Önce Ollama sunucusunu başlatın ve taban modeli indirin.' }
$firstFromSeen = $false
$textDefinition = foreach ($line in $definition) {
    if ($line -match '^FROM ') {
        if ($firstFromSeen) { continue }
        $firstFromSeen = $true
    }
    # Görüntü/ses projector ağırlıkları ve spekülatif üretim modeli yazılı akış için gerekmez.
    if ($line -match '^(DRAFT |PARAMETER draft_num_predict )') { continue }
    $line
}
if (!$firstFromSeen) { throw 'Taban modelin metin ağırlıkları bulunamadı.' }
$runtimeDirectory = Join-Path (Split-Path $PSScriptRoot -Parent) 'var'
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
$definitionPath = Join-Path $runtimeDirectory 'Modelfile.gemma4-e2b-text'
$textDefinition | Set-Content -LiteralPath $definitionPath -Encoding utf8
& $OllamaPath create $TargetModel -f $definitionPath
if ($LASTEXITCODE -ne 0) { throw 'Metin model tanımı oluşturulamadı.' }
