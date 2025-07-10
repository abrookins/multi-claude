#!/usr/bin/env python3
"""
Claude Task Setup Script

This script automates the workflow of:
1. Reading requirements from text input or GitHub issue URL
2. Cloning a repository
3. Creating a new branch
4. Creating TASK_MEMORY.md with requirements and self-instructions
5. Setting up the workspace for development

Usage:
    python gh_task_setup.py --repo <repo_url> --requirements <text_or_issue_url>
    python gh_task_setup.py --repo https://github.com/user/repo --requirements "Add feature X"
    python gh_task_setup.py --repo https://github.com/user/repo --requirements https://github.com/user/repo/issues/123
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


def run_command(cmd, cwd=None, capture_output=True):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=capture_output, text=True, check=True
        )
        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        print(f"Error running command '{cmd}': {e}")
        if capture_output and e.stderr:
            print(f"Error output: {e.stderr}")
        return None


def is_github_issue_url(text):
    """Check if the text is a GitHub issue URL."""
    pattern = r'https://github\.com/[\w\-\.]+/[\w\-\.]+/issues/\d+'
    return bool(re.match(pattern, text))


def is_requirements_file(text):
    """Check if the text is a file path that exists."""
    return os.path.isfile(text)


def read_requirements_file(file_path):
    """Read requirements from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            print(f"Warning: Requirements file {file_path} is empty")
            return "No requirements specified"
        
        return content
    except Exception as e:
        print(f"Error reading requirements file {file_path}: {e}")
        return None


def fetch_github_issue(issue_url):
    """Fetch GitHub issue content using GitHub API."""
    # Parse URL to extract owner, repo, and issue number
    pattern = r'https://github\.com/([\w\-\.]+)/([\w\-\.]+)/issues/(\d+)'
    match = re.match(pattern, issue_url)
    
    if not match:
        print(f"Invalid GitHub issue URL: {issue_url}")
        return None
    
    owner, repo, issue_number = match.groups()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
    
    try:
        # Create request with authentication if GITHUB_TOKEN is available
        headers = {}
        github_token = os.getenv('GITHUB_TOKEN')
        if github_token:
            headers['Authorization'] = f'token {github_token}'
            headers['User-Agent'] = 'gh-task-setup-script'
        
        request = Request(api_url, headers=headers)
        
        with urlopen(request) as response:
            if response.status != 200:
                print(f"HTTP error {response.status} fetching issue")
                return None
            issue_data = json.loads(response.read().decode('utf-8'))
        
        title = issue_data.get('title', '')
        body = issue_data.get('body', '')
        labels = [label['name'] for label in issue_data.get('labels', [])]
        
        # Format the issue content
        formatted_content = f"# {title}\n\n"
        if labels:
            formatted_content += f"**Labels:** {', '.join(labels)}\n\n"
        formatted_content += f"**Issue URL:** {issue_url}\n\n"
        formatted_content += f"## Description\n\n{body}\n"
        
        return formatted_content
    
    except (URLError, HTTPError) as e:
        print(f"Error fetching GitHub issue: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error fetching GitHub issue: {e}")
        return None


def is_local_path(repo_path):
    """Check if the repo argument is a local path rather than a URL."""
    # Handle relative and absolute paths
    abs_path = os.path.abspath(repo_path)
    return os.path.exists(abs_path) and os.path.isdir(abs_path)


def is_git_url(repo_url):
    """Check if the repo argument is a Git URL."""
    return repo_url.startswith(('http://', 'https://', 'git@', 'ssh://'))


def generate_feature_summary(requirements):
    """Generate a short feature summary from requirements for directory naming."""
    # Extract first line or first sentence
    first_line = requirements.split('\n')[0].strip()
    if not first_line:
        return "task"
    
    # Remove common prefixes and clean up
    prefixes_to_remove = ['add ', 'implement ', 'create ', 'build ', 'fix ', 'update ', 'modify ', 'refactor ']
    cleaned = first_line.lower()
    for prefix in prefixes_to_remove:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    
    # Extract key words (limit to 3-4 words)
    words = re.sub(r'[^a-zA-Z0-9\s]', '', cleaned).split()[:4]
    if not words:
        return "task"
    
    return "-".join(words)


