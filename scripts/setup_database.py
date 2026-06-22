#!/usr/bin/env python3
"""
setup_database.py

Initialize PostgreSQL database and user for Recipe project.

Usage:
    python setup_database.py --env /path/to/.env
"""

import psycopg2
from psycopg2 import sql
import argparse
import os
import sys
from dotenv import load_dotenv

def setup_database(
    db_host: str,
    db_port: int,
    db_admin_user: str,
    db_admin_password: str,
    new_db_name: str = "recipe_db",
    new_user: str = "recipe_user",
    new_password: str = ""
) -> bool:
    """
    Create recipe database and user on PostgreSQL.

    Args:
        db_host: PostgreSQL host (e.g., 100.81.127.54)
        db_port: PostgreSQL port (5432)
        db_admin_user: Admin user (e.g., oleksiisnikhovskyi)
        db_admin_password: Admin password
        new_db_name: Database name to create (recipe_db)
        new_user: User to create (recipe_user)
        new_password: Password for new user

    Returns:
        True if successful, False otherwise
    """

    try:
        # Connect to postgres database (system default)
        print(f"🔗 Connecting to PostgreSQL at {db_host}:{db_port}...")
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database="postgres",
            user=db_admin_user,
            password=db_admin_password,
            connect_timeout=10
        )
        conn.autocommit = True
        cursor = conn.cursor()

        print("✅ Connection successful!")

        # Check if database already exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (new_db_name,))
        if cursor.fetchone():
            print(f"⚠️  Database '{new_db_name}' already exists")
            # Continue to check/create user and schema
        else:
            # Create database
            print(f"📦 Creating database '{new_db_name}'...")
            cursor.execute(
                sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' LC_COLLATE = 'uk_UA.UTF-8' LC_CTYPE = 'uk_UA.UTF-8'").format(
                    sql.Identifier(new_db_name)
                )
            )
            print(f"✅ Database '{new_db_name}' created!")

        # Check if user already exists
        cursor.execute("SELECT 1 FROM pg_user WHERE usename = %s;", (new_user,))
        if cursor.fetchone():
            print(f"⚠️  User '{new_user}' already exists")
            # Update password
            print(f"🔄 Updating password for '{new_user}'...")
            cursor.execute(
                sql.SQL("ALTER USER {} WITH ENCRYPTED PASSWORD %s;").format(sql.Identifier(new_user)),
                (new_password,)
            )
            print(f"✅ Password updated!")
        else:
            # Create user
            print(f"👤 Creating user '{new_user}'...")
            cursor.execute(
                sql.SQL("CREATE USER {} WITH ENCRYPTED PASSWORD %s;").format(sql.Identifier(new_user)),
                (new_password,)
            )
            print(f"✅ User '{new_user}' created!")

        # Grant privileges
        print(f"🔐 Granting privileges to '{new_user}'...")
        cursor.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {};").format(
                sql.Identifier(new_db_name),
                sql.Identifier(new_user)
            )
        )
        cursor.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {};").format(sql.Identifier(new_user))
        )
        cursor.execute(
            sql.SQL("GRANT CREATE ON SCHEMA public TO {};").format(sql.Identifier(new_user))
        )
        cursor.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {};").format(
                sql.Identifier(new_user)
            )
        )
        cursor.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO {};").format(
                sql.Identifier(new_user)
            )
        )
        print("✅ Privileges granted!")

        cursor.close()
        conn.close()

        print(f"\n✨ Database setup complete!")
        print(f"   Database: {new_db_name}")
        print(f"   User: {new_user}")
        print(f"   Host: {db_host}:{db_port}")
        print(f"\nNext: Run schema.sql to initialize tables:")
        print(f"   psql -h {db_host} -U {new_user} -d {new_db_name} -f database/schema.sql")

        return True

    except psycopg2.Error as e:
        print(f"❌ PostgreSQL Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def init_schema(
    db_host: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_password: str,
    schema_file: str = "database/schema.sql"
) -> bool:
    """
    Initialize database schema from SQL file.

    Args:
        db_host: PostgreSQL host
        db_port: PostgreSQL port
        db_name: Database name
        db_user: Database user
        db_password: Database password
        schema_file: Path to schema.sql file

    Returns:
        True if successful, False otherwise
    """

    if not os.path.exists(schema_file):
        print(f"❌ Schema file not found: {schema_file}")
        return False

    try:
        print(f"\n📋 Initializing schema from {schema_file}...")

        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
            connect_timeout=10
        )
        cursor = conn.cursor()

        # Read and execute schema file
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        cursor.execute(schema_sql)
        conn.commit()

        print("✅ Schema initialized successfully!")

        cursor.close()
        conn.close()

        return True

    except psycopg2.Error as e:
        print(f"❌ PostgreSQL Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(description="Setup PostgreSQL for Recipe project")
    parser.add_argument("--env", default=".env", help="Path to .env file (default: .env)")
    parser.add_argument("--host", help="PostgreSQL host (overrides .env)")
    parser.add_argument("--port", type=int, help="PostgreSQL port (overrides .env)")
    parser.add_argument("--user", help="Admin username (overrides .env)")
    parser.add_argument("--password", help="Admin password (overrides .env)")
    parser.add_argument("--db-name", default="recipe_db", help="New database name")
    parser.add_argument("--db-user", default="recipe_user", help="New database user")
    parser.add_argument("--db-password", help="New user password (overrides RECIPE_DB_PASSWORD)")
    parser.add_argument("--schema-file", default="database/schema.sql", help="Path to schema.sql")
    parser.add_argument("--skip-schema", action="store_true", help="Skip schema initialization")

    args = parser.parse_args()

    # Load environment variables
    if os.path.exists(args.env):
        print(f"📂 Loading credentials from {args.env}...")
        load_dotenv(args.env)
    else:
        print(f"⚠️  .env file not found: {args.env}")

    # Get PostgreSQL connection details
    db_host = args.host or os.getenv("DB_HOST", "100.81.127.54")
    db_port = args.port or int(os.getenv("DB_PORT", 5432))
    db_user = args.user or os.getenv("DB_USER", "oleksiisnikhovskyi")
    db_password = args.password or os.getenv("DB_PASSWORD", "")

    if not db_password:
        print("❌ Database password not provided. Set DB_PASSWORD in .env or use --password")
        sys.exit(1)

    new_user_password = args.db_password or os.getenv("RECIPE_DB_PASSWORD", "")
    if not new_user_password:
        print("❌ Recipe user password not provided. Set RECIPE_DB_PASSWORD or use --db-password")
        sys.exit(1)

    # Step 1: Setup database and user
    if not setup_database(db_host, db_port, db_user, db_password, args.db_name, args.db_user, new_user_password):
        sys.exit(1)

    # Step 2: Initialize schema
    if not args.skip_schema:
        if not init_schema(db_host, db_port, args.db_name, args.db_user, new_user_password, args.schema_file):
            print("⚠️  Schema initialization failed, but database setup is complete")
            sys.exit(1)

    print("\n🎉 Setup complete! Recipe database is ready to use.")


if __name__ == "__main__":
    main()
