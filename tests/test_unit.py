"""
Unit tests for mcl.py script.

This test suite covers core functionality with proper mocking of external dependencies:
- Pure functions (string manipulation, validation)
- File system operations (with mocking)
- Git operations (with subprocess mocking)
- Network operations (with HTTP mocking)
- Command line parsing
- Error handling scenarios

All external dependencies (filesystem, subprocess, network) are mocked to ensure 
fast, reliable, isolated unit tests.
"""

import pytest
import tempfile
import shutil
import os
import json
from unittest.mock import Mock, patch, MagicMock, mock_open, call
from pathlib import Path
from io import StringIO
import subprocess

# Import the module under test
import mcl


class TestCoreFunctions:
    """Test pure functions with deterministic input/output."""
    
    def test_is_github_issue_url_valid_urls(self):
        """Test valid GitHub issue URLs."""
        valid_urls = [
            "https://github.com/user/repo/issues/123",
            "https://github.com/organization/project/issues/456",
            "https://github.com/user-name/repo-name/issues/1",
        ]
        for url in valid_urls:
            assert mcl.is_github_issue_url(url), f"Should be valid: {url}"
    
    def test_is_github_issue_url_invalid_urls(self):
        """Test invalid GitHub issue URLs."""
        invalid_urls = [
            "https://gitlab.com/user/repo/issues/123",
            "https://github.com/user/repo/pull/123",
            "https://github.com/user/repo",
            "not-a-url",
            "",
            "https://github.com/user/repo/issues/",
            "github.com/user/repo/issues/123",  # missing protocol
        ]
        for url in invalid_urls:
            assert not mcl.is_github_issue_url(url), f"Should be invalid: {url}"
    
    def test_is_github_issue_url_none_value(self):
        """Test GitHub issue URL with None value."""
        with pytest.raises(TypeError):
            mcl.is_github_issue_url(None)
    
    def test_is_git_url_valid_urls(self):
        """Test valid Git URLs."""
        valid_urls = [
            "https://github.com/user/repo.git",
            "http://github.com/user/repo",
            "git@github.com:user/repo.git",
            "ssh://git@github.com/user/repo.git",
        ]
        for url in valid_urls:
            assert mcl.is_git_url(url), f"Should be valid Git URL: {url}"
    
    def test_is_git_url_invalid_urls(self):
        """Test invalid Git URLs."""
        invalid_urls = [
            "/local/path",
            "not-a-url",
            "",
            "file:///path/to/repo",
        ]
        for url in invalid_urls:
            assert not mcl.is_git_url(url), f"Should be invalid Git URL: {url}"
    
    def test_generate_feature_summary(self):
        """Test feature summary generation."""
        test_cases = [
            ("Add authentication system", "authentication-system"),  # Removes "add " prefix
            ("Fix bug with user login", "bug-with-user-login"),  # Removes "fix " prefix, takes 4 words
            ("A very long feature description that should be truncated", "a-very-long-feature"),  # Takes first 4 words
            ("Feature with special chars!@#$%", "feature-with-special-chars"),  # Removes special chars
            ("", "task"),  # Empty string
            ("   spaces   around   ", "spaces-around"),  # Strips and normalizes
        ]
        for input_text, expected in test_cases:
            result = mcl.generate_feature_summary(input_text)
            assert result == expected, f"Input: '{input_text}' -> Expected: '{expected}', Got: '{result}'"
    
    def test_get_repo_name_from_urls(self):
        """Test repository name extraction from URLs."""
        with patch('mcl.is_local_path', return_value=False):
            test_cases = [
                ("https://github.com/user/repo.git", "repo"),
                ("https://github.com/user/repo", "repo"),
                ("git@github.com:user/repo.git", "repo"),
                ("ssh://git@github.com/user/repo.git", "repo"),
            ]
            for url, expected in test_cases:
                result = mcl.get_repo_name(url)
                assert result == expected, f"URL: '{url}' -> Expected: '{expected}', Got: '{result}'"
    
    @patch('mcl.is_local_path', return_value=True)
    def test_get_repo_name_from_local_path(self, mock_is_local):
        """Test repository name extraction from local paths."""
        test_cases = [
            ("/path/to/my-repo", "my-repo"),
            ("./local-repo", "local-repo"),
            ("/path/to/repo/", "repo"),
        ]
        for path, expected in test_cases:
            result = mcl.get_repo_name(path)
            assert result == expected, f"Path: '{path}' -> Expected: '{expected}', Got: '{result}'"
    
    def test_get_feature_repo_name(self):
        """Test combined repo name and feature summary."""
        with patch('mcl.is_local_path', return_value=False):
            result = mcl.get_feature_repo_name("https://github.com/user/myproject.git", "Add authentication")
            assert result == "myproject-authentication"  # "add " prefix is removed


