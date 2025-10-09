"""
Additional tests to increase coverage to 90% for mcl.py

This test file focuses on covering previously untested code paths:
- Error handling branches
- Rich library fallback paths
- GitHub issue fetching
- cmd_start workflow
- Edge cases in various functions
"""

import pytest
import tempfile
import os
import json
from unittest.mock import Mock, patch, MagicMock, mock_open, call
from pathlib import Path
import subprocess

import mcl


class TestErrorHandlingPaths:
    """Test error handling code paths."""

    @patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'cmd', stderr='error'))
    def test_run_command_with_stderr(self, mock_run):
        """Test run_command error output display."""
        result = mcl.run_command("failing-command")
        assert result is None

    @patch('builtins.open', new_callable=mock_open, read_data="")
    def test_read_requirements_file_empty(self, mock_file):
        """Test reading empty requirements file."""
        result = mcl.read_requirements_file("/path/to/empty.txt")
        assert result == "No requirements specified"

    def test_generate_feature_summary_empty_words(self):
        """Test feature summary with no extractable words."""
        result = mcl.generate_feature_summary("!@#$%^&*()")
        assert result == "task"


class TestGitHubIssueFetching:
    """Test GitHub issue fetching functionality."""

    def test_fetch_github_issue_invalid_url(self):
        """Test fetching with invalid URL format."""
        result = mcl.fetch_github_issue("https://gitlab.com/user/repo/issues/1")
        assert result is None

    @patch('mcl.urlopen')
    @patch('os.getenv', return_value='fake_token')
    def test_fetch_github_issue_with_token(self, mock_getenv, mock_urlopen):
        """Test GitHub issue fetch with authentication token."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            'title': 'Test Issue',
            'body': 'Issue description',
            'labels': [{'name': 'bug'}, {'name': 'priority-high'}]
        }).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = mcl.fetch_github_issue("https://github.com/user/repo/issues/123")

        assert result is not None
        assert "Test Issue" in result
        assert "bug" in result
        assert "priority-high" in result

    @patch('mcl.urlopen')
    def test_fetch_github_issue_http_error(self, mock_urlopen):
        """Test GitHub issue fetch with HTTP error."""
        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = mcl.fetch_github_issue("https://github.com/user/repo/issues/999")
        assert result is None

    @patch('mcl.urlopen', side_effect=Exception("Network error"))
    def test_fetch_github_issue_unexpected_error(self, mock_urlopen):
        """Test GitHub issue fetch with unexpected error."""
        result = mcl.fetch_github_issue("https://github.com/user/repo/issues/123")
        assert result is None


class TestRichLibraryFallback:
    """Test code paths when Rich library is not available."""

    @patch('mcl.HAS_RICH', False)
    @patch('pathlib.Path.exists', return_value=False)
    def test_list_staged_directories_no_rich_no_dir(self, mock_exists):
        """Test listing without Rich when staging dir doesn't exist."""
        with patch('builtins.print') as mock_print:
            mcl.list_staged_directories("/nonexistent")
            mock_print.assert_any_call("Staging directory /nonexistent does not exist.")

    @patch('mcl.HAS_RICH', False)
    @patch('pathlib.Path.iterdir')
    @patch('pathlib.Path.exists', return_value=True)
    def test_list_staged_directories_no_rich_empty(self, mock_exists, mock_iterdir):
        """Test listing without Rich when no tasks exist."""
        mock_iterdir.return_value = []

        with patch('builtins.print') as mock_print:
            mcl.list_staged_directories("/staging")
            mock_print.assert_any_call("No tasks found.")


