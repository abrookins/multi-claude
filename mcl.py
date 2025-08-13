#!/usr/bin/env python3
"""
Claude Task Setup Script

This script automates the workflow of:
1. Reading requirements from text input or GitHub issue URL
2. Cloning a repository
3. Creating a new branch
4. Creating TASK_MEMORY.md with requirements and self-instructions (not committed to git)
5. Setting up the workspace for development

Note: TASK_MEMORY.md is excluded from version control via .gitignore to keep task notes local.

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
import time
import asyncio
import socket
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Optional dependencies for enhanced UX
try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich import box

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def run_command(cmd, cwd=None, capture_output=True):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            check=True,
        )
        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        print(f"Error running command '{cmd}': {e}")
        if capture_output and e.stderr:
            print(f"Error output: {e.stderr}")
        return None


def is_github_issue_url(text):
    """Check if the text is a GitHub issue URL."""
    pattern = r"https://github\.com/[\w\-\.]+/[\w\-\.]+/issues/\d+"
    return bool(re.match(pattern, text))


def is_requirements_file(text):
    """Check if the text is a file path that exists."""
    return os.path.isfile(text)


def read_requirements_file(file_path):
    """Read requirements from a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
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
    pattern = r"https://github\.com/([\w\-\.]+)/([\w\-\.]+)/issues/(\d+)"
    match = re.match(pattern, issue_url)

    if not match:
        print(f"Invalid GitHub issue URL: {issue_url}")
        return None

    owner, repo, issue_number = match.groups()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"

    try:
        # Create request with authentication if GITHUB_TOKEN is available
        headers = {}
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            headers["Authorization"] = f"token {github_token}"
            headers["User-Agent"] = "gh-task-setup-script"

        request = Request(api_url, headers=headers)

        with urlopen(request) as response:
            if response.status != 200:
                print(f"HTTP error {response.status} fetching issue")
                return None
            issue_data = json.loads(response.read().decode("utf-8"))

        title = issue_data.get("title", "")
        body = issue_data.get("body", "")
        labels = [label["name"] for label in issue_data.get("labels", [])]

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
    return repo_url.startswith(("http://", "https://", "git@", "ssh://"))


def generate_feature_summary(requirements):
    """Generate a short feature summary from requirements for directory naming."""
    # Extract first line or first sentence
    first_line = requirements.split("\n")[0].strip()
    if not first_line:
        return "task"

    # Remove common prefixes and clean up
    prefixes_to_remove = [
        "add ",
        "implement ",
        "create ",
        "build ",
        "fix ",
        "update ",
        "modify ",
        "refactor ",
    ]
    cleaned = first_line.lower()
    for prefix in prefixes_to_remove:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break

    # Extract key words (limit to 3-4 words)
    words = re.sub(r"[^a-zA-Z0-9\s]", "", cleaned).split()[:4]
    if not words:
        return "task"

    return "-".join(words)


def get_repo_name(repo_input):
    """Extract repository name from URL or local path."""
    if is_local_path(repo_input):
        return os.path.basename(os.path.abspath(repo_input))
    else:
        parsed = urlparse(repo_input)
        path = parsed.path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return path.split("/")[-1]


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


def is_git_repo(path):
    """Check if a directory is a git repository."""
    git_dir = Path(path) / ".git"
    return git_dir.exists()


def setup_local_repo(source_path, dest_path, branch_name):
    """Set up local repository using git worktree if it's a git repo, otherwise copy."""
    import shutil

    # Find a unique destination path instead of overwriting
    unique_dest_path = get_unique_repo_path(dest_path)
    if unique_dest_path != dest_path:
        print(f"Directory {dest_path} exists, using {unique_dest_path} instead")
        dest_path = unique_dest_path

    # Check if source is a git repository
    if is_git_repo(source_path):
        print(f"Creating git worktree from {source_path} to {dest_path}")
        return create_git_worktree(source_path, dest_path, branch_name)
    else:
        print(
            f"Source is not a git repository, copying directory from {source_path} to {dest_path}"
        )
        return copy_non_git_directory(source_path, dest_path, branch_name)


def create_git_worktree(source_path, dest_path, branch_name):
    """Create a git worktree from source repository."""
    # First, ensure we're working from the main branch and have latest changes
    original_cwd = Path.cwd()

    try:
        # Work in the source repo to prepare it
        print("Preparing source repository...")

        # Stash any uncommitted changes in source
        status_result = run_command("git status --porcelain", cwd=source_path)
        if status_result and status_result.strip():
            print("Found uncommitted changes in source, stashing them...")
            run_command(
                "git stash push -m 'Auto-stash before worktree creation'",
                cwd=source_path,
            )

        # Try to fetch latest changes if remote exists
        remote_check = run_command("git remote", cwd=source_path)
        if remote_check and remote_check.strip():
            print("Fetching latest changes...")
            run_command("git fetch origin", cwd=source_path)

        # Find and checkout main/master branch
        main_branch = None
        for branch in ["main", "master"]:
            checkout_result = run_command(f"git checkout {branch}", cwd=source_path)
            if checkout_result is not None:
                main_branch = branch
                print(f"Checked out {branch} branch in source repository")
                break

        if not main_branch:
            print("Warning: Could not find main or master branch, using current branch")
            # Get current branch name
            current_branch = run_command("git branch --show-current", cwd=source_path)
            main_branch = current_branch.strip() if current_branch else "HEAD"

        # Create the worktree with new branch
        print(f"Creating worktree with branch '{branch_name}'...")
        worktree_result = run_command(
            f"git worktree add {dest_path} -b {branch_name}", cwd=source_path
        )

        if worktree_result is None:
            print("Failed to create git worktree, falling back to directory copy")
            return copy_non_git_directory(source_path, dest_path, branch_name)

        print(f"Successfully created git worktree at {dest_path}")
        return True

    except Exception as e:
        print(f"Error creating git worktree: {e}")
        print("Falling back to directory copy")
        return copy_non_git_directory(source_path, dest_path, branch_name)


def copy_non_git_directory(source_path, dest_path, branch_name):
    """Copy non-git directory or fallback copy method."""
    import shutil

    print(f"Copying directory from {source_path} to {dest_path}")
    shutil.copytree(source_path, dest_path)

    # Remove virtual environment directories
    venv_dirs = ["venv", "env", ".venv"]
    for venv_dir in venv_dirs:
        venv_path = dest_path / venv_dir
        if venv_path.exists():
            print(f"Removing virtual environment directory: {venv_path}")
            shutil.rmtree(venv_path)

    # If destination has .git, perform git operations
    if is_git_repo(dest_path):
        # Check if there are any uncommitted changes and stash them
        status_result = run_command("git status --porcelain", cwd=dest_path)
        if status_result and status_result.strip():
            print("Found uncommitted changes, stashing them...")
            stash_result = run_command(
                "git stash push -m 'Auto-stash before reset to main'", cwd=dest_path
            )
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
        for main_branch in ["main", "master"]:
            print(f"Attempting to checkout {main_branch} branch...")
            checkout_result = run_command(f"git checkout {main_branch}", cwd=dest_path)
            if checkout_result is not None:
                if has_remote:
                    # Reset to latest origin if we have a remote
                    reset_result = run_command(
                        f"git reset --hard origin/{main_branch}", cwd=dest_path
                    )
                    if reset_result is not None:
                        print(f"Successfully reset to origin/{main_branch}")
                        break
                    else:
                        print(
                            f"Failed to reset to origin/{main_branch}, using local {main_branch}"
                        )
                        break
                else:
                    print(f"Successfully checked out local {main_branch} branch")
                    break
            else:
                print(f"Branch {main_branch} not found")
        else:
            print(
                "Warning: Could not find main or master branch, staying on current branch"
            )

    return True


