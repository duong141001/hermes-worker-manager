[CmdletBinding()]
param(
    [string]$HermesHome = $env:HERMES_HOME,
    [switch]$SkipEnable
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($HermesHome)) {
    $HermesHome = Join-Path $HOME '.hermes'
}

$RepoRoot = Split-Path $PSScriptRoot -Parent
$HermesHome = [System.IO.Path]::GetFullPath($HermesHome)
$BackupRoot = Join-Path $HermesHome ('backups\hermes-worker-manager-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))

function Install-PluginFiles {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$TargetRoot,
        [Parameter(Mandatory = $true)][string[]]$Files
    )

    if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
        throw "Missing source directory: $SourceRoot"
    }

    foreach ($RelativePath in $Files) {
        $SourcePath = Join-Path $SourceRoot $RelativePath
        if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
            throw "Missing source file: $SourcePath"
        }
    }

    if (Test-Path -LiteralPath $TargetRoot) {
        $RelativeTarget = [System.IO.Path]::GetRelativePath($HermesHome, $TargetRoot)
        $BackupTarget = Join-Path $BackupRoot $RelativeTarget
        New-Item -ItemType Directory -Force -Path (Split-Path $BackupTarget -Parent) | Out-Null
        Copy-Item -LiteralPath $TargetRoot -Destination $BackupTarget -Recurse -Force
        Remove-Item -LiteralPath $TargetRoot -Recurse -Force
    }

    New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null
    foreach ($RelativePath in $Files) {
        $SourcePath = Join-Path $SourceRoot $RelativePath
        $TargetPath = Join-Path $TargetRoot $RelativePath
        New-Item -ItemType Directory -Force -Path (Split-Path $TargetPath -Parent) | Out-Null
        Copy-Item -LiteralPath $SourcePath -Destination $TargetPath -Force
    }
}

$RouterSource = Join-Path $RepoRoot 'plugins\smit-worker-router'
$HandoffSource = Join-Path $RepoRoot 'plugins\smit-opaque-handoff'
$GuardSource = Join-Path $RepoRoot 'plugins\smit-sanitization-guard'
$DesktopSource = Join-Path $RepoRoot 'desktop-plugins\smit-worker-router'

Install-PluginFiles `
    -SourceRoot $RouterSource `
    -TargetRoot (Join-Path $HermesHome 'plugins\smit-worker-router') `
    -Files @('__init__.py', 'plugin.yaml', 'dashboard\manifest.json', 'dashboard\plugin_api.py')

Install-PluginFiles `
    -SourceRoot $HandoffSource `
    -TargetRoot (Join-Path $HermesHome 'plugins\smit-opaque-handoff') `
    -Files @('__init__.py', 'plugin.yaml')

Install-PluginFiles `
    -SourceRoot $GuardSource `
    -TargetRoot (Join-Path $HermesHome 'plugins\smit-sanitization-guard') `
    -Files @('__init__.py', 'plugin.yaml')

Install-PluginFiles `
    -SourceRoot $DesktopSource `
    -TargetRoot (Join-Path $HermesHome 'desktop-plugins\smit-worker-router') `
    -Files @('plugin.js')

if (-not $SkipEnable) {
    $Hermes = Get-Command hermes -ErrorAction SilentlyContinue
    if ($null -eq $Hermes) {
        Write-Warning 'Hermes CLI was not found on PATH. Enable the plugins manually after Hermes is available.'
    }
    else {
        & $Hermes.Source plugins enable --no-allow-tool-override smit-worker-router
        if ($LASTEXITCODE -ne 0) { throw 'Failed to enable smit-worker-router.' }
        & $Hermes.Source plugins enable --no-allow-tool-override smit-opaque-handoff
        if ($LASTEXITCODE -ne 0) { throw 'Failed to enable smit-opaque-handoff.' }
        & $Hermes.Source plugins enable --no-allow-tool-override smit-sanitization-guard
        if ($LASTEXITCODE -ne 0) { throw 'Failed to enable smit-sanitization-guard.' }
    }
}

Write-Host ''
Write-Host 'Hermes Worker Manager installed.' -ForegroundColor Green
Write-Host "HERMES_HOME: $HermesHome"
if (Test-Path -LiteralPath $BackupRoot) {
    Write-Host "Backup: $BackupRoot"
}
Write-Host ''
Write-Host 'Next steps:'
Write-Host '  Restart the Hermes gateway from a separate shell.'
Write-Host '  Restart Hermes Desktop, or run Command Palette -> Reload desktop plugins.'
Write-Host '  Open the Worker Manager and Worker Monitor panes.'
Write-Host ''
Write-Host 'The installer did not change provider credentials, endpoints, or delegation sandbox policy.'
