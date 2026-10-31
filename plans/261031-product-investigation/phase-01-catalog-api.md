# Catalog API
Status: complete

Implement the catalog contract via private cronjob HTTP, current access checks, pagination and coherent revisions. Preserve legacy routes and auth. Own services/shopops-api/** only. Document disabled/source setup without secrets. Test unauthorized access, cross-shop/SKU denial, malformed/upstream failures, pagination, revision changes, unknown stock, order-level return attribution and freshness. Rollback: disable optional catalog mode; legacy SQLite data unchanged.
