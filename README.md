# GitHub-Essentials
## GitHub Repo Cleanup Script

Automates the cleanup of stale branches and PRs in GitHub repositories.

### Features
- Identifies all repositories.
- Detects **inactive branches** and **PRs over 30 days** old.
- **Deletes unused branches** and **closes stale PRs**.

### Usage
Run the script with your GitHub token and desired action:
```bash
python cleanup.py