# Maintain backward compatibility
def copy_local_repo(source_path, dest_path, branch_name):
    """Legacy function name - now delegates to setup_local_repo."""
    return setup_local_repo(source_path, dest_path, branch_name)


def cleanup_worktree(repo_path, source_path=None):
    """Clean up git worktree if it exists."""
    if not repo_path.exists():
        return True

    # Check if this is a git worktree by looking for .git file (not directory)
    git_file = repo_path / ".git"
    if git_file.exists() and git_file.is_file():
        try:
            # Read the .git file to find the source repository
            with open(git_file, "r") as f:
                git_content = f.read().strip()

            if git_content.startswith("gitdir: "):
                print(f"Removing git worktree: {repo_path}")
                # Use git worktree remove command
                if source_path and is_git_repo(source_path):
                    remove_result = run_command(
                        f"git worktree remove {repo_path}", cwd=source_path
                    )
                    if remove_result is not None:
                        print(f"Successfully removed worktree")
                        return True

                # If that fails, remove manually and prune
                import shutil

                if repo_path.exists():
                    shutil.rmtree(repo_path)
                    print(f"Manually removed worktree directory")
                return True
        except Exception as e:
            print(f"Error cleaning up worktree: {e}")

    return False


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
    with open(memory_file, "w") as f:
        f.write(content)

    print(f"Created TASK_MEMORY.md in {memory_file}")
    return memory_file


def list_staged_directories(staging_dir=None):
    """List staged tasks with Rich formatting."""
    from datetime import datetime

    # Get staging directory
    if staging_dir is None:
        home_dir = Path.home()
        staging_dir = home_dir / ".mcl" / "staging"
    else:
        staging_dir = Path(staging_dir)

    if not staging_dir.exists():
        if HAS_RICH:
            console = Console()
            console.print(f"[red]Staging directory {staging_dir} does not exist.[/red]")
        else:
            print(f"Staging directory {staging_dir} does not exist.")
        return

    # Find all directories in staging
    staged_dirs = []
    for item in staging_dir.iterdir():
        if item.is_dir():
            # Get last modified time for sorting
            mtime = item.stat().st_mtime
            dir_name = item.name

            staged_dirs.append(
                {
                    "name": dir_name,
                    "path": str(item),
                    "mtime": mtime,
                    "modified": datetime.fromtimestamp(mtime).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                }
            )

    if not staged_dirs:
        if HAS_RICH:
            console = Console()
            console.print("[yellow]No tasks found.[/yellow]")
        else:
            print("No tasks found.")
        return

    # Sort by modification time (newest first)
    staged_dirs.sort(key=lambda x: x["mtime"], reverse=True)

    # Display with Rich formatting if available
    if HAS_RICH:
        console = Console()

        # Create a beautiful table
        table = Table(title="📁 Staged Tasks", box=box.ROUNDED)
        table.add_column("#", style="cyan", width=3)
        table.add_column("Task Name", style="green")
        table.add_column("Last Modified", style="yellow")

        for i, dir_info in enumerate(staged_dirs, 1):
            table.add_row(str(i), dir_info["name"], dir_info["modified"])

        console.print(table)
        console.print()

    # Show shell integration info
    if HAS_RICH:
        console.print("[dim]Shell integration:[/dim]")
        console.print("[dim]- Use: mcl_cd N              (change to task N)[/dim]")
        console.print('[dim]- Or:  eval "$(mcl cd N)"    (manual method)[/dim]')
        console.print(
            "[dim]- Setup: Add 'eval \"$(mcl shell-init)\"' to your ~/.bashrc or ~/.zshrc[/dim]"
        )
    else:
        # Fallback to simple format
        print("Tasks:")
        print("------")
        for i, dir_info in enumerate(staged_dirs, 1):
            print(f"{i:2d}. {dir_info['name']} ({dir_info['modified']})")

        print()
        print("Shell integration:")
        print("- Use: mcl_cd N              (change to task N)")
        print('- Or:  eval "$(mcl cd N)"    (manual method)')
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
        print(
            "echo 'No tasks found - staging directory does not exist'", file=sys.stderr
        )
        sys.exit(1)

    # Find all directories in staging
    staged_dirs = []
    for item in staging_dir.iterdir():
        if item.is_dir():
            mtime = item.stat().st_mtime
            staged_dirs.append({"name": item.name, "path": str(item), "mtime": mtime})

    if not staged_dirs:
        print("echo 'No tasks found'", file=sys.stderr)
        sys.exit(1)

    # Sort by modification time (newest first)
    staged_dirs.sort(key=lambda x: x["mtime"], reverse=True)

    try:
        index = int(selection) - 1
        if 0 <= index < len(staged_dirs):
            selected_dir = staged_dirs[index]
            # Output shell command to change directory - use proper shell escaping
            import shlex

            print(f"cd {shlex.quote(selected_dir['path'])}")
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
        python "{script_path}" ls
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


