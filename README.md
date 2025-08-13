# Multi-Claude Task Setup Script

A Python script that streamlines development workflows by setting up isolated workspaces for multiple features for the same repository. It handles repository setup, branch management, task tracking, and automatically launches Claude Code with contextual prompts.

## Features

### Core Task Management
- **Multi-Feature Workflow**: Work on multiple features for the same repository simultaneously in isolated workspaces
- **Repository Management**: Clone remote repositories or copy local directories to staging areas
- **Branch Handling**: Create new branches or continue work on existing ones  
- **Task Tracking**: Creates and maintains `TASK_MEMORY.md` for progress tracking
- **Flexible Requirements**: Support text input, GitHub issue URLs, or file-based requirements
- **Claude Code Integration**: Automatically launches Claude Code with contextual prompts
- **Local Repository Support**: Copy and reset local repos to staging directories
- **Workspace Isolation**: Each feature gets its own directory to prevent conflicts

### Multi-Agent Manager (NEW)
- **Supervised Multi-Agent System**: Manage multiple Claude Code agents working simultaneously
- **Automated Approval Workflows**: LLM-based evaluation of agent tool requests
- **Risk Assessment**: Auto-approve safe operations, escalate risky ones to user
- **Centralized Task Management**: Submit, monitor, and control multiple tasks from one interface
- **Priority & Budget Management**: Assign priority levels and budget limits to tasks
- **Persistent State**: Agents and approvals survive manager restarts
- **macOS Notifications**: Get alerted when agent approval is needed

## Requirements

- Python 3.6+
- Git
- Claude Code CLI (optional, can be skipped with `--no-claude`)
- GitHub token (optional, set `GITHUB_TOKEN` environment variable for GitHub issue integration or higher rate limits)

## Installation

1. Download the script:
```bash
curl -O https://raw.githubusercontent.com/your-repo/mcl.py
chmod +x mcl.py
```

2. Or clone this repository:
```bash
git clone https://github.com/your-repo/multi-claude.git
cd multi-claude
```

3. (Optional) Set up GitHub authentication for GitHub issue integration:
```bash
export GITHUB_TOKEN=your_github_token_here
```

## Usage

Multi-Claude has a clean command-line interface with subcommands:

```bash
mcl <command> [options]
```

### Available Commands

#### Core Task Management

**Start a new task workspace:**
```bash
mcl start --repo REPO_URL_OR_PATH --requirements REQUIREMENTS [OPTIONS]
```

**Start a new task workspace (backwards compatible):**
```bash
mcl --repo REPO_URL_OR_PATH --requirements REQUIREMENTS [OPTIONS]
```

**List existing staged tasks:**
```bash
mcl list [--staging-dir STAGING_DIR]
```

**Shell integration setup (recommended):**
```bash
# Add to your ~/.bashrc or ~/.zshrc:
eval "$(mcl shell-init)"

# Then use the mcl_cd function:
mcl_cd        # List all staged tasks
mcl_cd 1      # Change to task #1
mcl_cd 3      # Change to task #3
```

#### Multi-Agent Manager

**Start the manager daemon:**
```bash
mcl manager start
```

**Submit tasks to the manager:**
```bash
mcl manager add "Fix Redis timeout bug" --repo ~/api-service
mcl manager add "Add dark mode toggle" --repo ~/frontend --priority high --budget 150
```

**Monitor agent status:**
```bash
mcl manager status      # Show active agents
mcl manager queue       # Show pending approvals
```

**Handle approvals:**
```bash
mcl manager approve 1   # Approve request #1
mcl manager deny 2      # Deny request #2
```

**Stop the manager:**
```bash
mcl manager stop
```

**Get help:**
```bash
mcl --help              # Main help
mcl start --help        # Help for start command
mcl manager --help      # Help for manager commands
mcl manager add --help  # Help for specific manager command
```

### Start Command Options