def get_repo_name(repo_input):
    """Extract repository name from URL or local path."""
    if is_local_path(repo_input):
        return os.path.basename(os.path.abspath(repo_input))
    else:
        parsed = urlparse(repo_input)
        path = parsed.path.strip('/')
        if path.endswith('.git'):
            path = path[:-4]
        return path.split('/')[-1]


def get_feature_repo_name(repo_input, requirements):
    """Get repository name with feature summary appended."""
    base_name = get_repo_name(repo_input)
    feature_summary = generate_feature_summary(requirements)
    return f"{base_name}-{feature_summary}"


def get_unique_repo_path(base_path):
    """Generate a unique repository path by appending a counter if needed."""
    if not base_path.exists():
        return base_path
    
    counter = 1
    while True:
        unique_path = Path(f"{base_path}-{counter}")
        if not unique_path.exists():
            return unique_path
        counter += 1


def copy_local_repo(source_path, dest_path, branch_name):
    """Copy local repository to destination and reset to main branch."""
    import shutil
    
    # Find a unique destination path instead of overwriting
    unique_dest_path = get_unique_repo_path(dest_path)
    if unique_dest_path != dest_path:
        print(f"Directory {dest_path} exists, using {unique_dest_path} instead")
        dest_path = unique_dest_path
    
    print(f"Copying repository from {source_path} to {dest_path}")
    shutil.copytree(source_path, dest_path)
    
    # Remove virtual environment directories
    venv_dirs = ['venv', 'env', '.venv']
    for venv_dir in venv_dirs:
        venv_path = dest_path / venv_dir
        if venv_path.exists():
            print(f"Removing virtual environment directory: {venv_path}")
            shutil.rmtree(venv_path)
    
    # Check if there are any uncommitted changes and stash them
    status_result = run_command("git status --porcelain", cwd=dest_path)
    if status_result and status_result.strip():
        print("Found uncommitted changes, stashing them...")
        stash_result = run_command("git stash push -m 'Auto-stash before reset to main'", cwd=dest_path)
        if stash_result is None:
            print("Failed to stash changes, performing hard reset...")
    
    # Try to fetch latest changes if remote exists
    remote_check = run_command("git remote", cwd=dest_path)
    if remote_check and remote_check.strip():
        print("Fetching latest changes...")
        fetch_result = run_command("git fetch origin", cwd=dest_path)
        has_remote = fetch_result is not None
    else:
        print("No remote repository configured, skipping fetch")
        has_remote = False
    
    # Try to checkout main/master branch
    for main_branch in ['main', 'master']:
        print(f"Attempting to checkout {main_branch} branch...")
        checkout_result = run_command(f"git checkout {main_branch}", cwd=dest_path)
        if checkout_result is not None:
            if has_remote:
                # Reset to latest origin if we have a remote
                reset_result = run_command(f"git reset --hard origin/{main_branch}", cwd=dest_path)
                if reset_result is not None:
                    print(f"Successfully reset to origin/{main_branch}")
                    break
                else:
                    print(f"Failed to reset to origin/{main_branch}, using local {main_branch}")
                    break
            else:
                print(f"Successfully checked out local {main_branch} branch")
                break
        else:
            print(f"Branch {main_branch} not found")
    else:
        print("Warning: Could not find main or master branch, staying on current branch")
    
    return True


def create_task_memory(requirements, repo_path, branch_name):
    """Create TASK_MEMORY.md file with requirements and instructions."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    content = f"""# Task Memory

**Created:** {timestamp}
**Branch:** {branch_name}

## Requirements

{requirements}

## Development Notes

*Update this section as you work on the task. Include:*
- *Progress updates*
- *Key decisions made*
- *Challenges encountered*
- *Solutions implemented*
- *Files modified*
- *Testing notes*

### Work Log

- [{timestamp}] Task setup completed, TASK_MEMORY.md created

---

