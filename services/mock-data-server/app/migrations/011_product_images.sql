-- Additive only: populate existing demo rows explicitly after both services deploy.
ALTER TABLE mock.products ADD COLUMN image_url text;
