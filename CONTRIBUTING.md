# Development and Testing

## Setup

After cloning the repository, install dependencies and the pre-push hook:

```console
uv sync --locked
uv run pre-commit install --hook-type pre-push
```

The pre-push hook runs `fix-and-check-all` before each push to apply formatting and linting fixes
and check typing and unit tests.

## Primary Development Commands

To check and resolve linting issues in the codebase, run:

```console
uv run ruff check --fix
```

To check and resolve formatting issues in the codebase, run:

```console
uv run ruff format
```

To check the unit tests in the codebase, run:

```console
uv run pytest
```

To check the typing in the codebase, run both type checkers:

```console
uv run mypy
uv run pyrefly check
```

To generate a code coverage report after testing locally, run:

```console
uv run coverage html
```

To check the lock file is up to date:

```console
uv lock --check
```

## Shortcut Task Commands

###### For Running Individual Checks

```console
uv run poe check-lock
uv run poe check-format
uv run poe check-lint
uv run poe check-tests
uv run poe check-mypy
uv run poe check-pyrefly
uv run poe check-typing  # runs both check-mypy and check-pyrefly
```

###### For Running All Checks

```console
uv run poe check-all
```

###### For Running Individual Fixes

```console
uv run poe fix-format
uv run poe fix-lint
```

###### For Running All Fixes

```console
uv run poe fix-all
```

###### For Running All Fixes and Checks

```console
uv run poe fix-and-check-all
```