- `--repo`: Repository URL to clone or local directory path (required)
- `--requirements`: Requirements text, GitHub issue URL, or file path (required)
- `--branch`: Branch name (auto-generated if not provided)
- `--workspace`: Workspace directory
- `--staging-dir`: Staging directory for copied repos (default: ~/.mcl/staging)
- `--instructions`: Additional instructions for Claude Code
- `--continue-branch`: Continue work on existing branch instead of creating new one
- `--no-clone`: Skip cloning (repo already exists)
- `--no-claude`: Skip starting Claude Code after setup

### List Command Options

- `--staging-dir`: Staging directory to list from (default: ~/.mcl/staging)

### Other Commands

- `mcl shell-init`: Output shell integration code for bash/zsh
- `mcl cd N`: Output shell command to change directory to task N

## Examples

### 1. Start New Feature with Text Requirements

```bash
mcl start \
  --repo https://github.com/user/myproject \
  --requirements "Add user authentication with OAuth2 support" \
  --instructions "Use TypeScript and include comprehensive tests"
```

**What it does:**
- Clones the repository to `~/.mcl/staging/myproject-add-user-authentication/`
- Creates a new branch `feature/add-user-authentication`
- Creates `TASK_MEMORY.md` with requirements
- Launches Claude Code with setup context and instructions

### 2. Start New Feature from GitHub Issue

```bash
mcl start \
  --repo https://github.com/user/myproject \
  --requirements https://github.com/user/myproject/issues/42
```

**What it does:**
- Fetches issue details from GitHub API
- Clones repository to isolated workspace directory
- Creates branch based on issue title
- Includes issue labels and description in task memory
- Launches Claude Code with full issue context

### 3. Continue Existing Work

```bash
mcl start \
  --repo https://github.com/user/myproject \
  --requirements https://github.com/user/myproject/issues/42 \
  --continue-branch \
  --branch "feature/oauth-implementation" \
  --instructions "Resolve merge conflicts with main branch and update documentation"
```

**What it does:**
- Uses existing repository
- Checks out existing branch `feature/oauth-implementation`
- Appends new session info to existing `TASK_MEMORY.md`
- Launches Claude Code with continuation context and specific instructions

### 4. Work on Feature in Existing Local Repository

```bash
mcl start \
  --repo https://github.com/user/myproject \
  --requirements "Fix performance issues in data processing" \
  --no-clone \
  --continue-branch \
  --branch "bugfix/performance" \
  --instructions "Profile the code and optimize the bottlenecks identified in the latest tests"
```

**What it does:**
- Works with existing local repository (no cloning)
- Switches to existing branch
- Updates task memory with new session
- Provides specific debugging instructions to Claude

### 5. Setup Only (No Claude Code)

```bash
mcl start \
  --repo https://github.com/user/myproject \
  --requirements "Implement caching layer" \
  --no-claude
```

**What it does:**
- Sets up the complete workspace
- Creates all files and branches
- Prints manual next steps instead of launching Claude Code

### 6. Custom Branch Name and Workspace

```bash
mcl start \
  --repo https://github.com/user/myproject \
  --requirements "Add Redis integration" \
  --branch "feature/redis-cache" \
  --workspace "/Users/dev/projects" \
  --instructions "Use Redis for session storage and implement connection pooling"
```

**What it does:**
- Creates custom branch name
- Uses specific workspace directory
- Provides detailed technical instructions

### 7. Work on Feature with Local Repository (Copy & Reset)

```bash
mcl start \
  --repo ./my-local-project \
  --requirements "Refactor authentication module" \
  --instructions "Preserve existing user sessions during refactoring"
```

**What it does:**
- Copies local repository to staging directory (~/src/claude-gh)
- Stashes any uncommitted changes
- Resets to main/master branch with latest changes
- Creates new feature branch for the task

### 8. Local Repository Feature with Custom Staging Directory

