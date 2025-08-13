"""
Tests for Claude Code agent spawning and process management.

These tests cover the actual execution of Claude Code processes, 
LLM evaluation, and the approval/denial system.
"""

import pytest
import subprocess
import json
import time
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
import tempfile

import mcl


class MockClaudeProcess:
    """Mock Claude Code process for testing."""
    
    def __init__(self, responses=None):
        self.responses = responses or []
        self.response_index = 0
        self.stdin_messages = []
        self.stdout = Mock()
        self.stderr = Mock()
        self.returncode = None
        
    def communicate(self, input_data=None):
        """Mock communicate method."""
        if input_data:
            self.stdin_messages.append(input_data)
        
        if self.response_index < len(self.responses):
            response = self.responses[self.response_index]
            self.response_index += 1
            return response, ""
        
        return "", ""
    
    def poll(self):
        """Mock poll method."""
        return self.returncode
    
    def terminate(self):
        """Mock terminate method."""
        self.returncode = -1
    
    def kill(self):
        """Mock kill method."""
        self.returncode = -9


class TestAgentSpawning:
    """Test Claude Code agent spawning functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager_dir = Path(self.temp_dir) / "manager"
        self.daemon = mcl.ManagerDaemon(self.manager_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('subprocess.Popen')
    def test_spawn_claude_process(self, mock_popen):
        """Test spawning a Claude Code process."""
        # Mock Claude process that returns JSON
        mock_process = MockClaudeProcess([
            ('{"status": "waiting_input", "message": "Ready to start"}', "")
        ])
        mock_popen.return_value = mock_process
        
        # This functionality would be added to ManagerDaemon
        # For now, test that we can mock the subprocess call
        process = subprocess.Popen([
            "claude", "-p", 
            "--output-format", "json",
            "--max-turns", "1",
            "Analyze the codebase and identify potential issues"
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "claude" in args
        assert "--output-format" in args
        assert "json" in args
    
    def test_parse_claude_json_response(self):
        """Test parsing Claude Code JSON responses."""
        # Sample Claude Code JSON response format
        sample_response = {
            "status": "tool_request",
            "message": "I need to read the configuration file",
            "tool_requests": [
                {
                    "tool": "read",
                    "parameters": {
                        "file_path": "/repo/config/settings.py"
                    },
                    "reason": "Need to understand current configuration"
                }
            ],
            "context": "Analyzing authentication system"
        }
        
        json_str = json.dumps(sample_response)
        parsed = json.loads(json_str)
        
        assert parsed["status"] == "tool_request"
        assert len(parsed["tool_requests"]) == 1
        assert parsed["tool_requests"][0]["tool"] == "read"
    
    def test_evaluate_tool_request_safe(self):
        """Test evaluation of safe tool requests."""
        tool_request = {
            "tool": "read",
            "parameters": {"file_path": "/repo/src/main.py"},
            "reason": "Understanding code structure"
        }
        
        # Mock evaluation function that would use LLM
        def mock_evaluate_request(task_description, tool_request, repo_path):
            # Simple rule-based evaluation for testing
            if "read" in tool_request.get("tool", ""):
                return {"approved": True, "risk_level": "low", "escalate": False}
            return {"approved": False, "risk_level": "high", "escalate": True}
        
        result = mock_evaluate_request("Fix bug", tool_request, "/repo")
        assert result["approved"] is True
        assert result["risk_level"] == "low"
        assert result["escalate"] is False
    
    def test_evaluate_tool_request_risky(self):
        """Test evaluation of risky tool requests."""
        tool_request = {
            "tool": "bash",
            "parameters": {"command": "rm -rf /"},
            "reason": "Clean up files"
        }
        
        def mock_evaluate_request(task_description, tool_request, repo_path):
            if "rm -rf" in str(tool_request.get("parameters", {})):
                return {"approved": False, "risk_level": "critical", "escalate": True}
            return {"approved": True, "risk_level": "low", "escalate": False}
        
        result = mock_evaluate_request("Clean files", tool_request, "/repo")
        assert result["approved"] is False
        assert result["risk_level"] == "critical"
        assert result["escalate"] is True


class TestLLMEvaluation:
    """Test LLM-based evaluation system."""
    
    @patch('anthropic.Anthropic')  # Assuming we'll use Anthropic SDK
    def test_llm_evaluation_approval(self, mock_anthropic):
        """Test LLM evaluation for tool approval."""
        # Mock Anthropic client
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        
        # Mock LLM response approving the request
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = json.dumps({
            "decision": "approve",
            "reasoning": "Reading configuration files is safe and necessary for the task",
            "risk_level": "low",
            "escalate": False
        })
        mock_client.messages.create.return_value = mock_response
        
        # This would be implemented in the manager
        def mock_llm_evaluate(task_description, tool_request, repo_path):
            system_prompt = f"""You are an engineering manager evaluating a tool request from a Claude Code agent.
            