class TestHandleCdCommand:
    """Test handle_cd_command function."""

    @patch('pathlib.Path.exists', return_value=False)
    @patch('sys.exit')
    def test_handle_cd_no_staging_dir(self, mock_exit, mock_exists):
        """Test cd command when staging directory doesn't exist."""
        with patch('builtins.print'):
            mcl.handle_cd_command(None, "1")
            mock_exit.assert_called_once_with(1)

    @patch('pathlib.Path.iterdir')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('sys.exit')
    def test_handle_cd_no_tasks(self, mock_exit, mock_exists, mock_iterdir):
        """Test cd command when no tasks exist."""
        mock_iterdir.return_value = []

        with patch('builtins.print'):
            mcl.handle_cd_command("/staging", "1")
            # Called twice - once for empty check, once for invalid selection
            assert mock_exit.call_count == 2

    @patch('pathlib.Path.iterdir')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('sys.exit')
    def test_handle_cd_invalid_number(self, mock_exit, mock_exists, mock_iterdir):
        """Test cd command with invalid task number."""
        mock_dir = Mock()
        mock_dir.is_dir.return_value = True
        mock_dir.name = "task1"
        mock_dir.stat.return_value.st_mtime = 1627980600
        mock_iterdir.return_value = [mock_dir]

        with patch('builtins.print'):
            mcl.handle_cd_command("/staging", "99")
            mock_exit.assert_called_once_with(1)

    @patch('pathlib.Path.iterdir')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('sys.exit')
    def test_handle_cd_non_numeric(self, mock_exit, mock_exists, mock_iterdir):
        """Test cd command with non-numeric input."""
        mock_dir = Mock()
        mock_dir.is_dir.return_value = True
        mock_dir.name = "task1"
        mock_dir.stat.return_value.st_mtime = 1627980600
        mock_iterdir.return_value = [mock_dir]

        with patch('builtins.print'):
            mcl.handle_cd_command("/staging", "abc")
            mock_exit.assert_called_once_with(1)

    @patch('pathlib.Path.iterdir')
    @patch('pathlib.Path.exists', return_value=True)
    def test_handle_cd_valid_selection(self, mock_exists, mock_iterdir):
        """Test cd command with valid selection."""
        mock_dir = Mock()
        mock_dir.is_dir.return_value = True
        mock_dir.name = "task1"
        mock_dir.stat.return_value.st_mtime = 1627980600
        mock_iterdir.return_value = [mock_dir]

        with patch('builtins.print') as mock_print:
            mcl.handle_cd_command("/staging", "1")
            # Should print cd command with quoted path
            assert any('cd' in str(call) for call in mock_print.call_args_list)


class TestCleanupWorktree:
    """Test cleanup_worktree function."""

    @patch('pathlib.Path.exists', return_value=False)
    def test_cleanup_worktree_nonexistent_path(self, mock_exists):
        """Test cleanup when path doesn't exist."""
        result = mcl.cleanup_worktree(Path("/nonexistent"))
        assert result is True

    @patch('builtins.open', new_callable=mock_open, read_data="gitdir: /path/to/git/worktrees/feature")
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    @patch('mcl.is_git_repo', return_value=True)
    @patch('mcl.run_command', return_value="")
    def test_cleanup_worktree_success(self, mock_run_cmd, mock_is_git, mock_is_file, mock_exists, mock_file):
        """Test successful worktree cleanup."""
        repo_path = Path("/path/to/worktree")
        source_path = Path("/path/to/source")

        result = mcl.cleanup_worktree(repo_path, source_path)
        assert result is True
        mock_run_cmd.assert_called_once()

    @patch('builtins.open', new_callable=mock_open, read_data="gitdir: /path/to/git/worktrees/feature")
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    @patch('mcl.is_git_repo', return_value=True)
    @patch('mcl.run_command', return_value=None)
    @patch('shutil.rmtree')
    def test_cleanup_worktree_manual_removal(self, mock_rmtree, mock_run_cmd, mock_is_git,
                                             mock_is_file, mock_exists, mock_file):
        """Test worktree cleanup with manual removal fallback."""
        repo_path = Path("/path/to/worktree")
        source_path = Path("/path/to/source")

        result = mcl.cleanup_worktree(repo_path, source_path)
        assert result is True
        mock_rmtree.assert_called_once()

    @patch('builtins.open', side_effect=Exception("Permission denied"))
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    def test_cleanup_worktree_error(self, mock_is_file, mock_exists, mock_file):
        """Test worktree cleanup with error."""
        repo_path = Path("/path/to/worktree")

        result = mcl.cleanup_worktree(repo_path)
        assert result is False


