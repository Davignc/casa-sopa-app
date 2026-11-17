param([string]$TextoPath, [string]$SaidaPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$narradorSopa = New-Object System.Speech.Synthesis.SpeechSynthesizer
$narradorSopa.SelectVoice('Microsoft Maria Desktop')
$narradorSopa.Rate = 1
$narradorSopa.SetOutputToWaveFile($SaidaPath)
$narradorSopa.Speak([System.IO.File]::ReadAllText($TextoPath, [System.Text.Encoding]::UTF8))
$narradorSopa.Dispose()
