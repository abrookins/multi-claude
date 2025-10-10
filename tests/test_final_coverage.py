"""
Final tests to push coverage to 90%+ for mcl.py

Targeting specific uncovered lines based on coverage report.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import sys

import mcl


class TestRemainingEdgeCases:
    """Test remaining edge cases to reach 90% coverage."""

    @patch('os.getenv', return_value=None)
    @patch('mcl.urlopen')
    def test_fetch_github_issue_no_token(self, mock_urlopen, mock_getenv):
        """Test GitHub issue fetch without authentication token."""
        import json
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            'title': 'Test Issue',
            'body': 'Description',
            'labels': []
        }).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = mcl.fetch_github_issue("https://github.com/user/repo/issues/123")
        assert result is not None

    @patch('mcl.urlopen', side_effect=mcl.URLError("Network error"))
    def test_fetch_github_issue_url_error(self, mock_urlopen):
        """Test GitHub issue fetch with URLError."""
        result = mcl.fetch_github_issue("https://github.com/user/repo/issues/123")
        assert result is None

    @patch('mcl.urlopen', side_effect=mcl.HTTPError("url", 404, "Not found", {}, None))
    def test_fetch_github_issue_http_error_exception(self, mock_urlopen):
        """Test GitHub issue fetch with HTTPError exception."""
        result = mcl.fetch_github_issue("https://github.com/user/repo/issues/123")
        assert result is None


class TestCopyNonGitEdgeCases:
    """Test edge cases in copy_non_git_directory."""

    @patch('shutil.copytree')
    @patch('mcl.is_git_repo', return_value=True)
    @patch('mcl.run_command')
    @patch('shutil.rmtree')
    def test_copy_non_git_stash_failure(self, mock_rmtree, mock_run_cmd, mock_is_git, mock_copytree):
        """Test copying when stash command fails."""
        mock_run_cmd.side_effect = [
            "M file.txt",  # git status (has changes)
            None,  # git stash (fails)
            "",  # git remote
            "",  # git checkout main
        ]

        result = mcl.copy_non_git_directory(Path("/source"), Path("/dest"), "branch")
        assert result is True

    @patch('shutil.copytree')
    @patch('mcl.is_git_repo', return_value=True)
    @patch('mcl.run_command')
    @patch('shutil.rmtree')
    def test_copy_non_git_with_remote_and_reset(self, mock_rmtree, mock_run_cmd, mock_is_git, mock_copytree):
        """Test copying with remote and reset to origin."""
        mock_run_cmd.side_effect = [
            "",  # git status
            "origin",  # git remote (has remote)
            "",  # git fetch origin
            "",  # git checkout main
            "",  # git reset --hard origin/main
        ]

        result = mcl.copy_non_git_directory(Path("/source"), Path("/dest"), "branch")
        assert result is True

    @patch('shutil.copytree')
    @patch('mcl.is_git_repo', return_value=True)
    @patch('mcl.run_command')
    @patch('shutil.rmtree')
    def test_copy_non_git_reset_failure(self, mock_rmtree, mock_run_cmd, mock_is_git, mock_copytree):
        """Test copying when reset command fails."""
        mock_run_cmd.side_effect = [
            "",  # git status
            "origin",  # git remote
            "",  # git fetch
            "",  # git checkout main
            None,  # git reset --hard (fails)
        ]

        result = mcl.copy_non_git_directory(Path("/source"), Path("/dest"), "branch")
        assert result is True

    @patch('shutil.copytree')
    @patch('mcl.is_git_repo', return_value=True)
    @patch('mcl.run_command')
    @patch('shutil.rmtree')
    def test_copy_non_git_master_branch(self, mock_rmtree, mock_run_cmd, mock_is_git, mock_copytree):
        """Test copying when only master branch exists."""
        mock_run_cmd.side_effect = [
            "",  # git status
            "",  # git remote
            None,  # git checkout main (fails)
            "",  # git checkout master (success)
        ]

        result = mcl.copy_non_git_directory(Path("/source"), Path("/dest"), "branch")
        assert result is True

    @patch('shutil.copytree')
    @patch('mcl.is_git_repo', return_value=True)
    @patch('mcl.run_command')
    @patch('shutil.rmtree')
    def test_copy_non_git_no_main_or_master(self, mock_rmtree, mock_run_cmd, mock_is_git, mock_copytree):
        """Test copying when neither main nor master branch exists."""
        mock_run_cmd.side_effect = [
            "",  # git status
            "",  # git remote
            None,  # git checkout main (fails)
            None,  # git checkout master (fails)
        ]

        result = mcl.copy_non_git_directory(Path("/source"), Path("/dest"), "branch")
        assert result is True


class TestRichLibraryPaths:
    """Test paths when Rich library is available."""

    @patch('mcl.HAS_RICH', True)
    @patch('pathlib.Path.exists', return_value=False)
    def test_list_staged_directories_with_rich_no_dir(self, mock_exists):
        """Test listing with Rich when staging dir doesn't exist."""
        with patch('mcl.Console') as mock_console:
            mcl.list_staged_directories("/nonexistent")
            # Should create console and print error
            mock_console.assert_called()

    @patch('mcl.HAS_RICH', True)
    @patch('pathlib.Path.iterdir')
    @patch('pathlib.Path.exists', return_value=True)
    def test_list_staged_directories_with_rich_empty(self, mock_exists, mock_iterdir):
        """Test listing with Rich when no tasks exist."""
        mock_iterdir.return_value = []

        with patch('mcl.Console') as mock_console:
            mcl.list_staged_directories("/staging")
            mock_console.assert_called()

    @patch('mcl.HAS_RICH', True)
    @patch('pathlib.Path.iterdir')
    @patch('pathlib.Path.exists', return_value=True)
    def test_list_staged_directories_with_rich_with_tasks(self, mock_exists, mock_iterdir):
        """Test listing with Rich when tasks exist."""
        mock_dir = Mock()
        mock_dir.is_dir.return_value = True
        mock_dir.name = "task1"
        mock_dir.stat.return_value.st_mtime = 1627980600
        mock_iterdir.return_value = [mock_dir]

        with patch('mcl.Console') as mock_console:
            with patch('mcl.Table') as mock_table:
                mcl.list_staged_directories("/staging")
                mock_console.assert_called()
                mock_table.assert_called()


