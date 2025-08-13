# MCL Manager Advanced Usage Guide

## Architecture Deep Dive

### Process Model

The MCL Manager uses a daemon-based architecture:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   mcl manager   │    │  Manager Daemon │    │  Claude Agents  │
│   CLI Commands  │───▶│   (Supervisor)  │───▶│   (Workers)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       ▼                       │
         │              ┌─────────────────┐              │
         └─────────────▶│  SQLite DB +    │◀─────────────┘
                        │  Unix Sockets   │
                        └─────────────────┘
```

### Communication Flow

1. **Command Submission**: `mcl manager add` → Unix socket → Manager daemon
2. **Agent Spawning**: Manager → `claude -p --output-format json` subprocess
3. **Tool Evaluation**: Agent request → Manager LLM → Approval/denial
4. **Status Updates**: Database writes → CLI reads → User display

## Database Schema Details

### Tables Structure

```sql
-- Agent tracking
CREATE TABLE agents (
    id TEXT PRIMARY KEY,                    -- Short UUID (8 chars)
    task_description TEXT NOT NULL,        -- Original task
    repo_path TEXT NOT NULL,              -- Working directory
    status TEXT NOT NULL,                 -- active, completed, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    priority TEXT DEFAULT 'normal',       -- low, normal, high
    budget INTEGER DEFAULT 100            -- Dollar limit
);

-- Approval workflow
CREATE TABLE approval_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,              -- References agents.id
    request_type TEXT NOT NULL,          -- tool_request, budget_exceeded, etc
    request_data TEXT NOT NULL,          -- JSON payload
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_id) REFERENCES agents (id)
);

-- Interaction logging table
CREATE TABLE interaction_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,                  -- References agents.id
    session_id TEXT NOT NULL,               -- Grouping identifier
    interaction_type TEXT NOT NULL,         -- agent_request, manager_response, etc.
    direction TEXT NOT NULL,                -- agent_to_manager, manager_to_agent, system  
    content TEXT NOT NULL,                  -- Log content
    metadata TEXT,                          -- JSON metadata
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_id) REFERENCES agents (id)
);
```

### Query Examples

```sql
-- Find agents needing attention
SELECT a.id, a.task_description, COUNT(aq.id) as pending_requests
FROM agents a
LEFT JOIN approval_queue aq ON a.id = aq.agent_id
WHERE a.status = 'active'
GROUP BY a.id
HAVING pending_requests > 0;

-- Budget utilization report
SELECT priority, AVG(budget) as avg_budget, COUNT(*) as task_count
FROM agents
WHERE status = 'completed'
GROUP BY priority;

-- Interaction patterns analysis
SELECT interaction_type, direction, COUNT(*) as frequency
FROM interaction_logs
WHERE timestamp > datetime('now', '-24 hours')
GROUP BY interaction_type, direction
ORDER BY frequency DESC;

-- Agent session analysis
SELECT il.agent_id, a.task_description, il.session_id,
       COUNT(*) as interactions, 
       MIN(il.timestamp) as session_start,
       MAX(il.timestamp) as session_end
FROM interaction_logs il
JOIN agents a ON il.agent_id = a.id
GROUP BY il.agent_id, il.session_id
ORDER BY session_start DESC;
```

## Confidence-Based Decision System

The manager uses a sophisticated confidence system with multiple factors:

### Decision Algorithm

```python
def should_escalate(request_data, confidence_score, autonomy_level):
    # 1. Assess risk level (0.0-1.0)
    risk_score = assess_risk(request_data)
    
    # 2. Get autonomy thresholds
    thresholds = {
        "conservative": {"confidence": 0.8, "risk": 0.3, "base_escalate": 0.7},
        "balanced": {"confidence": 0.6, "risk": 0.5, "base_escalate": 0.4},
        "aggressive": {"confidence": 0.4, "risk": 0.7, "base_escalate": 0.2}
    }
    
    config = thresholds[autonomy_level]
    
    # 3. Apply decision rules
    if risk_score > config["risk"]:
        return True  # High risk always escalates
    
    if confidence_score < config["confidence"]:
        return True  # Low confidence escalates
    
    # 4. Probabilistic escalation for learning
    escalate_probability = config["base_escalate"] * (1 - confidence_score)
    return random.random() < escalate_probability
