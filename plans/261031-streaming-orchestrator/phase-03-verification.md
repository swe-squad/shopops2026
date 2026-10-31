# Integration and handoff

Owner controller; reviewer read-only. Files: nginx, Vite proxy, env examples, service docs, root docs and plan records.

- [x] Configure separate private upstreams and streaming proxy behavior.
- [x] Validate viewer origins/CSP and verify both direct URLs and embedded app documents.
- [x] Run frontend/backend checks and independent code review; fix evidence-backed findings.
- [x] Inspect desktop/mobile browser behavior and document verification limits.
- [x] Update setup docs and capture journal; protect completed work in a scoped commit.

Risk: Docker daemon is unavailable; document container check gap. Live OpenAI requires user project credentials and saved agent access; never expose those values in browser or logs.