# Manager functionality
class ManagerDaemon:
    """Daemon process that manages multiple Claude Code agents."""
    
    def __init__(self, manager_dir=None):
        self.manager_dir = Path(manager_dir or Path.home() / ".mcl" / "manager")
        self.agents_dir = self.manager_dir / "agents"
        self.db_path = self.manager_dir / "manager.db"
        self.socket_path = "/tmp/mcl_manager.sock"
        self.state_file = self.manager_dir / "state.json"
        self.running = False
        
        # Ensure directories exist
        self.manager_dir.mkdir(parents=True, exist_ok=True)
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database for manager state."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                task_description TEXT NOT NULL,
                repo_path TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                priority TEXT DEFAULT 'normal',
                budget INTEGER DEFAULT 100
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approval_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                request_type TEXT NOT NULL,
                request_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents (id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS manager_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                request_data TEXT NOT NULL,
                decision TEXT NOT NULL,  -- 'approve', 'deny', 'escalate'
                confidence_score REAL NOT NULL,  -- 0.0 to 1.0
                autonomy_level TEXT NOT NULL,  -- 'conservative', 'balanced', 'aggressive'
                model_used TEXT NOT NULL,  -- 'gpt-4o', 'claude-3.5-sonnet', etc.
                user_feedback TEXT,  -- 'correct', 'incorrect', null
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents (id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS manager_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS interaction_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                interaction_type TEXT NOT NULL,  -- 'agent_request', 'manager_response', 'agent_output', 'system_event'
                direction TEXT NOT NULL,  -- 'agent_to_manager', 'manager_to_agent', 'system'
                content TEXT NOT NULL,
                metadata TEXT,  -- JSON metadata
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents (id)
            )
        """)
        conn.commit()
        conn.close()
    
    def spawn_agent(self, task_description, repo_path, priority="normal", budget=100):
        """Spawn a new Claude Code agent for a task."""
        # Validate inputs
        if task_description is None:
            raise TypeError("Task description cannot be None")
        if not task_description or not task_description.strip():
            raise ValueError("Task description cannot be empty")
        
        agent_id = str(uuid.uuid4())[:8]
        agent_dir = self.agents_dir / agent_id
        agent_dir.mkdir(exist_ok=True)
        
        # Create task memory file
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task_memory_content = f"""# Task Memory - Agent {agent_id}

**Created:** {timestamp}
**Priority:** {priority}
**Budget:** ${budget}
**Repository:** {repo_path}

## Task Description

{task_description}

## Manager Context

This agent is running under manager supervision:
- Auto-approval enabled for low-risk operations
- Manager will evaluate tool requests before execution
- Escalation triggers: high cost operations, destructive changes, external API calls

## Progress

- [ ] Initial codebase analysis
- [ ] Implementation planning  
- [ ] Code changes
- [ ] Testing verification

## Work Log

- [{timestamp}] Agent spawned under manager supervision

---

*This agent is managed by the mcl manager daemon. All tool requests are evaluated before execution.*
"""
        
        task_memory_path = agent_dir / "TASK_MEMORY.md"
        with open(task_memory_path, "w") as f:
            f.write(task_memory_content)
        
        # Store agent in database
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO agents (id, task_description, repo_path, status, priority, budget) VALUES (?, ?, ?, ?, ?, ?)",
            (agent_id, task_description, repo_path, "active", priority, budget)
        )
        conn.commit()
        conn.close()
        
        # Initialize logging for this agent
        session_id = f"session_{int(time.time())}"
        self.log_interaction(
            agent_id=agent_id,
            session_id=session_id,
            interaction_type="system_event",
            direction="system",
            content=f"Agent spawned for task: {task_description}",
            metadata={
                "repo_path": repo_path,
                "priority": priority,
                "budget": budget,
                "agent_dir": str(agent_dir)
            }
        )
        
        print(f"✅ Agent {agent_id} spawned for task: {task_description[:50]}...")
        return agent_id, session_id
    
    def get_active_agents(self):
        """Get list of active agents."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT id, task_description, repo_path, status, priority, created_at FROM agents WHERE status = 'active'"
        )
        agents = cursor.fetchall()
        conn.close()
        return agents
    
    def get_approval_queue(self):
        """Get pending approval requests."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT aq.id, aq.agent_id, aq.request_type, aq.request_data, aq.created_at, a.task_description
            FROM approval_queue aq
            JOIN agents a ON aq.agent_id = a.id
            ORDER BY aq.created_at
        """)
        queue = cursor.fetchall()
        conn.close()
        return queue
    
    def get_autonomy_level(self):
        """Get current autonomy level."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT value FROM manager_config WHERE key = 'autonomy_level'")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else "balanced"  # Default to balanced
    
    def set_autonomy_level(self, level):
        """Set autonomy level: conservative, balanced, aggressive."""
        if level not in ["conservative", "balanced", "aggressive"]:
            raise ValueError("Autonomy level must be: conservative, balanced, or aggressive")
        
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO manager_config (key, value) VALUES (?, ?)",
            ("autonomy_level", level)
        )
        conn.commit()
        conn.close()
    
    def get_evaluation_model(self):
        """Get current evaluation model."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT value FROM manager_config WHERE key = 'evaluation_model'")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else "claude-3.5-sonnet"  # Default
    
    def set_evaluation_model(self, model):
        """Set evaluation model: gpt-4o, claude-3.5-sonnet, gpt-4-turbo, etc."""
        valid_models = [
            "gpt-4o", "gpt-4-turbo", "gpt-4", 
            "claude-3.5-sonnet", "claude-3-opus", "claude-3-sonnet",
            "o1-preview", "o1-mini"
        ]
        if model not in valid_models:
            raise ValueError(f"Model must be one of: {', '.join(valid_models)}")
            
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO manager_config (key, value) VALUES (?, ?)",
            ("evaluation_model", model)
        )
        conn.commit()
        conn.close()
    
    def calculate_confidence_score(self):
        """Calculate manager's current confidence score based on historical accuracy."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as total_decisions,
                SUM(CASE WHEN user_feedback = 'correct' THEN 1 ELSE 0 END) as correct_decisions,
                AVG(confidence_score) as avg_confidence
            FROM manager_decisions 
            WHERE user_feedback IS NOT NULL
            AND created_at > datetime('now', '-30 days')
        """)
        row = cursor.fetchone()
        conn.close()
        
        if not row or row[0] == 0:
            return 0.5  # Default neutral confidence
        
        total, correct, avg_confidence = row
        accuracy = correct / total if total > 0 else 0.5
        
        # Weighted score: 70% accuracy, 30% historical confidence
        confidence_score = (accuracy * 0.7) + ((avg_confidence or 0.5) * 0.3)
        return min(max(confidence_score, 0.0), 1.0)
    
    def should_escalate(self, request_data, confidence_score):
        """Determine if request should be escalated based on autonomy level and confidence."""
        autonomy_level = self.get_autonomy_level()
        
        # Parse risk indicators from request
        risk_score = self._assess_risk(request_data)
        
        # Autonomy thresholds
        thresholds = {
            "conservative": {
                "confidence_threshold": 0.8,
                "risk_threshold": 0.3,
                "escalate_percentage": 0.7  # Escalate 70% of requests
            },
            "balanced": {
                "confidence_threshold": 0.6,
                "risk_threshold": 0.5,
                "escalate_percentage": 0.4  # Escalate 40% of requests
            },
            "aggressive": {
                "confidence_threshold": 0.4,
                "risk_threshold": 0.7,
                "escalate_percentage": 0.2  # Escalate 20% of requests
            }
        }
        
        config = thresholds[autonomy_level]
        
        # Decision logic
        if risk_score > config["risk_threshold"]:
            return True  # High risk always escalates
        if confidence_score < config["confidence_threshold"]:
            return True  # Low confidence escalates
        
        # Random escalation based on autonomy level (for learning)
        import random
        if random.random() < config["escalate_percentage"] * (1 - confidence_score):
            return True
        
        return False
    
    def _assess_risk(self, request_data):
        """Assess risk level of a request (0.0 = safe, 1.0 = dangerous)."""
        request_str = json.dumps(request_data).lower()
        
        # Risk indicators with weights
        risk_indicators = {
            # Critical risk (0.9-1.0)
            "destructive": ["rm -rf", "delete", "drop table", "truncate", "format"],
            "system": ["sudo", "chmod 777", "chown", "passwd"],
            "network": ["curl -X DELETE", "wget", "ssh", "scp"],
            
            # High risk (0.6-0.8)
            "database": ["alter table", "create table", "migration", "schema"],
            "config": ["config", "settings", ".env", "credentials"],
            "external": ["http", "api", "webhook"],
            
            # Medium risk (0.3-0.5) 
            "files": ["write", "edit", "move", "copy"],
            "install": ["npm install", "pip install", "apt install"],
            
            # Low risk (0.0-0.2)
            "read": ["read", "cat", "ls", "grep", "search"],
            "test": ["test", "pytest", "jest", "spec"]
        }
        
        risk_weights = {
            "destructive": 1.0, "system": 0.95, "network": 0.9,
            "database": 0.7, "config": 0.6, "external": 0.6,
            "files": 0.4, "install": 0.3,
            "read": 0.1, "test": 0.1
        }
        
        max_risk = 0.0
        for category, keywords in risk_indicators.items():
            for keyword in keywords:
                if keyword in request_str:
                    max_risk = max(max_risk, risk_weights[category])
        
        return max_risk
    
    def record_decision(self, agent_id, request_data, decision, confidence_score, model_used, session_id=None):
        """Record a manager decision for learning purposes."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO manager_decisions 
            (agent_id, request_data, decision, confidence_score, autonomy_level, model_used)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (agent_id, json.dumps(request_data), decision, confidence_score, 
              self.get_autonomy_level(), model_used))
        conn.commit()
        conn.close()
        
        # Log the interaction
        if not session_id:
            session_id = f"session_{int(time.time())}"
        
        # Log the agent request
        self.log_interaction(
            agent_id=agent_id,
            session_id=session_id,
            interaction_type="agent_request",
            direction="agent_to_manager",
            content=json.dumps(request_data, indent=2),
            metadata={
                "tool": request_data.get("tool"),
                "risk_assessment": "pending"
            }
        )
        
        # Log the manager decision
        self.log_interaction(
            agent_id=agent_id,
            session_id=session_id,
            interaction_type="manager_response",
            direction="manager_to_agent",
            content=f"Decision: {decision.upper()}",
            metadata={
                "confidence_score": confidence_score,
                "autonomy_level": self.get_autonomy_level(),
                "model_used": model_used,
                "decision_reasoning": f"Confidence: {confidence_score:.2f}, Autonomy: {self.get_autonomy_level()}"
            }
        )
    
    def provide_feedback(self, decision_id, feedback):
        """Provide feedback on a manager decision (correct/incorrect)."""
        if feedback not in ["correct", "incorrect"]:
            raise ValueError("Feedback must be 'correct' or 'incorrect'")
        
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE manager_decisions SET user_feedback = ? WHERE id = ?",
            (feedback, decision_id)
        )
        conn.commit()
        conn.close()
    
    def get_decision_history(self, limit=20):
        """Get recent manager decisions for review."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT md.id, md.agent_id, a.task_description, md.decision, 
                   md.confidence_score, md.autonomy_level, md.model_used,
                   md.user_feedback, md.created_at
            FROM manager_decisions md
            JOIN agents a ON md.agent_id = a.id
            ORDER BY md.created_at DESC
            LIMIT ?
        """, (limit,))
        decisions = cursor.fetchall()
        conn.close()
        return decisions
    
    def log_interaction(self, agent_id, session_id, interaction_type, direction, content, metadata=None):
        """Log an interaction between manager and agent."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO interaction_logs 
            (agent_id, session_id, interaction_type, direction, content, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (agent_id, session_id, interaction_type, direction, content, 
              json.dumps(metadata) if metadata else None))
        conn.commit()
        conn.close()
    
    def get_agent_logs(self, agent_id=None, session_id=None, limit=None, interaction_type=None):
        """Get interaction logs for an agent or session."""
        conn = sqlite3.connect(self.db_path)
        
        # Build query with filters
        query = """
            SELECT il.id, il.agent_id, a.task_description, il.session_id, 
                   il.interaction_type, il.direction, il.content, il.metadata, il.timestamp
            FROM interaction_logs il
            JOIN agents a ON il.agent_id = a.id
            WHERE 1=1
        """
        params = []
        
        if agent_id:
            query += " AND il.agent_id = ?"
            params.append(agent_id)
        
        if session_id:
            query += " AND il.session_id = ?"
            params.append(session_id)
        
        if interaction_type:
            query += " AND il.interaction_type = ?"
            params.append(interaction_type)
        
        query += " ORDER BY il.timestamp ASC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        cursor = conn.execute(query, params)
        logs = cursor.fetchall()
        conn.close()
        return logs
    
    def get_agent_sessions(self, agent_id):
        """Get all session IDs for an agent."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT DISTINCT session_id, MIN(timestamp) as start_time, MAX(timestamp) as end_time,
                   COUNT(*) as interaction_count
            FROM interaction_logs 
            WHERE agent_id = ?
            GROUP BY session_id
            ORDER BY start_time DESC
        """, (agent_id,))
        sessions = cursor.fetchall()
        conn.close()
        return sessions
    
    def search_logs(self, search_term, agent_id=None, limit=50):
        """Search interaction logs by content."""
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT il.id, il.agent_id, a.task_description, il.session_id, 
                   il.interaction_type, il.direction, il.content, il.metadata, il.timestamp
            FROM interaction_logs il
            JOIN agents a ON il.agent_id = a.id
            WHERE il.content LIKE ?
        """
        params = [f"%{search_term}%"]
        
        if agent_id:
            query += " AND il.agent_id = ?"
            params.append(agent_id)
        
        query += " ORDER BY il.timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = conn.execute(query, params)
        logs = cursor.fetchall()
        conn.close()
        return logs
    
    def export_logs(self, agent_id, format="json"):
        """Export all logs for an agent in specified format."""
        logs = self.get_agent_logs(agent_id)
        
        if format == "json":
            log_data = []
            for log in logs:
                log_entry = {
                    "id": log[0],
                    "agent_id": log[1],
                    "task_description": log[2],
                    "session_id": log[3],
                    "interaction_type": log[4],
                    "direction": log[5],
                    "content": log[6],
                    "metadata": json.loads(log[7]) if log[7] else None,
                    "timestamp": log[8]
                }
                log_data.append(log_entry)
            return json.dumps(log_data, indent=2)
        
        elif format == "text":
            lines = []
            current_session = None
            
            for log in logs:
                log_id, agent_id, task_desc, session_id, interaction_type, direction, content, metadata, timestamp = log
                
                if session_id != current_session:
                    lines.append(f"\n=== SESSION {session_id} ===")
                    lines.append(f"Task: {task_desc}")
                    lines.append("")
                    current_session = session_id
                
                # Format timestamp
                ts = timestamp.split('.')[0] if '.' in timestamp else timestamp
                
                # Format direction indicator
                if direction == "agent_to_manager":
                    indicator = "🤖→🧠"
                elif direction == "manager_to_agent":
                    indicator = "🧠→🤖"
                else:
                    indicator = "⚙️"
                
                lines.append(f"[{ts}] {indicator} {interaction_type.upper()}")
                
                # Format content with indentation
                content_lines = content.split('\n')
                for line in content_lines:
                    lines.append(f"    {line}")
                
                # Add metadata if present
                if metadata:
                    meta_data = json.loads(metadata)
                    lines.append(f"    📋 {json.dumps(meta_data, separators=(',', ':'))}")
                
                lines.append("")
            
            return '\n'.join(lines)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def simulate_agent_interaction(self, agent_id, session_id, tool_requests):
        """Simulate a series of agent interactions for testing/demo purposes."""
        for i, request in enumerate(tool_requests):
            # Log agent request
            self.log_interaction(
                agent_id=agent_id,
                session_id=session_id,
                interaction_type="agent_request",
                direction="agent_to_manager",
                content=json.dumps(request, indent=2),
                metadata={
                    "tool": request.get("tool"),
                    "sequence": i + 1,
                    "total_requests": len(tool_requests)
                }
            )
            
            # Simulate manager evaluation
            risk_score = self._assess_risk(request)
            confidence_score = self.calculate_confidence_score()
            should_escalate = self.should_escalate(request, confidence_score)
            
            decision = "escalate" if should_escalate else "approve"
            
            # Log manager response
            self.log_interaction(
                agent_id=agent_id,
                session_id=session_id,
                interaction_type="manager_response",
                direction="manager_to_agent",
                content=f"Decision: {decision.upper()}",
                metadata={
                    "confidence_score": confidence_score,
                    "risk_score": risk_score,
                    "autonomy_level": self.get_autonomy_level(),
                    "reasoning": f"Risk: {risk_score:.2f}, Confidence: {confidence_score:.2f}"
                }
            )
            
            # Log agent response to decision
            if decision == "approve":
                self.log_interaction(
                    agent_id=agent_id,
                    session_id=session_id,
                    interaction_type="agent_output",
                    direction="agent_to_manager",
                    content=f"Executing {request.get('tool')} operation...",
                    metadata={
                        "operation": request.get("tool"),
                        "status": "executing"
                    }
                )
                
                # Simulate completion
                import time
                time.sleep(0.1)  # Small delay for realistic timestamps
                
                self.log_interaction(
                    agent_id=agent_id,
                    session_id=session_id,
                    interaction_type="agent_output",
                    direction="agent_to_manager", 
                    content=f"✅ {request.get('tool')} operation completed successfully",
                    metadata={
                        "operation": request.get("tool"),
                        "status": "completed",
                        "result": "success"
                    }
                )
            else:
                self.log_interaction(
                    agent_id=agent_id,
                    session_id=session_id,
                    interaction_type="agent_output",
                    direction="agent_to_manager",
                    content=f"⏸️ Waiting for user approval for {request.get('tool')} operation",
                    metadata={
                        "operation": request.get("tool"),
                        "status": "waiting_approval"
                    }
                )


def get_manager_daemon():
    """Get or create manager daemon instance."""
    return ManagerDaemon()


def is_manager_running():
    """Check if manager daemon is running."""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect("/tmp/mcl_manager.sock")
        sock.close()
        return True
    except (ConnectionRefusedError, FileNotFoundError):
        return False


def send_manager_command(command, **kwargs):
    """Send command to running manager daemon."""
    if not is_manager_running():
        print("❌ Manager daemon not running. Start with: mcl manager start")
        return False
    
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect("/tmp/mcl_manager.sock")
        
        message = {
            'command': command,
            'timestamp': time.time(),
            **kwargs
        }
        
        sock.send(json.dumps(message).encode())
        response = sock.recv(4096).decode()
        print(response)
        sock.close()
        return True
        
    except Exception as e:
        print(f"❌ Error communicating with manager: {e}")
        return False


def cmd_manager(args):
    """Handle manager subcommands."""
    if not hasattr(args, 'manager_command') or args.manager_command is None:
        # No subcommand provided, show help
        import argparse
        parser = argparse.ArgumentParser(prog="mcl manager", description="Manage multiple Claude Code agents [EXPERIMENTAL]")
        subparsers = parser.add_subparsers(dest="manager_command", help="Manager commands")
        
        # Recreate subcommands for help display
        subparsers.add_parser("start", help="Start the manager daemon")
        subparsers.add_parser("add", help="Add a new task to the manager")
        subparsers.add_parser("status", help="Show active agents")
        subparsers.add_parser("queue", help="Show approval queue")
        subparsers.add_parser("approve", help="Approve a pending request")
        subparsers.add_parser("deny", help="Deny a pending request")
        subparsers.add_parser("stop", help="Stop the manager daemon")
        subparsers.add_parser("config", help="Configure manager autonomy and evaluation model")
        subparsers.add_parser("feedback", help="Provide feedback on manager decisions")
        subparsers.add_parser("history", help="Show manager decision history")
        subparsers.add_parser("stats", help="Show manager performance statistics")
        subparsers.add_parser("log", help="View interaction logs between manager and agents")
        subparsers.add_parser("sessions", help="List sessions for an agent")
        subparsers.add_parser("simulate", help="Simulate agent interactions for testing")
        
        parser.print_help()
        return
    
    if args.manager_command == "start":
        if is_manager_running():
            print("⚠️  Manager daemon already running")
            return
        
        print("🚀 Starting manager daemon...")
        daemon = get_manager_daemon()
        
        # Start daemon process (simplified for POC)  
        print(f"📡 Manager daemon started")
        print(f"📊 Agents directory: {daemon.agents_dir}")
        print(f"🔔 Submit tasks with: mcl manager add <task> --repo <path>")
        
    elif args.manager_command == "add":
        task_description = args.task
        repo_path = args.repo
        priority = getattr(args, 'priority', 'normal')
        
        if not is_manager_running():
            # Auto-start manager if not running
            print("🚀 Starting manager daemon...")
            daemon = get_manager_daemon()
        else:
            daemon = get_manager_daemon()
        
        agent_id, session_id = daemon.spawn_agent(task_description, repo_path, priority)
        print(f"🤖 Task queued with agent {agent_id}")
        
    elif args.manager_command == "status":
        daemon = get_manager_daemon()
        agents = daemon.get_active_agents()
        
        if not agents:
            print("📭 No active agents")
            return
        
        print("🤖 ACTIVE AGENTS:")
        print("-" * 80)
        print(f"{'AGENT ID':<10} | {'TASK DESCRIPTION':<43} | {'PRIORITY':<8} | CREATED")
        print("-" * 80)
        for agent in agents:
            agent_id, task_desc, repo_path, status, priority, created_at = agent
            task_short = task_desc[:40] + "..." if len(task_desc) > 40 else task_desc
            print(f"{agent_id:<10} | {task_short:<43} | {priority:<8} | {created_at}")
        
        print(f"\nUse agent IDs with other commands:")
        print(f"  mcl manager log --agent <AGENT_ID>      # View agent logs")
        print(f"  mcl manager sessions --agent <AGENT_ID> # List agent sessions")
        
    elif args.manager_command == "queue":
        daemon = get_manager_daemon()
        queue = daemon.get_approval_queue()
        
        if not queue:
            print("📭 No pending approvals")
            return
        
        print("⏳ APPROVAL QUEUE:")
        print("-" * 60)
        for item in queue:
            queue_id, agent_id, req_type, req_data, created_at, task_desc = item
            print(f"{queue_id} | {agent_id} | {req_type} | {created_at}")
            
    elif args.manager_command == "stop":
        if not is_manager_running():
            print("ℹ️  Manager daemon not running")
            return
        
        send_manager_command("stop")
        print("🛑 Manager daemon stopped")
    
    elif args.manager_command == "config":
        daemon = get_manager_daemon()
        
        if hasattr(args, 'autonomy') and args.autonomy:
            daemon.set_autonomy_level(args.autonomy)
            print(f"🎛️  Autonomy level set to: {args.autonomy}")
        
        if hasattr(args, 'model') and args.model:
            daemon.set_evaluation_model(args.model)
            print(f"🧠 Evaluation model set to: {args.model}")
        
        # Show current config
        autonomy = daemon.get_autonomy_level()
        model = daemon.get_evaluation_model()
        confidence = daemon.calculate_confidence_score()
        
        print(f"📊 CURRENT CONFIGURATION:")
        print(f"   Autonomy Level: {autonomy}")
        print(f"   Evaluation Model: {model}")
        print(f"   Confidence Score: {confidence:.2f}")
    
    elif args.manager_command == "feedback":
        daemon = get_manager_daemon()
        daemon.provide_feedback(args.decision_id, args.feedback)
        print(f"✅ Feedback recorded for decision {args.decision_id}: {args.feedback}")
    
    elif args.manager_command == "history":
        daemon = get_manager_daemon()
        decisions = daemon.get_decision_history(getattr(args, 'limit', 20))
        
        if not decisions:
            print("📭 No decision history found")
            return
        
        print("📈 DECISION HISTORY:")
        print("-" * 80)
        for decision in decisions:
            decision_id, agent_id, task_desc, decision_type, confidence, autonomy, model, feedback, created_at = decision
            task_short = task_desc[:30] + "..." if len(task_desc) > 30 else task_desc
            feedback_symbol = "✅" if feedback == "correct" else "❌" if feedback == "incorrect" else "⏳"
            print(f"{decision_id:3d} | {agent_id} | {task_short:<33} | {decision_type:<8} | {confidence:.2f} | {feedback_symbol} | {created_at}")
    
    elif args.manager_command == "stats":
        daemon = get_manager_daemon()
        
        # Get confidence and accuracy stats
        confidence = daemon.calculate_confidence_score()
        autonomy = daemon.get_autonomy_level()
        model = daemon.get_evaluation_model()
        
        # Get recent decision stats
        conn = sqlite3.connect(daemon.db_path)
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN decision = 'approve' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN decision = 'escalate' THEN 1 ELSE 0 END) as escalated,
                SUM(CASE WHEN user_feedback = 'correct' THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN user_feedback = 'incorrect' THEN 1 ELSE 0 END) as incorrect
            FROM manager_decisions 
            WHERE created_at > datetime('now', '-7 days')
        """)
        stats = cursor.fetchone()
        conn.close()
        
        if stats:
            total, approved, escalated, correct, incorrect = stats
            # Handle None values from SUM operations
            total = total or 0
            approved = approved or 0
            escalated = escalated or 0
            correct = correct or 0
            incorrect = incorrect or 0
        else:
            total = approved = escalated = correct = incorrect = 0
        
        print("📊 MANAGER STATISTICS (Last 7 Days):")
        print("-" * 50)
        print(f"Configuration:")
        print(f"  Autonomy Level: {autonomy}")
        print(f"  Evaluation Model: {model}")
        print(f"  Confidence Score: {confidence:.2f}")
        print()
        print(f"Decision Breakdown:")
        print(f"  Total Decisions: {total}")
        print(f"  Auto-Approved: {approved} ({approved/total*100:.1f}%)" if total > 0 else "  Auto-Approved: 0 (0%)")
        print(f"  Escalated: {escalated} ({escalated/total*100:.1f}%)" if total > 0 else "  Escalated: 0 (0%)")
        print()
        print(f"Accuracy (with feedback):")
        print(f"  Correct: {correct}")
        print(f"  Incorrect: {incorrect}")
        print(f"  Accuracy: {correct/(correct+incorrect)*100:.1f}%" if (correct+incorrect) > 0 else "  Accuracy: No feedback yet")
    
    elif args.manager_command == "log":
        daemon = get_manager_daemon()
        
        if hasattr(args, 'agent_id') and args.agent_id:
            # Show logs for specific agent
            logs = daemon.get_agent_logs(
                agent_id=args.agent_id,
                session_id=getattr(args, 'session_id', None),
                limit=getattr(args, 'limit', 100),
                interaction_type=getattr(args, 'type', None)
            )
            
            if not logs:
                print(f"📭 No logs found for agent {args.agent_id}")
                return
            
            # Display format
            format_type = getattr(args, 'format', 'text')
            if format_type == 'json':
                print(daemon.export_logs(args.agent_id, format='json'))
            else:
                print(daemon.export_logs(args.agent_id, format='text'))
        
        elif hasattr(args, 'search') and args.search:
            # Search logs by content
            logs = daemon.search_logs(
                search_term=args.search,
                agent_id=getattr(args, 'agent_id', None),
                limit=getattr(args, 'limit', 50)
            )
            
            if not logs:
                print(f"📭 No logs found matching '{args.search}'")
                return
            
            print(f"🔍 SEARCH RESULTS FOR '{args.search}':")
            print("-" * 60)
            for log in logs:
                log_id, agent_id, task_desc, session_id, interaction_type, direction, content, metadata, timestamp = log
                ts = timestamp.split('.')[0] if '.' in timestamp else timestamp
                
                # Direction indicator
                if direction == "agent_to_manager":
                    indicator = "🤖→🧠"
                elif direction == "manager_to_agent": 
                    indicator = "🧠→🤖"
                else:
                    indicator = "⚙️"
                
                print(f"[{ts}] {indicator} {agent_id} | {interaction_type}")
                # Show first line of content
                first_line = content.split('\n')[0][:80]
                if len(first_line) == 80:
                    first_line += "..."
                print(f"    {first_line}")
                print()
        
        else:
            # List all agents with log activity
            conn = sqlite3.connect(daemon.db_path)
            cursor = conn.execute("""
                SELECT il.agent_id, a.task_description, COUNT(*) as log_count,
                       MIN(il.timestamp) as first_log, MAX(il.timestamp) as last_log
                FROM interaction_logs il
                JOIN agents a ON il.agent_id = a.id
                GROUP BY il.agent_id, a.task_description
                ORDER BY last_log DESC
            """)
            agents_with_logs = cursor.fetchall()
            conn.close()
            
            if not agents_with_logs:
                print("📭 No interaction logs found")
                return
            
            print("📋 AGENTS WITH INTERACTION LOGS:")
            print("-" * 80)
            print(f"{'AGENT ID':<10} | {'TASK DESCRIPTION':<43} | {'LOGS':<8} | LAST ACTIVITY")
            print("-" * 80)
            for agent_id, task_desc, log_count, first_log, last_log in agents_with_logs:
                task_short = task_desc[:40] + "..." if len(task_desc) > 40 else task_desc
                last_ts = last_log.split('.')[0] if '.' in last_log else last_log
                print(f"{agent_id:<10} | {task_short:<43} | {log_count:>4} logs | {last_ts}")
            
            print(f"\nCommands:")
            print(f"  mcl manager log --agent <AGENT_ID>         # View detailed logs")
            print(f"  mcl manager sessions --agent <AGENT_ID>    # List sessions")
            print(f"  mcl manager log --search <term>            # Search all logs")
    
    elif args.manager_command == "sessions":
        daemon = get_manager_daemon()
        
        if not hasattr(args, 'agent_id') or not args.agent_id:
            # Show help for sessions command
            import argparse
            parser = argparse.ArgumentParser(prog="mcl manager sessions", description="List sessions for an agent")
            parser.add_argument("--agent", dest="agent_id", required=True, help="Agent ID to list sessions for")
            parser.print_help()
            return
        
        sessions = daemon.get_agent_sessions(args.agent_id)
        
        if not sessions:
            print(f"📭 No sessions found for agent {args.agent_id}")
            return
        
        print(f"📅 SESSIONS FOR AGENT {args.agent_id}:")
        print("-" * 70)
        for session_id, start_time, end_time, interaction_count in sessions:
            start_ts = start_time.split('.')[0] if '.' in start_time else start_time
            end_ts = end_time.split('.')[0] if '.' in end_time else end_time
            print(f"{session_id} | {start_ts} → {end_ts} | {interaction_count} interactions")
        
        print(f"\nUse: mcl manager log --agent {args.agent_id} --session <session_id> to view session logs")
    
    elif args.manager_command == "simulate":
        # Demo/testing command to simulate agent interactions
        daemon = get_manager_daemon()
        
        if not hasattr(args, 'agent_id') or not args.agent_id:
            # Show help for simulate command
            import argparse
            parser = argparse.ArgumentParser(prog="mcl manager simulate", description="Simulate agent interactions for testing")
            parser.add_argument("--agent", dest="agent_id", required=True, help="Agent ID to simulate interactions for")
            parser.print_help()
            return
        
        # Sample tool requests for simulation
        tool_requests = [
            {"tool": "read", "file_path": "src/main.py", "reason": "Understanding current implementation"},
            {"tool": "grep", "pattern": "function.*auth", "reason": "Finding authentication functions"},
            {"tool": "edit", "file_path": "src/auth.py", "content": "# Updated auth logic", "reason": "Implementing fix"},
            {"tool": "bash", "command": "npm test", "reason": "Running tests"},
            {"tool": "edit", "file_path": "config/database.yml", "content": "pool: 10", "reason": "Updating DB config"}
        ]
        
        session_id = f"sim_session_{int(time.time())}"
        
        print(f"🎭 Simulating agent interactions for {args.agent_id}...")
        daemon.simulate_agent_interaction(args.agent_id, session_id, tool_requests)
        print(f"✅ Simulation complete. View logs with: mcl manager log --agent {args.agent_id}")
        
    else:
        print(f"❌ Unknown manager command: {args.manager_command}")


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
    repo_path = (
        get_unique_repo_path(base_repo_path)
        if not args.continue_branch and not args.no_clone
        else base_repo_path
    )

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
        words = re.sub(r"[^\w\s]", "", requirements.split("\n")[0]).split()[:3]
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
                copy_success = copy_local_repo(
                    Path(args.repo).resolve(), repo_path, branch_name
                )
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
                clone_result = run_command(
                    f"git clone {args.repo} {clone_dir_name}", cwd=workspace_path
                )
                if clone_result is None:
                    print("Failed to clone repository")
                    sys.exit(1)
    else:
        if not repo_path.exists():
            print(
                f"Repository path {repo_path} does not exist and --no-clone specified"
            )
            sys.exit(1)

    # Handle branch creation/checkout (skip if worktree already created the branch)
    current_branch_result = run_command("git branch --show-current", cwd=repo_path)
    current_branch = current_branch_result.strip() if current_branch_result else ""

    # Only handle branch operations if we're not already on the target branch
    # (worktrees automatically create and checkout the branch)
    if current_branch != branch_name:
        if args.continue_branch:
            print(f"Checking out existing branch '{branch_name}'...")
            # Try to checkout existing branch, create if it doesn't exist
            checkout_result = run_command(f"git checkout {branch_name}", cwd=repo_path)
            if checkout_result is None:
                print(f"Branch '{branch_name}' not found, creating new branch...")
                checkout_result = run_command(
                    f"git checkout -b {branch_name}", cwd=repo_path
                )
                if checkout_result is None:
                    print("Failed to create branch")
                    sys.exit(1)
        else:
            print(f"Creating new branch '{branch_name}'...")
            checkout_result = run_command(
                f"git checkout -b {branch_name}", cwd=repo_path
            )
            if checkout_result is None:
                print("Failed to create branch")
                sys.exit(1)
    else:
        print(f"Already on branch '{branch_name}'")

    # Create or update TASK_MEMORY.md
    memory_file = os.path.join(repo_path, "TASK_MEMORY.md")
    if args.continue_branch and os.path.exists(memory_file):
        print("TASK_MEMORY.md exists, updating with new session...")
        # Append new session info to existing file
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        additional_content = f"\n\n## New Session - {timestamp}\n\n"
        if args.instructions:
            additional_content += (
                f"**Additional Instructions:** {args.instructions}\n\n"
            )
        additional_content += f"**Requirements (refresher):**\n{requirements}\n\n"
        additional_content += f"- [{timestamp}] Resumed work on existing branch\n"

        with open(memory_file, "a") as f:
            f.write(additional_content)
    else:
        print("Creating TASK_MEMORY.md...")
        memory_file = create_task_memory(requirements, repo_path, branch_name)

    # Note: TASK_MEMORY.md is excluded from git via .gitignore to keep task notes local
    print("TASK_MEMORY.md created (not committed - kept as local task notes)")

    print("\n" + "=" * 50)
    print("SETUP COMPLETE!")
    print("=" * 50)
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
            subprocess.run(["claude", initial_prompt], check=True)
        except subprocess.CalledProcessError:
            print(
                "Failed to start Claude Code. Make sure 'claude' command is available."
            )
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
        prog="mcl",
        description="Multi-Claude task management - work on multiple features simultaneously",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mcl start --repo https://github.com/user/repo --requirements "Add auth"
  mcl --repo https://github.com/user/repo --requirements "Add auth"  # (backwards compatible)
  mcl ls
  eval "$(mcl cd 1)"    # Change to task 1 (manual method)
  mcl shell-init

