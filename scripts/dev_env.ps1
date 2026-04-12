param(
  [string]$CondaEnv = "tracking",
  [string]$LJHome = "E:\projects\LJDDS\LJDDS\DDSCore3.0.1",
  [ValidateSet("mock","real")]
  [string]$Mode = "real"
)

conda activate $CondaEnv

$env:LJDDSHOME = $LJHome
$env:PATH = "$env:LJDDSHOME\bin\x64Win64Python;$env:PATH"
$env:DDS_MODE = $Mode
$env:DDS_PLATFORM = "win"
$env:DDS_QOS_FILE = "$env:LJDDSHOME\qosconf\example.xml"
$env:DDS_LICENSE_FILE = "$env:LJDDSHOME\ljddslicense.lic"

Write-Host "DDS env ready:"
Write-Host "  CONDA_ENV=$CondaEnv"
Write-Host "  DDS_MODE=$env:DDS_MODE"
Write-Host "  DDS_PLATFORM=$env:DDS_PLATFORM"
Write-Host "  DDS_QOS_FILE=$env:DDS_QOS_FILE"
Write-Host "  DDS_LICENSE_FILE=$env:DDS_LICENSE_FILE"
