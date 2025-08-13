# MCL Manager Quick Reference

## Essential Commands

| Command | Description | Example |
|---------|-------------|---------|
| `mcl manager start` | Start manager daemon | `mcl manager start` |
| `mcl manager add <task> --repo <path>` | Add new task | `mcl manager add "Fix bug" --repo ~/project` |
| `mcl manager status` | Show active agents | `mcl manager status` |
| `mcl manager queue` | Show approval queue | `mcl manager queue` |
| `mcl manager approve <id>` | Approve request | `mcl manager approve 1` |
| `mcl manager deny <id>` | Deny request | `mcl manager deny 2` |
| `mcl manager config` | Configure autonomy/model | `mcl manager config --autonomy aggressive` |
| `mcl manager feedback <id> <feedback>` | Provide decision feedback | `mcl manager feedback 123 correct` |
| `mcl manager history` | Show decision history | `mcl manager history --limit 10` |
| `mcl manager stats` | Show performance stats | `mcl manager stats` |
| `mcl manager log --agent <id>` | View agent interaction logs | `mcl manager log --agent a1b2c3d4` |
| `mcl manager log --search <term>` | Search logs by content | `mcl manager log --search "error"` |
| `mcl manager sessions --agent <id>` | List agent sessions | `mcl manager sessions --agent a1b2c3d4` |
| `mcl manager simulate --agent <id>` | Simulate interactions (testing) | `mcl manager simulate --agent a1b2c3d4` |
| `mcl manager stop` | Stop manager | `mcl manager stop` |

## Task Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--priority` | `low`, `normal`, `high` | `normal` | Task urgency level |
| `--budget` | Number (dollars) | `100` | Cost limit for task |

## Priority Guidelines

- **`high`** - Production bugs, security issues, blockers
- **`normal`** - Regular features, improvements  
- **`low`** - Documentation, cleanup, nice-to-have

## Budget Guidelines

- **$10-25** - Simple edits, documentation fixes
- **$50-100** - Standard feature development
- **$150-300** - Complex features, integrations
- **$100-200** - Research, exploration tasks

## Autonomy Levels

| Level | Escalation Rate | Best For |
|-------|----------------|----------|
| `conservative` | 60-70% | New projects, learning system |
| `balanced` | 30-40% | Most workflows (default) |
| `aggressive` | 15-25% | Trusted environments |

## Evaluation Models

| Model | Provider | Best For |
|-------|----------|----------|
| `gpt-4o` | OpenAI | Most capable reasoning |
| `o1-preview` | OpenAI | Complex problem solving |
| `claude-3.5-sonnet` | Anthropic | Balanced performance (default) |
| `claude-3-opus` | Anthropic | Maximum capability |

## Typical Workflow

```bash
# 1. Start manager with good model
mcl manager start
mcl manager config --model gpt-4o

# 2. Submit tasks
mcl manager add "Fix auth timeout" --repo ~/api --priority high
mcl manager add "Update README" --repo ~/docs --priority low --budget 25

# 3. Monitor progress & handle approvals
mcl manager status
mcl manager queue
mcl manager approve 1

# 4. Provide feedback for learning
mcl manager history --limit 5
mcl manager feedback 101 correct
mcl manager feedback 102 incorrect

# 5. Check performance & adjust autonomy
mcl manager stats
# If accuracy > 85%: mcl manager config --autonomy aggressive

# 6. Review agent activity (optional)
mcl manager log                              # List agents with logs
mcl manager log --agent a1b2c3d4            # Review specific agent's work
mcl manager sessions --agent a1b2c3d4       # Check session breakdown
mcl manager log --search "error"            # Find any issues

# 7. End of day
mcl manager stop
```

## Auto-Approved Operations

✅ **Safe** (auto-approved):
- Reading files, searching code
- Simple edits, documentation
- Git operations, testing
- Low-cost operations

## Escalation Triggers

⚠️ **Requires approval**:
- Database changes
- System commands (`sudo`, `rm`)
- External API calls
- High-cost operations
- Security-sensitive changes

## File Locations

```
~/.mcl/manager/
├── agents/{id}/TASK_MEMORY.md    # Agent workspaces
├── manager.db                    # State database
└── state.json                    # Manager config
```

## Common Issues

| Problem | Solution |
|---------|----------|
| Manager won't start | `mcl manager stop && mcl manager start` |
| Agent stuck | Check `mcl manager queue` for pending approvals |
| Permission error | `chmod -R 755 ~/.mcl/manager/` |
| Database corrupt | `rm ~/.mcl/manager/manager.db && mcl manager start` |

## Status Indicators

| Symbol | Meaning |
|--------|---------|
| 🤖 | Active agent working |
| ⏳ | Pending approval needed |
| ✅ | Task completed successfully |
| ❌ | Task failed or denied |
| 🔔 | User attention required |

## Example Task Descriptions

**Good:**
```bash
mcl manager add "Fix Redis timeout in session handling" --repo ~/api
mcl manager add "Add dark mode toggle with localStorage" --repo ~/frontend  
mcl manager add "Update OAuth documentation for v2 API" --repo ~/docs
```

**Avoid:**
```bash
mcl manager add "Fix bug" --repo ~/project           # Too vague
mcl manager add "Make it work" --repo ~/app          # No context
mcl manager add "Do the thing" --repo ~/code         # Unclear
```

## Integration Notes

- Works with existing `mcl start` task memory format
- Agents appear in `mcl ls` output when appropriate
- Uses same directory conventions as regular MCL tasks
- Compatible with `mcl_cd` shell integration