```

### Risk Assessment Matrix

```python
RISK_CATEGORIES = {
    # Critical (1.0) - Always escalate
    "destructive": ["rm -rf", "delete", "drop table", "truncate"],
    "system": ["sudo", "chmod 777", "chown root"],
    
    # High (0.7-0.9) - Usually escalate
    "database": ["alter table", "migration", "schema"],
    "config": ["config", "settings", ".env"],
    "external": ["http", "api", "webhook"],
    
    # Medium (0.3-0.6) - Context dependent
    "files": ["write", "edit", "move"],
    "install": ["npm install", "pip install"],
    
    # Low (0.0-0.2) - Usually approve
    "read": ["read", "cat", "grep"],
    "test": ["test", "pytest", "spec"]
}
```

### Confidence Calculation

The confidence score combines historical accuracy with decision consistency:

```python
def calculate_confidence_score():
    # Get recent decisions with feedback (last 30 days)
    decisions = get_recent_decisions_with_feedback()
    
    if not decisions:
        return 0.5  # Neutral starting point
    
    # Calculate accuracy rate
    correct_decisions = sum(1 for d in decisions if d.feedback == 'correct')
    accuracy_rate = correct_decisions / len(decisions)
    
    # Calculate average confidence of past decisions
    avg_past_confidence = sum(d.confidence_score for d in decisions) / len(decisions)
    
    # Weighted combination: 70% accuracy, 30% consistency
    confidence_score = (accuracy_rate * 0.7) + (avg_past_confidence * 0.3)
    
    return max(0.0, min(1.0, confidence_score))
```

## LLM Evaluation System

### Decision Making Context

Each tool request evaluation includes:

```python
evaluation_context = {
    "task_description": "Fix Redis timeout bug",
    "repository_path": "/Users/dev/api-service",
    "agent_id": "a1b2c3d4",
    "budget_remaining": 85,
    "priority": "high",
    "tool_request": {
        "tool": "edit",
        "parameters": {
            "file_path": "config/redis.py",
            "old_string": "timeout=30",
            "new_string": "timeout=120"
        },
        "reason": "Increase timeout to prevent connection drops"
    },
    "previous_actions": [...],
    "risk_factors": ["config_change", "production_setting"]
}
```

### Custom Evaluation Rules

You can customize evaluation by modifying the system prompt:

```python
# In future versions, this will be configurable
MANAGER_SYSTEM_PROMPT = """
You are an engineering manager evaluating tool requests from Claude Code agents.

APPROVAL CRITERIA:
- Read operations: Always approve
- Documentation edits: Always approve  
- Test file changes: Always approve
- Config changes: Approve if low risk
- Database changes: Escalate to user
- External API calls: Escalate if not in task scope

RISK ASSESSMENT:
- Low: Documentation, tests, simple edits
- Medium: Configuration, dependencies, refactoring
- High: Database, security, external integrations
- Critical: System commands, destructive operations

BUDGET CONSIDERATIONS:
- Under 50% budget: Be permissive
- 50-80% budget: Be more selective
- Over 80% budget: Escalate expensive operations

PRIORITY MODIFIERS:
- High priority: More permissive for task-relevant operations
- Normal priority: Standard evaluation
- Low priority: More restrictive, prefer safe operations

Respond with JSON:
{
    "decision": "approve|deny|escalate",
    "reasoning": "Brief explanation",
    "risk_level": "low|medium|high|critical",
    "cost_estimate": number,
    "alternatives": ["suggestion1", "suggestion2"]
}
"""
```

## Process Management

### Agent Lifecycle States

```
┌─────────┐    spawn    ┌─────────┐    working    ┌─────────┐
│  Idle   │─────────────▶│ Active  │──────────────▶│ Working │
└─────────┘              └─────────┘               └─────────┘
                              │                         │
                              │                         ▼
                              │                    ┌─────────┐
                              │           approve  │ Waiting │
                              │           ◀────────│Approval │
                              │                    └─────────┘
                              │                         │
                              ▼                         │ deny
                         ┌─────────┐                    │
                         │Completed│◀───────────────────┘
                         └─────────┘
                              │
                              ▼
                         ┌─────────┐
                         │ Archive │
                         └─────────┘