class TestCopyNonGitDirectory:
    """Test copy_non_git_directory function."""

    @patch('shutil.copytree')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('mcl.is_git_repo')
    @patch('shutil.rmtree')
    def test_copy_non_git_with_venv(self, mock_rmtree, mock_is_git, mock_exists, mock_copytree):
        """Test copying directory with virtual environment cleanup."""
        mock_is_git.return_value = False

        result = mcl.copy_non_git_directory(Path("/source"), Path("/dest"), "branch")

        assert result is True
        mock_copytree.assert_called_once()

    @patch('shutil.copytree')
    @patch('mcl.is_git_repo', return_value=True)
    @patch('mcl.run_command')
    @patch('shutil.rmtree')
    def test_copy_non_git_with_git_dest_no_remote(self, mock_rmtree, mock_run_cmd, mock_is_git, mock_copytree):
        """Test copying to git directory without remote."""
        # Mock git commands: no uncommitted changes, no remote, successful checkout
        mock_run_cmd.side_effect = [
            "",  # git status --porcelain (no changes)
            "",  # git remote (no remote)
            "",  # git checkout main (success)
        ]

        result = mcl.copy_non_git_directory(Path("/source"), Path("/dest"), "branch")
        assert result is True

    @patch('shutil.copytree')
    @patch('mcl.is_git_repo', return_value=True)
    @patch('mcl.run_command')
    @patch('shutil.rmtree')
    def test_copy_non_git_with_uncommitted_changes(self, mock_rmtree, mock_run_cmd, mock_is_git, mock_copytree):
        """Test copying to git directory with uncommitted changes."""
        # Mock git commands with uncommitted changes
        mock_run_cmd.side_effect = [
            "M file.txt",  # git status --porcelain (has changes)
            "",  # git stash (success)
            "",  # git remote (no remote)
            "",  # git checkout main
        ]

        result = mcl.copy_non_git_directory(Path("/source"), Path("/dest"), "branch")
        assert result is True


class TestCreateGitWorktree:
    """Test create_git_worktree edge cases."""

    @patch('mcl.run_command')
    @patch('mcl.copy_non_git_directory', return_value=True)
    def test_create_worktree_with_uncommitted_changes(self, mock_copy, mock_run_cmd):
        """Test worktree creation with uncommitted changes in source."""
        mock_run_cmd.side_effect = [
            "M file.txt",  # git status (has changes)
            "",  # git stash
            "origin",  # git remote
            "",  # git fetch
            "",  # git checkout main
            "",  # git worktree add
        ]

        result = mcl.create_git_worktree("/source", "/dest", "feature/test")
        assert result is True

    @patch('mcl.run_command')
    @patch('mcl.copy_non_git_directory', return_value=True)
    def test_create_worktree_no_main_branch(self, mock_copy, mock_run_cmd):
        """Test worktree creation when main/master branches don't exist."""
        mock_run_cmd.side_effect = [
            "",  # git status
            "",  # git remote
            "",  # git fetch
            None,  # git checkout main (fails)
            None,  # git checkout master (fails)
            "develop",  # git branch --show-current
            "",  # git worktree add
        ]

        result = mcl.create_git_worktree("/source", "/dest", "feature/test")
        assert result is True

    @patch('mcl.run_command', side_effect=Exception("Git error"))
    @patch('mcl.copy_non_git_directory', return_value=True)
    def test_create_worktree_exception(self, mock_copy, mock_run_cmd):
        """Test worktree creation with exception."""
        result = mcl.create_git_worktree("/source", "/dest", "feature/test")
        assert result is True
        mock_copy.assert_called_once()