For shell integration, add this to your ~/.bashrc or ~/.zshrc:
  eval "$(mcl shell-init)"
  
Then use:
  mcl_cd        # List tasks
  mcl_cd 1      # Change to task 1 (recommended)
        """,
    )

    # Add backwards compatibility arguments to main parser
    parser.add_argument(
        "-r", "--repo", help="Repository URL to clone or local directory path"
    )
    parser.add_argument(
        "-rq",
        "--requirements",
        help="Requirements text, GitHub issue URL, or file path",
    )
    parser.add_argument(
        "-b", "--branch", help="Branch name (auto-generated if not provided)"
    )
    parser.add_argument("-w", "--workspace", help="Workspace directory")
    parser.add_argument(
        "-s", "--staging-dir", help="Staging directory (default: ~/.mcl/staging)"
    )
    parser.add_argument(
        "-i", "--instructions", help="Additional instructions for Claude Code"
    )
    parser.add_argument(
        "-c",
        "--continue-branch",
        action="store_true",
        help="Continue work on existing branch instead of creating new one",
    )
    parser.add_argument(
        "-nc",
        "--no-clone",
        action="store_true",
        help="Skip cloning (repo already exists)",
    )
    parser.add_argument(
        "-nd",
        "--no-claude",
        action="store_true",
        help="Skip starting Claude Code after setup",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Start subcommand
    start_parser = subparsers.add_parser("start", help="Start a new task workspace")
    start_parser.add_argument(
        "--repo", required=True, help="Repository URL to clone or local directory path"
    )
    start_parser.add_argument(
        "--requirements",
        required=True,
        help="Requirements text, GitHub issue URL, or file path",
    )
    start_parser.add_argument(
        "--branch", help="Branch name (auto-generated if not provided)"
    )
    start_parser.add_argument("--workspace", help="Workspace directory")
    start_parser.add_argument(
        "--staging-dir", help="Staging directory (default: ~/.mcl/staging)"
    )
    start_parser.add_argument(
        "--instructions", help="Additional instructions for Claude Code"
    )
    start_parser.add_argument(
        "--continue-branch",
        action="store_true",
        help="Continue work on existing branch instead of creating new one",
    )
    start_parser.add_argument(
        "--no-clone", action="store_true", help="Skip cloning (repo already exists)"
    )
    start_parser.add_argument(
        "--no-claude", action="store_true", help="Skip starting Claude Code after setup"
    )
    start_parser.set_defaults(func=cmd_start)

    # ls subcommand (primary)
    ls_parser = subparsers.add_parser("ls", help="List all staged tasks")
    ls_parser.add_argument(
        "--staging-dir", help="Staging directory (default: ~/.mcl/staging)"
    )
    ls_parser.set_defaults(func=cmd_list)

    # list alias for backwards compatibility
    list_parser = subparsers.add_parser(
        "list", help="List all staged tasks (backwards compatibility alias for ls)"
    )
    list_parser.add_argument(
        "--staging-dir", help="Staging directory (default: ~/.mcl/staging)"
    )
    list_parser.set_defaults(func=cmd_list)

    # Shell-init subcommand
    shell_parser = subparsers.add_parser(
        "shell-init", help="Output shell integration code for bash/zsh"
    )
    shell_parser.set_defaults(func=cmd_shell_init)

    # CD subcommand (for shell integration)
    cd_parser = subparsers.add_parser(
        "cd", help="Output shell command to change directory to task N"
    )
    cd_parser.add_argument("number", help="Task number to change to")
    cd_parser.add_argument(
        "--staging-dir", help="Staging directory (default: ~/.mcl/staging)"
    )
    cd_parser.set_defaults(func=cmd_cd)

    # Manager subcommand
    manager_parser = subparsers.add_parser("manager", help="Manage multiple Claude Code agents [EXPERIMENTAL]")
    manager_parser.set_defaults(func=cmd_manager)
    manager_subparsers = manager_parser.add_subparsers(dest="manager_command", help="Manager commands")
    
    # manager start
    manager_start_parser = manager_subparsers.add_parser("start", help="Start the manager daemon")
    manager_start_parser.set_defaults(func=cmd_manager)
    
    # manager add
    manager_add_parser = manager_subparsers.add_parser("add", help="Add a new task to the manager")
    manager_add_parser.add_argument("task", help="Task description")
    manager_add_parser.add_argument("--repo", required=True, help="Repository path")
    manager_add_parser.add_argument("--priority", choices=["low", "normal", "high"], default="normal", help="Task priority")
    manager_add_parser.add_argument("--budget", type=int, default=100, help="Budget limit for task")
    manager_add_parser.set_defaults(func=cmd_manager)
    
    # manager status
    manager_status_parser = manager_subparsers.add_parser("status", help="Show active agents")
    manager_status_parser.set_defaults(func=cmd_manager)
    
    # manager queue
    manager_queue_parser = manager_subparsers.add_parser("queue", help="Show approval queue")
    manager_queue_parser.set_defaults(func=cmd_manager)
    
    # manager approve
    manager_approve_parser = manager_subparsers.add_parser("approve", help="Approve a pending request")
    manager_approve_parser.add_argument("request_id", help="Request ID to approve")
    manager_approve_parser.set_defaults(func=cmd_manager)
    
    # manager deny
    manager_deny_parser = manager_subparsers.add_parser("deny", help="Deny a pending request")
    manager_deny_parser.add_argument("request_id", help="Request ID to deny")
    manager_deny_parser.set_defaults(func=cmd_manager)
    
    # manager stop
    manager_stop_parser = manager_subparsers.add_parser("stop", help="Stop the manager daemon")
    manager_stop_parser.set_defaults(func=cmd_manager)
    
    # manager config
    manager_config_parser = manager_subparsers.add_parser("config", help="Configure manager autonomy and evaluation model")
    manager_config_parser.add_argument("--autonomy", choices=["conservative", "balanced", "aggressive"], help="Set autonomy level")
    manager_config_parser.add_argument("--model", choices=["gpt-4o", "gpt-4-turbo", "claude-3.5-sonnet", "claude-3-opus", "o1-preview", "o1-mini"], help="Set evaluation model")
    manager_config_parser.set_defaults(func=cmd_manager)
    
    # manager feedback
    manager_feedback_parser = manager_subparsers.add_parser("feedback", help="Provide feedback on manager decisions")
    manager_feedback_parser.add_argument("decision_id", type=int, help="Decision ID from history")
    manager_feedback_parser.add_argument("feedback", choices=["correct", "incorrect"], help="Feedback on decision quality")
    manager_feedback_parser.set_defaults(func=cmd_manager)
    
    # manager history
    manager_history_parser = manager_subparsers.add_parser("history", help="Show manager decision history")
    manager_history_parser.add_argument("--limit", type=int, default=20, help="Number of decisions to show")
    manager_history_parser.set_defaults(func=cmd_manager)
    
    # manager stats
    manager_stats_parser = manager_subparsers.add_parser("stats", help="Show manager performance statistics")
    manager_stats_parser.set_defaults(func=cmd_manager)
    
    # manager log
    manager_log_parser = manager_subparsers.add_parser("log", help="View interaction logs between manager and agents")
    manager_log_parser.add_argument("--agent", dest="agent_id", help="Agent ID to view logs for")
    manager_log_parser.add_argument("--session", dest="session_id", help="Session ID to filter by")
    manager_log_parser.add_argument("--search", help="Search logs by content")
    manager_log_parser.add_argument("--type", choices=["agent_request", "manager_response", "agent_output", "system_event"], help="Filter by interaction type")
    manager_log_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    manager_log_parser.add_argument("--limit", type=int, default=100, help="Limit number of log entries")
    manager_log_parser.set_defaults(func=cmd_manager)
    
    # manager sessions
    manager_sessions_parser = manager_subparsers.add_parser("sessions", help="List sessions for an agent")
    manager_sessions_parser.add_argument("--agent", dest="agent_id", help="Agent ID to list sessions for")
    manager_sessions_parser.set_defaults(func=cmd_manager)
    
    # manager simulate (for testing/demo)
    manager_simulate_parser = manager_subparsers.add_parser("simulate", help="Simulate agent interactions for testing")
    manager_simulate_parser.add_argument("--agent", dest="agent_id", help="Agent ID to simulate interactions for")
    manager_simulate_parser.set_defaults(func=cmd_manager)

    args = parser.parse_args()

    # Backwards compatibility: if no subcommand but --repo and --requirements are provided, assume 'start'
    if not args.command:
        if args.repo and args.requirements:
            # Redirect to start command
            args.command = "start"
            args.func = cmd_start
        else:
            parser.print_help()
            return

    args.func(args)


if __name__ == "__main__":
    main()
