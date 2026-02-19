# Contributing

Thanks for contributing to this project.

## Development setup

1. Fork and clone the repository.
2. Install dependencies:
   - `uv sync --dev`
   - or `pip install -e .[dev]`
3. Run tests: `pytest`

## Pull requests

- Keep changes focused and small.
- Add or update tests when behavior changes.
- Ensure `pytest` passes before opening a PR.
- Update `CHANGELOG.md` when user-facing behavior changes.

## Code style

- Follow existing project style and naming.
- Prefer clear, descriptive symbols.
- Keep public interfaces stable unless intentionally changing them.
