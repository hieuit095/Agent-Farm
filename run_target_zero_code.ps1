$ErrorActionPreference = "Continue"
$env:GITHUB_TOKEN = "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"
$env:MINIMAX_API_KEY = "sk-cp-Z4G537Cg5j_dS3BMexXLL69tDq3V6ULdPHuUnMlk8dY-tYVY66oCRXGaXRN2qAOFrrLOAB9uyhOzm4PX7v-gLi8uu8LykVcQMeytB4IsD1upPW9v0zj4ETo"

Write-Host "=== Farm-Agent Live Fire: zero-code ==="
Write-Host "Token: $($env:GITHUB_TOKEN.Substring(0,8))..."
Write-Host "Starting at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

cd C:\Users\USER\Documents\GitHub\ContribAI
python -m farm_agent.cli.main target "https://github.com/hieuit095/zero-code" 2>&1
$exitCode = $LASTEXITCODE

Write-Host "Finished at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "Exit code: $exitCode"
exit $exitCode
