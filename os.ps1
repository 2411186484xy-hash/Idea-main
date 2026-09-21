#Requires -Version 5.1
<# Idea OS v2 single entry. Usage: .\os.ps1 <command> [args...] #>
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
& python "$Repo\cli.py" @args
exit $LASTEXITCODE
