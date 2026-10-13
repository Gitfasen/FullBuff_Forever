<#
.SYNOPSIS
  Creates a directory junction <AddOns>\FullBuff -> <repo>\addon\FullBuff.
  Never deletes or overwrites real folders.
#>
param(
    [string]$AddOnsPath = 'C:\Program Files (x86)\World of Warcraft\_classic_beta_\Interface\AddOns',
    [string]$RepoAddonPath = (Join-Path $PSScriptRoot '..\addon\FullBuff')
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $RepoAddonPath -PathType Container)) {
    Write-Error "Repo addon folder not found: $RepoAddonPath"
    exit 1
}
$source = (Resolve-Path -LiteralPath $RepoAddonPath).Path.TrimEnd('\')

if (-not (Test-Path -LiteralPath $AddOnsPath -PathType Container)) {
    Write-Error "AddOns folder not found: $AddOnsPath"
    exit 1
}
$target = Join-Path $AddOnsPath 'FullBuff'

$item = Get-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue
if ($null -ne $item) {
    $isJunction = ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -and ($item.LinkType -eq 'Junction')
    if (-not $isJunction) {
        Write-Error "Refusing: '$target' exists and is not a junction. Remove or rename it yourself."
        exit 1
    }
    $current = @($item.Target)[0]
    if ($null -ne $current -and $current.TrimEnd('\') -ieq $source) {
        Write-Host "Junction already exists: $target -> $source"
        exit 0
    }
    Write-Error "Refusing: junction '$target' points to '$current', not '$source'. Remove it yourself if intended."
    exit 1
}

cmd /c mklink /J "$target" "$source"
if ($LASTEXITCODE -ne 0) {
    Write-Error "mklink failed (exit $LASTEXITCODE)"
    exit 1
}
Write-Host "Junction created: $target -> $source"
exit 0