class TestFileSystemOperations:
    """Test file system operations with proper mocking."""
    
    @patch('os.path.exists')
    @patch('os.path.isdir')
    def test_is_local_path(self, mock_isdir, mock_exists):
        """Test local path detection."""
        mock_exists.return_value = True
        mock_isdir.return_value = True
        
        assert mcl.is_local_path("/existing/directory")
        mock_exists.assert_called_with("/existing/directory")
        mock_isdir.assert_called_with("/existing/directory")
        
        mock_exists.return_value = False
        assert not mcl.is_local_path("/nonexistent/path")
    
    @patch('pathlib.Path.exists')
    def test_is_git_repo(self, mock_exists):
        """Test git repository detection."""
        mock_exists.return_value = True
        assert mcl.is_git_repo("/path/to/repo")
        
        mock_exists.return_value = False
        assert not mcl.is_git_repo("/path/to/non-repo")
    
    def test_get_unique_repo_path_no_conflict(self):
        """Test unique path generation when no conflict."""
        with patch.object(Path, 'exists', return_value=False):
            base_path = Path("/test/path")
            result = mcl.get_unique_repo_path(base_path)
            assert result == base_path
    
    def test_get_unique_repo_path_with_conflict(self):
        """Test unique path generation with conflicts."""
        def custom_exists(self):
            return str(self) in ["/test/path", "/test/path-1", "/test/path-2"]
        
        with patch.object(Path, 'exists', custom_exists):
            base_path = Path("/test/path")
            result = mcl.get_unique_repo_path(base_path)
            assert str(result) == "/test/path-3"
    
    @patch('os.path.isfile')
    def test_is_requirements_file(self, mock_isfile):
        """Test requirements file detection."""
        mock_isfile.return_value = True
        assert mcl.is_requirements_file("/path/to/requirements.txt")
        
        mock_isfile.return_value = False
        assert not mcl.is_requirements_file("/nonexistent/file.txt")
    
    @patch('builtins.open', new_callable=mock_open, read_data="Feature requirements content")
    @patch('os.path.exists', return_value=True)
    def test_read_requirements_file_success(self, mock_exists, mock_file):
        """Test successful requirements file reading."""
        result = mcl.read_requirements_file("/path/to/file.txt")
        assert result == "Feature requirements content"
        mock_file.assert_called_once_with("/path/to/file.txt", 'r', encoding='utf-8')
    
    @patch('builtins.open', side_effect=FileNotFoundError)
    @patch('os.path.exists', return_value=False)
    def test_read_requirements_file_not_found(self, mock_exists, mock_file):
        """Test requirements file reading when file doesn't exist."""
        result = mcl.read_requirements_file("/nonexistent/file.txt")
        assert result is None
    
    @patch('builtins.open', side_effect=PermissionError)
    @patch('os.path.exists', return_value=True)
    def test_read_requirements_file_permission_error(self, mock_exists, mock_file):
        """Test requirements file reading with permission error."""
        result = mcl.read_requirements_file("/restricted/file.txt")
        assert result is None


