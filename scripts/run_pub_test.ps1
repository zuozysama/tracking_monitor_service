param(
  [string]$CondaEnv = "tracking",
  [string]$LJHome = "E:\projects\LJDDS\LJDDS\DDSCore3.0.1",
  [ValidateSet("mock","real")]
  [string]$Mode = "real"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

Set-Location $projectRoot
. "$scriptDir\dev_env.ps1" -CondaEnv $CondaEnv -LJHome $LJHome -Mode $Mode

python .\scripts\win_dds_pub_test.py
