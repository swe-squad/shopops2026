# Regression snapshot provenance

`full_snapshot.json` is a service-contained copy of the raw documents under
`data_preparation/data_mock_sample/{shopee-open-platform,lazada,shopify}/raw/`
and its access JSONL files. Original user IDs were replaced consistently with
synthetic international phone IDs. Document resource revisions are 1. Source
counts come from the existing normalized core JSONL and access records.

Business payloads, ownership, dates and formulas remain unchanged: four shops,
1,344 orders, 1,400 lines, nine source documents and 29 expected issue candidates.
This regression input is separate from the source service's 140-order MVP seed.
It is a test asset only and is excluded from the processor image.
