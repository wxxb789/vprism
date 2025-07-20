# Development Workflow Standards

## Post-Task Completion Protocol

This document defines the mandatory steps to be executed after completing any development task in this repository.

### Mandatory Post-Task Steps

Every time a task is completed, **ALWAYS** execute these steps in order:

#### 1. Update Task Status in tasks.md
- [ ] Mark the completed task with `[x]` in the corresponding `tasks.md` file
- [ ] Use markdown checkbox format: `- [x] Task description`
- [ ] Ensure the checkbox is properly formatted with space after `[x]`

#### 2. Update Steering Documentation
- [ ] Run `/steering-update` command if project structure changed
- [ ] Review and update relevant `.kiro/steering/*.md` files
- [ ] Ensure documentation reflects current state of the codebase

#### 3. Code Formatting
- [ ] Execute `ruff format` from project root to format all Python files
- [ ] Execute `ruff check --fix` to auto-fix linting issues
- [ ] Verify no formatting issues remain

#### 4. Git Commit (Atomic Commits)
- [ ] Stage all changes: `git add -A`
- [ ] Create atomic commit with clear message
- [ ] Commit message format: `type(scope): description`
- [ ] Examples:
  - `feat(cache): implement multi-level caching`
  - `fix(provider): handle rate limiting in yfinance`
  - `docs(steering): update project structure documentation`

### Commit Message Standards

Follow conventional commits specification:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

### Quality Checklist

Before committing, ensure:
- [ ] All tests pass: `pytest`
- [ ] Type checking passes: `mypy src/vprism --strict`
- [ ] Code formatting is applied: `ruff format`
- [ ] Linting passes: `ruff check`
- [ ] Task status updated in tasks.md
- [ ] Steering docs updated if needed

### Automation

These steps are enforced through:
- Pre-commit hooks (when configured)
- Manual verification during development
- CI/CD pipeline validation

### Examples

#### Example 1: Completing a Feature
```bash
# 1. Update tasks.md (mark checkbox as [x])
# 2. Update steering if structure changed
/steering-update

# 3. Format and lint code
ruff format
ruff check --fix

# 4. Commit changes
git add -A
git commit -m "feat(cache): implement multi-level caching with memory and duckdb"
```

#### Example 2: Documentation Update
```bash
# 1. Update tasks.md
# 2. Format docs
ruff format

# 3. Commit
git add -A
git commit -m "docs(steering): update project structure documentation"
```

### Enforcement

This workflow is mandatory for all contributors. Violations will be caught during code review and must be resolved before merge.