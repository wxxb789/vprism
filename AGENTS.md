# AGENTS.md - vprism Development Guidelines

## Commands

- **Run all tests:** `uv run pytest`
- **Run a single test file:** `uv run pytest tests/path/to/test_file.py`
- **Run a single test:** `uv run pytest tests/path/to/test_file.py::test_name`
- **Lint:** `uv run ruff check .`
- **Format:** `uv run ruff format .`
- **Type Check:** `uv run mypy ./vprism`

## Code Style

- **Formatting:** Black style, 196-char line length (`uv run ruff format .`).
- **Imports:** Sorted with `uv run ruff check --fix .` (isort).
- **Typing:** Fully type-hinted (`uv run mypy --strict ./vprism`). Use `from typing import ...`.
- **Naming:**
  - Classes: `PascalCase`
  - Functions/Variables: `snake_case`
  - Private members: `_leading_underscore`
- **Docstrings:** Google-style for public APIs.
- **Error Handling:** Use custom exceptions from `vprism.core.exceptions` where applicable.
- **Structure:** Follow existing project structure. Place business logic in `core`, infrastructure in `infrastructure`.