class TestCmdStartMorePaths:
    """Test more cmd_start paths."""

    @patch('mcl.is_local_path', return_value=True)
    @patch('mcl.is_github_issue_url', return_value=False)
    @patch('mcl.is_requirements_file', return_value=False)
    @patch('mcl.get_repo_name', return_value="test-repo")
    @patch('mcl.get_feature_repo_name', return_value="test-repo-feature")
    @patch('mcl.get_unique_repo_path')
    @patch('mcl.copy_local_repo', return_value=True)
    @patch('mcl.run_command')
    @patch('mcl.create_task_memory', return_value="/path/TASK_MEMORY.md")
    @patch('os.chdir')
    def test_cmd_start_local_repo_with_workspace(self, mock_chdir, mock_create_memory, mock_run_cmd,
                                                 mock_copy, mock_unique, mock_feature_name,
                                                 mock_repo_name, mock_is_file, mock_is_issue, mock_is_local):
        """Test cmd_start with local repo and custom workspace."""
        mock_unique.return_value = Path("/custom/workspace/test-repo-feature")
        mock_run_cmd.return_value = "feature/test"

        args = Mock()
        args.repo = "/local/repo"
        args.requirements = "Plain text requirements"
        args.workspace = "/custom/workspace"
        args.staging_dir = None
        args.branch = None
        args.continue_branch = False
        args.no_clone = False
        args.no_claude = True
        args.instructions = None

        with patch('builtins.print'):
            with patch('pathlib.Path.resolve', return_value=Path("/custom/workspace")):
                with patch('pathlib.Path.exists', return_value=False):
                    mcl.cmd_start(args)

        # Should use custom workspace
        assert mock_unique.called

    @patch('mcl.is_local_path', return_value=False)
    @patch('mcl.is_github_issue_url', return_value=True)
    @patch('mcl.fetch_github_issue', return_value=None)
    def test_cmd_start_failed_github_issue_fetch(self, mock_fetch, mock_is_issue, mock_is_local):
        """Test cmd_start when GitHub issue fetch fails."""
        args = Mock()
        args.repo = "https://github.com/user/repo.git"
        args.requirements = "https://github.com/user/repo/issues/123"
        args.workspace = None
        args.staging_dir = None

        with patch('builtins.print'):
            with patch('pathlib.Path.resolve', return_value=Path("/staging")):
                with patch('pathlib.Path.mkdir'):
                    with pytest.raises(SystemExit) as exc_info:
                        mcl.cmd_start(args)
                    assert exc_info.value.code == 1

    @patch('mcl.is_local_path', return_value=False)
    @patch('mcl.is_github_issue_url', return_value=False)
    @patch('mcl.is_requirements_file', return_value=True)
    @patch('mcl.read_requirements_file', return_value=None)
    def test_cmd_start_failed_requirements_file_read(self, mock_read, mock_is_file,
                                                     mock_is_issue, mock_is_local):
        """Test cmd_start when requirements file read fails."""
        args = Mock()
        args.repo = "https://github.com/user/repo.git"
        args.requirements = "/path/to/requirements.txt"
        args.workspace = None
        args.staging_dir = None

        with patch('builtins.print'):
            with patch('pathlib.Path.resolve', return_value=Path("/staging")):
                with patch('pathlib.Path.mkdir'):
                    with pytest.raises(SystemExit) as exc_info:
                        mcl.cmd_start(args)
                    assert exc_info.value.code == 1

    @patch('mcl.is_local_path', return_value=True)
    @patch('mcl.is_github_issue_url', return_value=False)
    @patch('mcl.is_requirements_file', return_value=False)
    @patch('mcl.get_repo_name', return_value="test-repo")
    @patch('mcl.get_feature_repo_name', return_value="test-repo-feature")
    @patch('mcl.get_unique_repo_path')
    @patch('mcl.copy_local_repo', return_value=False)
    def test_cmd_start_failed_local_copy(self, mock_copy, mock_unique, mock_feature_name,
                                        mock_repo_name, mock_is_file, mock_is_issue, mock_is_local):
        """Test cmd_start when local copy fails."""
        mock_unique.return_value = Path("/staging/test-repo-feature")

        args = Mock()
        args.repo = "/local/repo"
        args.requirements = "Plain text requirements"
        args.workspace = None
        args.staging_dir = None
        args.branch = None
        args.continue_branch = False
        args.no_clone = False

        with patch('builtins.print'):
            with patch('pathlib.Path.resolve', return_value=Path("/staging")):
                with patch('pathlib.Path.mkdir'):
                    with patch('pathlib.Path.exists', return_value=False):
                        with pytest.raises(SystemExit) as exc_info:
                            mcl.cmd_start(args)
                        assert exc_info.value.code == 1

    @patch('mcl.is_local_path', return_value=False)
    @patch('mcl.is_github_issue_url', return_value=False)
    @patch('mcl.is_requirements_file', return_value=False)
    @patch('mcl.get_repo_name', return_value="test-repo")
    @patch('mcl.get_feature_repo_name', return_value="test-repo-feature")
    @patch('mcl.get_unique_repo_path')
    @patch('mcl.run_command', return_value=None)
    def test_cmd_start_failed_clone(self, mock_run_cmd, mock_unique, mock_feature_name,
                                   mock_repo_name, mock_is_file, mock_is_issue, mock_is_local):
        """Test cmd_start when git clone fails."""
        mock_unique.return_value = Path("/staging/test-repo-feature")

        args = Mock()
        args.repo = "https://github.com/user/repo.git"
        args.requirements = "Plain text requirements"
        args.workspace = None
        args.staging_dir = None
        args.branch = None
        args.continue_branch = False
        args.no_clone = False

        with patch('builtins.print'):
            with patch('pathlib.Path.resolve', return_value=Path("/staging")):
                with patch('pathlib.Path.mkdir'):
                    with patch('pathlib.Path.exists', return_value=False):
                        with pytest.raises(SystemExit) as exc_info:
                            mcl.cmd_start(args)
                        assert exc_info.value.code == 1

    @patch('mcl.is_local_path', return_value=False)
    @patch('mcl.is_github_issue_url', return_value=False)
    @patch('mcl.is_requirements_file', return_value=False)
    @patch('mcl.get_repo_name', return_value="test-repo")
    @patch('mcl.get_feature_repo_name', return_value="test-repo-feature")
    @patch('mcl.get_unique_repo_path')
    def test_cmd_start_no_clone_missing_repo(self, mock_unique, mock_feature_name,
                                            mock_repo_name, mock_is_file, mock_is_issue, mock_is_local):
        """Test cmd_start with --no-clone when repo doesn't exist."""
        mock_unique.return_value = Path("/staging/test-repo-feature")

        args = Mock()
        args.repo = "https://github.com/user/repo.git"
        args.requirements = "Plain text requirements"
        args.workspace = None
        args.staging_dir = None
        args.branch = None
        args.continue_branch = False
        args.no_clone = True

        with patch('builtins.print'):
            with patch('pathlib.Path.resolve', return_value=Path("/staging")):
                with patch('pathlib.Path.mkdir'):
                    with patch('pathlib.Path.exists', return_value=False):
                        with pytest.raises(SystemExit) as exc_info:
                            mcl.cmd_start(args)
                        assert exc_info.value.code == 1

    @patch('mcl.is_local_path', return_value=False)
    @patch('mcl.is_github_issue_url', return_value=False)
    @patch('mcl.is_requirements_file', return_value=False)
    @patch('mcl.get_repo_name', return_value="test-repo")
    @patch('mcl.get_feature_repo_name', return_value="test-repo-feature")
    @patch('mcl.get_unique_repo_path')
    @patch('mcl.run_command')
    def test_cmd_start_failed_branch_creation(self, mock_run_cmd, mock_unique,
                                              mock_feature_name, mock_repo_name, mock_is_file,
                                              mock_is_issue, mock_is_local):
        """Test cmd_start when branch creation fails."""
        mock_unique.return_value = Path("/staging/test-repo-feature")
        mock_run_cmd.side_effect = [
            "",  # git clone
            "",  # git branch --show-current
            None,  # git checkout -b (fails)
        ]

        args = Mock()
        args.repo = "https://github.com/user/repo.git"
        args.requirements = "Plain text requirements"
        args.workspace = None
        args.staging_dir = None
        args.branch = None
        args.continue_branch = False
        args.no_clone = False

        with patch('builtins.print'):
            with patch('pathlib.Path.resolve', return_value=Path("/staging")):
                with patch('pathlib.Path.mkdir'):
                    with patch('pathlib.Path.exists', return_value=False):
                        with pytest.raises(SystemExit) as exc_info:
                            mcl.cmd_start(args)
                        assert exc_info.value.code == 1

    @patch('mcl.is_local_path', return_value=False)
    @patch('mcl.is_github_issue_url', return_value=False)
    @patch('mcl.is_requirements_file', return_value=False)
    @patch('mcl.get_repo_name', return_value="test-repo")
    @patch('mcl.get_feature_repo_name', return_value="test-repo-feature")
    @patch('mcl.get_unique_repo_path')
    @patch('mcl.run_command')
    @patch('mcl.create_task_memory', return_value="/path/TASK_MEMORY.md")
    @patch('os.chdir')
    def test_cmd_start_already_on_branch(self, mock_chdir, mock_create_memory, mock_run_cmd,
                                        mock_unique, mock_feature_name, mock_repo_name,
                                        mock_is_file, mock_is_issue, mock_is_local):
        """Test cmd_start when already on target branch."""
        mock_unique.return_value = Path("/staging/test-repo-feature")
        mock_run_cmd.side_effect = [
            "",  # git clone
            "feature/test",  # git branch --show-current (already on branch)
        ]

        args = Mock()
        args.repo = "https://github.com/user/repo.git"
        args.requirements = "Plain text requirements"
        args.workspace = None
        args.staging_dir = None
        args.branch = "feature/test"
        args.continue_branch = False
        args.no_clone = False
        args.no_claude = True
        args.instructions = None

        with patch('builtins.print'):
            with patch('pathlib.Path.resolve', return_value=Path("/staging")):
                with patch('pathlib.Path.mkdir'):
                    with patch('pathlib.Path.exists', return_value=False):
                        mcl.cmd_start(args)

        # Should have called git clone and git branch --show-current
        assert mock_run_cmd.call_count == 2
        # Should NOT have tried to create branch (no git checkout -b call)
        calls = str(mock_run_cmd.call_args_list)
        assert "git clone" in calls
        assert "git branch --show-current" in calls


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
