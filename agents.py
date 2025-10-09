#!/usr/bin/env python3
"""
Agent abstraction layer for multi-agent support.

This module defines the interface for coding agents and provides
concrete implementations for different agent types (Claude, Auggie, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any
import subprocess
import os


@dataclass
class AgentConfig:
    """Configuration for an agent instance."""
    agent_id: str
    task_description: str
    repo_path: str
    agent_dir: Path
    priority: str = "normal"
    budget: int = 100
    additional_instructions: Optional[str] = None


class CodingAgent(ABC):
    """Abstract base class for coding agents."""
    
    def __init__(self, config: AgentConfig):
        """Initialize the agent with configuration."""
        self.config = config
    
    @abstractmethod
    def spawn(self) -> bool:
        """
        Spawn the agent process.
        
        Returns:
            bool: True if agent was spawned successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the agent CLI is available on the system.
        
        Returns:
            bool: True if agent CLI is installed and accessible.
        """
        pass
    
    @abstractmethod
    def get_command_name(self) -> str:
        """
        Get the CLI command name for this agent.
        
        Returns:
            str: The command name (e.g., 'claude', 'auggie').
        """
        pass
    
    @abstractmethod
    def build_initial_prompt(self, is_continuation: bool = False) -> str:
        """
        Build the initial prompt to send to the agent.
        
        Args:
            is_continuation: Whether this is continuing existing work.
            
        Returns:
            str: The formatted prompt for the agent.
        """
        pass
    
    def create_task_memory(self, timestamp: str) -> Path:
        """
        Create the TASK_MEMORY.md file for this agent.
        
        Args:
            timestamp: Formatted timestamp string.
            
        Returns:
            Path: Path to the created task memory file.
        """
        task_memory_content = f"""# Task Memory - Agent {self.config.agent_id}

**Created:** {timestamp}
**Priority:** {self.config.priority}
**Budget:** ${self.config.budget}
**Repository:** {self.config.repo_path}
**Agent Type:** {self.__class__.__name__}

## Task Description

{self.config.task_description}

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
        
        task_memory_path = self.config.agent_dir / "TASK_MEMORY.md"
        with open(task_memory_path, "w") as f:
            f.write(task_memory_content)
        
        return task_memory_path


