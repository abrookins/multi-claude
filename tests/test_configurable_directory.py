#!/usr/bin/env python3
"""Tests for configurable TASK_MEMORY.md directory functionality."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcl import get_task_memory_path, create_task_memory


class TestConfigurableDirectory(unittest.TestCase):
    """Test configurable TASK_MEMORY.md directory functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Store original environment to restore later
        self.original_env = os.environ.get("MULTI_CLAUDE_PREFIX_DIR")
        # Clear environment variable
        if "MULTI_CLAUDE_PREFIX_DIR" in os.environ:
            del os.environ["MULTI_CLAUDE_PREFIX_DIR"]

    def tearDown(self):
        """Clean up after tests."""
        # Restore original environment
        if self.original_env:
            os.environ["MULTI_CLAUDE_PREFIX_DIR"] = self.original_env
        elif "MULTI_CLAUDE_PREFIX_DIR" in os.environ:
            del os.environ["MULTI_CLAUDE_PREFIX_DIR"]

    def test_get_task_memory_path_default(self):
        """Test default behavior without environment variable."""
        result = get_task_memory_path("/tmp/test-repo")
        self.assertEqual(result, "/tmp/test-repo/TASK_MEMORY.md")

    def test_get_task_memory_path_relative_with_slash(self):
        """Test relative path with trailing slash."""
        os.environ["MULTI_CLAUDE_PREFIX_DIR"] = ".ai/"
        result = get_task_memory_path("/tmp/test-repo")
        self.assertEqual(result, "/tmp/test-repo/.ai/TASK_MEMORY.md")

    def test_get_task_memory_path_relative_without_slash(self):
        """Test relative path without trailing slash."""
        os.environ["MULTI_CLAUDE_PREFIX_DIR"] = ".ai"
        result = get_task_memory_path("/tmp/test-repo")
        self.assertEqual(result, "/tmp/test-repo/.ai/TASK_MEMORY.md")

    def test_get_task_memory_path_absolute(self):
        """Test absolute path configuration."""
        os.environ["MULTI_CLAUDE_PREFIX_DIR"] = "/tmp/custom-location"
        result = get_task_memory_path("/tmp/test-repo")
        self.assertEqual(result, "/tmp/custom-location/TASK_MEMORY.md")

    def test_get_task_memory_path_creates_directory(self):
        """Test that directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_repo = os.path.join(temp_dir, "test-repo")
            os.makedirs(test_repo)
            
            os.environ["MULTI_CLAUDE_PREFIX_DIR"] = ".ai"
            result = get_task_memory_path(test_repo)
            
            expected_path = os.path.join(test_repo, ".ai", "TASK_MEMORY.md")
            self.assertEqual(result, expected_path)
            
            # Check that the .ai directory was created
            ai_dir = os.path.join(test_repo, ".ai")
            self.assertTrue(os.path.exists(ai_dir))
            self.assertTrue(os.path.isdir(ai_dir))

    def test_get_task_memory_path_absolute_creates_directory(self):
        """Test that absolute path directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_location = os.path.join(temp_dir, "custom-memory")
            
            os.environ["MULTI_CLAUDE_PREFIX_DIR"] = custom_location
            result = get_task_memory_path("/some/repo/path")
            
            expected_path = os.path.join(custom_location, "TASK_MEMORY.md")
            self.assertEqual(result, expected_path)
            
            # Check that the custom directory was created
            self.assertTrue(os.path.exists(custom_location))
            self.assertTrue(os.path.isdir(custom_location))

    def test_create_task_memory_uses_configurable_path(self):
        """Test that create_task_memory function uses configurable path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_repo = os.path.join(temp_dir, "test-repo")
            os.makedirs(test_repo)
            
            os.environ["MULTI_CLAUDE_PREFIX_DIR"] = ".ai"
            
            # Create task memory file
            result = create_task_memory("Test requirements", test_repo, "feature/test")
            
            expected_path = os.path.join(test_repo, ".ai", "TASK_MEMORY.md")
            self.assertEqual(result, expected_path)
            
            # Verify file exists and has content
            self.assertTrue(os.path.exists(expected_path))
            with open(expected_path, "r") as f:
                content = f.read()
            
            self.assertIn("# Task Memory", content)
            self.assertIn("Test requirements", content)
            self.assertIn("feature/test", content)

    def test_create_task_memory_absolute_path(self):
        """Test create_task_memory with absolute path configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_repo = os.path.join(temp_dir, "test-repo")
            custom_location = os.path.join(temp_dir, "custom-memory")
            os.makedirs(test_repo)
            
            os.environ["MULTI_CLAUDE_PREFIX_DIR"] = custom_location
            
            # Create task memory file
            result = create_task_memory("Test requirements", test_repo, "feature/test")
            
            expected_path = os.path.join(custom_location, "TASK_MEMORY.md")
            self.assertEqual(result, expected_path)
            
            # Verify file exists and has content
            self.assertTrue(os.path.exists(expected_path))
            with open(expected_path, "r") as f:
                content = f.read()
            
            self.assertIn("# Task Memory", content)
            self.assertIn("Test requirements", content)

    def test_empty_prefix_dir_environment_variable(self):
        """Test behavior with empty environment variable."""
        os.environ["MULTI_CLAUDE_PREFIX_DIR"] = ""
        result = get_task_memory_path("/tmp/test-repo")
        # Empty string should be treated as "not set"
        self.assertEqual(result, "/tmp/test-repo/TASK_MEMORY.md")

    def test_whitespace_only_prefix_dir(self):
        """Test behavior with whitespace-only environment variable."""
        os.environ["MULTI_CLAUDE_PREFIX_DIR"] = "   "
        result = get_task_memory_path("/tmp/test-repo")
        # Whitespace should be preserved and create a directory named "   "
        self.assertEqual(result, "/tmp/test-repo/   /TASK_MEMORY.md")


class TestConfigurableDirectoryIntegration(unittest.TestCase):
    """Integration tests for configurable directory functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.original_env = os.environ.get("MULTI_CLAUDE_PREFIX_DIR")
        if "MULTI_CLAUDE_PREFIX_DIR" in os.environ:
            del os.environ["MULTI_CLAUDE_PREFIX_DIR"]

    def tearDown(self):
        """Clean up after tests."""
        if self.original_env:
            os.environ["MULTI_CLAUDE_PREFIX_DIR"] = self.original_env
        elif "MULTI_CLAUDE_PREFIX_DIR" in os.environ:
            del os.environ["MULTI_CLAUDE_PREFIX_DIR"]

    def test_manager_spawn_agent_uses_configurable_path(self):
        """Test that manager daemon spawn_agent uses configurable path."""
        # This test would require more complex setup to test the manager functionality
        # For now, we'll just verify that the get_task_memory_path function is called correctly
        pass  # Placeholder for future implementation


if __name__ == "__main__":
    unittest.main()