class TestSetupLocalRepo:
    """Test setup_local_repo function."""

    @patch('mcl.get_unique_repo_path')
    @patch('mcl.is_git_repo', return_value=True)
    @patch('mcl.create_git_worktree', return_value=True)
    def test_setup_local_repo_with_conflict(self, mock_create, mock_is_git, mock_unique):
        """Test setup with conflicting destination path."""
        mock_unique.return_value = Path("/dest-1")

        with patch('builtins.print'):
            result = mcl.setup_local_repo(Path("/source"), Path("/dest"), "branch")

        assert result is True
        mock_create.assert_called_once_with(Path("/source"), Path("/dest-1"), "branch")


class TestBackwardsCompatibilityMain:
    """Test backwards compatibility in main() function."""

    @patch('mcl.cmd_start')
    @patch('sys.argv', ['mcl', '--repo', 'https://github.com/user/repo', '--requirements', 'Add feature'])
    def test_main_backwards_compat_with_dash_flags(self, mock_cmd_start):
        """Test main() with backwards compatible dash flags."""
        mcl.main()
        mock_cmd_start.assert_called_once()

    @patch('sys.argv', ['mcl'])
    def test_main_no_args_prints_help(self):
        """Test main() with no arguments prints help."""
        with patch('argparse.ArgumentParser.print_help') as mock_help:
            mcl.main()
            mock_help.assert_called_once()


class TestManagerCommandEdgeCases:
    """Test manager command edge cases."""

    @patch('mcl.get_manager_daemon')
    @patch('mcl.is_manager_running', return_value=False)
    def test_manager_add_auto_start(self, mock_running, mock_get_daemon):
        """Test manager add command auto-starts daemon."""
        mock_daemon = Mock()
        mock_daemon.spawn_agent.return_value = ("agent123", "session456")
        mock_get_daemon.return_value = mock_daemon

        args = Mock()
        args.manager_command = 'add'
        args.task = 'Test task'
        args.repo = '/test/repo'
        args.priority = 'normal'

        with patch('builtins.print'):
            mcl.cmd_manager(args)

        mock_daemon.spawn_agent.assert_called_once()

    @patch('mcl.get_manager_daemon')
    def test_manager_queue_with_items(self, mock_get_daemon):
        """Test manager queue command with items."""
        mock_daemon = Mock()
        mock_daemon.get_approval_queue.return_value = [
            (1, 'agent1', 'tool_request', '{"tool": "bash"}', '2023-01-01', 'Task 1')
        ]
        mock_get_daemon.return_value = mock_daemon

        args = Mock()
        args.manager_command = 'queue'

        with patch('builtins.print'):
            mcl.cmd_manager(args)

    @patch('mcl.get_manager_daemon')
    def test_manager_history_with_decisions(self, mock_get_daemon):
        """Test manager history command with decisions."""
        mock_daemon = Mock()
        mock_daemon.get_decision_history.return_value = [
            (1, 'agent1', 'Task description', 'approve', 0.8, 'balanced', 'claude-3.5-sonnet', 'correct', '2023-01-01')
        ]
        mock_get_daemon.return_value = mock_daemon

        args = Mock()
        args.manager_command = 'history'
        args.limit = 20

        with patch('builtins.print'):
            mcl.cmd_manager(args)


