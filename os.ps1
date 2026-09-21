#Requires -Version 7.0
<# Idea OS v2 single entry. Usage: .\os.ps1 <command> [args...] #>
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
& python "$Repo\cli.py" @args
exit $LASTEXITCODE