class TestGitOperations:
    """Test git operations with subprocess mocking."""
    
    @patch('subprocess.run')
    def test_run_command_success(self, mock_run):
        """Test successful command execution."""
        mock_run.return_value = Mock(returncode=0, stdout="command output", stderr="")
        
        result = mcl.run_command("git status")
        assert result == "command output"
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_run_command_failure(self, mock_run):
        """Test failed command execution."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error message")
        
        result = mcl.run_command("git invalid-command")
        assert result == ""  # Function returns empty string for failed commands
    
    @patch('subprocess.run', side_effect=subprocess.TimeoutExpired("cmd", 30))
    def test_run_command_timeout(self, mock_run):
        """Test command timeout - should raise exception since timeout not handled."""
        with pytest.raises(subprocess.TimeoutExpired):
            mcl.run_command("long-running-command")
    
    @patch('mcl.run_command')
    def test_create_git_worktree_success(self, mock_run_cmd):
        """Test successful git worktree creation."""
        # Mock successful git commands - need more return values for all the calls
        mock_run_cmd.side_effect = [
            "",  # git status --porcelain (no changes)
            "origin",  # git remote
            "",  # git fetch origin (success)
            "",  # git checkout main (success)
            "main",  # git branch --show-current
            "",  # git worktree add (success)
        ]
        
        result = mcl.create_git_worktree("/source/repo", "/dest/worktree", "feature/test")
        assert result is True
    
    @patch('mcl.run_command')
    @patch('mcl.copy_non_git_directory', return_value=True)
    def test_create_git_worktree_fallback(self, mock_copy, mock_run_cmd):
        """Test git worktree creation with fallback to copy."""
        # Mock failed worktree creation
        mock_run_cmd.side_effect = [
            "",  # git status --porcelain
            "origin",  # git remote
            None,  # git fetch origin
            None,  # git checkout main
            None,  # git worktree add fails (returns None)
        ]
        
        result = mcl.create_git_worktree("/source/repo", "/dest/worktree", "feature/test")
        assert result is True
        mock_copy.assert_called_once_with("/source/repo", "/dest/worktree", "feature/test")
    
    @patch('shutil.copytree')
    @patch('pathlib.Path.exists', return_value=False)
    @patch('mcl.is_git_repo', return_value=False)
    def test_copy_non_git_directory_non_git(self, mock_is_git, mock_exists, mock_copytree):
        """Test copying non-git directory."""
        result = mcl.copy_non_git_directory(Path("/source"), Path("/dest"), "branch")
        assert result is True
        mock_copytree.assert_called_once_with(Path("/source"), Path("/dest"))
    
    @patch('mcl.is_git_repo', return_value=True)
    @patch('mcl.create_git_worktree', return_value=True)
    @patch('mcl.get_unique_repo_path')
    def test_setup_local_repo_git_source(self, mock_unique_path, mock_create_worktree, mock_is_git):
        """Test setup with git repository source."""
        mock_unique_path.return_value = Path("/dest")
        
        result = mcl.setup_local_repo(Path("/git/repo"), Path("/dest"), "feature/branch")
        assert result is True
        mock_create_worktree.assert_called_once_with(Path("/git/repo"), Path("/dest"), "feature/branch")
    
    @patch('mcl.is_git_repo', return_value=False)
    @patch('mcl.copy_non_git_directory', return_value=True)
    @patch('mcl.get_unique_repo_path')
    def test_setup_local_repo_non_git_source(self, mock_unique_path, mock_copy, mock_is_git):
        """Test setup with non-git directory source."""
        mock_unique_path.return_value = Path("/dest")
        
        result = mcl.setup_local_repo(Path("/non/git"), Path("/dest"), "feature/branch")
        assert result is True
        mock_copy.assert_called_once_with(Path("/non/git"), Path("/dest"), "feature/branch")


class TestNetworkOperations:
    """Test network operations with HTTP mocking."""
    
    def test_fetch_github_issue_function_exists(self):
        """Test that fetch_github_issue function exists and is callable."""
        assert hasattr(mcl, 'fetch_github_issue')
        assert callable(mcl.fetch_github_issue)
    
    def test_github_issue_url_parsing(self):
        """Test GitHub issue URL parsing logic."""
        # Test that invalid URLs return None quickly
        assert mcl.fetch_github_issue("not-a-url") is None
        assert mcl.fetch_github_issue("https://gitlab.com/user/repo/issues/123") is None


class TestCommandLineInterface:
    """Test command line interface and argument parsing."""
    
    @patch('sys.argv', ['mcl', '--help'])
    def test_help_argument(self):
        """Test help argument parsing."""
        with pytest.raises(SystemExit):
            mcl.main()
    
    @patch('mcl.cmd_start')
    @patch('sys.argv', ['mcl', 'start', '--repo', 'https://github.com/user/repo', '--requirements', 'Add feature'])
    def test_start_command_parsing(self, mock_cmd_start):
        """Test start command argument parsing."""
        mcl.main()
        mock_cmd_start.assert_called_once()
        args = mock_cmd_start.call_args[0][0]
        assert args.repo == 'https://github.com/user/repo'
        assert args.requirements == 'Add feature'
    
    @patch('mcl.list_staged_directories')
    @patch('sys.argv', ['mcl', 'ls'])
    def test_list_command_parsing(self, mock_list):
        """Test list command parsing."""
        mcl.main()
        mock_list.assert_called_once()
    
    @patch('mcl.handle_cd_command')
    @patch('sys.argv', ['mcl', 'cd', '1'])
    def test_cd_command_parsing(self, mock_handle_cd):
        """Test cd command parsing."""
        mcl.main()
        mock_handle_cd.assert_called_once()


class TestUtilityFunctions:
    """Test utility and helper functions."""
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.join', return_value="/repo/path/TASK_MEMORY.md")
    def test_create_task_memory(self, mock_join, mock_file):
        """Test task memory file creation."""
        with patch('mcl.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2023-07-23 10:30:00"
            
            result = mcl.create_task_memory("Add authentication", "/repo/path", "feature/auth")
            
            assert result == "/repo/path/TASK_MEMORY.md"
            mock_file.assert_called_once_with("/repo/path/TASK_MEMORY.md", 'w')
            
            # Check that content was written
            written_content = ''.join(call.args[0] for call in mock_file().write.call_args_list)
            assert "Add authentication" in written_content
            assert "feature/auth" in written_content
            assert "2023-07-23 10:30:00" in written_content
    
    @patch('os.path.abspath', return_value="/path/to/mcl.py")
    def test_generate_shell_integration(self, mock_abspath):
        """Test shell integration code generation."""
        result = mcl.generate_shell_integration()
        
        assert "mcl_cd()" in result
        assert "/path/to/mcl.py" in result
        assert "bash" in result or "zsh" in result
    
    @patch('pathlib.Path.iterdir')
    @patch('pathlib.Path.exists', return_value=True)
    def test_list_staged_directories_with_tasks(self, mock_exists, mock_iterdir):
        """Test listing staged directories when tasks exist."""
        # Mock directory structure
        mock_dir1 = Mock()
        mock_dir1.is_dir.return_value = True
        mock_dir1.name = "task1-feature"
        mock_dir1.stat.return_value.st_mtime = 1627980600
        
        mock_dir2 = Mock()
        mock_dir2.is_dir.return_value = True
        mock_dir2.name = "task2-bugfix"
        mock_dir2.stat.return_value.st_mtime = 1627980700
        
        mock_iterdir.return_value = [mock_dir1, mock_dir2]
        
        with patch('mcl.HAS_RICH', False):  # Test without Rich
            result = mcl.list_staged_directories("/staging")
            
            assert len(result) == 2
            assert result[0]['name'] == "task2-bugfix"  # Should be sorted by time (newest first)
            assert result[1]['name'] == "task1-feature"
    
    @patch('pathlib.Path.exists', return_value=False)
    def test_list_staged_directories_no_staging_dir(self, mock_exists):
        """Test listing when staging directory doesn't exist."""
        with patch('mcl.HAS_RICH', False):
            mcl.list_staged_directories("/nonexistent")
            # Should not raise an exception, just print message


class TestErrorHandling:
    """Test error handling scenarios and edge cases."""
    
    def test_github_issue_url_with_none(self):
        """Test GitHub URL validation with None input."""
        with pytest.raises(TypeError):
            mcl.is_github_issue_url(None)
    
    @patch('builtins.open', side_effect=FileNotFoundError)
    @patch('os.path.exists', return_value=False)
    def test_read_requirements_file_not_found(self, mock_exists, mock_open):
        """Test reading non-existent requirements file."""
        result = mcl.read_requirements_file("/nonexistent/file.txt")
        assert result is None
    
    @patch('builtins.open', side_effect=PermissionError)
    @patch('os.path.exists', return_value=True)
    def test_read_requirements_file_permission_error(self, mock_exists, mock_open):
        """Test reading requirements file with permission error."""
        result = mcl.read_requirements_file("/restricted/file.txt")
        assert result is None
    
    @patch('subprocess.run', side_effect=Exception("Unexpected error"))
    def test_run_command_unexpected_error(self, mock_run):
        """Test command execution with unexpected error - should raise exception."""
        with pytest.raises(Exception):
            mcl.run_command("some-command")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])