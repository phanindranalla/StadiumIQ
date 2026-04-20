# StadiumIQ Git Push Script
# This script stages all changes and pushes them directly to the main branch.

Write-Host "Checking for git..."

# Attempt to find git.exe in common GitHub Desktop paths if not in PATH
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    $GhDesktopGit = Get-ChildItem -Path "$env:LOCALAPPDATA\GitHubDesktop" -Filter "git.exe" -Recurse -ErrorAction SilentlyContinue | 
                    Where-Object { $_.FullName -match "cmd\\git.exe" } | 
                    Sort-Object LastWriteTime -Descending | 
                    Select-Object -First 1 -ExpandProperty FullName
    
    if ($GhDesktopGit) {
        Write-Host "Git detected in GitHub Desktop: $GhDesktopGit"
        function git { & $GhDesktopGit $args }
    } else {
        Write-Error "Git is not installed or not in your PATH. Please install Git for Windows or point to your git.exe path."
        exit 1
    }
}

Write-Host "Staging all changes..."
git add .

Write-Host "Committing changes..."
git commit -m "Deploying StadiumIQ to Cloud Run - automated commit"

Write-Host "Pushing to the main branch..."
git push origin main

Write-Host "Git push complete!"
