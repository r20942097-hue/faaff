# Install Agent Reach v1.6.0 and/or NVIDIA SkillSpector on Windows.
# Source: https://github.com/Panniantong/Agent-Reach/blob/main/docs/install.md
#         https://github.com/NVIDIA/SkillSpector
# Does not need administrator privileges and does not install uv automatically.
[CmdletBinding()]
param(
    [ValidateSet('Both', 'AgentReach', 'SkillSpector')]
    [string]$Target = 'Both',
    [switch]$DryRun,
    [switch]$RunSetup,
    [switch]$SkipSetup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$agentReachRelease = 'git+https://github.com/Panniantong/Agent-Reach.git@beabda7486e9a666360b18cdb5c0e759c2c4d20f'
$skillSpectorSource = 'git+https://github.com/NVIDIA/skillspector.git@54921c8c7c23008c8af2328d5ab492a904b6ece4'
$wantAgentReach = $Target -eq 'Both' -or $Target -eq 'AgentReach'
$wantSkillSpector = $Target -eq 'Both' -or $Target -eq 'SkillSpector'
if ($RunSetup -and $SkipSetup) { throw 'Choose only one of -RunSetup or -SkipSetup.' }

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    Write-Host ('> ' + [IO.Path]::GetFileName($Executable) + ' ' + ($Arguments -join ' '))
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit $LASTEXITCODE): $Executable $($Arguments -join ' ')"
    }
}

function Assert-AgentReachVersionInfo {
    param([Parameter(Mandatory)][string]$VersionText)
    try {
        $parsed = ConvertFrom-Json -InputObject $VersionText -ErrorAction Stop
        if ($null -eq $parsed -or $parsed.schema_version -ne 1 -or
            $parsed.ok -ne $true -or $parsed.action -ne 'version' -or
            $null -eq $parsed.result) { throw 'Unexpected version response envelope' }
        $value = [string]$parsed.result.version
        if ($value -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid semantic version' }
        if ([version]$value -lt [version]'1.6.0') { throw 'Version is older than 1.6.0' }
        return $value
    }
    catch {
        throw 'Existing agent-reach version cannot be verified as v1.6+. No installation was overwritten or setup executed.'
    }
}

Write-Host 'Development tool setup — existing installations are not overwritten.'
Write-Host 'Target:' $Target
Write-Host 'Pinned Agent Reach version: v1.6.0 / beabda7486e9a666360b18cdb5c0e759c2c4d20f'
Write-Host 'SkillSpector: upstream commit 54921c8c7c23008c8af2328d5ab492a904b6ece4 (content-ref pinned).'

if ($DryRun) {
    Write-Host '[DRY RUN] No commands executed and no files changed.'
    if ($wantSkillSpector) { Write-Host "PLAN: uv tool install $skillSpectorSource (only if command absent)" }
    if ($wantAgentReach) {
        Write-Host "PLAN: uv tool install $agentReachRelease (only if command absent)"
        if ($RunSetup -and -not $SkipSetup) { Write-Host 'PLAN: agent-reach setup (installs default channels and links agent skill)' }
    }
    return
}

$uvCmd = Get-Command 'uv' -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    throw 'uv is not on PATH. Install uv from https://docs.astral.sh/uv/getting-started/installation/ and rerun. No changes were made.'
}
$uvExe = $uvCmd.Source
$binDirectory = (& $uvExe tool dir --bin | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $binDirectory) { throw 'Could not locate uv tool binary directory.' }
# Extend the PATH only for this PowerShell process, not the machine/user PATH.
$env:PATH = $binDirectory + [IO.Path]::PathSeparator + $env:PATH

if ($wantSkillSpector) {
    $spectorCmd = Get-Command 'skillspector' -ErrorAction SilentlyContinue
    if ($spectorCmd) {
        Write-Host 'SkillSpector already present; leaving the installation unchanged.'
    }
    else {
        Invoke-Checked -Executable $uvExe -Arguments @('tool', 'install', $skillSpectorSource)
        $spectorCmd = Get-Command 'skillspector' -ErrorAction Stop
    }
    Invoke-Checked -Executable $spectorCmd.Source -Arguments @('--help')
}

if ($wantAgentReach) {
    $reachCmd = Get-Command 'agent-reach' -ErrorAction SilentlyContinue
    $wasAlreadyInstalled = [bool]$reachCmd
    if ($wasAlreadyInstalled) {
        $versionText = (& $reachCmd.Source version | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { throw 'An existing agent-reach command could not report its version. No overwrite attempted.' }
        $currentVersion = Assert-AgentReachVersionInfo -VersionText $versionText
        Write-Host "Agent Reach v$currentVersion already present; leaving the installation unchanged."
    }
    else {
        Invoke-Checked -Executable $uvExe -Arguments @('tool', 'install', $agentReachRelease)
        $reachCmd = Get-Command 'agent-reach' -ErrorAction Stop
        $freshVersion = (& $reachCmd.Source version | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { throw 'Fresh Agent Reach CLI failed its version command.' }
        $null = Assert-AgentReachVersionInfo -VersionText $freshVersion
    }
    if ($RunSetup -and -not $SkipSetup) {
        Write-Host 'Setting up Agent Reach default channels and agent skill. No optional account login is requested.'
        Invoke-Checked -Executable $reachCmd.Source -Arguments @('setup')
    }
    else {
        Write-Host 'Agent Reach setup skipped by default. Explicitly use -RunSetup after reviewing its channel/skill changes.'
    }
    if ($wasAlreadyInstalled -or ($RunSetup -and -not $SkipSetup)) {
        Invoke-Checked -Executable $reachCmd.Source -Arguments @('doctor', '--text')
        Invoke-Checked -Executable $reachCmd.Source -Arguments @('skill')
    }
    else {
        Write-Host 'Fresh installation is staged; doctor and skill checks require -RunSetup.'
    }
}

Write-Host 'Completed requested installer steps. Review all diagnostic output above.'
Write-Host 'For future updates, inspect release notes before running: agent-reach update / uv tool upgrade skillspector'
