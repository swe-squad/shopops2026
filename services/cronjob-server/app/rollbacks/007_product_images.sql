-- Manual only, in one transaction after stopping the processor.
SELECT pg_advisory_xact_lock(8173602);
ALTER TABLE core.products DROP COLUMN image_url;
DELETE FROM sync.schema_migrations WHERE name = '007_product_images.sql';
