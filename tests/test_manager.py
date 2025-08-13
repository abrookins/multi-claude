"""
Unit tests for multi-agent manager functionality.

Tests cover:
- ManagerDaemon class functionality
- Manager CLI commands
- Agent spawning and management
- Database operations
- Socket communication (mocked)
- LLM evaluation system (when implemented)
"""

import pytest
import tempfile
import sqlite3
import json
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import socket
import uuid

# Import the module under test  
import mcl


class TestManagerDaemon:
    """Test ManagerDaemon class functionality."""
    
    def setup_method(self):
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager_dir = Path(self.temp_dir) / "manager"
        
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_manager_daemon_init(self):
        """Test ManagerDaemon initialization."""
        daemon = mcl.ManagerDaemon(self.manager_dir)
        
        assert daemon.manager_dir == self.manager_dir
        assert daemon.agents_dir == self.manager_dir / "agents"
        assert daemon.db_path == self.manager_dir / "manager.db"
        assert daemon.socket_path == "/tmp/mcl_manager.sock"
        
        # Check directories were created
        assert daemon.manager_dir.exists()
        assert daemon.agents_dir.exists()
        
        # Check database was created
        assert daemon.db_path.exists()
    
    def test_database_schema_creation(self):
        """Test that database tables are created correctly."""
        daemon = mcl.ManagerDaemon(self.manager_dir)
        
        # Check agents table
        conn = sqlite3.connect(daemon.db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agents'")
        assert cursor.fetchone() is not None
        
        # Check approval_queue table
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='approval_queue'")
        assert cursor.fetchone() is not None
        
        # Check agents table schema
        cursor = conn.execute("PRAGMA table_info(agents)")
        columns = [row[1] for row in cursor.fetchall()]
        expected_columns = ['id', 'task_description', 'repo_path', 'status', 'created_at', 'priority', 'budget']
        for col in expected_columns:
            assert col in columns
        
        conn.close()
    
    @patch('uuid.uuid4')
    @patch('mcl.datetime')
    def test_spawn_agent(self, mock_datetime, mock_uuid):
        """Test agent spawning functionality."""
        # Setup mocks
        mock_uuid.return_value = Mock()
        mock_uuid.return_value.__str__ = Mock(return_value="12345678-1234-1234-1234-123456789012")
        mock_datetime.now.return_value.strftime.return_value = "2023-07-23 10:30:00"
        
        daemon = mcl.ManagerDaemon(self.manager_dir)
        
        # Spawn an agent
        agent_id, session_id = daemon.spawn_agent(
            task_description="Fix authentication bug",
            repo_path="/path/to/repo",
            priority="high",
            budget=200
        )
        
        assert agent_id == "12345678"
        assert session_id is not None
        
        # Check agent directory was created
        agent_dir = daemon.agents_dir / agent_id
        assert agent_dir.exists()
        
        # Check TASK_MEMORY.md was created
        task_memory_path = agent_dir / "TASK_MEMORY.md"
        assert task_memory_path.exists()
        
        # Check task memory content
        with open(task_memory_path) as f:
            content = f.read()
            assert "Fix authentication bug" in content
            assert "/path/to/repo" in content
            assert "high" in content
            assert "$200" in content
            assert "manager supervision" in content
        
        # Check database entry
        conn = sqlite3.connect(daemon.db_path)
        cursor = conn.execute("SELECT id, task_description, repo_path, status, priority, budget FROM agents WHERE id = ?", (agent_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == "Fix authentication bug"  # task_description
        assert row[2] == "/path/to/repo"  # repo_path
        assert row[3] == "active"  # status
        assert row[4] == "high"  # priority
        assert row[5] == 200  # budget
        conn.close()
    
    def test_get_active_agents_empty(self):
        """Test getting active agents when none exist."""
        daemon = mcl.ManagerDaemon(self.manager_dir)
        agents = daemon.get_active_agents()
        assert agents == []
    
    def test_get_active_agents_with_data(self):
        """Test getting active agents with existing data."""
        daemon = mcl.ManagerDaemon(self.manager_dir)
        
        # Insert test data directly into database
        conn = sqlite3.connect(daemon.db_path)
        conn.execute(
            "INSERT INTO agents (id, task_description, repo_path, status, priority, budget) VALUES (?, ?, ?, ?, ?, ?)",
            ("agent1", "Task 1", "/repo1", "active", "normal", 100)
        )
        conn.execute(
            "INSERT INTO agents (id, task_description, repo_path, status, priority, budget) VALUES (?, ?, ?, ?, ?, ?)",
            ("agent2", "Task 2", "/repo2", "completed", "high", 200)
        )
        conn.execute(
            "INSERT INTO agents (id, task_description, repo_path, status, priority, budget) VALUES (?, ?, ?, ?, ?, ?)",
            ("agent3", "Task 3", "/repo3", "active", "low", 50)
        )
        conn.commit()
        conn.close()
        
        # Should only return active agents
        agents = daemon.get_active_agents()
        assert len(agents) == 2
        
        agent_ids = [agent[0] for agent in agents]
        assert "agent1" in agent_ids
        assert "agent3" in agent_ids
        assert "agent2" not in agent_ids  # completed, not active
    
    def test_get_approval_queue_empty(self):
        """Test getting approval queue when empty."""
        daemon = mcl.ManagerDaemon(self.manager_dir)
        queue = daemon.get_approval_queue()
        assert queue == []
    
    def test_get_approval_queue_with_data(self):
        """Test getting approval queue with existing requests."""
        daemon = mcl.ManagerDaemon(self.manager_dir)
        
        # Insert test data
        conn = sqlite3.connect(daemon.db_path)
        conn.execute(
            "INSERT INTO agents (id, task_description, repo_path, status, priority, budget) VALUES (?, ?, ?, ?, ?, ?)",
            ("agent1", "Task 1", "/repo1", "active", "normal", 100)
        )
        conn.execute(
            "INSERT INTO approval_queue (agent_id, request_type, request_data) VALUES (?, ?, ?)",
            ("agent1", "tool_request", '{"tool": "edit", "file": "config.py"}')
        )
        conn.commit()
        conn.close()
        
        queue = daemon.get_approval_queue()
        assert len(queue) == 1
        assert queue[0][1] == "agent1"  # agent_id
        assert queue[0][2] == "tool_request"  # request_type
        assert queue[0][5] == "Task 1"  # task_description from join


class TestManagerCommands:
    """Test manager CLI command functions."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager_dir = Path(self.temp_dir) / "manager"
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('mcl.is_manager_running', return_value=False)
    @patch('mcl.get_manager_daemon')
    @patch('builtins.print')
    def test_cmd_manager_start_not_running(self, mock_print, mock_get_daemon, mock_is_running):
        """Test manager start command when not running."""
        mock_daemon = Mock()
        mock_daemon.agents_dir = Path("/test/agents")
        mock_get_daemon.return_value = mock_daemon
        
        args = Mock()
        args.manager_command = "start"
        
        mcl.cmd_manager(args)
        
        mock_print.assert_any_call("🚀 Starting manager daemon...")
        mock_print.assert_any_call("📡 Manager daemon started")
    
    @patch('mcl.is_manager_running', return_value=True)
    @patch('builtins.print')
    def test_cmd_manager_start_already_running(self, mock_print, mock_is_running):
        """Test manager start command when already running."""
        args = Mock()
        args.manager_command = "start"
        
        mcl.cmd_manager(args)
        
        mock_print.assert_called_with("⚠️  Manager daemon already running")
    
    @patch('mcl.is_manager_running', return_value=False)
    @patch('mcl.get_manager_daemon')
    @patch('builtins.print')
    def test_cmd_manager_add_auto_start(self, mock_print, mock_get_daemon, mock_is_running):
        """Test manager add command with auto-start."""
        mock_daemon = Mock()
        mock_daemon.spawn_agent.return_value = ("test_agent_id", "test_session_id")
        mock_get_daemon.return_value = mock_daemon
        
        args = Mock()
        args.manager_command = "add"
        args.task = "Fix bug"
        args.repo = "/test/repo"
        args.priority = "normal"
        
        mcl.cmd_manager(args)
        
        mock_print.assert_any_call("🚀 Starting manager daemon...")
        mock_daemon.spawn_agent.assert_called_once_with("Fix bug", "/test/repo", "normal")
        mock_print.assert_any_call("🤖 Task queued with agent test_agent_id")
    
    @patch('mcl.get_manager_daemon')
    @patch('builtins.print')
    def test_cmd_manager_status_no_agents(self, mock_print, mock_get_daemon):
        """Test manager status command with no agents."""
        mock_daemon = Mock()
        mock_daemon.get_active_agents.return_value = []
        mock_get_daemon.return_value = mock_daemon
        
        args = Mock()
        args.manager_command = "status"
        
        mcl.cmd_manager(args)
        
        mock_print.assert_called_with("📭 No active agents")
    
    @patch('mcl.get_manager_daemon')
    @patch('builtins.print')
    def test_cmd_manager_status_with_agents(self, mock_print, mock_get_daemon):
        """Test manager status command with active agents."""
        mock_daemon = Mock()
        mock_daemon.get_active_agents.return_value = [
            ("agent1", "Fix authentication bug in user service", "/repo1", "active", "high", "2023-07-23 10:30:00"),
            ("agent2", "Add dark mode toggle", "/repo2", "active", "normal", "2023-07-23 11:00:00")
        ]
        mock_get_daemon.return_value = mock_daemon
        
        args = Mock()
        args.manager_command = "status"
        
        mcl.cmd_manager(args)
        
        mock_print.assert_any_call("🤖 ACTIVE AGENTS:")
        mock_print.assert_any_call("-" * 80)
        # Check that agent info is printed (exact format may vary)
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        agent_lines = [line for line in print_calls if "agent1" in line or "agent2" in line]
        assert len(agent_lines) == 2
    
    @patch('mcl.get_manager_daemon')
    @patch('builtins.print')
    def test_cmd_manager_queue_empty(self, mock_print, mock_get_daemon):
        """Test manager queue command with empty queue."""
        mock_daemon = Mock()
        mock_daemon.get_approval_queue.return_value = []
        mock_get_daemon.return_value = mock_daemon
        
        args = Mock()
        args.manager_command = "queue"
        
        mcl.cmd_manager(args)
        
        mock_print.assert_called_with("📭 No pending approvals")
    
    @patch('mcl.is_manager_running', return_value=False)
    @patch('builtins.print')
    def test_cmd_manager_stop_not_running(self, mock_print, mock_is_running):
        """Test manager stop command when not running."""
        args = Mock()
        args.manager_command = "stop"
        
        mcl.cmd_manager(args)
        
        mock_print.assert_called_with("ℹ️  Manager daemon not running")
    
    @patch('builtins.print')
    def test_cmd_manager_unknown_command(self, mock_print):
        """Test manager with unknown command."""
        args = Mock()
        args.manager_command = "invalid_command"
        
        mcl.cmd_manager(args)
        
        mock_print.assert_called_with("❌ Unknown manager command: invalid_command")
    
    @patch('argparse.ArgumentParser.print_help')
    def test_cmd_manager_no_subcommand(self, mock_help):
        """Test manager command with no subcommand shows help."""
        args = Mock()
        args.manager_command = None
        
        mcl.cmd_manager(args)
        
        mock_help.assert_called_once()


class TestManagerUtilities:
    """Test manager utility functions."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager_dir = Path(self.temp_dir) / "manager"
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_manager_daemon(self):
        """Test manager daemon factory function."""
        daemon = mcl.get_manager_daemon()
        assert isinstance(daemon, mcl.ManagerDaemon)
    
    @patch('socket.socket')
    def test_is_manager_running_true(self, mock_socket):
        """Test manager running detection when running."""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        mock_sock.connect.return_value = None  # Success
        
        result = mcl.is_manager_running()
        assert result is True
        mock_sock.connect.assert_called_once_with("/tmp/mcl_manager.sock")
        mock_sock.close.assert_called_once()
    
    @patch('socket.socket')
    def test_is_manager_running_false(self, mock_socket):
        """Test manager running detection when not running."""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        mock_sock.connect.side_effect = ConnectionRefusedError()
        
        result = mcl.is_manager_running()
        assert result is False
    
    @patch('mcl.is_manager_running', return_value=False)
    @patch('builtins.print')
    def test_send_manager_command_not_running(self, mock_print, mock_is_running):
        """Test sending command when manager not running."""
        result = mcl.send_manager_command("test_command")
        assert result is False
        mock_print.assert_called_with("❌ Manager daemon not running. Start with: mcl manager start")
    
    @patch('mcl.is_manager_running', return_value=True)
    @patch('socket.socket')
    @patch('builtins.print')
    def test_send_manager_command_success(self, mock_print, mock_socket, mock_is_running):
        """Test successful manager command sending."""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        mock_sock.recv.return_value = b"Command executed successfully"
        
        result = mcl.send_manager_command("test_command", param1="value1")
        
        assert result is True
        mock_sock.connect.assert_called_once_with("/tmp/mcl_manager.sock")
        mock_sock.send.assert_called_once()
        mock_sock.recv.assert_called_once_with(4096)
        mock_print.assert_called_with("Command executed successfully")
        mock_sock.close.assert_called_once()
    
    @patch('mcl.is_manager_running', return_value=True)
    @patch('socket.socket')
    @patch('builtins.print')  
    def test_send_manager_command_error(self, mock_print, mock_socket, mock_is_running):
        """Test manager command sending with error."""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        mock_sock.connect.side_effect = Exception("Connection failed")
        
        result = mcl.send_manager_command("test_command")
        
        assert result is False
        mock_print.assert_called_with("❌ Error communicating with manager: Connection failed")


class TestManagerIntegration:
    """Test manager CLI integration with argument parsing."""
    
    @patch('mcl.cmd_manager')
    @patch('sys.argv', ['mcl', 'manager', 'start'])
    def test_manager_start_parsing(self, mock_cmd_manager):
        """Test manager start command parsing."""
        mcl.main()
        mock_cmd_manager.assert_called_once()
        args = mock_cmd_manager.call_args[0][0]
        assert args.manager_command == 'start'
    
    @patch('mcl.cmd_manager')
    @patch('sys.argv', ['mcl', 'manager', 'add', 'Fix bug', '--repo', '/test/repo', '--priority', 'high', '--budget', '150'])
    def test_manager_add_parsing(self, mock_cmd_manager):
        """Test manager add command parsing."""
        mcl.main()
        mock_cmd_manager.assert_called_once()
        args = mock_cmd_manager.call_args[0][0]
        assert args.manager_command == 'add'
        assert args.task == 'Fix bug'
        assert args.repo == '/test/repo'
        assert args.priority == 'high'
        assert args.budget == 150
    
    @patch('mcl.cmd_manager')
    @patch('sys.argv', ['mcl', 'manager', 'status'])
    def test_manager_status_parsing(self, mock_cmd_manager):
        """Test manager status command parsing."""
        mcl.main()
        mock_cmd_manager.assert_called_once()
        args = mock_cmd_manager.call_args[0][0]
        assert args.manager_command == 'status'


class TestManagerErrorHandling:
    """Test error handling in manager functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager_dir = Path(self.temp_dir) / "manager"
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('sqlite3.connect', side_effect=sqlite3.OperationalError("Database locked"))
    def test_manager_daemon_database_error(self, mock_connect):
        """Test manager daemon handling database errors."""
        with pytest.raises(sqlite3.OperationalError):
            mcl.ManagerDaemon(self.manager_dir)
    
    @patch('pathlib.Path.mkdir', side_effect=PermissionError("Permission denied"))
    def test_manager_daemon_permission_error(self, mock_mkdir):
        """Test manager daemon handling permission errors."""
        with pytest.raises(PermissionError):
            mcl.ManagerDaemon(self.manager_dir)
    
    def test_spawn_agent_invalid_inputs(self):
        """Test agent spawning with invalid inputs."""
        daemon = mcl.ManagerDaemon(self.manager_dir)
        
        # Test empty task description
        with pytest.raises((ValueError, sqlite3.IntegrityError)):
            daemon.spawn_agent("", "/repo/path")
        
        # Test None task description  
        with pytest.raises((TypeError, sqlite3.IntegrityError)):
            daemon.spawn_agent(None, "/repo/path")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])