CREATE TABLE mock.users (
    user_id text PRIMARY KEY CHECK (user_id ~ '^[+][1-9][0-9]{7,14}$'),
    display_name text NOT NULL CHECK (btrim(display_name) <> ''),
    is_active boolean NOT NULL DEFAULT true,
    deleted_at timestamptz
);
CREATE TABLE mock.merchants (
    merchant_id text PRIMARY KEY CHECK (btrim(merchant_id) <> ''),
    name text NOT NULL CHECK (btrim(name) <> ''),
    is_active boolean NOT NULL DEFAULT true,
    deleted_at timestamptz
);
CREATE TABLE mock.merchant_memberships (
    user_id text REFERENCES mock.users NOT NULL,
    merchant_id text REFERENCES mock.merchants NOT NULL,
    role text NOT NULL CHECK (role IN ('owner','analyst','viewer')),
    is_active boolean NOT NULL DEFAULT true,
    deleted_at timestamptz,
    PRIMARY KEY (user_id, merchant_id)
);
CREATE TABLE mock.state (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    revision bigint NOT NULL DEFAULT 0,
    seeded boolean NOT NULL DEFAULT false
);
INSERT INTO mock.state (singleton) VALUES (true);