class ClaudeAgent(CodingAgent):
    """Claude Code agent implementation."""
    
    def get_command_name(self) -> str:
        return "claude"
    
    def is_available(self) -> bool:
        """Check if Claude Code CLI is available."""
        try:
            result = subprocess.run(
                ["which", "claude"],
                capture_output=True,
                text=True,
                check=False
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def build_initial_prompt(self, is_continuation: bool = False) -> str:
        """Build the initial prompt for Claude Code."""
        if is_continuation:
            prompt = f"""I'm continuing work on an existing task. Here's the current state:

**Repository:** {Path(self.config.repo_path).name}
**Task Memory:** TASK_MEMORY.md (contains previous work and notes)

Please start by reading the TASK_MEMORY.md file to understand the requirements and previous work done.
"""
            if self.config.additional_instructions:
                prompt += f"\n**Current Instructions:** \n{self.config.additional_instructions}\n"
            
            prompt += f"""
**Requirements (refresher):**
{self.config.task_description}

Please review the current state and continue working on the task!"""
        else:
            prompt = f"""I've set up a new task workspace for you. Here's what's been prepared:

**Repository:** {Path(self.config.repo_path).name}
**Task Memory:** TASK_MEMORY.md (contains requirements and notes)

Please start by reading the TASK_MEMORY.md file to understand the requirements, then begin working on the task.
"""
            if self.config.additional_instructions:
                prompt += f"\n**Additional Instructions:** \n{self.config.additional_instructions}\n"
            
            prompt += f"""
**Requirements:**
{self.config.task_description}

Let's get started!"""
        
        return prompt
    
    def spawn(self) -> bool:
        """Spawn a Claude Code agent process."""
        if not self.is_available():
            print(f"Claude Code not found. Install it or start manually with: claude")
            return False
        
        try:
            # Change to the repo directory and start Claude Code
            initial_prompt = self.build_initial_prompt()
            os.chdir(self.config.repo_path)
            subprocess.run(["claude", initial_prompt], check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to start Claude Code: {e}")
            return False
        except Exception as e:
            print(f"Error spawning Claude agent: {e}")
            return False


class AuggieAgent(CodingAgent):
    """Auggie (Augment Code) agent implementation."""
    
    def get_command_name(self) -> str:
        return "auggie"
    
    def is_available(self) -> bool:
        """Check if Auggie CLI is available."""
        try:
            result = subprocess.run(
                ["which", "auggie"],
                capture_output=True,
                text=True,
                check=False
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def build_initial_prompt(self, is_continuation: bool = False) -> str:
        """Build the initial prompt for Auggie."""
        if is_continuation:
            prompt = f"""I'm continuing work on an existing task. Here's the current state:

**Repository:** {Path(self.config.repo_path).name}
**Task Memory:** TASK_MEMORY.md (contains previous work and notes)

Please start by reading the TASK_MEMORY.md file to understand the requirements and previous work done.
"""
            if self.config.additional_instructions:
                prompt += f"\n**Current Instructions:** \n{self.config.additional_instructions}\n"
            
            prompt += f"""
**Requirements (refresher):**
{self.config.task_description}

Please review the current state and continue working on the task!"""
        else:
            prompt = f"""I've set up a new task workspace for you. Here's what's been prepared:

**Repository:** {Path(self.config.repo_path).name}
**Task Memory:** TASK_MEMORY.md (contains requirements and notes)

Please start by reading the TASK_MEMORY.md file to understand the requirements, then begin working on the task.
"""
            if self.config.additional_instructions:
                prompt += f"\n**Additional Instructions:** \n{self.config.additional_instructions}\n"
            
            prompt += f"""
**Requirements:**
{self.config.task_description}

Let's get started!"""
        
        return prompt
    
    def spawn(self) -> bool:
        """Spawn an Auggie agent process."""
        if not self.is_available():
            print(f"Auggie not found. Install it or start manually with: auggie")
            return False
        
        try:
            # Change to the repo directory and start Auggie
            initial_prompt = self.build_initial_prompt()
            os.chdir(self.config.repo_path)
            # Auggie uses similar interface to Claude
            subprocess.run(["auggie", initial_prompt], check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to start Auggie: {e}")
            return False
        except Exception as e:
            print(f"Error spawning Auggie agent: {e}")
            return False


class AgentFactory:
    """Factory for creating agent instances."""
    
    _agents = {
        "claude": ClaudeAgent,
        "auggie": AuggieAgent,
    }
    
    @classmethod
    def create_agent(cls, agent_type: str, config: AgentConfig) -> CodingAgent:
        """
        Create an agent instance of the specified type.
        
        Args:
            agent_type: Type of agent to create ('claude', 'auggie', etc.).
            config: Agent configuration.
            
        Returns:
            CodingAgent: Instance of the requested agent type.
            
        Raises:
            ValueError: If agent_type is not supported.
        """
        agent_type = agent_type.lower()
        if agent_type not in cls._agents:
            available = ", ".join(cls._agents.keys())
            raise ValueError(f"Unknown agent type: {agent_type}. Available: {available}")
        
        agent_class = cls._agents[agent_type]
        return agent_class(config)
    
    @classmethod
    def get_available_agents(cls) -> list[str]:
        """
        Get list of available agent types.
        
        Returns:
            list[str]: List of agent type names.
        """
        return list(cls._agents.keys())
    
    @classmethod
    def register_agent(cls, name: str, agent_class: type[CodingAgent]):
        """
        Register a new agent type.
        
        Args:
            name: Name for the agent type.
            agent_class: Agent class to register.
        """
        cls._agents[name.lower()] = agent_class

