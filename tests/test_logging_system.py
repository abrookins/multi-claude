"""
Tests for the interaction logging system.

Tests cover:
- Logging system initialization
- Interaction log recording
- Log retrieval and filtering
- Session management
- Search functionality
- Export capabilities
- CLI command integration
"""

import pytest
import tempfile
import sqlite3
import json
import time
from unittest.mock import Mock, patch
from pathlib import Path

import mcl


class TestInteractionLogging:
    """Test interaction logging functionality."""
    
    def setup_method(self):
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager_dir = Path(self.temp_dir) / "manager"
        self.daemon = mcl.ManagerDaemon(self.manager_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_interaction_logs_table_creation(self):
        """Test that interaction_logs table is created with correct schema."""
        conn = sqlite3.connect(self.daemon.db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='interaction_logs'")
        assert cursor.fetchone() is not None
        
        # Check table schema
        cursor = conn.execute("PRAGMA table_info(interaction_logs)")
        columns = [row[1] for row in cursor.fetchall()]
        expected_columns = ['id', 'agent_id', 'session_id', 'interaction_type', 'direction', 'content', 'metadata', 'timestamp']
        for col in expected_columns:
            assert col in columns
        
        conn.close()
    
    def test_log_interaction(self):
        """Test logging basic interactions."""
        # First create an agent so the JOIN works
        agent_id, session_id = self.daemon.spawn_agent("Test task", "/test/repo")
        
        self.daemon.log_interaction(
            agent_id=agent_id,
            session_id=session_id,
            interaction_type="agent_request",
            direction="agent_to_manager",
            content="Test request content",
            metadata={"tool": "read", "file": "test.py"}
        )
        
        # Verify log was recorded (should be 2: spawn event + our log)
        logs = self.daemon.get_agent_logs(agent_id=agent_id)
        assert len(logs) == 2
        
        # Find our test log (not the spawn event)
        test_log = None
        for log in logs:
            if log[4] == "agent_request":  # interaction_type
                test_log = log
                break
        
        assert test_log is not None
        assert test_log[1] == agent_id  # agent_id
        assert test_log[4] == "agent_request"  # interaction_type
        assert test_log[5] == "agent_to_manager"  # direction
        assert test_log[6] == "Test request content"  # content
        
        metadata = json.loads(test_log[7])
        assert metadata["tool"] == "read"
        assert metadata["file"] == "test.py"
    
    def test_get_agent_logs_filtering(self):
        """Test filtering logs by various criteria."""
        # Create an agent first
        agent_id, session_id = self.daemon.spawn_agent("Test filtering task", "/test/repo")
        
        # Create test logs
        test_logs = [
            ("agent_request", "agent_to_manager", "Request 1", {"sequence": 1}),
            ("manager_response", "manager_to_agent", "Response 1", {"decision": "approve"}),
            ("agent_output", "agent_to_manager", "Output 1", {"status": "completed"}),
            ("system_event", "system", "System event", {"event": "startup"})
        ]
        
        for interaction_type, direction, content, metadata in test_logs:
            self.daemon.log_interaction(agent_id, session_id, interaction_type, direction, content, metadata)
        
        # Test filtering by interaction type
        agent_requests = self.daemon.get_agent_logs(agent_id=agent_id, interaction_type="agent_request")
        assert len(agent_requests) == 1
        assert agent_requests[0][4] == "agent_request"
        
        manager_responses = self.daemon.get_agent_logs(agent_id=agent_id, interaction_type="manager_response")
        assert len(manager_responses) == 1
        assert manager_responses[0][4] == "manager_response"
        
        # Test limit
        limited_logs = self.daemon.get_agent_logs(agent_id=agent_id, limit=2)
        assert len(limited_logs) == 2
        
        # Test no filters (all logs - should include spawn event + 4 test logs = 5)
        all_logs = self.daemon.get_agent_logs(agent_id=agent_id)
        assert len(all_logs) == 5
    
    def test_get_agent_sessions(self):
        """Test session tracking functionality."""
        # Create an agent first
        agent_id, spawn_session_id = self.daemon.spawn_agent("Test sessions task", "/test/repo")
        
        # Create logs in different sessions
        sessions = ["session_1", "session_2", "session_3"]
        for i, session_id in enumerate(sessions):
            # Create multiple interactions per session
            for j in range(i + 1):  # session_1: 1 interaction, session_2: 2 interactions, etc.
                self.daemon.log_interaction(
                    agent_id=agent_id,
                    session_id=session_id,
                    interaction_type="agent_request",
                    direction="agent_to_manager",
                    content=f"Request {i}-{j}",
                    metadata={"session": session_id, "sequence": j}
                )
                # Small delay to ensure different timestamps
                time.sleep(0.01)
        
        # Get sessions
        sessions_data = self.daemon.get_agent_sessions(agent_id)
        assert len(sessions_data) == 4  # 3 test sessions + 1 spawn session
        
        # Check session data structure - include spawn session
        all_sessions = sessions + [spawn_session_id]
        for session_data in sessions_data:
            session_id, start_time, end_time, interaction_count = session_data
            assert session_id in all_sessions
            assert start_time is not None
            assert end_time is not None
            assert interaction_count > 0
        
        # Verify interaction counts
        session_counts = {s[0]: s[3] for s in sessions_data}
        assert session_counts["session_1"] == 1
        assert session_counts["session_2"] == 2
        assert session_counts["session_3"] == 3
    
    def test_search_logs(self):
        """Test log search functionality."""
        # Create an agent first
        agent_id, session_id = self.daemon.spawn_agent("Test search task", "/test/repo")
        
        # Create logs with searchable content
        search_logs = [
            ("Found authentication function", {"tool": "grep"}),
            ("Reading config file", {"tool": "read"}),
            ("Editing authentication module", {"tool": "edit"}),
            ("Running authentication tests", {"tool": "bash"}),
            ("System startup complete", {"tool": "system"})
        ]
        
        for content, metadata in search_logs:
            self.daemon.log_interaction(
                agent_id=agent_id,
                session_id=session_id,
                interaction_type="agent_request",
                direction="agent_to_manager",
                content=content,
                metadata=metadata
            )
        
        # Search for "authentication"
        auth_logs = self.daemon.search_logs("authentication")
        assert len(auth_logs) == 3  # Should find 3 logs containing "authentication"
        
        for log in auth_logs:
            content = log[6]  # content field
            assert "authentication" in content.lower()
        
        # Search with agent filter
        agent_auth_logs = self.daemon.search_logs("authentication", agent_id=agent_id)
        assert len(agent_auth_logs) == 3
        
        # Search for specific term
        config_logs = self.daemon.search_logs("config")
        assert len(config_logs) == 1
        assert "config file" in config_logs[0][6]
        
        # Search with limit
        limited_search = self.daemon.search_logs("auth", limit=2)
        assert len(limited_search) <= 2
    
    def test_export_logs_json(self):
        """Test exporting logs in JSON format."""
        # Create an agent first
        agent_id, session_id = self.daemon.spawn_agent("Test export JSON task", "/test/repo")
        
        # Create test logs
        self.daemon.log_interaction(
            agent_id=agent_id,
            session_id=session_id,
            interaction_type="agent_request",
            direction="agent_to_manager",
            content="Test request",
            metadata={"tool": "read", "priority": "high"}
        )
        
        # Export as JSON
        json_export = self.daemon.export_logs(agent_id, format="json")
        parsed_json = json.loads(json_export)
        
        assert isinstance(parsed_json, list)
        assert len(parsed_json) == 2  # spawn event + our test log
        
        # Find our test log (not the spawn event)
        test_log = None
        for log in parsed_json:
            if log["interaction_type"] == "agent_request":
                test_log = log
                break
        
        assert test_log is not None
        assert test_log["agent_id"] == agent_id
        assert test_log["session_id"] == session_id
        assert test_log["interaction_type"] == "agent_request"
        assert test_log["direction"] == "agent_to_manager"
        assert test_log["content"] == "Test request"
        assert test_log["metadata"]["tool"] == "read"
        assert test_log["metadata"]["priority"] == "high"
    
    def test_export_logs_text(self):
        """Test exporting logs in text format."""
        # First create an agent so the JOIN works
        agent_id, session_id = self.daemon.spawn_agent("Test export text task", "/test/repo")
        
        # Create test logs with different types
        interactions = [
            ("agent_request", "agent_to_manager", "Agent requests file read"),
            ("manager_response", "manager_to_agent", "Manager approves request"),
            ("agent_output", "agent_to_manager", "File content retrieved")
        ]
        
        for interaction_type, direction, content in interactions:
            self.daemon.log_interaction(
                agent_id=agent_id,
                session_id=session_id,
                interaction_type=interaction_type,
                direction=direction,
                content=content,
                metadata={"sequence": len(interactions)}
            )
        
        # Export as text
        text_export = self.daemon.export_logs(agent_id, format="text")
        
        # Check text format contains expected elements
        assert f"SESSION {session_id}" in text_export
        assert "🤖→🧠" in text_export  # agent_to_manager indicator
        assert "🧠→🤖" in text_export  # manager_to_agent indicator
        assert "Agent requests file read" in text_export
        assert "Manager approves request" in text_export
        assert "File content retrieved" in text_export
        
        # Check metadata formatting
        assert "📋" in text_export  # metadata indicator
    
    def test_export_logs_invalid_format(self):
        """Test export with invalid format raises error."""
        # Create an agent first (even though we're testing error case)
        agent_id, _ = self.daemon.spawn_agent("Test invalid format task", "/test/repo")
        
        with pytest.raises(ValueError, match="Unsupported format"):
            self.daemon.export_logs(agent_id, format="invalid")
    
    def test_agent_spawn_logging(self):
        """Test that agent spawning creates initial log entry."""
        agent_id, session_id = self.daemon.spawn_agent(
            task_description="Test logging on spawn",
            repo_path="/test/repo",
            priority="high",
            budget=150
        )
        
        # Check that spawn event was logged
        logs = self.daemon.get_agent_logs(agent_id=agent_id)
        assert len(logs) == 1
        
        log = logs[0]
        assert log[4] == "system_event"  # interaction_type
        assert log[5] == "system"  # direction
        assert "Agent spawned for task" in log[6]  # content
        
        # Check metadata
        metadata = json.loads(log[7])
        assert metadata["repo_path"] == "/test/repo"
        assert metadata["priority"] == "high"
        assert metadata["budget"] == 150
    
    def test_simulate_agent_interaction(self):
        """Test the simulation functionality."""
        agent_id, session_id = self.daemon.spawn_agent("Test simulation", "/test/repo")
        
        # Define test requests
        tool_requests = [
            {"tool": "read", "file_path": "test.py"},
            {"tool": "edit", "file_path": "test.py", "content": "new content"}
        ]
        
        # Run simulation
        sim_session = "sim_test_123"
        self.daemon.simulate_agent_interaction(agent_id, sim_session, tool_requests)
        
        # Check simulation logs
        sim_logs = self.daemon.get_agent_logs(agent_id=agent_id, session_id=sim_session)
        
        # Should have logs for each request: agent_request + manager_response + agent_output
        # 2 requests * 3 interactions each = 6 logs
        assert len(sim_logs) >= 4  # At least agent_request + manager_response for each
        
        # Check log types
        log_types = [log[4] for log in sim_logs]  # interaction_type
        assert "agent_request" in log_types
        assert "manager_response" in log_types
        assert "agent_output" in log_types
        
        # Check content contains tool information
        request_logs = [log for log in sim_logs if log[4] == "agent_request"]
        assert len(request_logs) == 2  # One for each tool request
        
        for log in request_logs:
            content = json.loads(log[6])  # content should be JSON
            assert "tool" in content


class TestLoggingCommands:
    """Test logging CLI commands."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager_dir = Path(self.temp_dir) / "manager"
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('mcl.get_manager_daemon')
    @patch('builtins.print')
    def test_cmd_manager_log_no_logs(self, mock_print, mock_get_daemon):
        """Test log command when no logs exist."""
        mock_daemon = Mock()
        mock_daemon.get_agent_logs.return_value = []
        mock_get_daemon.return_value = mock_daemon
        
        args = Mock()
        args.manager_command = "log"
        args.agent_id = "test_agent"
        
        mcl.cmd_manager(args)
        
        mock_print.assert_called_with("📭 No logs found for agent test_agent")
    
    @patch('mcl.get_manager_daemon')
    @patch('builtins.print')
    def test_cmd_manager_log_list_agents(self, mock_print, mock_get_daemon):
        """Test log command listing agents with logs."""
        mock_daemon = Mock()
        mock_daemon.db_path = ":memory:"
        
        # Mock database query result
        with patch('sqlite3.connect') as mock_connect:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = [
                ("agent1", "Task 1", 10, "2023-07-23 10:00:00", "2023-07-23 11:00:00"),
                ("agent2", "Task 2", 5, "2023-07-23 12:00:00", "2023-07-23 12:30:00")
            ]
            mock_conn.execute.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            mock_get_daemon.return_value = mock_daemon
            
            args = Mock()
            args.manager_command = "log"
            # Configure the Mock to behave like it doesn't have agent_id or search attributes
            args.agent_id = None
            args.search = None
            
            mcl.cmd_manager(args)
            
            # Check that agents list is displayed
            print_calls = [call.args[0] for call in mock_print.call_args_list if call.args]
            assert any("AGENTS WITH INTERACTION LOGS:" in call for call in print_calls)
    
    @patch('mcl.get_manager_daemon')
    @patch('builtins.print')
    def test_cmd_manager_log_search(self, mock_print, mock_get_daemon):
        """Test log command with search functionality."""
        mock_daemon = Mock()
        mock_daemon.search_logs.return_value = [
            (1, "agent1", "Task 1", "session1", "agent_request", "agent_to_manager", 
             "Search term found here", None, "2023-07-23 10:00:00")
        ]
        mock_get_daemon.return_value = mock_daemon
        
        args = Mock()
        args.manager_command = "log"
        args.search = "test search"
        args.limit = 50
        # Add missing attributes that cmd_manager checks for
        args.agent_id = None
        
        mcl.cmd_manager(args)
        
        mock_daemon.search_logs.assert_called_once_with(
            search_term="test search",
            agent_id=None,
            limit=50
        )
        
        # Check search results display
        print_calls = [call.args[0] for call in mock_print.call_args_list if call.args]
        assert any("SEARCH RESULTS FOR 'test search':" in call for call in print_calls)
    
    @patch('mcl.get_manager_daemon')
    @patch('builtins.print')
    def test_cmd_manager_sessions(self, mock_print, mock_get_daemon):
        """Test sessions command."""
        mock_daemon = Mock()
        mock_daemon.get_agent_sessions.return_value = [
            ("session_1", "2023-07-23 10:00:00", "2023-07-23 10:30:00", 15),
            ("session_2", "2023-07-23 11:00:00", "2023-07-23 11:15:00", 8)
        ]
        mock_get_daemon.return_value = mock_daemon
        
        args = Mock()
        args.manager_command = "sessions"
        args.agent_id = "test_agent"
        
        mcl.cmd_manager(args)
        
        mock_daemon.get_agent_sessions.assert_called_once_with("test_agent")
        
        # Check sessions display
        print_calls = [call.args[0] for call in mock_print.call_args_list if call.args]
        assert any("SESSIONS FOR AGENT test_agent:" in call for call in print_calls)
        assert any("session_1" in call for call in print_calls)
        assert any("session_2" in call for call in print_calls)
    
    @patch('mcl.get_manager_daemon')
    @patch('builtins.print')
    def test_cmd_manager_simulate(self, mock_print, mock_get_daemon):
        """Test simulate command."""
        mock_daemon = Mock()
        mock_get_daemon.return_value = mock_daemon
        
        args = Mock()
        args.manager_command = "simulate"
        args.agent_id = "test_agent"
        
        mcl.cmd_manager(args)
        
        mock_daemon.simulate_agent_interaction.assert_called_once()
        call_args = mock_daemon.simulate_agent_interaction.call_args
        assert call_args[0][0] == "test_agent"  # agent_id
        assert "sim_session_" in call_args[0][1]  # session_id
        assert len(call_args[0][2]) == 5  # 5 sample tool requests
    
    @patch('argparse.ArgumentParser.print_help')
    def test_cmd_manager_sessions_no_agent(self, mock_help):
        """Test sessions command with no agent shows help."""
        args = Mock()
        args.manager_command = "sessions"
        args.agent_id = None
        
        mcl.cmd_manager(args)
        
        mock_help.assert_called_once()
    
    @patch('argparse.ArgumentParser.print_help')
    def test_cmd_manager_simulate_no_agent(self, mock_help):
        """Test simulate command with no agent shows help."""
        args = Mock()
        args.manager_command = "simulate"
        args.agent_id = None
        
        mcl.cmd_manager(args)
        
        mock_help.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])