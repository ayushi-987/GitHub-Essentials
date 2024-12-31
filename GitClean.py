import git
import os
import requests
import subprocess
import sys
from datetime import datetime, timedelta

headers = {
    'Authorization': 'token <PERSONAL_TOKEN>',
    'Accept': 'application/vnd.github.v3+json'
}


def get_all_repositories():
    url = "https://api.github.com/orgs/<ORG_NAME>/repos"
    repos = []
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            repos.extend([repo['name'] for repo in response.json()])            
            if 'next' in response.links:
                url = response.links['next']['url']
            else:
                url = None
        else:
            break
    return repos

def get_branches(repo, days=90):
    """
    Fetch all branches and categorize them into active and inactive based on recent commits within the last 'days'.
    """
    active_branches = []
    inactive_branches = []
    url = f"https://api.github.com/repos/<ORG_NAME>/{repo}/branches"
    params = {'per_page': 100}
    page = 1
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    print("Fetching all the branches...")

    while True:
        response = requests.get(url, headers=headers, params={**params, 'page': page})

        if response.status_code == 200:
            branches = response.json()
            if not branches:
                print("No more branches found.")
                break

            print(f"Fetched {len(branches)} branches from page {page}.")

            for branch in branches:
                branch_name = branch['name']
                commit_url = branch['commit']['url']
                commit_response = requests.get(commit_url, headers=headers)

                if commit_response.status_code == 200:
                    commit_data = commit_response.json()
                    try:
                        commit_date = datetime.strptime(
                            commit_data['commit']['committer']['date'], "%Y-%m-%dT%H:%M:%SZ"
                        )
                    except KeyError:
                        print(f"Error: Missing date for branch {branch_name}")
                        continue

                    print(f"Branch: {branch_name}, Last Commit Date: {commit_date}")

                    if commit_date >= cutoff_date:
                        active_branches.append({'name': branch_name, 'commit_date': commit_date})
                    else:
                        inactive_branches.append({'name': branch_name, 'commit_date': commit_date})
                else:
                    print(f"Error fetching commit details for branch {branch_name}: {commit_response.status_code} - {commit_response.json().get('message', '')}")
        elif response.status_code == 403:
            print("Rate limit reached. Waiting before retrying...")
            time.sleep(60)  # Wait and retry
            continue
        else:
            print(f"Error fetching branches: {response.status_code} - {response.json().get('message', '')}")
            sys.exit(1)

        if len(branches) < 100:
            break
        page += 1

    # Sort by commit date in ascending order
    active_branches = sorted(active_branches, key=lambda x: x['commit_date'])
    inactive_branches = sorted(inactive_branches, key=lambda x: x['commit_date'])

    return active_branches, inactive_branches

def delete_branch(repo, branch_name):
    """
    Delete the specified branch from the repository.
    """
    delete_url = f"https://api.github.com/repos/<ORG_NAME>/{repo}/git/refs/heads/{branch_name}"
    response = requests.delete(delete_url, headers=headers)

    if response.status_code == 204:
        print(f"Branch {branch_name} deleted successfully.")
    else:
        print(f"Error deleting branch {branch_name}: {response.status_code} - {response.json().get('message', '')}")

def get_open_pull_requests(repo):
    """Fetch all open pull requests for a repository."""
    url = f"https://api.github.com/repos/<ORG_NAME>/{repo}/pulls"
    params = {'state': 'open', 'per_page': 100}
    page = 1
    open_prs = []

    while True:
        response = requests.get(url, headers=headers, params={**params, 'page': page})

        if response.status_code == 200:
            prs = response.json()
            if not prs:
                print("No more open PRs found.")
                break

            print(f"Fetched {len(prs)} open PRs from page {page}.")

            for pr in prs:
                pr_data = {
                    'number': pr['number'],
                    'created_at': pr['created_at'],
                    'title': pr['title'],
                    'url': pr['html_url'],
                    'commits_url': pr['commits_url']
                }
                open_prs.append(pr_data)
        elif response.status_code == 403:
            print("Rate limit reached. Waiting before retrying...")
            time.sleep(60)  # Wait and retry
            continue
        else:
            print(f"Error fetching pull requests: {response.status_code} - {response.json().get('message', '')}")
            sys.exit(1)

        if len(prs) < 100:
            break
        page += 1

    return open_prs

def close_old_prs(repo, days=30):
    """Close open PRs that have no commits in the last specified number of days."""
    open_prs = get_open_pull_requests(repo)
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    for pr in open_prs:
        commits_url = pr['commits_url']
        params = {'per_page': 100}
        page = 1
        latest_commit_date = None

        while True:
            commits_response = requests.get(commits_url, headers=headers, params={**params, 'page': page})
            if commits_response.status_code == 200:
                commits = commits_response.json()
                if not commits:
                    break

                # Check the date of the last commit on this page
                commit_date = datetime.strptime(commits[-1]['commit']['committer']['date'], "%Y-%m-%dT%H:%M:%SZ")
                if not latest_commit_date or commit_date > latest_commit_date:
                    latest_commit_date = commit_date

                # If the latest commit date is before the cutoff date, no need to check further
                if latest_commit_date < cutoff_date:
                    break
            else:
                print(f"Error fetching commits for PR #{pr['number']}: {commits_response.status_code} - {commits_response.text}")
                break

            if len(commits) < 100:
                break
            page += 1

        if latest_commit_date and latest_commit_date < cutoff_date:
            print(f"Closing PR #{pr['number']} titled '{pr['title']}' with latest commit on {latest_commit_date}")
            #close_pr(repo, pr['number'])
        elif not latest_commit_date:
            print(f"No commits found for PR #{pr['number']}. Closing it.")
            #close_pr(repo, pr['number'])

def close_pr(repo, pr_number):
    """Close a pull request by number."""
    print(f"Closing pr: {pr_number}")
    url = f"https://api.github.com/repos/<ORG_NAME>/{repo}/pulls/{pr_number}"
    response = requests.patch(url, headers=headers, json={'state': 'closed'})

    if response.status_code == 200:
        print(f"PR #{pr_number} closed successfully.")
    else:
        print(f"Error closing PR #{pr_number}: {response.status_code} - {response.json().get('message', '')}")

if __name__ == "__main__":
    #print(f"script start")
    repos = get_all_repositories()
    #print(f"reepoooo {repos}")
    for repo in repos:
        print(f"Processing repository: {repo}")
        #active_branches, inactive_branches = get_branches(repo, days=90)
        #for branch in inactive_branches:
            #print(f"Deleting branch: {branch['name']} in repository: {repo}")
            #delete_branch(repo, branch['name'])
        close_old_prs(repo, days=30)
