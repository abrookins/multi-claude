"""Tests for the agent abstraction layer."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

from agents import (
    AgentConfig,
    CodingAgent,
    ClaudeAgent,
    AuggieAgent,
    AgentFactory
)


class TestAgentConfig:
    """Test AgentConfig dataclass."""
    
    def test_agent_config_creation(self):
        """Test creating an agent configuration."""
        config = AgentConfig(
            agent_id="test123",
            task_description="Test task",
            repo_path="/path/to/repo",
            agent_dir=Path("/path/to/agent"),
            priority="high",
            budget=200
        )
        
        assert config.agent_id == "test123"
        assert config.task_description == "Test task"
        assert config.repo_path == "/path/to/repo"
        assert config.priority == "high"
        assert config.budget == 200
    
    def test_agent_config_defaults(self):
        """Test agent configuration with default values."""
        config = AgentConfig(
            agent_id="test123",
            task_description="Test task",
            repo_path="/path/to/repo",
            agent_dir=Path("/path/to/agent")
        )
        
        assert config.priority == "normal"
        assert config.budget == 100
        assert config.additional_instructions is None


class TestClaudeAgent:
    """Test Claude agent implementation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = AgentConfig(
            agent_id="claude123",
            task_description="Implement feature X",
            repo_path="/path/to/repo",
            agent_dir=Path("/tmp/test_agent")
        )
        self.agent = ClaudeAgent(self.config)
    
    def test_get_command_name(self):
        """Test getting Claude command name."""
        assert self.agent.get_command_name() == "claude"
    
    @patch('subprocess.run')
    def test_is_available_true(self, mock_run):
        """Test checking if Claude is available (installed)."""
        mock_run.return_value = Mock(returncode=0)
        assert self.agent.is_available() is True
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_is_available_false(self, mock_run):
        """Test checking if Claude is not available."""
        mock_run.return_value = Mock(returncode=1)
        assert self.agent.is_available() is False
    
    def test_build_initial_prompt_new_task(self):
        """Test building initial prompt for new task."""
        prompt = self.agent.build_initial_prompt(is_continuation=False)
        
        assert "new task workspace" in prompt
        assert "TASK_MEMORY.md" in prompt
        assert "Implement feature X" in prompt
        assert "Let's get started!" in prompt
    
    def test_build_initial_prompt_continuation(self):
        """Test building initial prompt for continuing work."""
        prompt = self.agent.build_initial_prompt(is_continuation=True)
        
        assert "continuing work" in prompt
        assert "previous work" in prompt
        assert "Implement feature X" in prompt
        assert "continue working" in prompt
    
    def test_build_initial_prompt_with_instructions(self):
        """Test building prompt with additional instructions."""
        self.config.additional_instructions = "Use TypeScript"
        agent = ClaudeAgent(self.config)
        prompt = agent.build_initial_prompt(is_continuation=False)
        
        assert "Use TypeScript" in prompt
        assert "Additional Instructions" in prompt
    
    @patch('os.chdir')
    @patch('subprocess.run')
    @patch.object(ClaudeAgent, 'is_available', return_value=True)
    def test_spawn_success(self, mock_available, mock_run, mock_chdir):
        """Test successfully spawning Claude agent."""
        mock_run.return_value = Mock(returncode=0)
        
        result = self.agent.spawn()
        
        assert result is True
        mock_chdir.assert_called_once_with(self.config.repo_path)
        mock_run.assert_called_once()
        
        # Check that claude command was called
        call_args = mock_run.call_args
        assert call_args[0][0][0] == "claude"
    
    @patch.object(ClaudeAgent, 'is_available', return_value=False)
    def test_spawn_not_available(self, mock_available):
        """Test spawning when Claude is not available."""
        result = self.agent.spawn()
        
        assert result is False
    
    @patch('os.chdir')
    @patch('subprocess.run')
    @patch.object(ClaudeAgent, 'is_available', return_value=True)
    def test_spawn_subprocess_error(self, mock_available, mock_run, mock_chdir):
        """Test spawning with subprocess error."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "claude")
        
        result = self.agent.spawn()
        
        assert result is False


class TestAuggieAgent:
    """Test Auggie agent implementation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = AgentConfig(
            agent_id="auggie123",
            task_description="Fix bug Y",
            repo_path="/path/to/repo",
            agent_dir=Path("/tmp/test_agent")
        )
        self.agent = AuggieAgent(self.config)
    
    def test_get_command_name(self):
        """Test getting Auggie command name."""
        assert self.agent.get_command_name() == "auggie"
    
    @patch('subprocess.run')
    def test_is_available_true(self, mock_run):
        """Test checking if Auggie is available."""
        mock_run.return_value = Mock(returncode=0)
        assert self.agent.is_available() is True
    
    @patch('subprocess.run')
    def test_is_available_false(self, mock_run):
        """Test checking if Auggie is not available."""
        mock_run.return_value = Mock(returncode=1)
        assert self.agent.is_available() is False
    
    def test_build_initial_prompt(self):
        """Test building initial prompt for Auggie."""
        prompt = self.agent.build_initial_prompt(is_continuation=False)
        
        assert "new task workspace" in prompt
        assert "Fix bug Y" in prompt
    
    @patch('os.chdir')
    @patch('subprocess.run')
    @patch.object(AuggieAgent, 'is_available', return_value=True)
    def test_spawn_success(self, mock_available, mock_run, mock_chdir):
        """Test successfully spawning Auggie agent."""
        mock_run.return_value = Mock(returncode=0)
        
        result = self.agent.spawn()
        
        assert result is True
        mock_chdir.assert_called_once_with(self.config.repo_path)
        
        # Check that auggie command was called
        call_args = mock_run.call_args
        assert call_args[0][0][0] == "auggie"


