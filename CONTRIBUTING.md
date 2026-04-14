# Contributing to Ombra

Thanks for contributing to Ombra.

## Development Setup

1. Create and activate a Python virtual environment in `backend/`.
2. Install core dependencies:
   - `pip install -r requirements.txt`
3. Install optional dependencies only when needed:
   - `pip install -r requirements-optional.txt`
4. Install frontend dependencies in `frontend/`:
   - `npm install`

## Dependency Strategy

- `backend/requirements.txt` is a stable entrypoint that installs only `requirements-core.txt`.
- `backend/requirements-optional.txt` contains integrations that may be unavailable on public indexes.
- Do not move optional/private packages back into the core requirements path.

## Code Quality

- Keep changes focused and minimal.
- Do not commit secrets or tokens.
- Add or update tests when behavior changes.
- Run relevant checks before opening a PR.

## Pull Requests

- Use clear titles and concise descriptions.
- Include impact and verification steps.
- Document config or dependency changes.

## Reporting Issues

- Share reproduction steps.
- Include expected vs actual behavior.
- Provide logs or tracebacks when possible.
