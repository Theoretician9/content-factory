# PowerShell script to sync local changes to GitHub
$repoPath = "C:\Users\nikit\cod\content-factory"
$gitPath = "git"

# Change to repository directory
Set-Location $repoPath

# Add all changes
& $gitPath add .

# Commit changes with timestamp
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
& $gitPath commit -m "Auto-sync: $timestamp"

# Push to GitHub
& $gitPath push origin main 