class TestAgentFactory:
    """Test AgentFactory."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = AgentConfig(
            agent_id="test123",
            task_description="Test task",
            repo_path="/path/to/repo",
            agent_dir=Path("/tmp/test_agent")
        )
    
    def test_create_claude_agent(self):
        """Test creating a Claude agent."""
        agent = AgentFactory.create_agent("claude", self.config)
        
        assert isinstance(agent, ClaudeAgent)
        assert agent.config == self.config
    
    def test_create_auggie_agent(self):
        """Test creating an Auggie agent."""
        agent = AgentFactory.create_agent("auggie", self.config)
        
        assert isinstance(agent, AuggieAgent)
        assert agent.config == self.config
    
    def test_create_agent_case_insensitive(self):
        """Test that agent type is case-insensitive."""
        agent1 = AgentFactory.create_agent("CLAUDE", self.config)
        agent2 = AgentFactory.create_agent("Claude", self.config)
        
        assert isinstance(agent1, ClaudeAgent)
        assert isinstance(agent2, ClaudeAgent)
    
    def test_create_unknown_agent(self):
        """Test creating an unknown agent type."""
        with pytest.raises(ValueError) as exc_info:
            AgentFactory.create_agent("unknown", self.config)
        
        assert "Unknown agent type" in str(exc_info.value)
        assert "unknown" in str(exc_info.value)
    
    def test_get_available_agents(self):
        """Test getting list of available agents."""
        agents = AgentFactory.get_available_agents()
        
        assert "claude" in agents
        assert "auggie" in agents
        assert len(agents) >= 2
    
    def test_register_custom_agent(self):
        """Test registering a custom agent type."""
        class CustomAgent(CodingAgent):
            def spawn(self):
                return True
            
            def is_available(self):
                return True
            
            def get_command_name(self):
                return "custom"
            
            def build_initial_prompt(self, is_continuation=False):
                return "Custom prompt"
        
        AgentFactory.register_agent("custom", CustomAgent)
        
        assert "custom" in AgentFactory.get_available_agents()
        
        agent = AgentFactory.create_agent("custom", self.config)
        assert isinstance(agent, CustomAgent)


class TestTaskMemoryCreation:
    """Test task memory file creation."""

    def setup_method(self):
        """Set up test fixtures."""
        import tempfile
        self.temp_dir = Path(tempfile.mkdtemp())

        self.config = AgentConfig(
            agent_id="test123",
            task_description="Test task",
            repo_path="/path/to/repo",
            agent_dir=self.temp_dir
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_create_task_memory(self):
        """Test creating task memory file."""
        agent = ClaudeAgent(self.config)
        timestamp = "2024-01-01 12:00:00"

        task_memory_path = agent.create_task_memory(timestamp)

        assert task_memory_path.exists()
        assert task_memory_path.name == "TASK_MEMORY.md"

        content = task_memory_path.read_text()
        assert "test123" in content
        assert "Test task" in content
        assert timestamp in content
        assert "ClaudeAgent" in content

    def test_create_task_memory_with_priority_and_budget(self):
        """Test task memory includes priority and budget."""
        config = AgentConfig(
            agent_id="test456",
            task_description="High priority task",
            repo_path="/path/to/repo",
            agent_dir=self.temp_dir,
            priority="high",
            budget=500
        )
        agent = AuggieAgent(config)
        timestamp = "2024-01-01 12:00:00"

        task_memory_path = agent.create_task_memory(timestamp)
        content = task_memory_path.read_text()

        assert "high" in content
        assert "500" in content
        assert "AuggieAgent" in content


class TestAgentExceptionHandling:
    """Test exception handling in agents."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = AgentConfig(
            agent_id="test123",
            task_description="Test task",
            repo_path="/path/to/repo",
            agent_dir=Path("/tmp/test_agent")
        )

    @patch('subprocess.run')
    def test_claude_is_available_exception(self, mock_run):
        """Test Claude is_available handles exceptions."""
        mock_run.side_effect = Exception("Unexpected error")
        agent = ClaudeAgent(self.config)

        assert agent.is_available() is False

    @patch('subprocess.run')
    def test_auggie_is_available_exception(self, mock_run):
        """Test Auggie is_available handles exceptions."""
        mock_run.side_effect = Exception("Unexpected error")
        agent = AuggieAgent(self.config)

        assert agent.is_available() is False

    @patch('os.chdir')
    @patch('subprocess.run')
    @patch.object(ClaudeAgent, 'is_available', return_value=True)
    def test_claude_spawn_generic_exception(self, mock_available, mock_run, mock_chdir):
        """Test Claude spawn handles generic exceptions."""
        mock_run.side_effect = Exception("Unexpected error")
        agent = ClaudeAgent(self.config)

        result = agent.spawn()

        assert result is False

    @patch('os.chdir')
    @patch('subprocess.run')
    @patch.object(AuggieAgent, 'is_available', return_value=True)
    def test_auggie_spawn_subprocess_error(self, mock_available, mock_run, mock_chdir):
        """Test Auggie spawn handles subprocess errors."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "auggie")
        agent = AuggieAgent(self.config)

        result = agent.spawn()

        assert result is False

    @patch('os.chdir')
    @patch('subprocess.run')
    @patch.object(AuggieAgent, 'is_available', return_value=True)
    def test_auggie_spawn_generic_exception(self, mock_available, mock_run, mock_chdir):
        """Test Auggie spawn handles generic exceptions."""
        mock_run.side_effect = Exception("Unexpected error")
        agent = AuggieAgent(self.config)

        result = agent.spawn()

        assert result is False


class TestAuggieAgentPrompts:
    """Test Auggie agent prompt building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = AgentConfig(
            agent_id="auggie123",
            task_description="Fix bug Y",
            repo_path="/path/to/repo",
            agent_dir=Path("/tmp/test_agent")
        )
        self.agent = AuggieAgent(self.config)

    def test_build_initial_prompt_continuation(self):
        """Test building continuation prompt for Auggie."""
        prompt = self.agent.build_initial_prompt(is_continuation=True)

        assert "continuing work" in prompt
        assert "previous work" in prompt
        assert "Fix bug Y" in prompt
        assert "continue working" in prompt

    def test_build_initial_prompt_with_instructions(self):
        """Test building prompt with additional instructions for Auggie."""
        self.config.additional_instructions = "Use Python 3.12"
        agent = AuggieAgent(self.config)
        prompt = agent.build_initial_prompt(is_continuation=False)

        assert "Use Python 3.12" in prompt
        assert "Additional Instructions" in prompt

    def test_build_continuation_prompt_with_instructions(self):
        """Test building continuation prompt with additional instructions."""
        self.config.additional_instructions = "Focus on performance"
        agent = AuggieAgent(self.config)
        prompt = agent.build_initial_prompt(is_continuation=True)

        assert "Focus on performance" in prompt
        assert "Current Instructions" in prompt


class TestAgentFactoryEdgeCases:
    """Test edge cases in AgentFactory."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = AgentConfig(
            agent_id="test123",
            task_description="Test task",
            repo_path="/path/to/repo",
            agent_dir=Path("/tmp/test_agent")
        )

    def test_register_agent_case_insensitive(self):
        """Test that agent registration is case-insensitive."""
        class TestAgent(CodingAgent):
            def spawn(self):
                return True
            def is_available(self):
                return True
            def get_command_name(self):
                return "test"
            def build_initial_prompt(self, is_continuation=False):
                return "Test prompt"

        AgentFactory.register_agent("TestAgent", TestAgent)

        # Should be registered as lowercase
        assert "testagent" in AgentFactory.get_available_agents()

        # Should be able to create with any case
        agent = AgentFactory.create_agent("TESTAGENT", self.config)
        assert isinstance(agent, TestAgent)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

