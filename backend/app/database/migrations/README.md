# Database Migrations with Alembic

This document covers the setup and usage of Alembic for database migrations in this project.

---

## Setup

### 1. Initialize Alembic

Run this from inside `app/database`:

```bash
cd app/database
alembic init migrations
```

Move `alembic.ini` to the project root:

```bash
mv alembic.ini ../../alembic.ini
```

---

### 2. Configure `alembic.ini`

Update the script location to point to the migrations folder:

```ini
[alembic]
script_location = app/database/migrations
```

Leave `sqlalchemy.url` empty — the URL is set programmatically in `env.py`.

---

### 3. Configure `env.py`

Replace the contents of `app/database/migrations/env.py` with the following:

```python
import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add the backend root to sys.path so app imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
print(sys.path[0])

from app.database.base import Base
from app.database.models import (
    ChatMessage,
    ChatThread,
    DocumentChunk,
    MessageCitation,
    MessageRole,
    SourceDocument,
    User,
)
from app.core.config import settings
from pgvector.sqlalchemy import Vector  # registers pgvector type

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    """
    Use the database_url from settings and normalize it for SQLAlchemy + psycopg v3.
    Bypasses the computed_field on Settings due to a pydantic-settings limitation.
    """
    url = settings.database_url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

## Generating and Applying Migrations

### Generate the initial migration

Run from the project root:

```bash
alembic revision --autogenerate -m "initial"
```

Alembic will detect all models registered under `Base.metadata` and generate a migration file in `app/database/migrations/versions/`.

---

### Enable the pgvector extension

Because this project uses `pgvector` for embeddings, the `vector` extension must be enabled in the database before the migration runs.

Open the generated migration file and add this at the top of the `upgrade` function:

```python
def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # ... rest of generated migration
```

And in `downgrade`:

```python
def downgrade() -> None:
    # ... rest of generated migration

    op.execute('DROP EXTENSION IF EXISTS vector')
```

---

### Apply the migration

```bash
alembic upgrade head
```

---

## Ongoing Workflow

After making any changes to your SQLAlchemy models, follow these steps:

```bash
# 1. Generate a new migration
alembic revision --autogenerate -m "describe what changed"

# 2. Review the generated file in app/database/migrations/versions/

# 3. Apply it
alembic upgrade head
```

---

## Useful Commands

| Command | Description |
|---|---|
| `alembic revision --autogenerate -m "message"` | Generate a migration from model changes |
| `alembic upgrade head` | Apply all pending migrations |
| `alembic downgrade -1` | Roll back the last migration |
| `alembic current` | Show the current migration version |
| `alembic history` | List all migrations |

---

## Notes

- The `@computed_field` property `sqlalchemy_database_url` on the `Settings` class is not used in `env.py` due to a pydantic-settings limitation where computed fields are not accessible via attribute access in all versions. The URL normalization is duplicated directly in `get_url()` instead.
- `CREATE EXTENSION IF NOT EXISTS vector` is safe to run multiple times. Supabase projects typically have pgvector enabled by default, so this will be a no-op in that environment.
- Always run `alembic upgrade head` from the project root, not from inside `app/database`.