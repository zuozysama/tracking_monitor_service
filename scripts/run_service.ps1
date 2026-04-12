param(
  [string]$CondaEnv = "tracking",
  [string]$LJHome = "E:\projects\LJDDS\LJDDS\DDSCore3.0.1",
  [ValidateSet("mock","real")]
  [string]$Mode = "real",
  [int]$Port = 8080
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

Set-Location $projectRoot
. "$scriptDir\dev_env.ps1" -CondaEnv $CondaEnv -LJHome $LJHome -Mode $Mode

uvicorn app:app --host 0.0.0.0 --port $Port
