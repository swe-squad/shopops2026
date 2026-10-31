# ShopOps API

Operations backend for manually entered incidents, a navigation mailbox between the standalone browser and mobile chat apps, and an optional read-only catalog from the persistent mock shop through private cronjob HTTP. Chat runs independently in [shopops-chat-api](../shopops-chat-api/README.md). This is a single-workspace service; it does not implement user accounts or multi-tenant isolation.

Set `SHOP_API_TOKEN` to a strong secret and `SHOP_DATA_PATH` to a SQLite file on a persistent writable volume (default `/data/shopops.sqlite3`). Startup rejects blank tokens and blank configured database paths. The container runs as UID 1001; the volume must be writable by that user. An ephemeral container filesystem loses data on redeploy. Keep the API internal and use HTTPS at the frontend. The bearer token grants access to the entire workspace and its configured source user's shops. Do not share it across independent users.

`GET /health` is public. `GET` and `POST /api/operations/incidents` require `Authorization: Bearer <token>`. Lists return the latest 100 records. Chat routes are absent. Existing `messages` tables in an operations database are preserved; they are not automatically copied into the new chat database. Run `make ci` for checks; `make run` listens locally on port 8000.

`POST /api/operations/navigation` accepts `{url}` and returns HTTP 201 `{id,url}` using the same bearer authentication. URLs must be absolute HTTP(S) without embedded credentials or begin with the origin-relative `/shop/` path (`/shop` is also accepted). Whitespace, control characters, backslashes, unsafe schemes, and protocol-relative URLs are rejected. The service never fetches or proxies the URL. `GET /api/operations/navigation` returns the latest `{id,url}` or `null`. SQLite stores one current event with IDs increasing across replacements and restarts. The standalone browser polls once per second and navigates only when it sees a new ID; mobile chat posts link targets through its own same-origin proxy.

`/openapi.json` and `/docs` on this internal service describe the Bearer security scheme, response models, and authentication/validation errors. See the [service integration pattern](../../docs/service-integration-pattern.md) for extension ownership and verification.

## Optional product catalog

Direct Python startup defaults `SHOP_CATALOG_MODE` to `disabled`. Catalog requests then return sanitized HTTP 503; health, incidents and navigation remain available. The Docker image defaults to `source`, so deployed Products require the real configured source and fail startup when its required configuration is missing. There is no default source URL or user identity in the image. Configure these backend runtime values (placeholders in `.env.example`; no dotenv is loaded automatically):

| Variable | Source mode |
| --- | --- |
| `SHOP_CATALOG_MODE` | `source` |
| `CRONJOB_SERVER_URL` | Required HTTP(S) origin; locally `http://localhost:8001` |
| `SHOP_DATA_USER_ID` | Required E.164 identity already granted access in the mock source |

Source mode rejects missing or invalid configuration at startup. In CapRover, set `CRONJOB_SERVER_URL` to `http://srv-captain--cronjob-server-dev:8000` for development or `http://srv-captain--cronjob-server:8000` for production. Keep cronjob private. Credentials, source identity and this upstream URL never belong in the frontend. Browser identity headers/query parameters cannot change the configured actor. Registration, per-user identity/vault mapping and hosted MCP transport remain separate integration work; this workspace token is not a multi-user session.

All routes require the existing bearer token:

| GET route | Result |
| --- | --- |
| `/api/operations/catalog/shops` | `{shops, source_revision, fetched_at}` |
| `/api/operations/catalog?shop_key=...` | `{shop, products, source_revision, fetched_at, data_mode}` |
| `/api/operations/catalog/product?shop_key=...&sku=...` | `{shop, product, reviews, orders, returns, source_revision, fetched_at, data_mode}` |

`data_mode` is `mock_source`. These routes read current grants and complete paginated `/v1/mock/{resource}` lists from cronjob; they do not read sibling service files, processed marts or local catalog fixtures. Each request first reads fresh source shops and their revision. The adapter reuses an in-memory shop snapshot only for the exact source URL, configured user, shop and revision; its least-recently-used cache holds at most eight shops. A per-provider lock prevents simultaneous polls from duplicating history reads. Source/access errors never return cached success, and a changed revision requires a complete rebuild. Cache misses use one `source_revision` across all reads, including a final grant/revision check. Concurrent changes restart the complete read at most twice; continued changes or malformed/incomplete source responses return sanitized HTTP 503. Missing/inaccessible selections return 404; invalid selection input returns 422. No partial or fabricated fallback is returned. For catalog/product responses, `fetched_at` stays at the original coherent evidence fetch time on cache hits; it is neither the latest access-check time nor the age of business events. Shop-list responses use their fresh fetch time.

Money is a decimal string in major currency units. `image_url` passes through an optional source image and stays null when the source field is absent or null; the API never fetches images or invents image URLs. The frontend accepts HTTPS image URLs and keeps its placeholder when an image is missing or fails to load. No current listing price is inferred: `last_sold_price` is historical order-line evidence. It uses the newest known purchase line (`open`, `shipped` or `completed`), excluding cancelled/unknown parent orders; ties use order ID then line ID. `last_sold_at` is that order's creation time. `orders[].status` is the product line's status (important for mixed Lazada orders); multiple same-SKU lines remain separate, while `order_count` counts unique orders.

Stock sums only the newest observation per location. Missing inventory or any unknown contributing location keeps `available` null; zero stays zero. `inventory_observed_at` is the oldest of those latest observations, so the sum cannot appear fresher than its oldest component. Reviews are SKU scoped; negative reviews have ratings 1–2. Returns and `return_order_count` describe related orders only: the source has no returned-SKU evidence, so a return may appear for several products in one order.

Tests can inject `create_app(..., catalog_transport=httpx.MockTransport(handler))` while using source configuration, or inject a `catalog_provider` implementing `shops()` and `catalog(shop_key, sku=None)`. This keeps the HTTP adapter and identity boundary replaceable without granting browser-controlled principals. `make ci` verifies the offline source/error/security contracts; live cronjob/DB access is not implied by these tests.

## Read-only deployment preflight

Run `python -m app.catalog_check` inside the configured API runtime before accepting a Products deployment. It reads current authorized shops and every catalog through the same HTTP adapter as the UI, including complete evidence pagination and revision checks. The API connects only to private cronjob HTTP; the data services own persistent PostgreSQL access. This command never connects directly to PostgreSQL, reads local fixtures, mutates records or requires the operations SQLite file/workspace token.

The command prints one JSON object containing only `status`, aggregate `shops`/`products` counts and `source_revision`. It emits no shop names, source user IDs, record details, URLs or credentials. Exit 0 means products are available. Exit 1 with `empty` means the source was reachable but no products were visible; that fails demo readiness by default, while `--allow-empty` explicitly accepts this legitimate empty state with exit 0. Exit 2 means `disabled`, `invalid_configuration`, `unavailable` (including access changes) or `revision_changed`; resolve the configuration/source state and rerun. A changing revision is not reported as a coherent aggregate. This is an operational check, not a container startup hook, and running offline tests does not prove the live dataset is configured.
