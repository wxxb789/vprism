# vprism Examples

This directory contains example scripts demonstrating how to use the vprism library.

## Running Examples

All examples can be run from the project root directory:

### 1. Data Quality Example
```bash
python examples/data_quality_example.py
```

### 2. Library Usage Example
```bash
python examples/library_usage.py
```

### 3. Provider Usage Example
```bash
python examples/provider_usage.py
```

### 4. Web Service Demo
```bash
# First start the web service
python -m src.web.main web
# Then in another terminal
python examples/web_service_demo.py
```

## Import Path Fixes

All examples have been updated to use correct import paths:
- Added proper `sys.path` configuration to find the `src` directory
- Fixed module paths to match the actual project structure
- Updated import statements to use relative paths where appropriate