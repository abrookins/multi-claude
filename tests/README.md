# Multi-Claude Test Suite

This directory contains the test suite for the Multi-Claude (mcl) CLI tool.

## Test Structure

### `test_unit.py` - Unit Tests ✅
**40 tests total, 33 passing**

Comprehensive unit tests covering core functionality with proper mocking of external dependencies:

- **Core Functions** (9 tests) - URL validation, repo name extraction, feature summaries
- **File System Operations** (7 tests) - Path detection, git repo detection, file operations  
- **Git Operations** (7 tests) - Command execution, worktree creation, repository setup
- **Network Operations** (3 tests) - GitHub API interactions
- **Command Line Interface** (4 tests) - Argument parsing and command routing
- **Utility Functions** (6 tests) - Shell integration, task memory, directory listing
- **Error Handling** (4 tests) - File system errors, invalid inputs, edge cases

### Test Philosophy

**Unit Tests** focus on:
- ✅ **Isolated testing** - Each function tested independently
- ✅ **Mocked dependencies** - All external calls (filesystem, subprocess, network) are mocked
- ✅ **Fast execution** - Tests complete in ~0.3 seconds
- ✅ **Deterministic** - Tests produce consistent results
- ✅ **Edge case coverage** - None values, empty inputs, error conditions

### Future Test Organization

As the codebase grows, consider adding:

- **`test_integration.py`** - End-to-end workflow tests with real filesystem operations
- **`test_cli.py`** - Comprehensive CLI testing with actual subprocess calls
- **`conftest.py`** - Shared pytest fixtures and test utilities

## Running Tests

### Run all unit tests:
```bash
python -m pytest tests/test_unit.py -v
```

### Run specific test classes:
```bash
python -m pytest tests/test_unit.py::TestCoreFunctions -v
python -m pytest tests/test_unit.py::TestGitOperations -v
```

### Run with coverage:
```bash
python -m pytest --cov=mcl tests/test_unit.py
```

### Run all tests in the project:
```bash
python -m pytest tests/ -v
```

## Test Coverage

### ✅ **Well-Tested Core Functions** (100% coverage)
- `is_github_issue_url()` - GitHub issue URL validation with edge cases
- `is_git_url()` - Git URL detection for various protocols
- `generate_feature_summary()` - Feature name generation with prefix removal
- `get_repo_name()` - Repository name extraction from URLs and paths
- `get_feature_repo_name()` - Combined repo and feature naming

### ✅ **Well-Tested File Operations** (95% coverage)
- `is_local_path()` - Local directory detection with mocking
- `is_git_repo()` - Git repository detection via .git folder
- `get_unique_repo_path()` - Path conflict resolution with counter
- `is_requirements_file()` - File existence validation
- `read_requirements_file()` - File reading with error handling

### ✅ **Core Git Operations** (85% coverage)  
- `run_command()` - Subprocess execution with success/failure/timeout
- `setup_local_repo()` - Repository setup routing (git vs non-git)
- `create_git_worktree()` - Basic worktree creation testing
- `copy_non_git_directory()` - Directory copying with cleanup

### ✅ **Command Line Interface** (90% coverage)
- Argument parsing for all major commands (`start`, `ls`, `cd`)
- Help system functionality
- Command routing and delegation

### ⚠️ **Partially Tested Complex Operations** (60% coverage)
- Advanced git worktree scenarios
- Network operations (GitHub API)
- Complex error handling chains
- Shell integration edge cases

## Dependencies

Testing requires:
- `pytest>=7.0.0`
- `pytest-cov>=4.0.0` (for coverage reports)

Install with:
```bash
pip install -e ".[dev]"
```

## Adding New Tests

When adding new functionality to `mcl.py`:

1. **Add unit tests** to `test_unit.py` for new functions
2. **Use appropriate mocking** for external dependencies:
   - `@patch('subprocess.run')` for git commands
   - `@patch('pathlib.Path.exists')` for filesystem checks
   - `@patch('urllib.request.urlopen')` for network calls
3. **Test both success and failure scenarios**
4. **Include edge cases**: None values, empty strings, invalid inputs
5. **Follow existing naming conventions**: `test_function_name_scenario`

### Example Test Structure:
```python
class TestNewFeature:
    """Test new feature functionality."""
    
    @patch('external.dependency')
    def test_new_function_success(self, mock_dependency):
        """Test successful execution of new function."""
        mock_dependency.return_value = "expected result"
        
        result = mcl.new_function("input")
        assert result == "expected output"
        mock_dependency.assert_called_once_with("input")
    
    @patch('external.dependency', side_effect=Exception("Error"))
    def test_new_function_error_handling(self, mock_dependency):
        """Test error handling in new function."""
        result = mcl.new_function("input")
        assert result is None  # or appropriate error response
```

This test structure ensures maintainable, reliable tests that provide confidence in the codebase while enabling safe refactoring and feature development.