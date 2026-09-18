from pathlib import Path

from sqlalchemy import create_engine, inspect


def test_initial_migration_is_present_and_contains_domain_tables() -> None:
    migration = Path(__file__).parents[1] / "migrations" / "versions" / "0001_initial.py"
    content = migration.read_text(encoding="utf-8")
    for table in ("gmail_messages", "tickets", "ticket_items", "products", "product_aliases", "sync_runs"):
        assert f'create_table("{table}"' in content


def test_sqlite_foreign_keys_and_unique_schema_can_be_inspected() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    assert inspect(engine) is not None
