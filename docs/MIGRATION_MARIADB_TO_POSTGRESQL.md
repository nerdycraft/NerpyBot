# Migrating from MariaDB/MySQL to PostgreSQL

NerpyBot no longer supports MariaDB/MySQL. This guide covers migrating your data to PostgreSQL.

## Prerequisites

- PostgreSQL 15+ installed and running
- Access to your existing MariaDB/MySQL database
- A database management tool like [DBeaver](https://dbeaver.io/) (recommended)

## Step 1: Create the PostgreSQL Database

```bash
createdb -U postgres nerpybot
```

## Step 2: Migrate Data with DBeaver (Recommended)

DBeaver can connect to both databases and transfer data with proper type mapping:

1. Connect to both your MariaDB/MySQL and PostgreSQL databases in DBeaver
2. Right-click the source database (MariaDB/MySQL) and select **Export Data**
3. Choose the PostgreSQL database as the target
4. DBeaver handles type conversion, quoting differences, and schema creation automatically
5. Review the transfer log for any warnings

## Step 3: Update config.yaml

```yaml
database:
  db_type: postgresql
  db_name: nerpybot
  db_username: postgres
  db_password: your_password
  db_host: localhost
  db_port: 5432
```

## Step 4: Run Migrations

Ensure the schema is up to date:

```bash
uv run alembic upgrade head
```

## Step 5: Verify

Start the bot and check for errors:

```bash
uv run python NerdyPy/bot.py -d
```

Look for successful startup messages and test a few commands.
