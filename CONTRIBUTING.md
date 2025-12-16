# Contributing to R CLI

Thank you for your interest in contributing to R CLI! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.10+
- [LM Studio](https://lmstudio.ai/) or [Ollama](https://ollama.ai/) for testing LLM features
- Git

### Installation

1. Clone the repository:
```bash
git clone https://github.com/raym33/r.git
cd r
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install in development mode:
```bash
pip install -e ".[dev]"
```

4. Install pre-commit hooks:
```bash
pip install pre-commit
pre-commit install
```

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=r_cli --cov-report=term-missing

# Run specific test file
pytest tests/test_skills.py -v

# Run specific test
pytest tests/test_skills.py::TestPDFSkill -v
```

### Code Quality

We use Ruff for linting and formatting:

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .

# Check formatting without changes
ruff format --check .
```

Type checking with mypy:

```bash
mypy r_cli --ignore-missing-imports
```

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`. To run manually:

```bash
pre-commit run --all-files
```

## Project Structure

```
r/
├── r_cli/
│   ├── api/            # REST API daemon (FastAPI)
│   │   ├── server.py   # API server and routes
│   │   └── models.py   # Pydantic request/response models
│   ├── core/           # Core components
│   │   ├── agent.py    # Main agent orchestrator
│   │   ├── config.py   # Configuration management
│   │   ├── llm.py      # LLM client abstraction
│   │   ├── memory.py   # Context and memory
│   │   └── plugins.py  # Plugin system
│   ├── skills/         # Built-in skills (27 total)
│   │   ├── pdf_skill.py
│   │   ├── sql_skill.py
│   │   ├── logs_skill.py      # Log analysis
│   │   ├── benchmark_skill.py # Performance profiling
│   │   ├── openapi_skill.py   # API integration
│   │   └── ...
│   ├── ui/             # Terminal UI
│   │   ├── terminal.py
│   │   ├── themes.py
│   │   └── ps2_loader.py
│   └── main.py         # CLI entry point
├── services/           # Service files
│   ├── r-cli.service   # systemd (Linux)
│   └── com.rcli.agent.plist  # launchd (macOS)
├── tests/              # Test suite
├── docs/               # Documentation
└── examples/           # Usage examples
```

## Creating a New Skill

1. Create a new file in `r_cli/skills/`:

```python
from r_cli.core.agent import Skill
from r_cli.core.llm import Tool

class MySkill(Skill):
    name = "my_skill"
    description = "Description of what this skill does"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="my_function",
                description="What this function does",
                parameters={
                    "type": "object",
                    "properties": {
                        "arg1": {"type": "string", "description": "Argument 1"},
                    },
                    "required": ["arg1"],
                },
                handler=self.my_function,
            )
        ]

    def my_function(self, arg1: str) -> str:
        return f"Result: {arg1}"

    def execute(self, **kwargs) -> str:
        return self.my_function(kwargs.get("arg1", ""))
```

2. Register in `r_cli/skills/__init__.py`:

```python
from r_cli.skills.my_skill import MySkill

def get_all_skills():
    return [
        # ... existing skills
        MySkill,
    ]
```

3. Add tests in `tests/test_skills.py`

4. Update documentation in `README.md` and `docs/COMPLETE_GUIDE.md`

## Adding API Endpoints

To add new API endpoints to the daemon mode:

1. Add Pydantic models in `r_cli/api/models.py`
2. Add route handlers in `r_cli/api/server.py` within `register_routes()`
3. Test with `r serve` and Swagger UI at `/docs`

## Pull Request Process

1. **Fork** the repository
2. **Create a branch** for your feature/fix:
   ```bash
   git checkout -b feature/my-feature
   ```
3. **Make your changes** following the code style
4. **Add tests** for new functionality
5. **Run the test suite** and ensure all tests pass:
   ```bash
   pytest tests/ -v
   ruff check .
   ruff format --check .
   ```
6. **Commit** with a clear message:
   ```bash
   git commit -m "feat: add new feature description"
   ```
7. **Push** to your fork:
   ```bash
   git push origin feature/my-feature
   ```
8. **Open a Pull Request** with:
   - Clear description of changes
   - Link to related issues
   - Screenshots/examples if applicable

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` new feature or skill
- `fix:` bug fix
- `docs:` documentation changes
- `style:` formatting, no code change
- `refactor:` code refactoring
- `test:` test additions or fixes
- `chore:` maintenance tasks

## Code Style

- Follow PEP 8 (enforced by Ruff)
- Use type hints for all function signatures
- Write docstrings for public functions and classes
- Keep functions focused and single-purpose
- Maximum line length: 100 characters

## Reporting Issues

When reporting issues, please include:

1. R CLI version (`r --version`)
2. Python version (`python --version`)
3. Operating system
4. LLM backend (LM Studio/Ollama) and model
5. Steps to reproduce
6. Expected vs actual behavior
7. Error messages/logs

## Areas for Contribution

We welcome contributions in these areas:

- **New Skills**: Add useful capabilities (see existing skills for examples)
- **API Improvements**: Enhance the REST API daemon
- **Documentation**: Improve docs, add examples
- **Tests**: Increase test coverage
- **Bug Fixes**: Fix reported issues
- **Performance**: Optimize existing code

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

Feel free to open an issue for questions or reach out to the maintainers.

- GitHub Issues: [github.com/raym33/r/issues](https://github.com/raym33/r/issues)
- Email: learntouseai@gmail.com
- Twitter/X: [@learntouseai](https://x.com/learntouseai)

Thank you for contributing!