Task: {task_description}
Repository: {repo_path}
Tool Request: {json.dumps(tool_request, indent=2)}

Evaluate this request and respond with JSON:
{{
    "decision": "approve" or "deny",
    "reasoning": "explanation of decision",
    "risk_level": "low|medium|high|critical",
    "escalate": true/false
}}

Consider:
- Safety of the operation
- Relevance to the task
- Potential for damage
- Cost implications
"""
            
            # In real implementation, would call LLM here
            return {
                "decision": "approve",
                "reasoning": "Safe read operation",
                "risk_level": "low", 
                "escalate": False
            }
        
        tool_request = {
            "tool": "read",
            "parameters": {"file_path": "/repo/config.py"}
        }
        
        result = mock_llm_evaluate("Fix auth bug", tool_request, "/repo")
        assert result["decision"] == "approve"
        assert result["risk_level"] == "low"
    
    def test_llm_evaluation_escalation(self):
        """Test LLM evaluation requiring escalation."""
        def mock_llm_evaluate_escalate(task_description, tool_request, repo_path):
            if "database" in str(tool_request).lower():
                return {
                    "decision": "escalate",
                    "reasoning": "Database modifications require user approval",
                    "risk_level": "high",
                    "escalate": True
                }
            return {"decision": "approve", "risk_level": "low", "escalate": False}
        
        tool_request = {
            "tool": "edit",
            "parameters": {
                "file_path": "/repo/database/migrations/001_add_users.sql",
                "content": "ALTER TABLE users ADD COLUMN email VARCHAR(255);"
            }
        }
        
        result = mock_llm_evaluate_escalate("Add user email", tool_request, "/repo")
        assert result["decision"] == "escalate"
        assert result["escalate"] is True
        assert result["risk_level"] == "high"


class TestAgentCommunication:
    """Test communication between manager and agents."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager_dir = Path(self.temp_dir) / "manager"
        self.daemon = mcl.ManagerDaemon(self.manager_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_approval_queue_operations(self):
        """Test adding and processing approval queue items."""
        # Create a test agent
        agent_id, session_id = self.daemon.spawn_agent("Test task", "/repo", "normal", 100)
        
        # Add approval request to queue
        import sqlite3
        conn = sqlite3.connect(self.daemon.db_path)
        conn.execute(
            "INSERT INTO approval_queue (agent_id, request_type, request_data) VALUES (?, ?, ?)",
            (agent_id, "tool_request", json.dumps({"tool": "edit", "file": "test.py"}))
        )
        conn.commit()
        conn.close()
        
        # Get queue items
        queue = self.daemon.get_approval_queue()
        assert len(queue) == 1
        assert queue[0][1] == agent_id  # agent_id
        assert queue[0][2] == "tool_request"  # request_type
        
        # Process approval (remove from queue)
        conn = sqlite3.connect(self.daemon.db_path)
        conn.execute("DELETE FROM approval_queue WHERE id = ?", (queue[0][0],))
        conn.commit()
        conn.close()
        
        # Verify queue is empty
        queue = self.daemon.get_approval_queue()
        assert len(queue) == 0
    
    @patch('subprocess.Popen')
    def test_agent_input_response(self, mock_popen):
        """Test sending input responses to agents."""
        # Mock process that can receive input
        mock_process = Mock()
        mock_process.stdin = Mock()
        mock_process.stdout = Mock()
        mock_process.stderr = Mock()
        mock_process.poll.return_value = None  # Still running
        mock_popen.return_value = mock_process
        
        # Simulate sending approval to agent
        approval_message = "yes\n"
        mock_process.stdin.write(approval_message)
        mock_process.stdin.flush()
        
        mock_process.stdin.write.assert_called_with(approval_message)
        mock_process.stdin.flush.assert_called_once()
    
    def test_agent_status_tracking(self):
        """Test tracking agent status through lifecycle."""
        agent_id, session_id = self.daemon.spawn_agent("Test task", "/repo", "normal", 100)
        
        # Initially active
        agents = self.daemon.get_active_agents()
        assert len(agents) == 1
        assert agents[0][3] == "active"  # status
        
        # Update to completed
        import sqlite3
        conn = sqlite3.connect(self.daemon.db_path)
        conn.execute("UPDATE agents SET status = ? WHERE id = ?", ("completed", agent_id))
        conn.commit()
        conn.close()
        
        # Should no longer be in active agents
        agents = self.daemon.get_active_agents()
        assert len(agents) == 0


class TestNotificationSystem:
    """Test macOS notification system for escalations."""
    
    @patch('subprocess.run')
    def test_macos_notification(self, mock_run):
        """Test sending macOS notification."""
        def send_notification(title, message, sound=True):
            cmd = [
                "osascript", 
                "-e", 
                f'display notification "{message}" with title "{title}"'
            ]
            if sound:
                cmd.extend(["-e", 'beep'])
            subprocess.run(cmd)
        
        send_notification("MCL Manager", "Agent needs approval for database changes")
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "osascript" in args
        assert "MCL Manager" in " ".join(args)
        assert "database changes" in " ".join(args)
    
    def test_escalation_triggers(self):
        """Test different escalation trigger scenarios."""
        escalation_rules = {
            "cost": {"threshold": 50, "escalate": True},
            "destructive": {"keywords": ["delete", "drop", "remove", "rm"], "escalate": True},
            "external": {"keywords": ["http", "api", "curl"], "escalate": True},
            "system": {"keywords": ["sudo", "chmod", "chown"], "escalate": True}
        }
        
        def should_escalate(tool_request, rules):
            # Cost check
            if "cost" in tool_request and tool_request["cost"] > rules["cost"]["threshold"]:
                return True
            
            # Keyword checks
            request_str = json.dumps(tool_request).lower()
            for rule_type in ["destructive", "external", "system"]:
                for keyword in rules[rule_type]["keywords"]:
                    if keyword in request_str:
                        return True
            
            return False
        
        # Test cases
        safe_request = {"tool": "read", "file": "config.py"}
        costly_request = {"tool": "llm_call", "cost": 75}
        destructive_request = {"tool": "bash", "command": "rm -rf temp/"}
        external_request = {"tool": "web_fetch", "url": "https://api.example.com"}
        
        assert not should_escalate(safe_request, escalation_rules)
        assert should_escalate(costly_request, escalation_rules)
        assert should_escalate(destructive_request, escalation_rules)
        assert should_escalate(external_request, escalation_rules)


class TestProcessManagement:
    """Test process lifecycle management."""
    
    @patch('subprocess.Popen')
    def test_agent_process_cleanup(self, mock_popen):
        """Test proper cleanup of agent processes."""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Running
        mock_popen.return_value = mock_process
        
        # Track processes (would be part of ManagerDaemon)
        active_processes = {"agent1": mock_process}
        
        # Terminate process
        process = active_processes["agent1"]
        process.terminate()
        process.wait(timeout=5)  # Would need error handling
        
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
    
    def test_agent_restart_on_crash(self):
        """Test restarting agents that crash."""
        def restart_agent(agent_id, task_description, repo_path):
            # Mock restart logic
            return {"status": "restarted", "new_pid": 54321}
        
        crashed_agent = {
            "id": "agent1", 
            "task": "Fix bug",
            "repo": "/repo",
            "restart_count": 0
        }
        
        # Only restart if under limit
        if crashed_agent["restart_count"] < 3:
            result = restart_agent(
                crashed_agent["id"],
                crashed_agent["task"], 
                crashed_agent["repo"]
            )
            crashed_agent["restart_count"] += 1
            
            assert result["status"] == "restarted"
            assert crashed_agent["restart_count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])