class TestCmdStartWorkflow:
    """Test cmd_start workflow paths."""

    @patch('mcl.is_local_path', return_value=True)
    @patch('pathlib.Path.mkdir')
    @patch('pathlib.Path.resolve')
    @patch('mcl.is_github_issue_url', return_value=True)
    @patch('mcl.fetch_github_issue', return_value="Issue requirements")
    @patch('mcl.get_repo_name', return_value="test-repo")
    @patch('mcl.get_feature_repo_name', return_value="test-repo-feature")
    @patch('mcl.get_unique_repo_path')
    @patch('pathlib.Path.exists', return_value=False)
    @patch('mcl.copy_local_repo', return_value=True)
    @patch('mcl.run_command')
    @patch('mcl.create_task_memory', return_value="/path/TASK_MEMORY.md")
    @patch('os.chdir')
    @patch('subprocess.run')
    def test_cmd_start_with_github_issue(self, mock_subprocess, mock_chdir, mock_create_memory,
                                        mock_run_cmd, mock_copy, mock_exists, mock_unique,
                                        mock_feature_name, mock_repo_name, mock_fetch,
                                        mock_is_issue, mock_resolve, mock_mkdir, mock_is_local):
        """Test cmd_start with GitHub issue URL."""
        mock_unique.return_value = Path("/staging/test-repo-feature")
        mock_resolve.return_value = Path("/staging")
        mock_run_cmd.return_value = "feature/test"

        args = Mock()
        args.repo = "/local/repo"
        args.requirements = "https://github.com/user/repo/issues/123"
        args.workspace = None
        args.staging_dir = None
        args.branch = None
        args.continue_branch = False
        args.no_clone = False
        args.no_claude = True
        args.instructions = None

        with patch('builtins.print'):
            mcl.cmd_start(args)

        mock_fetch.assert_called_once()

    @patch('mcl.is_local_path', return_value=False)
    @patch('mcl.is_github_issue_url', return_value=False)
    @patch('mcl.is_requirements_file', return_value=True)
    @patch('mcl.read_requirements_file', return_value="File requirements")
    @patch('mcl.get_repo_name', return_value="test-repo")
    @patch('mcl.get_feature_repo_name', return_value="test-repo-feature")
    @patch('mcl.get_unique_repo_path')
    @patch('mcl.run_command')
    @patch('mcl.create_task_memory', return_value="/path/TASK_MEMORY.md")
    @patch('os.chdir')
    def test_cmd_start_with_requirements_file(self, mock_chdir, mock_create_memory, mock_run_cmd,
                                             mock_unique, mock_feature_name, mock_repo_name,
                                             mock_read_file, mock_is_file, mock_is_issue, mock_is_local):
        """Test cmd_start with requirements file."""
        mock_unique.return_value = Path("/staging/test-repo-feature")

        mock_run_cmd.side_effect = [
            "",  # git clone
            "feature/test",  # git branch --show-current
            "",  # git checkout -b
        ]

        args = Mock()
        args.repo = "https://github.com/user/repo.git"
        args.requirements = "/path/to/requirements.txt"
        args.workspace = None
        args.staging_dir = None
        args.branch = None
        args.continue_branch = False
        args.no_clone = False
        args.no_claude = True
        args.instructions = None

        with patch('builtins.print'):
            with patch('pathlib.Path.mkdir'):
                with patch('pathlib.Path.resolve', return_value=Path("/staging")):
                    with patch('pathlib.Path.exists', return_value=False):
                        mcl.cmd_start(args)

        mock_read_file.assert_called_once()

    @patch('mcl.is_local_path', return_value=False)
    @patch('mcl.is_github_issue_url', return_value=False)
    @patch('mcl.is_requirements_file', return_value=False)
    @patch('mcl.get_repo_name', return_value="test-repo")
    @patch('mcl.get_feature_repo_name', return_value="test-repo-feature")
    @patch('mcl.get_unique_repo_path')
    @patch('mcl.run_command')
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.chdir')
    def test_cmd_start_continue_branch(self, mock_chdir, mock_file, mock_os_exists, mock_run_cmd,
                                       mock_unique, mock_feature_name, mock_repo_name,
                                       mock_is_file, mock_is_issue, mock_is_local):
        """Test cmd_start with continue_branch option."""
        mock_unique.return_value = Path("/staging/test-repo-feature")

        mock_run_cmd.side_effect = [
            "",  # git clone (not called)
            "other-branch",  # git branch --show-current
            "",  # git checkout
        ]

        args = Mock()
        args.repo = "https://github.com/user/repo.git"
        args.requirements = "Plain text requirements"
        args.workspace = None
        args.staging_dir = None
        args.branch = "feature/existing"
        args.continue_branch = True
        args.no_clone = False
        args.no_claude = True
        args.instructions = "Additional context"

        with patch('builtins.print'):
            with patch('pathlib.Path.mkdir'):
                with patch('pathlib.Path.resolve', return_value=Path("/staging")):
                    with patch('pathlib.Path.exists', return_value=True):
                        mcl.cmd_start(args)

        # Should append to existing file
        mock_file().write.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