```

### Subprocess Management

Each agent runs as a controlled subprocess:

```python
# Agent spawning (simplified)
def spawn_claude_agent(agent_id, task_description, repo_path):
    cmd = [
        "claude", "-p",
        "--output-format", "json",
        "--max-turns", "1",
        f"cd {repo_path} && {task_description}"
    ]
    
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        text=True,
        cwd=agent_dir
    )
    
    return AgentProcess(agent_id, process, task_description)
```

### Error Recovery

The manager handles various failure modes:

```python
class AgentProcess:
    def handle_failure(self, error_type):
        if error_type == "process_crash":
            if self.restart_count < 3:
                self.restart_agent()
            else:
                self.mark_failed("max_restarts_exceeded")
        
        elif error_type == "timeout":
            self.send_interrupt()
            self.queue_for_user_review()
        
        elif error_type == "permission_denied":
            self.escalate_to_user("permission_issue")
```

## Advanced Workflows

### Batch Processing

Process multiple related tasks with dependencies:

```bash
# Complex feature implementation
mcl manager add "Create user model changes" --repo ~/backend --priority high --budget 100
mcl manager add "Update API endpoints" --repo ~/backend --priority high --budget 150
mcl manager add "Add frontend components" --repo ~/frontend --priority high --budget 120
mcl manager add "Write integration tests" --repo ~/tests --priority normal --budget 80
mcl manager add "Update documentation" --repo ~/docs --priority low --budget 30
```

### Cross-Repository Coordination

Manage tasks that span multiple repositories:

```bash
# Microservices update
mcl manager add "Update auth service" --repo ~/auth-service --priority high
mcl manager add "Update user service" --repo ~/user-service --priority high  
mcl manager add "Update API gateway" --repo ~/api-gateway --priority high
mcl manager add "Update shared models" --repo ~/shared-lib --priority high
```

### Interaction Logging and Analysis

The manager automatically logs all interactions between agents and the supervisor:

#### Log Analysis Scripts

```bash
#!/bin/bash
# analyze_agent_patterns.sh - Daily analysis script

AGENT_ID=$1
if [ -z "$AGENT_ID" ]; then
    echo "Usage: $0 <agent_id>"
    exit 1
fi

echo "=== AGENT $AGENT_ID ANALYSIS ==="

# Session summary
echo "Sessions:"
mcl manager sessions --agent $AGENT_ID

# Recent activity
echo -e "\nRecent activity (last 24 hours):"
mcl manager log --agent $AGENT_ID --limit 50 | grep "$(date +%Y-%m-%d)"

# Error patterns
echo -e "\nError patterns:"
mcl manager log --search "error" --agent $AGENT_ID

# Decision patterns
echo -e "\nDecision patterns:"
mcl manager log --search "Decision:" --agent $AGENT_ID | tail -20

# Export for further analysis
mcl manager log --agent $AGENT_ID --format json > "agent_${AGENT_ID}_$(date +%Y%m%d).json"
echo -e "\nFull log exported to agent_${AGENT_ID}_$(date +%Y%m%d).json"
```

#### Performance Monitoring

```python
#!/usr/bin/env python3
# log_analytics.py - Analyze manager performance

import json
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

