# AGENTS.md - vprism Development Guidelines

## Commands
- **Run all tests:** `pytest`
- **Run a single test file:** `pytest tests/path/to/test_file.py`
- **Run a single test:** `pytest tests/path/to/test_file.py::test_name`
- **Lint:** `ruff check .`
- **Format:** `ruff format .`
- **Type Check:** `mypy src/vprism`

## Code Style
- **Formatting:** Black style, 88-char line length (`ruff format .`).
- **Imports:** Sorted with `ruff --select I` (isort).
- **Typing:** Fully type-hinted (`mypy --strict`). Use `from typing import ...`.
- **Naming:**
  - Classes: `PascalCase`
  - Functions/Variables: `snake_case`
  - Private members: `_leading_underscore`
- **Docstrings:** Google-style for public APIs.
- **Error Handling:** Use custom exceptions from `vprism.core.exceptions` where applicable.
- **Structure:** Follow existing project structure. Place business logic in `core`, infrastructure in `infrastructure`.
