# Development environment

This project uses Python 3.12.3, `uv`, `pyproject.toml`, and the committed
`uv.lock` so macOS and Ubuntu resolve the same Python package versions. Each
machine keeps its own `.venv`; virtual environments are not copied between
operating systems.

## Prerequisites

- macOS or Ubuntu with `uv` installed.
- Docker Engine and Docker Compose for the local MySQL 8.4 service.
- Python 3.12.3, managed by `uv` if it is not already available.

Install `uv` on macOS with Homebrew (`brew install uv`) or on Ubuntu using the
official `uv` installer. Then, from the repository root, install the matching
Python interpreter if needed:

```sh
uv python install 3.12.3
```

## Configure environment variables

Create the local environment file from the safe example and replace the
placeholder passwords with local development values:

```sh
cp .env.example .env
```

`.env` is ignored by Git. Do not commit it. `MYSQL_ROOT_PASSWORD` is required
by Docker Compose; `MYSQL_PASSWORD` is required by the application. The
application defaults to MySQL at `127.0.0.1:3307` and an OpenAI-compatible
model endpoint at `http://127.0.0.1:8102/v1`. Set `LLM_BASE_URL` to the
reachable model service address for the machine running the application.

## Create a machine-local environment

Run this command on each machine. It creates a separate `.venv` and installs
runtime, test, and migration dependencies from the lockfile:

```sh
uv sync --locked --group dev --group migrations
```

Use the same committed `uv.lock` on macOS and Ubuntu. `uv sync` performs an
exact sync by default and may remove packages in an existing virtual
environment if they are not declared in this project's dependencies or
selected groups.

Do not copy `.venv` between macOS and Ubuntu. Commit changes to
`pyproject.toml` and `uv.lock` together so both machines use the same package
versions.

## Start MySQL, migrate, test, and run

```sh
docker compose up -d mysql
uv run --locked --group migrations alembic upgrade head
uv run --locked pytest
uv run --locked uvicorn app.main:app --reload
```

The Compose file maps the container's MySQL port to `127.0.0.1:3307` on the
host. The LLM endpoint is configured separately; this backend calls it over
HTTP and does not load a model locally.

## GPU inference dependencies

PyTorch, vLLM, CUDA, and Transformers are intentionally not project
dependencies. Manage them in the separate Ubuntu model inference or training
environment. The backend communicates with that service through
`LLM_BASE_URL`.

## Database initialization mount

`docker-compose.yml` mounts `./database/init` into MySQL's
`/docker-entrypoint-initdb.d`, but this repository currently has no
`database/init` directory. Docker may create an empty host directory for the
bind mount, leaving the container with no initialization scripts. If database
bootstrap scripts are needed, create and review that directory and its files
in a separate change. If no scripts are intended, remove or revise the mount
in a separately reviewed Compose change; this environment setup does not
change database initialization behavior.
