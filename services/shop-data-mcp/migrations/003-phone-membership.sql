-- Apply once in the AUTHORITATIVE SOURCE database, not the derived/control DB.
-- access.user_shop_access must filter inactive users, memberships and merchants.
-- Provision the password out of band, then set membership_dsn in the MCP config.
CREATE ROLE mcp_membership LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE
    NOCREATEDB NOREPLICATION NOINHERIT;
ALTER ROLE mcp_membership SET default_transaction_read_only = on;
GRANT USAGE ON SCHEMA access TO mcp_membership;
GRANT SELECT (user_id, shop_key) ON access.user_shop_access TO mcp_membership;

-- Rollback: remove membership_dsn/use the previous image, then revoke the two
-- grants and drop this role after terminating its connections. Do not drop data.
