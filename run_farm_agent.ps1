$ErrorActionPreference = "Continue"
$env:GITHUB_TOKEN = "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"
$env:MINIMAX_API_KEY = "sk-cp-Z4G537Cg5j_dS3BMexXLL69tDq3V6ULdPHuUnMlk8dY-tYVY66oCRXGaXRN2qAOFrrLOAB9uyhOzm4PX7v-gLi8uu8LykVcQMeytB4IsD1upPW9v0zj4ETo"

Write-Host "Token: $($env:GITHUB_TOKEN.Substring(0,8))..."
Write-Host "Minimax: $($env:MINIMAX_API_KEY.Substring(0,8))..."

# Test GitHub API first
python -c "import os; print('Test:', os.environ['GITHUB_TOKEN'][:8])"
