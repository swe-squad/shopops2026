# Deployment data route
Status: complete

User requires persistent records on the existing server's PostgreSQL listener15432. Prepare
configuration only; user explicitly skipped live inspection. Product reads use privateHTTP through
shopops-api→cronjob-server→mock-data-server. Do not give browser/API catalog database credentials.

- Container defaults to source catalog mode; required URL and server-owned source principal fail
  startup when absent. Keep local disabled mode for existing noncatalog tests/workflows.
- Add read-only catalog preflight reporting counts/revision/status only; no seed/reset or fixture
  fallback. Allow explicitly empty datasets when intended.
- Record POSTGRES_PORT15432 on both source/processor runtime setup, preserving host/database/TLS/
  credentials in the operator's existing source of truth.
- Carry optional upcoming source image_url through catalog DTO without depending on an unmerged PR.
- Integrate merged PR12/14, preserve connections demo and chat identity work, rerun affected checks.

Rollback: explicit disabled catalog mode or prior compatible image; never reset PostgreSQL.
