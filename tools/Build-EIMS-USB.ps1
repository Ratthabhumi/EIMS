#requires -Version 5.1
# Compatibility launcher. The reviewed clone workflow refuses existing targets.
& (Join-Path $PSScriptRoot 'handover/Clone-TwoUsb.ps1') -Kind USB_AUDITOR @args
exit $LASTEXITCODE
