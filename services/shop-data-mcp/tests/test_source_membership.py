"""Membership access uses the live mock-data schema, never a derived snapshot."""

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo


@pytest.fixture
def source_membership() -> Iterator[tuple[str, str]]:
    dsn = os.environ.get("TEST_DATABASE_DSN")
    if not dsn:
        pytest.skip("Set TEST_DATABASE_DSN for real PostgreSQL integration checks")
    migrations = Path(os.environ.get("MOCK_SOURCE_DIR", "../mock-data-server")) / "app/migrations"
    assert migrations.is_dir(), "Set MOCK_SOURCE_DIR to the mock-data-server service directory"
    with psycopg.connect(dsn) as conn:
        assert not conn.execute(
            "SELECT 1 FROM pg_namespace WHERE nspname IN ('mock','access')"
        ).fetchall(), "Use an empty disposable database"
    try:
        with psycopg.connect(dsn) as conn:
            conn.execute("CREATE SCHEMA mock")
            for migration in sorted(migrations.glob("*.sql")):
                conn.execute(migration.read_text())
            conn.execute("INSERT INTO mock.users VALUES ('+84900000001','Demo',true,NULL)")
            conn.execute("INSERT INTO mock.merchants VALUES ('merchant','Demo',true,NULL)")
            conn.execute(
                "INSERT INTO mock.merchant_memberships "
                "VALUES ('+84900000001','merchant','owner',true,NULL)"
            )
            conn.execute(
                "INSERT INTO mock.shops VALUES "
                "('shopee-open-platform:1001','merchant','shopee-open-platform','1001',"
                "'Shop','VND','Asia/Ho_Chi_Minh','{}',NULL)"
            )
            conn.execute(Path("migrations/005-source-membership.sql").read_text())
            conn.execute(Path("migrations/003-phone-membership.sql").read_text())
        yield dsn, make_conninfo(dsn, user="mcp_membership")
    finally:
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute("DROP SCHEMA IF EXISTS access CASCADE")
            conn.execute("DROP SCHEMA IF EXISTS mock CASCADE")
            conn.execute("DROP ROLE IF EXISTS mcp_membership")


def test_source_membership_login_reads_only_safe_columns(
    source_membership: tuple[str, str],
) -> None:
    _, restricted = source_membership
    with psycopg.connect(restricted, autocommit=True) as conn:
        assert conn.execute("SHOW default_transaction_read_only").fetchone() == ("on",)
        assert conn.execute("SELECT user_id,shop_key FROM access.user_shop_access").fetchall() == [
            ("+84900000001", "shopee-open-platform:1001")
        ]
        for table in ("users", "merchants", "merchant_memberships", "shops"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql.SQL("SELECT * FROM mock.{}").format(sql.Identifier(table)))
        for privilege in ("INSERT", "UPDATE", "DELETE"):
            assert conn.execute(
                "SELECT has_table_privilege(current_user,'access.user_shop_access',%s)",
                (privilege,),
            ).fetchone() == (False,)


@pytest.mark.parametrize("table", ["users", "merchants", "merchant_memberships", "shops"])
def test_source_tombstones_immediately_revoke_membership(
    source_membership: tuple[str, str], table: str
) -> None:
    operator, restricted = source_membership
    with psycopg.connect(restricted, autocommit=True) as reader:
        assert reader.execute("SELECT count(*) FROM access.user_shop_access").fetchone() == (1,)
        with psycopg.connect(operator) as conn:
            conn.execute(
                sql.SQL("UPDATE mock.{} SET deleted_at=now()").format(sql.Identifier(table))
            )
        assert reader.execute("SELECT count(*) FROM access.user_shop_access").fetchone() == (0,)


@pytest.mark.parametrize("table", ["users", "merchants", "merchant_memberships"])
def test_source_inactive_entities_immediately_revoke_membership(
    source_membership: tuple[str, str], table: str
) -> None:
    operator, restricted = source_membership
    with psycopg.connect(operator) as conn:
        conn.execute(sql.SQL("UPDATE mock.{} SET is_active=false").format(sql.Identifier(table)))
    with psycopg.connect(restricted) as reader:
        assert reader.execute("SELECT count(*) FROM access.user_shop_access").fetchone() == (0,)
