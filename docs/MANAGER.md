# Multi-Agent Manager Documentation

The MCL Manager is a supervisory system that manages multiple Claude Code agents simultaneously, providing automated approval workflows and centralized task management.

## Overview

The manager acts as an "engineering manager" that:
- Spawns and monitors multiple Claude Code agents
- Evaluates tool requests using LLM-based decision making
- Auto-approves safe operations, escalates risky ones
- Provides centralized status tracking and control
- Maintains persistent state across restarts

## Quick Start

### 1. Start the Manager

```bash
# Start the manager daemon
mcl manager start
```

Output:
```
🚀 Starting manager daemon...
📡 Manager daemon started
📊 Agents directory: /Users/you/.mcl/manager/agents
🔔 Submit tasks with: mcl manager add <task> --repo <path>
```

### 2. Submit Tasks

```bash
# Add tasks to the manager
mcl manager add "Fix Redis timeout bug" --repo ~/api-service
mcl manager add "Add dark mode toggle" --repo ~/frontend --priority high
mcl manager add "Update user documentation" --repo ~/docs --priority low --budget 50
```

Output:
```
✅ Agent a1b2c3d4 spawned for task: Fix Redis timeout bug...
🤖 Task queued with agent a1b2c3d4
```

### 3. Monitor Progress

```bash
# Check active agents
mcl manager status
```

Output:
```
🤖 ACTIVE AGENTS:
------------------------------------------------------------
a1b2c3d4 | Fix Redis timeout bug                   | normal | 2025-08-13 14:30:15
f5e6d7c8 | Add dark mode toggle                    | high   | 2025-08-13 14:32:22
b9a8c7d6 | Update user documentation               | low    | 2025-08-13 14:35:10
```

### 4. Handle Approvals

```bash
# Check approval queue
mcl manager queue
```

Output:
```
⏳ APPROVAL QUEUE:
------------------------------------------------------------
1 | a1b2c3d4 | tool_request | 2025-08-13 14:31:45
2 | f5e6d7c8 | tool_request | 2025-08-13 14:33:12
```

```bash
# Approve or deny requests
mcl manager approve 1
mcl manager deny 2
```

## Command Reference

### Core Commands

#### `mcl manager start`
Start the manager daemon process.

**Options:** None

**Example:**
```bash
mcl manager start
```

#### `mcl manager add <task> --repo <path>`
Add a new task to the manager.

**Arguments:**
- `task` - Task description (required)
- `--repo` - Repository path (required)
- `--priority` - Task priority: `low`, `normal`, `high` (default: `normal`)
- `--budget` - Budget limit in dollars (default: 100)

**Examples:**
```bash
mcl manager add "Fix authentication bug" --repo ~/api-service
mcl manager add "Add caching layer" --repo ~/backend --priority high --budget 150
mcl manager add "Update README" --repo ~/project --priority low --budget 25
```

#### `mcl manager status`
Show all active agents and their current status.

**Example:**
```bash
mcl manager status
```

#### `mcl manager queue`
Show pending approval requests that need user input.

**Example:**
```bash
mcl manager queue
```

#### `mcl manager approve <request_id>`
Approve a pending request from the approval queue.

**Arguments:**
- `request_id` - ID from the queue command

**Example:**
```bash
mcl manager approve 1
```

#### `mcl manager deny <request_id>`
Deny a pending request from the approval queue.

**Arguments:**
- `request_id` - ID from the queue command

**Example:**
```bash
mcl manager deny 2
```

#### `mcl manager stop`
Stop the manager daemon and all active agents.

**Example:**
```bash
mcl manager stop
```

#### `mcl manager config`
Configure manager autonomy level and evaluation model.

**Arguments:**
- `--autonomy` - Set autonomy level: `conservative`, `balanced`, `aggressive`
- `--model` - Set evaluation model: `gpt-4o`, `claude-3.5-sonnet`, `o1-preview`, etc.

**Examples:**
```bash
mcl manager config                                    # Show current config
mcl manager config --autonomy conservative            # Set to conservative mode
mcl manager config --model gpt-4o                    # Use GPT-4o for evaluation
mcl manager config --autonomy aggressive --model o1-preview  # Set both
```

#### `mcl manager feedback <decision_id> <feedback>`
Provide feedback on manager decisions to improve accuracy.

**Arguments:**
- `decision_id` - Decision ID from history command
- `feedback` - Either `correct` or `incorrect`

