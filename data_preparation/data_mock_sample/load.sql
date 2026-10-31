\set ON_ERROR_STOP on
BEGIN;
\ir sql/001_schema.sql
\ir .generated/seed.sql
\ir sql/003_access.sql
\ir mart/002_views.sql
COMMIT;