*This file serves as your working memory for this task. Keep it updated as you progress through the implementation.*
"""
    
    memory_file = os.path.join(repo_path, "TASK_MEMORY.md")
    with open(memory_file, 'w') as f:
        f.write(content)
    
    print(f"Created TASK_MEMORY.md in {memory_file}")
    return memory_file


def list_staged_directories(staging_dir=None):
    """List staged tasks in a simple table format."""
    from datetime import datetime
    
    # Get staging directory
    if staging_dir is None:
        home_dir = Path.home()
        staging_dir = home_dir / ".mcl" / "staging"
    else:
        staging_dir = Path(staging_dir)
    
    if not staging_dir.exists():
        print(f"Staging directory {staging_dir} does not exist.")
        return
    
    # Find all directories in staging
    staged_dirs = []
    for item in staging_dir.iterdir():
        if item.is_dir():
            # Get last modified time for sorting
            mtime = item.stat().st_mtime
            dir_name = item.name
            
            staged_dirs.append({
                'name': dir_name,
                'path': str(item),
                'mtime': mtime
            })
    
    if not staged_dirs:
        print("No tasks found.")
        return
    
    # Sort by modification time (newest first)
    staged_dirs.sort(key=lambda x: x['mtime'], reverse=True)
    
    # Simple table format
    print("Tasks:")
    print("------")
    for i, dir_info in enumerate(staged_dirs, 1):
        print(f"{i:2d}. {dir_info['name']}")
    
    print()
    print("Shell integration:")
    print("- Use: mcl_cd N           (change to task N)")
    print("- Or:  mcl cd N | source")
    print("- Setup: Add 'eval \"$(mcl shell-init)\"' to your ~/.bashrc or ~/.zshrc")
    print()
    
    return staged_dirs


def handle_cd_command(staging_dir, selection):
    """Handle the --cd command for shell integration."""
    # Get staging directory
    if staging_dir is None:
        home_dir = Path.home()
        staging_dir = home_dir / ".mcl" / "staging"
    else:
        staging_dir = Path(staging_dir)
    
    if not staging_dir.exists():
        print("echo 'No tasks found - staging directory does not exist'", file=sys.stderr)
        sys.exit(1)
    
    # Find all directories in staging
    staged_dirs = []
    for item in staging_dir.iterdir():
        if item.is_dir():
            mtime = item.stat().st_mtime
            staged_dirs.append({
                'name': item.name,
                'path': str(item),
                'mtime': mtime
            })
    
    if not staged_dirs:
        print("echo 'No tasks found'", file=sys.stderr)
        sys.exit(1)
    
    # Sort by modification time (newest first)
    staged_dirs.sort(key=lambda x: x['mtime'], reverse=True)
    
    try:
        index = int(selection) - 1
        if 0 <= index < len(staged_dirs):
            selected_dir = staged_dirs[index]
            # Output shell command to change directory
            print(f"cd '{selected_dir['path']}'")
        else:
            print("echo 'Invalid selection'", file=sys.stderr)
            sys.exit(1)
    except ValueError:
        print("echo 'Invalid selection - must be a number'", file=sys.stderr)
        sys.exit(1)


def generate_shell_integration():
    """Generate shell integration code for bash/zsh."""
    # Get the absolute path to this script
    script_path = os.path.abspath(__file__)
    
    shell_code = f'''
# Multi-Claude (mcl) shell integration
# Add this to your ~/.bashrc or ~/.zshrc: eval "$(python {script_path} shell-init)"

mcl_cd() {{
    if [[ $# -eq 0 ]]; then
        # No arguments - show list
        python "{script_path}" list
    else
        # Change to task by number
        local dir_command=$(python "{script_path}" cd "$1")
        if [[ $? -eq 0 ]] && [[ -n "$dir_command" ]]; then
            eval "$dir_command"
        fi
    fi
}}

# Autocomplete for mcl_cd
_mcl_cd_complete() {{
    local cur="${{COMP_WORDS[COMP_CWORD]}}"
    local staging_dir="$HOME/.mcl/staging"
    
    if [[ -d "$staging_dir" ]]; then
        local count=$(find "$staging_dir" -maxdepth 1 -type d | wc -l)
        count=$((count - 1))  # Subtract 1 for the staging directory itself
        
        if [[ $count -gt 0 ]]; then
            COMPREPLY=($(compgen -W "$(seq 1 $count)" -- "$cur"))
        fi
    fi
}}

# Register completion for bash
if [[ -n "$BASH_VERSION" ]]; then
    complete -F _mcl_cd_complete mcl_cd
fi'''
    return shell_code.strip()


def cmd_start(args):
    """Handle the 'start' subcommand - create a new task workspace."""
    # Determine if we're working with a local repo or URL
    is_local = is_local_path(args.repo)
    
    # Determine workspace directory
    if is_local:
        # For local repos, use staging directory (unless workspace explicitly overrides)
        if args.workspace:
            workspace_path = Path(args.workspace).resolve()
        else:
            # Default to ~/.mcl/staging directory
            home_dir = Path.home()
            default_staging = home_dir / ".mcl" / "staging"
            staging_dir = args.staging_dir or str(default_staging)
            
            workspace_path = Path(staging_dir).resolve()
            workspace_path.mkdir(parents=True, exist_ok=True)
    else:
        # For URLs, use staging directory by default
        if args.workspace:
            workspace_path = Path(args.workspace).resolve()
        else:
            # Default to ~/.mcl/staging directory
            home_dir = Path.home()
            default_staging = home_dir / ".mcl" / "staging"
            staging_dir = args.staging_dir or str(default_staging)
            
            workspace_path = Path(staging_dir).resolve()
            workspace_path.mkdir(parents=True, exist_ok=True)
    
    # Process requirements first (needed for feature naming)
    if is_github_issue_url(args.requirements):
        print(f"Fetching GitHub issue: {args.requirements}")
        requirements = fetch_github_issue(args.requirements)
        if not requirements:
            print("Failed to fetch GitHub issue")
            sys.exit(1)
    elif is_requirements_file(args.requirements):
        print(f"Reading requirements from file: {args.requirements}")
        requirements = read_requirements_file(args.requirements)
        if not requirements:
            print("Failed to read requirements file")
            sys.exit(1)
    else:
        requirements = args.requirements
    
    # Get repository name with feature summary and determine unique path
    repo_name = get_repo_name(args.repo)
    feature_repo_name = get_feature_repo_name(args.repo, requirements)
    base_repo_path = workspace_path / feature_repo_name
    repo_path = get_unique_repo_path(base_repo_path) if not args.continue_branch and not args.no_clone else base_repo_path
    
    print("Setting up task workflow...")
    print(f"Repository: {args.repo}")
    print(f"Workspace: {workspace_path}")
    print(f"Repository path: {repo_path}")
    print(f"Feature directory: {feature_repo_name}")
    
    # Generate branch name if not provided
    if args.branch:
        branch_name = args.branch
    else:
        # Create branch name from requirements (first few words, sanitized)
        words = re.sub(r'[^\w\s]', '', requirements.split('\n')[0]).split()[:3]
        branch_name = "feature/" + "-".join(words).lower()
    
    print(f"Using branch: {branch_name}")
    
    # Handle repository cloning/copying
    if not args.no_clone:
        if is_local:
            print("Copying local repository...")
            if repo_path.exists():
                if args.continue_branch:
                    print(f"Directory {repo_path} exists, using existing repository")
                else:
                    print(f"Directory {repo_path} already exists. Will overwrite...")
            
            if not args.continue_branch or not repo_path.exists():
                copy_success = copy_local_repo(Path(args.repo).resolve(), repo_path, branch_name)
                if not copy_success:
                    print("Failed to copy local repository")
                    sys.exit(1)
        else:
            print("Cloning repository...")
            if repo_path.exists():
                if args.continue_branch:
                    print(f"Directory {repo_path} exists, using existing repository")
                else:
                    # repo_path should already be unique from get_unique_repo_path above
                    print(f"Using unique directory path: {repo_path}")
                    
            if not repo_path.exists():
                # Extract just the directory name for the clone command
                clone_dir_name = repo_path.name
                clone_result = run_command(f"git clone {args.repo} {clone_dir_name}", cwd=workspace_path)
                if clone_result is None:
                    print("Failed to clone repository")
                    sys.exit(1)
    else:
        if not repo_path.exists():
            print(f"Repository path {repo_path} does not exist and --no-clone specified")
            sys.exit(1)
    
    # Handle branch creation/checkout
    if args.continue_branch:
        print(f"Checking out existing branch '{branch_name}'...")
        # Try to checkout existing branch, create if it doesn't exist
        checkout_result = run_command(f"git checkout {branch_name}", cwd=repo_path)
        if checkout_result is None:
            print(f"Branch '{branch_name}' not found, creating new branch...")
            checkout_result = run_command(f"git checkout -b {branch_name}", cwd=repo_path)
            if checkout_result is None:
                print("Failed to create branch")
                sys.exit(1)
    else:
        print(f"Creating new branch '{branch_name}'...")
        checkout_result = run_command(f"git checkout -b {branch_name}", cwd=repo_path)
        if checkout_result is None:
            print("Failed to create branch")
            sys.exit(1)
    
    # Create or update TASK_MEMORY.md
    memory_file = os.path.join(repo_path, "TASK_MEMORY.md")
    if args.continue_branch and os.path.exists(memory_file):
        print("TASK_MEMORY.md exists, updating with new session...")
        # Append new session info to existing file
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        additional_content = f"\n\n## New Session - {timestamp}\n\n"
        if args.instructions:
            additional_content += f"**Additional Instructions:** {args.instructions}\n\n"
        additional_content += f"**Requirements (refresher):**\n{requirements}\n\n"
        additional_content += f"- [{timestamp}] Resumed work on existing branch\n"
        
        with open(memory_file, 'a') as f:
            f.write(additional_content)
    else:
        print("Creating TASK_MEMORY.md...")
        memory_file = create_task_memory(requirements, repo_path, branch_name)
    
    # Add and commit TASK_MEMORY.md changes
    print("Committing TASK_MEMORY.md changes...")
    run_command("git add TASK_MEMORY.md", cwd=repo_path)
    commit_msg = "Update TASK_MEMORY.md" if args.continue_branch else "Add TASK_MEMORY.md for task tracking"
    run_command(f'git commit -m "{commit_msg}"', cwd=repo_path)
    
    print("\n" + "="*50)
    print("SETUP COMPLETE!")
    print("="*50)
    print(f"Repository cloned to: {repo_path}")
    print(f"Branch created: {branch_name}")
    print(f"Task memory file: {memory_file}")
    
    if not args.no_claude:
        print("\nStarting Claude Code with initial prompt...")
        
        # Create initial prompt for Claude
        if args.continue_branch:
            initial_prompt = f"""I'm continuing work on an existing task. Here's the current state:

**Repository:** {repo_name}
**Branch:** {branch_name} (existing branch)
**Task Memory:** TASK_MEMORY.md (contains previous work and notes)

Please start by reading the TASK_MEMORY.md file to understand the requirements and previous work done. The file has been updated with this new session."""
            
            if args.instructions:
                initial_prompt += f"""

**Current Instructions:** 
{args.instructions}"""
            
            initial_prompt += f"""

**Requirements (refresher):**
{requirements}

Please review the current state and continue working on the task!"""
        else:
            initial_prompt = f"""I've set up a new task workspace for you. Here's what's been prepared:

**Repository:** {repo_name}
**Branch:** {branch_name} (new branch)
**Task Memory:** TASK_MEMORY.md (contains requirements and notes)

**Important:** If this is a Python project, you should set up a virtual environment before starting work:
1. Check the README or setup documentation for specific virtualenv instructions
2. If no specific instructions exist, create a standard virtual environment:
   - `python -m venv venv` (or `python3 -m venv venv`)
   - Activate it: `source venv/bin/activate` (Linux/Mac) or `venv\\Scripts\\activate` (Windows)
   - Install dependencies: `pip install -r requirements.txt` (if requirements.txt exists)

Please start by reading the TASK_MEMORY.md file to understand the requirements, then set up the development environment as needed, and begin working on the task. Remember to update TASK_MEMORY.md with your progress, decisions, and notes as you work."""
            
            if args.instructions:
                initial_prompt += f"""