```bash
mcl start \
  --repo /Users/dev/existing-project \
  --requirements "Implement new payment gateway" \
  --staging-dir /Users/dev/staging \
  --branch "feature/stripe-integration"
```

**What it does:**
- Copies repository to custom staging directory
- Preserves original repository unchanged
- Sets up clean workspace for development

### 9. Continue Feature Work on Local Repository Copy

```bash
mcl start \
  --repo ./my-project \
  --requirements "Continue payment gateway implementation" \
  --continue-branch \
  --branch "feature/stripe-integration" \
  --instructions "Add error handling and webhook validation"
```

**What it does:**
- Uses existing copy in staging directory
- Continues work on existing branch
- Updates task memory with new session info

### 10. Requirements from File

```bash
mcl start \
  --repo https://github.com/user/myproject \
  --requirements ./task-requirements.txt \
  --instructions "Follow the detailed specifications in the requirements file"
```

**What it does:**
- Reads requirements from the specified file
- Includes entire file content in task memory
- Perfect for complex, multi-section requirements

### 11. Local Repository Feature with File Requirements

```bash
mcl start \
  --repo ./my-local-project \
  --requirements ./docs/feature-spec.md \
  --branch "feature/user-dashboard"
```

**What it does:**
- Copies local repository to staging directory
- Reads requirements from markdown specification file
- Sets up workspace with comprehensive requirements documentation

### 12. List and Navigate Staged Tasks

```bash
# List all staged tasks
mcl list
```

**Output:**
```
Tasks:
------
 1. myproject-add-authentication
 2. myproject-fix-performance
 3. otherproject-new-feature

Shell integration:
- Use: mcl_cd N           (change to task N)
- Or:  mcl cd N | source
- Setup: Add 'eval "$(mcl shell-init)"' to your ~/.bashrc or ~/.zshrc
```

```bash
# Shell integration setup (one-time)
eval "$(mcl shell-init)" >> ~/.bashrc  # or ~/.zshrc

# Then use the mcl_cd function:
mcl_cd        # List tasks
mcl_cd 1      # Change to task #1
mcl_cd 3      # Change to task #3
```

**What it does:**
- Lists all staged tasks in a simple format, sorted by last modification time (newest first)
- Shows task names without clutter
- Provides `mcl_cd` shell function with tab completion for easy navigation
- Works with custom staging directories via `--staging-dir`

## Repository Types

The script handles two types of repository sources:

### Remote Repository URLs
When you provide a remote URL (e.g., `https://github.com/user/repo`):
- Repository is cloned to the staging directory
- Uses `--staging-dir` parameter or default `~/.mcl/staging`
- Original repository remains untouched
- Standard git clone workflow
- Each feature gets its own isolated workspace

### Local Directories (Local Repositories)
When you provide a local path (e.g., `./my-project` or `/Users/dev/project`):
- Repository is **copied** to a staging directory 
- Default staging directory: `~/.mcl/staging`
- Uncommitted changes are automatically stashed
- Repository is reset to main/master branch with latest changes
- Original repository remains completely untouched
- Perfect for experimenting with multiple features without affecting your main workspace

### Staging Directory Behavior
- **Default**: `~/.mcl/staging` 
- **Custom**: Use `--staging-dir` to specify different location
- **Multi-Feature Support**: Each feature gets its own directory within staging (e.g., `myproject-add-auth`, `myproject-fix-bug`)
- **Conflict Resolution**: If staging directory equals current directory, uses `staging/` subdirectory
- **Workspace Override**: Use `--workspace` to override staging directory for local repos

## Requirements Sources

The `--requirements` parameter supports three input types:

### 1. Text Requirements (Direct Input)
```bash
--requirements "Add user authentication with OAuth2 support"
```
- Simple text string with task description
- Good for straightforward tasks
- Auto-generates branch names from text

### 2. GitHub Issue URLs
```bash
--requirements https://github.com/user/repo/issues/123
```
- Automatically fetches issue title, description, and labels
- Includes issue URL for reference
- Useful for tracking work against specific issues (optional integration)