**Examples:**
```bash
mcl manager feedback 123 correct     # Manager made the right decision
mcl manager feedback 124 incorrect   # Manager made the wrong decision
```

#### `mcl manager history`
Show recent manager decisions for review and feedback.

**Arguments:**
- `--limit` - Number of decisions to show (default: 20)

**Examples:**
```bash
mcl manager history           # Show last 20 decisions
mcl manager history --limit 50   # Show last 50 decisions
```

#### `mcl manager stats`
Show manager performance statistics and accuracy metrics.

**Example:**
```bash
mcl manager stats
```

## Interaction Logging System

The manager includes a comprehensive logging system that records all interactions between the manager and agents. This allows you to review what happened during task execution, debug issues, and understand agent behavior patterns.

### Log Commands

#### `mcl manager log --agent <agent_id>`
View all interaction logs for a specific agent.

**Arguments:**
- `--agent` - Agent ID to view logs for (required)
- `--session` - Filter by specific session ID (optional)
- `--type` - Filter by interaction type: `agent_request`, `manager_response`, `agent_output`, `system_event` (optional)
- `--format` - Output format: `text` or `json` (default: `text`)
- `--limit` - Maximum number of log entries to show (default: 100)

**Examples:**
```bash
mcl manager log --agent a1b2c3d4                           # View all logs for agent
mcl manager log --agent a1b2c3d4 --format json            # Export as JSON
mcl manager log --agent a1b2c3d4 --type agent_request     # Only agent requests
mcl manager log --agent a1b2c3d4 --session session_123    # Specific session
```

#### `mcl manager log --search <term>`
Search all interaction logs for specific content.

**Arguments:**
- `--search` - Search term to find in log content (required)
- `--agent` - Limit search to specific agent (optional)
- `--limit` - Maximum search results (default: 50)

**Examples:**
```bash
mcl manager log --search "authentication"        # Find logs containing "authentication"
mcl manager log --search "error" --agent a1b2c3d4  # Search within specific agent's logs
```

#### `mcl manager log`
List all agents that have interaction logs.

**Example:**
```bash
mcl manager log
```

Output:
```
📋 AGENTS WITH INTERACTION LOGS:
----------------------------------------------------------------------
a1b2c3d4 | Fix Redis timeout bug                   |   45 logs | 2025-08-13 14:35:22
f5e6d7c8 | Add dark mode toggle                    |   23 logs | 2025-08-13 14:32:18
```

#### `mcl manager sessions --agent <agent_id>`
List all sessions for a specific agent.

**Arguments:**
- `--agent` - Agent ID to list sessions for (required)

**Example:**
```bash
mcl manager sessions --agent a1b2c3d4
```

Output:
```
📅 SESSIONS FOR AGENT a1b2c3d4:
----------------------------------------------------------------------
session_1755120034 | 2025-08-13 14:30:15 → 2025-08-13 14:45:22 | 12 interactions
session_1755120891 | 2025-08-13 15:15:30 → 2025-08-13 15:18:45 | 5 interactions
```

### Log Format

#### Text Format (Default)
The text format provides a human-readable view of interactions:

```
=== SESSION session_1755120034 ===
Task: Fix Redis timeout bug

[2025-08-13 14:30:15] ⚙️ SYSTEM_EVENT
    Agent spawned for task: Fix Redis timeout bug
    📋 {"repo_path":"/api-service","priority":"high","budget":150}

[2025-08-13 14:30:22] 🤖→🧠 AGENT_REQUEST
    {
      "tool": "read",
      "file_path": "config/redis.py"
    }
    📋 {"tool":"read","risk_assessment":"pending"}

[2025-08-13 14:30:23] 🧠→🤖 MANAGER_RESPONSE
    Decision: APPROVE
    📋 {"confidence_score":0.85,"autonomy_level":"balanced","decision_reasoning":"Confidence: 0.85, Autonomy: balanced"}

[2025-08-13 14:30:25] 🤖→🧠 AGENT_OUTPUT
    ✅ Read operation completed successfully
    📋 {"operation":"read","status":"completed","result":"success"}
```

**Legend:**
- `🤖→🧠` - Agent sending to Manager
- `🧠→🤖` - Manager responding to Agent  
- `⚙️` - System events
- `📋` - Metadata information

#### JSON Format
Use `--format json` for programmatic processing:

```json
[
  {
    "id": 1,
    "agent_id": "a1b2c3d4",
    "task_description": "Fix Redis timeout bug",
    "session_id": "session_1755120034",
    "interaction_type": "agent_request",
    "direction": "agent_to_manager",
    "content": "{\"tool\": \"read\", \"file_path\": \"config/redis.py\"}",
    "metadata": {"tool": "read", "risk_assessment": "pending"},
    "timestamp": "2025-08-13 14:30:22"
  }
]
```

### Session Management

Sessions group related interactions together. A new session typically starts when:
- An agent is first spawned
- An agent begins a new major task phase
- Manual session boundaries are created

Each session has:
- **Session ID** - Unique identifier
- **Start/End Times** - Duration of the session
- **Interaction Count** - Number of logged interactions
- **Agent Context** - Associated agent and task

### Use Cases

#### Debugging Agent Issues
```bash
# Agent seems stuck - check recent logs
mcl manager log --agent a1b2c3d4 --limit 20

# Look for error patterns
mcl manager log --search "error" --agent a1b2c3d4
mcl manager log --search "failed" --agent a1b2c3d4
```

#### Understanding Decision Patterns
```bash
# See what the manager is approving/denying
mcl manager log --search "Decision:" --limit 50

# Check specific tool usage
mcl manager log --search "edit" --agent a1b2c3d4
```

#### Reviewing Task Progress
```bash
# Get overview of agent activity
mcl manager sessions --agent a1b2c3d4

# Export full task history for analysis
mcl manager log --agent a1b2c3d4 --format json > task_history.json
```

#### Performance Analysis
```bash
# Find long-running operations
mcl manager log --search "executing" 

# Review approval patterns
mcl manager log --search "APPROVE"
mcl manager log --search "ESCALATE"
```

## Task Management

### Priority Levels

- **`low`** - Non-urgent tasks, documentation, cleanup
- **`normal`** - Standard development tasks (default)
- **`high`** - Bug fixes, urgent features, time-sensitive work

Priority affects:
- Agent attention and resource allocation
- Escalation thresholds (high priority gets more approvals)
- Queue ordering for approval requests

### Budget Management

Each task has a budget limit that controls:
- LLM API call expenses
- External service usage
- Resource-intensive operations

When a task approaches its budget limit, the manager will:
1. Warn the agent to be more conservative
2. Require approval for expensive operations
3. Escalate to user for budget increase

### Task Memory Integration

Each agent gets its own isolated workspace:

```
~/.mcl/manager/agents/{agent_id}/
├── TASK_MEMORY.md    # Task context and progress
└── ...               # Agent working files
```

The task memory file contains:
- Original task description
- Manager supervision context
- Progress tracking
- Work log with timestamps
- Agent status and decisions

## Confidence-Based Autonomy System

The manager uses an adaptive confidence system that learns from your feedback and adjusts its autonomy level accordingly.

### Autonomy Levels

The manager operates in three autonomy modes that control how often it escalates decisions to you:

#### **Conservative Mode**
- **Escalates 60-70%** of requests for user approval
- **High confidence threshold** (0.8) required for auto-approval
- **Low risk tolerance** - escalates even minor configuration changes
- **Best for**: New projects, critical systems, learning the manager's behavior

```bash
mcl manager config --autonomy conservative
```

#### **Balanced Mode** (Default)
- **Escalates 30-40%** of requests for user approval  
- **Medium confidence threshold** (0.6) required for auto-approval
- **Moderate risk tolerance** - balances autonomy with safety
- **Best for**: Most development workflows, established trust

```bash
mcl manager config --autonomy balanced
```

#### **Aggressive Mode**
- **Escalates only 15-25%** of requests for user approval
- **Low confidence threshold** (0.4) required for auto-approval
- **High risk tolerance** - allows more autonomous operation
- **Best for**: Trusted environments, routine tasks, experienced users

```bash
mcl manager config --autonomy aggressive
```

### Confidence Score System

The manager calculates a **confidence score (0.0-1.0)** based on:

- **Historical accuracy** (70% weight) - How often your feedback marked decisions as "correct"
- **Decision consistency** (30% weight) - How confident the manager was in past decisions

**Initial confidence**: 0.5 (neutral)
**High confidence**: 0.8+ (manager makes good decisions)
**Low confidence**: 0.3- (manager needs more guidance)