def analyze_manager_performance(db_path):
    conn = sqlite3.connect(db_path)
    
    # Get interaction patterns
    cursor = conn.execute("""
        SELECT interaction_type, direction, COUNT(*) as count,
               AVG(JULIANDAY(timestamp) - LAG(JULIANDAY(timestamp)) 
                   OVER (PARTITION BY agent_id ORDER BY timestamp)) * 24 * 60 as avg_gap_minutes
        FROM interaction_logs 
        WHERE timestamp > datetime('now', '-7 days')
        GROUP BY interaction_type, direction
    """)
    
    patterns = cursor.fetchall()
    
    print("📊 INTERACTION PATTERNS (Last 7 Days)")
    print("-" * 50)
    for pattern in patterns:
        int_type, direction, count, avg_gap = pattern
        gap_str = f"{avg_gap:.1f}min" if avg_gap else "N/A"
        print(f"{int_type:15} {direction:20} {count:6} interactions, avg gap: {gap_str}")
    
    # Get most active sessions
    cursor = conn.execute("""
        SELECT il.session_id, a.task_description, COUNT(*) as interactions,
               MIN(il.timestamp) as start_time, MAX(il.timestamp) as end_time
        FROM interaction_logs il
        JOIN agents a ON il.agent_id = a.id
        WHERE il.timestamp > datetime('now', '-7 days')
        GROUP BY il.session_id
        ORDER BY interactions DESC
        LIMIT 10
    """)
    
    sessions = cursor.fetchall()
    
    print("\n🎯 MOST ACTIVE SESSIONS")
    print("-" * 80)
    for session in sessions:
        session_id, task_desc, interactions, start, end = session
        task_short = task_desc[:40] + "..." if len(task_desc) > 40 else task_desc
        print(f"{session_id[:12]}... | {task_short:43} | {interactions:3} interactions")
    
    conn.close()

if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "~/.mcl/manager/manager.db"
    analyze_manager_performance(db_path)
```

### Monitoring and Alerting

Set up monitoring workflows:

```bash
#!/bin/bash
# monitoring_script.sh - Run every 15 minutes

# Check for stuck agents
STUCK_AGENTS=$(mcl manager status | grep -c "Working.*[0-9][0-9]+ min")
if [ "$STUCK_AGENTS" -gt 0 ]; then
    echo "⚠️ Found $STUCK_AGENTS stuck agents" | notify
fi

# Check approval queue size
QUEUE_SIZE=$(mcl manager queue | grep -c "tool_request")
if [ "$QUEUE_SIZE" -gt 5 ]; then
    echo "📋 Large approval queue: $QUEUE_SIZE items" | notify
fi

# Budget alerts
HIGH_BUDGET_AGENTS=$(sqlite3 ~/.mcl/manager/manager.db \
    "SELECT COUNT(*) FROM agents WHERE budget > 200 AND status = 'active'")
if [ "$HIGH_BUDGET_AGENTS" -gt 0 ]; then
    echo "💰 $HIGH_BUDGET_AGENTS high-budget agents active" | notify
fi
```

## Customization

### Custom Approval Rules

Create task-specific approval rules:

```python
# Custom evaluation function (future feature)
def custom_approval_rules(task_desc, tool_request, context):
    # Documentation tasks - very permissive  
    if "documentation" in task_desc.lower():
        if tool_request["tool"] in ["read", "write", "edit"]:
            return {"decision": "approve", "risk": "low"}
    
    # Database tasks - require specific patterns
    if "database" in task_desc.lower():
        if "migration" in str(tool_request):
            return {"decision": "escalate", "risk": "high"}
        if "SELECT" in str(tool_request):
            return {"decision": "approve", "risk": "low"}
    
    # Fallback to default evaluation
    return None
```

### Integration Scripts

Integrate with external tools:

```bash
#!/bin/bash
# slack_notifications.sh

# Send status updates to Slack
STATUS=$(mcl manager status --format json)
QUEUE_SIZE=$(mcl manager queue --format json | jq length)