### 3. File-based Requirements
```bash
--requirements ./requirements.txt
--requirements /path/to/specs/feature-spec.md
--requirements ../docs/task-definition.txt
```
- Reads requirements from any text file
- Supports relative and absolute paths
- Ideal for complex, detailed specifications
- Maintains formatting (markdown, etc.)
- Perfect for PRDs, technical specs, or detailed task descriptions

**File Example:**
```markdown
# Feature: User Dashboard

## Overview
Implement a comprehensive user dashboard with the following components...

## Requirements
- [ ] Real-time activity feed
- [ ] Customizable widgets
- [ ] Export functionality

## Technical Specifications
- React components with TypeScript
- REST API integration
- Responsive design for mobile
```

## Task Memory Management

The script creates and maintains a `TASK_MEMORY.md` file that serves as a persistent memory for your work:

### New Tasks
Includes your requirements and any custom instructions, e.g.:
```markdown
# Task Memory

**Created:** 2024-01-15 14:30:00
**Branch:** feature/add-authentication

## Requirements

Add user authentication with OAuth2 support

## Development Notes

*Update this section as you work on the task. Include:*
- *Progress updates*
- *Key decisions made*
- *Challenges encountered*
- *Solutions implemented*
- *Files modified*
- *Testing notes*

### Work Log

- [2024-01-15 14:30:00] Task setup completed, TASK_MEMORY.md created
```

### Continued Work
When using `--continue-branch`, new session information is appended:

```markdown
## New Session - 2024-01-15 16:45:00

**Additional Instructions:** Resolve merge conflicts with main branch

**Requirements (refresher):**
Add user authentication with OAuth2 support

- [2024-01-15 16:45:00] Resumed work on existing branch
```

## Claude Code Integration

When the script launches Claude Code, it provides rich context that includes referencing the TASK_MEMORY.md file and any custom instructions you provded, e.g.:

### For New Tasks:
```
I've set up a new task workspace for you. Here's what's been prepared:

**Repository:** myproject
**Branch:** feature/add-authentication (new branch)
**Task Memory:** TASK_MEMORY.md (contains requirements and notes)

Please start by reading the TASK_MEMORY.md file to understand the requirements, then begin working on the task.

**Additional Instructions:** 
Use TypeScript and include comprehensive tests

**Requirements:**
Add user authentication with OAuth2 support

Let's get started!
```

### For Continued Work:
```
I'm continuing work on an existing task. Here's the current state:

**Repository:** myproject
**Branch:** feature/oauth-implementation (existing branch)
**Task Memory:** TASK_MEMORY.md (contains previous work and notes)

Please start by reading the TASK_MEMORY.md file to understand the requirements and previous work done.

**Current Instructions:** 
Resolve merge conflicts with main branch and update documentation

**Requirements (refresher):**
Add user authentication with OAuth2 support

Please review the current state and continue working on the task!
```

## Workflow Examples

### Daily Development Workflow

1. **Morning: Start new feature**
```bash
mcl start \
  --repo https://github.com/company/api \
  --requirements https://github.com/company/api/issues/156 \
  --instructions "Focus on API design first, then implementation"
```

2. **Afternoon: Continue after meeting**
```bash
mcl start \
  --repo https://github.com/company/api \
  --requirements https://github.com/company/api/issues/156 \
  --continue-branch \
  --branch "feature/user-profiles" \
  --no-clone \
  --instructions "Implement the changes discussed in the team meeting: add email validation and profile pictures"
```

3. **Next day: Handle merge conflicts**
```bash
mcl start \
  --repo https://github.com/company/api \
  --requirements https://github.com/company/api/issues/156 \
  --continue-branch \
  --branch "feature/user-profiles" \
  --no-clone \
  --instructions "Main branch was updated overnight. Merge latest changes and resolve any conflicts."
```

### Bug Fix Workflow

