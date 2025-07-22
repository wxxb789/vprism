# vprism Directory Structure Rules - STRICT ENFORCEMENT

## Absolute Path Requirements

### ✅ CORRECT STRUCTURE
```
Q:/repos/my/vprism/          # Git repository root
├── src/vprism/             # ONLY source code location
├── tests/                  # ONLY test code location
├── .kiro/                  # Steering documentation
├── pyproject.toml          # Project configuration
├── uv.lock                 # Dependency lock file
├── README.md               # Project documentation
├── Dockerfile              # Container configuration
└── docker-compose.yml      # Development environment
```

### ❌ STRICTLY FORBIDDEN
```
Q:/repos/my/vprism/vprism/  # NEVER create this directory
Q:/repos/my/vprism/vprism/src/  # NEVER create nested structure
Q:/repos/my/vprism/vprism/tests/  # NEVER create nested structure
```

## File Location Rules

### Source Code
- **MUST BE**: `Q:/repos/my/vprism/src/vprism/**/*.py`
- **NEVER**: Anywhere else in the repository

### Test Code
- **MUST BE**: `Q:/repos/my/vprism/tests/**/*.py`
- **NEVER**: Anywhere else in the repository

### Configuration Files
- **MUST BE**: Directly in `Q:/repos/my/vprism/`
- **NEVER**: In any subdirectory

## Verification Commands

### Before Any Code Changes
```bash
# Check for duplicate directories
find Q:/repos/my/vprism -maxdepth 2 -name "vprism" -type d

# Verify source code location
ls -la Q:/repos/my/vprism/src/vprism/

# Verify test location
ls -la Q:/repos/my/vprism/tests/

# Check for Python files outside correct locations
find Q:/repos/my/vprism -name "*.py" -type f | grep -v "^Q:/repos/my/vprism/src/" | grep -v "^Q:/repos/my/vprism/tests/"
```

### If Violations Found
```bash
# Remove duplicate directories immediately
rm -rf Q:/repos/my/vprism/vprism/
```

## Development Workflow

### 1. Before Starting Work
Always run directory verification:
```bash
# Verify correct structure
ls Q:/repos/my/vprism/src/vprism/
ls Q:/repos/my/vprism/tests/
```

### 2. When Adding New Files
- Source files: Always add to `src/vprism/`
- Test files: Always add to `tests/`
- Never create new directories at root level

### 3. Before Committing
```bash
# Final verification
if [ -d "Q:/repos/my/vprism/vprism" ]; then
    echo "ERROR: Duplicate directory found!";
    exit 1;
fi
echo "✅ Directory structure verified"
```

## Error Prevention

### IDE Configuration
- Set project root to `Q:/repos/my/vprism/`
- Configure Python path to include `Q:/repos/my/vprism/src/`
- Never configure nested project roots

### Git Hooks (Recommended)
Create `.git/hooks/pre-commit`:
```bash
#!/bin/bash
if [ -d "vprism" ]; then
    echo "ERROR: Duplicate vprism directory detected!"
    exit 1
fi
```

## Emergency Recovery

### If Structure is Broken
1. Immediately remove any duplicate directories
2. Verify all code is in correct locations
3. Update steering documentation
4. Run full test suite to ensure integrity