**Additional Instructions:** 
{args.instructions}"""
            
            initial_prompt += f"""

**Requirements:**
{requirements}

Let's get started!"""
        
        # Change to the repo directory and start Claude Code
        os.chdir(repo_path)
        
        try:
            # Start Claude Code with the initial prompt
            subprocess.run(['claude', initial_prompt], check=True)
        except subprocess.CalledProcessError:
            print("Failed to start Claude Code. Make sure 'claude' command is available.")
            print("You can start it manually with: claude")
        except FileNotFoundError:
            print("Claude Code not found. Install it or start manually with: claude")
    else:
        print("\nNext steps:")
        print(f"1. cd {repo_path}")
        print("2. Start Claude Code: claude")
        print("3. Read TASK_MEMORY.md and begin working")
        print("4. Update TASK_MEMORY.md as you progress")


def cmd_list(args):
    """Handle the 'list' subcommand - list all staged tasks."""
    list_staged_directories(args.staging_dir)


def cmd_shell_init(args):
    """Handle the 'shell-init' subcommand - output shell integration code."""
    print(generate_shell_integration())


def cmd_cd(args):
    """Handle the 'cd' subcommand - output shell command to change directory."""
    handle_cd_command(args.staging_dir, args.number)


def main():
    """Main CLI entry point with subcommands."""
    parser = argparse.ArgumentParser(
        prog='mcl',
        description='Multi-Claude task management - work on multiple features simultaneously',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  mcl start --repo https://github.com/user/repo --requirements "Add auth"
  mcl --repo https://github.com/user/repo --requirements "Add auth"  # (backwards compatible)
  mcl list
  mcl cd 1
  mcl shell-init

For shell integration, add this to your ~/.bashrc or ~/.zshrc:
  eval "$(mcl shell-init)"
  
Then use:
  mcl_cd        # List tasks
  mcl_cd 1      # Change to task 1
        '''
    )
    
    # Add backwards compatibility arguments to main parser
    parser.add_argument('--repo', help='Repository URL to clone or local directory path')
    parser.add_argument('--requirements', help='Requirements text, GitHub issue URL, or file path')
    parser.add_argument('--branch', help='Branch name (auto-generated if not provided)')
    parser.add_argument('--workspace', help='Workspace directory')
    parser.add_argument('--staging-dir', help='Staging directory (default: ~/.mcl/staging)')
    parser.add_argument('--instructions', help='Additional instructions for Claude Code')
    parser.add_argument('--continue-branch', action='store_true',
                        help='Continue work on existing branch instead of creating new one')
    parser.add_argument('--no-clone', action='store_true', help='Skip cloning (repo already exists)')
    parser.add_argument('--no-claude', action='store_true', help='Skip starting Claude Code after setup')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Start subcommand
    start_parser = subparsers.add_parser('start', help='Start a new task workspace')
    start_parser.add_argument('--repo', required=True, 
                             help='Repository URL to clone or local directory path')
    start_parser.add_argument('--requirements', required=True,
                             help='Requirements text, GitHub issue URL, or file path')
    start_parser.add_argument('--branch', help='Branch name (auto-generated if not provided)')
    start_parser.add_argument('--workspace', help='Workspace directory')
    start_parser.add_argument('--staging-dir', help='Staging directory (default: ~/.mcl/staging)')
    start_parser.add_argument('--instructions', help='Additional instructions for Claude Code')
    start_parser.add_argument('--continue-branch', action='store_true',
                             help='Continue work on existing branch instead of creating new one')
    start_parser.add_argument('--no-clone', action='store_true', help='Skip cloning (repo already exists)')
    start_parser.add_argument('--no-claude', action='store_true', help='Skip starting Claude Code after setup')
    start_parser.set_defaults(func=cmd_start)
    
    # List subcommand
    list_parser = subparsers.add_parser('list', help='List all staged tasks')
    list_parser.add_argument('--staging-dir', help='Staging directory (default: ~/.mcl/staging)')
    list_parser.set_defaults(func=cmd_list)
    
    # Shell-init subcommand
    shell_parser = subparsers.add_parser('shell-init', help='Output shell integration code for bash/zsh')
    shell_parser.set_defaults(func=cmd_shell_init)
    
    # CD subcommand (for shell integration)
    cd_parser = subparsers.add_parser('cd', help='Output shell command to change directory to task N')
    cd_parser.add_argument('number', help='Task number to change to')
    cd_parser.add_argument('--staging-dir', help='Staging directory (default: ~/.mcl/staging)')
    cd_parser.set_defaults(func=cmd_cd)
    
    args = parser.parse_args()
    
    # Backwards compatibility: if no subcommand but --repo and --requirements are provided, assume 'start'
    if not args.command:
        if args.repo and args.requirements:
            # Redirect to start command
            args.command = 'start'
            args.func = cmd_start
        else:
            parser.print_help()
            return
    
    args.func(args)


if __name__ == "__main__":
    main()