```bash
mcl start \
  --repo https://github.com/company/frontend \
  --requirements "Critical: Login page crashes on mobile Safari" \
  --branch "hotfix/mobile-safari-login" \
  --instructions "Reproduce the issue first, then fix. Prioritize mobile Safari 14+ compatibility."
```

### Local Development Workflow

```bash
# Start work on existing local project
mcl start \
  --repo ./my-local-project \
  --requirements "Add dark mode support" \
  --instructions "Ensure compatibility with existing themes"

# Continue work later
mcl start \
  --repo ./my-local-project \
  --requirements "Continue dark mode implementation" \
  --continue-branch \
  --branch "feature/dark-mode" \
  --instructions "Focus on the mobile responsive design issues found during testing"
```

### File-based Requirements Workflow

```bash
# Create detailed requirements file
echo "# API Redesign Project
## Goals
- Improve response times by 50%
- Add GraphQL support
- Implement better error handling

## Technical Requirements
- Migrate from REST to GraphQL
- Add Redis caching layer
- Implement circuit breaker pattern" > api-redesign-spec.md

# Start project with file requirements
mcl start \
  --repo https://github.com/company/api \
  --requirements ./api-redesign-spec.md \
  --instructions "Start with the caching layer implementation"
```

### Code Review Follow-up

```bash
mcl start \
  --repo https://github.com/company/service \
  --requirements "Address code review feedback on PR #89" \
  --continue-branch \
  --branch "feature/payment-processing" \
  --no-clone \
  --instructions "Review the PR comments and implement the suggested changes: extract payment logic into separate service, add error handling for network timeouts, and update tests."
```

## Tips

1. **Branch Naming**: If you don't specify `--branch`, the script auto-generates names from requirements
2. **GitHub Issues**: Use issue URLs for automatic requirement fetching and better documentation
3. **Task Memory**: Always update `TASK_MEMORY.md` as you work - it helps maintain context across sessions
4. **Instructions**: Use `--instructions` for session-specific guidance while keeping core requirements in `--requirements`
5. **Workspace Organization**: Use `--workspace` to organize projects in specific directories

## Troubleshooting

### Claude Code Not Found
```
Claude Code not found. Install it or start manually with: claude
```
**Solution**: Install Claude Code CLI or use `--no-claude` flag

### Git Authentication
```
Error running command 'git clone ...': authentication failed
```
**Solution**: Ensure your Git credentials are set up for the repository

### GitHub API Rate Limiting
```
HTTP error 403 fetching issue
```
**Solution**: Set the `GITHUB_TOKEN` environment variable to increase rate limits:
```bash
export GITHUB_TOKEN=your_github_token_here
```

### Private Repository Access
```
HTTP error 404 fetching issue
```
**Solution**: For private repositories, you need a GitHub token with appropriate permissions:
```bash
export GITHUB_TOKEN=your_github_token_here
```

### Repository Already Exists
```
Directory /path/to/repo already exists. Removing...
```
**Solution**: Use `--continue-branch` and `--no-clone` for existing repositories

### Branch Already Exists
```
fatal: A branch named 'feature/...' already exists
```
**Solution**: Use `--continue-branch` to work with existing branches, or specify a different `--branch` name

## Documentation

### Manager Documentation
For detailed information about the Multi-Agent Manager system:

- **[Manager User Guide](docs/MANAGER.md)** - Complete usage guide with examples
- **[Manager Quick Reference](docs/MANAGER_QUICK_REFERENCE.md)** - Command reference and common workflows  
- **[Manager Advanced Guide](docs/MANAGER_ADVANCED.md)** - Architecture, customization, and power user features

### Testing
The project includes a comprehensive test suite:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_manager.py -v      # Manager functionality
python -m pytest tests/test_unit.py -v        # Core MCL functionality
python -m pytest tests/test_agent_spawning.py -v  # Agent process tests
```

## License

MIT License - feel free to modify and distribute.
