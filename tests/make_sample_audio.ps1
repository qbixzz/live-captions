# Makes tests\sample.wav: about 40 s of English from Windows text-to-speech, with pauses between sentences,
# for tests\test_pipeline.py and rehearse.bat. Run:  powershell -ExecutionPolicy Bypass -File tests\make_sample_audio.ps1
param([string]$Out = (Join-Path $PSScriptRoot "sample.wav"))
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = 0
$s.SetOutputToWaveFile($Out)
$lines = @(
  "Good morning everyone, and thank you for joining the call today.",
  "First, I will give a short overview of the project and the timeline.",
  "We started the proof of concept in September, and the first version went live last month.",
  "The main goal is to let people sign in once and use the same account for several services.",
  "So far, about two thousand users have tried it, and the feedback has been mostly positive.",
  "The biggest problem we found was the time it takes to verify a new account.",
  "Next quarter, we want to cut that time in half.",
  "Do you have any questions before we move on to the budget?"
)
foreach ($l in $lines) {
  $s.Speak($l)
  $p = New-Object System.Speech.Synthesis.PromptBuilder
  $p.AppendBreak([TimeSpan]::FromMilliseconds(900))
  $s.Speak($p)
}
$s.Dispose()
Write-Output "wrote $Out"
