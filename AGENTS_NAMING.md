# Naming Rules for vprism

These conventions guide AI agents and contributors when adding or renaming
symbols in the codebase.

- Use `vprism` in all non-code text, documentation, and comments.
- Prefix all class names with `VPrism` and use `PascalCase`.
- Prefix modules, functions, and variables with `vprism_` using `snake_case`.
- Prefix environment variables with `VPRISM_` in `SCREAMING_SNAKE_CASE`.
- Test helper classes may include `VPrism` after `Test` to conform with pytest conventions.

Examples:

- `class VPrismClient` defines a public client class.
- `def vprism_fetch_data()` declares a helper function.
- `vprism_cache_dir = Path("~/.vprism")` sets a variable.
- `VPRISM_CACHE_ENABLED=true` configures an environment variable.