curl -X POST -H 'Content-type: application/json' \
    --data "{
        \"text\": \"MCL Manager Status\",
        \"attachments\": [{
            \"color\": \"good\",
            \"fields\": [
                {\"title\": \"Active Agents\", \"value\": \"$(echo $STATUS | jq length)\", \"short\": true},
                {\"title\": \"Pending Approvals\", \"value\": \"$QUEUE_SIZE\", \"short\": true}
            ]
        }]
    }" \
    $SLACK_WEBHOOK_URL
```

## Performance Optimization

### Resource Management

Monitor system resources:

```bash
# Check agent resource usage
ps aux | grep "claude.*json" | awk '{print $2, $3, $4}' | while read pid cpu mem; do
    echo "Agent PID $pid: CPU ${cpu}%, Memory ${mem}%"
done

# Disk usage monitoring
du -sh ~/.mcl/manager/agents/*
```

### Database Optimization

Keep the database performant:

```sql
-- Add indexes for common queries
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_priority ON agents(priority, status);
CREATE INDEX idx_approval_queue_created ON approval_queue(created_at);

-- Archive old completed tasks
DELETE FROM approval_queue WHERE created_at < datetime('now', '-7 days');
UPDATE agents SET status = 'archived' 
WHERE status = 'completed' AND created_at < datetime('now', '-30 days');
```

### Concurrent Agent Limits

Prevent system overload:

```python
# Configuration (future feature)
MANAGER_CONFIG = {
    "max_concurrent_agents": 5,
    "max_memory_per_agent": "512M", 
    "agent_timeout": 1800,  # 30 minutes
    "approval_timeout": 3600,  # 1 hour
    "auto_archive_days": 30
}
```

## Security Considerations

### Sandboxing

While not implemented yet, future versions will include:

```python
# Proposed security model
class SecureAgentEnvironment:
    def __init__(self, agent_id, repo_path):
        self.chroot_jail = f"/tmp/mcl_agent_{agent_id}"
        self.allowed_paths = [repo_path, "/usr/bin", "/bin"]
        self.blocked_commands = ["sudo", "su", "chmod 777"]
        self.network_policy = "deny_external"
```

### Audit Logging

Track all agent actions:

```python
# Audit log format
{
    "timestamp": "2025-08-13T14:30:15Z",
    "agent_id": "a1b2c3d4",
    "action": "tool_request",
    "tool": "edit", 
    "target": "/repo/config.py",
    "approved": true,
    "approver": "manager_llm",
    "risk_assessment": "low"
}
```

## Troubleshooting

### Debug Mode

Enable verbose logging:

```bash
# Future feature
export MCL_MANAGER_DEBUG=1
mcl manager start --verbose
```

### Agent Debugging

Inspect agent state:

```bash
# Check agent working directory
ls -la ~/.mcl/manager/agents/a1b2c3d4/

# View agent logs
tail -f ~/.mcl/manager/agents/a1b2c3d4/agent.log

# Check task memory
cat ~/.mcl/manager/agents/a1b2c3d4/TASK_MEMORY.md
```

### Database Debugging

Direct database inspection:

```bash
# Connect to database
sqlite3 ~/.mcl/manager/manager.db

# Common debug queries
.tables
SELECT * FROM agents WHERE status = 'active';
SELECT * FROM approval_queue ORDER BY created_at DESC LIMIT 10;
SELECT COUNT(*) as total_agents, status FROM agents GROUP BY status;
```

## API Reference (Future)

Planned programmatic API:

```python
from mcl.manager import ManagerClient

# Connect to running manager
client = ManagerClient()

# Submit task programmatically  
agent_id = client.add_task(
    description="Fix authentication timeout",
    repo_path="/path/to/repo",
    priority="high",
    budget=150
)

# Monitor progress
status = client.get_agent_status(agent_id)
if status.needs_approval:
    client.approve_request(status.pending_request_id)

# Batch operations
results = client.submit_batch([
    {"task": "Fix bug A", "repo": "/repo1"},
    {"task": "Fix bug B", "repo": "/repo2"}
])
```

This advanced guide provides the foundation for power users to maximize the manager's capabilities while maintaining security and reliability.