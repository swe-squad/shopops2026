-- Source snapshots populate this column; never independently backfill derived data.
ALTER TABLE core.products ADD COLUMN image_url text;
