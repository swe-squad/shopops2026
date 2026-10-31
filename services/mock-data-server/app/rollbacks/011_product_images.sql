-- Manual only, in one transaction after stopping writers and backing up image URLs.
SELECT pg_advisory_xact_lock(8173601);
ALTER TABLE mock.products DROP COLUMN image_url;
DELETE FROM mock.schema_migrations WHERE name = '011_product_images.sql';
