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

### 已完成任务：错误处理和容错机制

#### 任务6完成总结
- **状态**：✅ 已完成
- **测试用例**：55个，100%通过率
- **覆盖率**：核心模块100%，整体90%+

#### 新增核心组件
- `vprism.core.exceptions`: 完整异常层次结构
- `vprism.core.error_codes`: 标准化错误代码系统
- `vprism.core.error_handler`: 错误处理和日志系统
- `vprism.core.circuit_breaker`: 熔断器实现
- `vprism.core.retry`: 指数退避重试机制

#### 使用模式
```python
# 异常处理
from vprism.core.exceptions import ProviderError
from vprism.core.error_handler import ErrorHandler

# 熔断器
from vprism.core.circuit_breaker import circuit_breaker

# 重试机制
from vprism.core.retry import retry, ResilientExecutor
```

### Enforcement

This workflow is mandatory for all contributors. Violations will be caught during code review and must be resolved before merge.