### Better Evaluation Models

Use more capable models for more accurate decision-making:

```bash
# State-of-the-art models
mcl manager config --model gpt-4o                # OpenAI's most capable
mcl manager config --model o1-preview            # OpenAI's reasoning model
mcl manager config --model claude-3.5-sonnet     # Anthropic's latest (default)

# Alternative models
mcl manager config --model gpt-4-turbo           # Fast and capable
mcl manager config --model claude-3-opus         # Maximum capability
```

### Feedback Learning Loop

The system improves through user feedback:

1. **Review decisions**: `mcl manager history`
2. **Provide feedback**: `mcl manager feedback <id> correct/incorrect` 
3. **Monitor improvement**: `mcl manager stats`
4. **Adjust autonomy**: Increase autonomy as confidence grows

**Example Learning Workflow:**
```bash
# Week 1: Start conservative, provide lots of feedback
mcl manager config --autonomy conservative --model gpt-4o
mcl manager history --limit 20
mcl manager feedback 101 correct
mcl manager feedback 102 incorrect  
mcl manager feedback 103 correct

# Week 2: Check stats, maybe increase autonomy
mcl manager stats
# If accuracy > 80%, consider: mcl manager config --autonomy balanced

# Week 4: High confidence, go more autonomous  
mcl manager stats
# If accuracy > 90%, consider: mcl manager config --autonomy aggressive
```

## Approval System

### Auto-Approval Rules

The manager automatically approves:
- **Read operations** - Reading files, searching code
- **Low-risk edits** - Simple code changes, documentation updates  
- **Standard tools** - Git operations, testing, linting
- **Within budget** - Operations under cost thresholds

### Escalation Triggers

The manager escalates to user approval for:

#### 🔴 **High Risk Operations**
- Database schema changes
- System configuration modifications
- Destructive operations (`rm`, `delete`, `drop`)
- External API calls

#### 💰 **Cost Concerns**
- Operations exceeding budget thresholds
- Expensive LLM API calls
- Resource-intensive computations

#### 🔒 **Security Sensitive**
- System-level commands (`sudo`, `chmod`)
- Network operations (`curl`, `wget`)
- Package installations
- Environment modifications

#### ❓ **Unclear Intent**
- Operations outside task scope
- Ambiguous tool requests
- Complex multi-step changes

### Escalation Workflow

1. **Agent Request** - Agent requests tool usage
2. **LLM Evaluation** - Manager evaluates with context:
   ```
   Task: Fix authentication bug
   Repository: ~/api-service  
   Request: Edit database migration file
   
   Assessment: HIGH RISK - Database changes require approval
   ```
3. **User Notification** - macOS notification sent
4. **User Decision** - Approve/deny via `mcl manager approve/deny`
5. **Agent Continuation** - Agent proceeds or finds alternative

## Directory Structure

The manager creates the following structure:

```
~/.mcl/manager/
├── agents/                 # Agent workspaces
│   ├── a1b2c3d4/          # Agent ID directory
│   │   ├── TASK_MEMORY.md # Task context
│   │   └── ...            # Agent files
│   └── f5e6d7c8/          # Another agent
├── manager.db             # SQLite database
└── state.json             # Manager state
```

### Database Schema

**agents table:**
- `id` - Unique agent identifier
- `task_description` - Original task description
- `repo_path` - Repository path
- `status` - Agent status (active, completed, failed)
- `priority` - Task priority level
- `budget` - Budget limit
- `created_at` - Timestamp

**approval_queue table:**
- `id` - Queue item ID
- `agent_id` - Associated agent
- `request_type` - Type of request
- `request_data` - JSON request details
- `created_at` - Timestamp

## Advanced Usage

### Multiple Repository Management

Manage tasks across different repositories:

```bash
mcl manager add "Fix API rate limiting" --repo ~/backend
mcl manager add "Update login UI" --repo ~/frontend  
mcl manager add "Add deployment docs" --repo ~/infrastructure
```

Each agent works in isolation with proper repository context.

### Batch Task Submission

Submit multiple related tasks:

```bash
# User authentication overhaul
mcl manager add "Update user model" --repo ~/backend --priority high
mcl manager add "Implement JWT tokens" --repo ~/backend --priority high  
mcl manager add "Add login/logout UI" --repo ~/frontend --priority high
mcl manager add "Update auth documentation" --repo ~/docs --priority normal
```

