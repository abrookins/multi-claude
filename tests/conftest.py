"""
Shared pytest configuration and fixtures for the multi-claude test suite.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_git_repo(temp_dir):
    """Create a mock git repository structure."""
    git_dir = temp_dir / ".git"
    git_dir.mkdir()
    (temp_dir / "README.md").write_text("# Test Repo")
    (temp_dir / "src").mkdir()
    (temp_dir / "src" / "main.py").write_text("print('hello')")
    return temp_dir


@pytest.fixture
def mock_non_git_dir(temp_dir):
    """Create a mock non-git directory structure."""
    (temp_dir / "file.txt").write_text("test content")
    (temp_dir / "subdir").mkdir()
    return temp_dir


@pytest.fixture
def mock_subprocess_success():
    """Mock successful subprocess calls."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="success", stderr="")
        yield mock_run


@pytest.fixture
def mock_subprocess_failure():
    """Mock failed subprocess calls."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")
        yield mock_run


@pytest.fixture
def mock_filesystem():
    """Mock filesystem operations."""
    with patch('pathlib.Path.exists') as mock_exists, \
         patch('pathlib.Path.is_dir') as mock_is_dir, \
         patch('os.path.exists') as mock_os_exists, \
         patch('os.path.isdir') as mock_os_isdir:
        
        yield {
            'path_exists': mock_exists,
            'path_is_dir': mock_is_dir, 
            'os_exists': mock_os_exists,
            'os_isdir': mock_os_isdir
        }


# Test data constants
VALID_GITHUB_URLS = [
    "https://github.com/user/repo/issues/123",
    "https://github.com/org/project/issues/456",
    "https://github.com/user-name/repo-name/issues/1",
]

INVALID_GITHUB_URLS = [
    "https://gitlab.com/user/repo/issues/123",
    "https://github.com/user/repo/pull/123",
    "https://github.com/user/repo",
    "not-a-url",
    "",
    "https://github.com/user/repo/issues/",
]

VALID_GIT_URLS = [
    "https://github.com/user/repo.git",
    "http://github.com/user/repo",
    "git@github.com:user/repo.git", 
    "ssh://git@github.com/user/repo.git",
]

INVALID_GIT_URLS = [
    "/local/path",
    "not-a-url",
    "",
    "file:///path/to/repo",
]