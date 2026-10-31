# Product images

`mock.products.image_url` and the processor's `core.products.image_url` are
nullable text columns. Product create/read/patch contracts expose an optional
HTTPS URL (maximum 2048 characters, no embedded credentials); `null` clears it.
Old clients and old snapshots may omit it. The services store URLs without
fetching the remote images. Orders, inventory and reviews reference products by
`(shop_key, sku)` and can obtain the image by joining that key; they do not store
duplicate image columns. Raw supplement documents retain the URL as evidence.

## Catalog and image sources

The authoritative MVP fixture defines these three generic products, repeated
across seven merchants and 21 shops (63 product rows). These are representative
stock photos matching the descriptions, not photographs of a specific branded
item. The URLs are fixed photo URLs, not random-image or search endpoints.

| SKU | Fixture product | Photo and credit | License |
|---|---|---|---|
| SHIRT-M | Cotton T-shirt, size M | [White cotton T-shirt — Skylar Kang](https://www.pexels.com/photo/white-cotton-t-shirt-in-studio-6046231/) | [Pexels](https://www.pexels.com/license/) |
| CAP | Baseball cap | [Tan baseball cap — Thom Bradley](https://www.shopify.com/stock-photos/photos/tan-colored-hat-on-monochrome-background) | [Burst](https://www.shopify.com/stock-photos/licenses/shopify-some-rights-reserved) |
| TOTE | Canvas tote bag | [Black canvas tote — Stephanie Ho](https://www.pexels.com/photo/black-tote-bag-1214212/) | [Pexels](https://www.pexels.com/license/) |

The exact image URLs live in `app/fixtures/mvp_base.json`. All three returned
HTTP 200 and `image/jpeg` on 2026-10-31. External hosts can change or remove them;
replace the stored URL if a host stops serving an image.

## Redeploy, then backfill existing PostgreSQL data

1. Redeploy **cronjob-server first**, then **mock-data-server**. Their existing
   container startup commands apply `007_product_images.sql` and
   `011_product_images.sql` respectively. Confirm `/health/ready` for both.
   Old migration files are unchanged. Startup does not populate existing rows.
2. In the source container, using its existing runtime PostgreSQL configuration,
   preview the backfill:

   ```sh
   python -m app.cli backfill-product-images
   ```

3. Apply the reviewed backfill in the source container:

   ```sh
   python -m app.cli backfill-product-images --apply
   ```

   An untouched seeded database reports `matched: 63, updated: 63`. Only NULL
   URLs in the known demo shops with matching SKU, name and cost basis qualify.
   Existing URLs, renamed products, deleted products/shops and unrelated shops
   are preserved. A repeat reports `updated: 0` without advancing the revision.
   The source rows, new supplement documents and source revision commit in one
   transaction. Any exception rolls the entire backfill back.

4. Trigger `POST /v1/sync-runs` with `{}` on cronjob-server through the private
   network, including `X-Demo-User-Id` for an active demo user and a fresh
   `Idempotency-Key`. Poll the returned `status_url` until `succeeded` and check
   the applied revision is at least the backfill's `source_revision`. A periodic
   sync also works if configured. See [processor examples](../cronjob-server/README.md#mcp-facing-contract).
   Never update `core.products` directly: the next snapshot would overwrite it.
5. Compare image coverage in the source and derived databases (each query runs
   against its owning database):

   ```sql
   SELECT shop_key, count(*) AS products, count(image_url) AS with_image
   FROM mock.products WHERE deleted_at IS NULL GROUP BY shop_key ORDER BY shop_key;

   SELECT shop_key, count(*) AS products, count(image_url) AS with_image
   FROM core.products GROUP BY shop_key ORDER BY shop_key;
   ```

   The untouched MVP expects 21 shops with three images each. Confirm the same
   values through `GET /v1/core/products` for representative users from each
   merchant. Fresh databases get the image URLs from the normal explicit seed.

## Rollback

Prefer rolling back application images while retaining the additive nullable
columns. Existing versions ignore them. To undo a backfilled URL, PATCH that
product's `image_url` to its previous value through the source/facade API and
synchronize; this preserves revision and raw-evidence history.

Manual schema down scripts are in each service's `app/rollbacks/` directory,
outside the automatic migration directory. Stop both services, back up product
URLs, and execute each script in a single transaction only when intentionally
removing the field. These scripts discard image-column values and remove only
their migration ledger entry. Reapplying migrations restores nullable columns.
If the derived column was removed after a sync, a new source revision containing
images must be published to restore it; replaying an unchanged revision is a
no-op. Retaining the columns avoids this recovery step.
