<#!
.SYNOPSIS
Launch Bonzi from a Windows source checkout.

.EXAMPLE
.\run.ps1
#>
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSCommandPath

# Match run.sh: import the package directly from the source tree.
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$repoRoot\src;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = "$repoRoot\src"
}

& py -3.12 -m bonzi.app @Arguments
exit $LASTEXITCODE
