"""Operator-only provisioning of a query login for the cronjob derived database."""

import argparse
import os
import re

import psycopg
from psycopg import sql


def provision(conn: psycopg.Connection, shop_key: str, role: str) -> None:
    """Create a fresh restricted login; never repurpose an existing database identity."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", role):
        raise ValueError("Use a lowercase PostgreSQL role identifier")
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("mcp-role:" + role,))
        shop = conn.execute(
            "SELECT merchant_id FROM core.shops WHERE shop_key=%s", (shop_key,)
        ).fetchone()
        if not shop:
            raise ValueError("Shop must be synchronized before provisioning")
        merchant = shop["merchant_id"] if isinstance(shop, dict) else shop[0]
        mapping = conn.execute(
            "SELECT shop_key,merchant_id FROM mcp_access.shop_roles WHERE role_name=%s", (role,)
        ).fetchone()
        if mapping:
            # Works with either tuple or dict row factories.
            mapped_shop = mapping["shop_key"] if isinstance(mapping, dict) else mapping[0]
            mapped_merchant = mapping["merchant_id"] if isinstance(mapping, dict) else mapping[1]
            if mapped_shop != shop_key or mapped_merchant != merchant:
                raise ValueError("Query login is already bound to another shop")
            return
        if conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
            raise ValueError("Use a new dedicated query login")
        identity = sql.Identifier(role)
        conn.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS "
                "NOCREATEDB NOCREATEROLE NOREPLICATION"
            ).format(identity)
        )
        conn.execute(
            "INSERT INTO mcp_access.shop_roles(role_name,shop_key,merchant_id) VALUES (%s,%s,%s)",
            (role, shop_key, merchant),
        )
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA mcp_data, mcp_access TO {}").format(identity))
        conn.execute(
            sql.SQL("GRANT EXECUTE ON FUNCTION mcp_access.current_shop() TO {}").format(identity)
        )
        conn.execute(
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA mcp_data TO {}").format(identity)
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shop", required=True)
    parser.add_argument("--role", required=True)
    args = parser.parse_args()
    try:
        with psycopg.connect(os.environ["MCP_PROVISION_DSN"], connect_timeout=5) as conn:
            provision(conn, args.shop, args.role)
    except Exception:
        raise SystemExit(
            "Provisioning failed; check operator access, migrations, shop and role"
        ) from None
    print("Query login provisioned; set its password out of band before configuring MCP")


if __name__ == "__main__":
    main()