### Custom Budget Allocation

Allocate budgets based on task complexity:

```bash
# Simple documentation task
mcl manager add "Fix typos in README" --repo ~/project --budget 10

# Complex feature implementation  
mcl manager add "Add payment processing" --repo ~/ecommerce --budget 300

# Research and exploration
mcl manager add "Evaluate GraphQL migration" --repo ~/api --budget 150
```

### Status Monitoring Workflow

Regular monitoring routine:

```bash
# Morning standup
mcl manager status

# Check for approvals needed
mcl manager queue

# Process any pending requests
mcl manager approve 1
mcl manager approve 3
mcl manager deny 2   # Too risky
```

## Integration with Existing MCL

The manager integrates seamlessly with existing MCL workflows:

### Task Memory Compatibility

Agents use the same TASK_MEMORY.md format as `mcl start`, ensuring:
- Consistent task tracking
- Familiar agent behavior  
- Proper context preservation
- Progress visibility

### Directory Integration

Manager agents appear alongside regular MCL tasks:

```bash
# List all tasks (including managed ones)
mcl ls

# Change to managed agent directory
mcl_cd 3   # If it appears in the list
```

## Troubleshooting

### Manager Not Starting

```bash
# Check if already running
mcl manager status

# If stuck, stop and restart
mcl manager stop
mcl manager start
```

### Agent Not Responding

```bash
# Check agent status
mcl manager status

# Look for pending approvals
mcl manager queue

# Check agent task memory
cat ~/.mcl/manager/agents/{agent_id}/TASK_MEMORY.md
```

### Permission Issues

```bash
# Ensure manager directory permissions
ls -la ~/.mcl/manager/

# If needed, fix permissions
chmod -R 755 ~/.mcl/manager/
```

### Database Issues

```bash
# Check database exists
ls -la ~/.mcl/manager/manager.db

# If corrupted, remove and restart
rm ~/.mcl/manager/manager.db
mcl manager start
```

## Best Practices

### Task Description Guidelines

**Good task descriptions:**
```bash
mcl manager add "Fix Redis connection timeout in user session handling" --repo ~/api
mcl manager add "Add dark mode toggle to settings page with persistence" --repo ~/frontend
mcl manager add "Update authentication flow documentation with new OAuth steps" --repo ~/docs
```

**Avoid vague descriptions:**
```bash
# Too vague
mcl manager add "Fix bug" --repo ~/project
mcl manager add "Make it better" --repo ~/app
```

### Priority Assignment

- **High**: Production bugs, security issues, blocking dependencies
- **Normal**: Feature development, improvements, scheduled tasks
- **Low**: Documentation, cleanup, nice-to-have features

### Budget Planning

- **Simple tasks**: $10-25 (typos, small edits)
- **Standard features**: $50-100 (typical development)
- **Complex features**: $150-300 (architecture, integrations)
- **Research/exploration**: $100-200 (investigation, evaluation)

### Approval Strategy

- **Trust but verify**: Let agents work autonomously while monitoring
- **Quick responses**: Check approval queue regularly (every 30 minutes)
- **Context awareness**: Review task description before approving
- **Risk assessment**: When in doubt, deny and provide guidance

## Security Considerations

### Access Control

The manager operates with the same permissions as the user, so:
- Only run managers in trusted environments
- Review agent requests carefully
- Use appropriate budget limits
- Monitor agent activities

### Data Privacy

Agent workspaces are isolated but accessible:
- Task memory files contain sensitive information
- Repository access requires existing user permissions
- No additional authentication beyond file system permissions

### Network Security

The manager uses local Unix sockets for communication:
- No network exposure by default
- Local machine communication only
- Standard file system security applies

## Future Enhancements

Planned features for future releases:

- **Web Dashboard** - Browser-based monitoring interface
- **Team Sharing** - Multi-user manager coordination  
- **Advanced Scheduling** - Time-based task execution
- **Integration APIs** - Webhook and API integrations
- **Enhanced LLM Models** - Better evaluation accuracy
- **Resource Monitoring** - CPU, memory, disk usage tracking

## Getting Help

For issues or questions:

1. Check this documentation
2. Review agent TASK_MEMORY.md files
3. Check manager status and queue
4. File issues at the project repository

The manager system is designed to make multi-agent development workflows efficient and safe while maintaining full user control over important decisions.