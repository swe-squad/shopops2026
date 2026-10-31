# Hosted acceptance (T08)

This runbook covers synthetic acceptance of AC15–AC22. Offline tests, including the synthetic
saved-item fixtures, are not proof of OpenAI-hosted execution. AC01–AC14 remain baseline regressions.

## Dependencies and current boundary

T08 imports the T05 foundation `1e45865` and lifecycle amendment `ebd7537`, plus T07 implementation
`c955460` and handoff `944481f`, and T06 provider `dc05790`/handoff `6e122fc`.
Its application workflow uses the registered T07 manifest, version
and digest; it does not activate the example registry's placeholder digest.

T06's hosted environment/provider implementation is now imported for offline integration. If a
consumer still has the foundation stub, an enabled runner returns
`blocked / t06_hosted_provider_handoff_required` before reading credentials or creating a provider.
With the integrated provider, missing credentials return `blocked / missing_key_or_model`.
No fallback to `none`, fake execution or local shell is
used by the live runner. `test_hosted_workflow.py` explicitly injects synthetic provider files and
tool results to exercise the application/SQLite/worker boundary offline.

The T05 API currently maps `environment_failed`, `environment_timeout` and
`environment_unavailable` to `internal_error` in `app/api/runs.py:public_error`. Strict expected
failures preserve these three acceptance requirements without treating them as passes. T05 must
extend its safe error mapping; these tests will XPASS strictly and require removal of their xfail
marks after that shared amendment is imported. Do not weaken the expected errors.

## Offline checks

From this service directory, use its private Python 3.14 environment:

```bash
.venv/bin/pytest tests/runtime/test_hosted_live_gate.py tests/integration/test_hosted_workflow.py -v
PATH="$PWD/.venv/bin:$PATH" make ci
```

The scoped suite checks report-mode validation and source provenance; text and clarification
semantics; same-session follow-up and replay; distinct conversations/environments; cross-user and
cross-tenant rejection before remote reads; artifact size/digest/root ownership; expired download
without history mutation; app recreation with persisted profile/artifact metadata; setup
failure/timeout/expiry; and two child events/stream loss waiting for authoritative root completion.
Baseline T05 tests additionally cover unknown restart/submission and artifact-finalization recovery.

Gate tests run sanitized subprocesses. Neither flag or either single flag must skip hosted work
without reading the credentials file or constructing an OpenAI client. The CLI rejects missing
acknowledgements before importing the runner. Enabling only legacy live skips the hosted pytest.

Cleanup failure tests include known 404, bounded 409, unknown outcome, artifact deletion failure and
worker shutdown failure. Other known resources still receive cleanup attempts. A successful session
delete response alone does not establish confirmed removal or physical sandbox destruction.

## Explicit live execution

Only run after the T06 handoff, integrated application verification and explicit hosted authorization.
Use synthetic data and an operator-configured model/account supporting the installed SDK surfaces.
The existing ignored credentials file may supply only `OPENAI_API_KEY` and `OPENAI_MODEL`; it is read
explicitly, never copied or included in the plugin. Other credentials-file settings are ignored.

```bash
python -m scripts.demo_live_hosted --live --hosted \
  --credentials-file <ignored-file> --evidence .evidence/live-hosted.json
```

Alternatively, supply key/model through the process and opt in to both pytest gates:

```bash
AGENT_CORE_LIVE=1 AGENT_CORE_LIVE_HOSTED=1 .venv/bin/pytest tests/live/test_hosted_runtime.py -v
```

CLI flags enable that invocation only and do not change process environment or the legacy smoke.
Exit zero requires `status=passed`, confirmed remote cleanup and local cleanup. Skipped/blocked/failed
results exit 2. Default CI skips both live suites. Offline success never changes live acceptance state.

The runner starts an isolated loopback application with mock Data/Knowledge MCP, a private SQLite
database and pinned hosted revision. It provisions and sends messages through `/api/v1`. The first
report requests actual skill reads, helper execution and two specialists with original MCP sources.
It downloads the canonical report through the artifact API and checks numeric metrics/data source
against `fixtures/runtime/report.json`; generated wording is not compared. The knowledge fixture's
`#synthetic` chunk is only an offline oracle; live knowledge references must originate in persisted
ToolResults and retain their actual chunk IDs. The text follow-up reuses the first session. A second
conversation asks for missing inputs and must clarify without artifacts, using a distinct session
and environment. Foreign fixture identities must receive 404 for the report download.

Saved records are inspected before the first follow-up, so there must be exactly one authoritative
root at that point. The verifier requires a hosted/disabled-network environment connected to the
same session; separate successful `cat` items whose output matches both approved skills; the
digest-verified Python helper writing the canonical report; and two distinct child identities with
their own completed turns and saved results. Each child must carry exactly one specialist role.
Child knowledge references must match successful persisted ToolResults in that same session/root,
rather than merely having a plausible prefix. Encrypted, absent or ambiguous records fail verification.

Helper execution uses the exact `bundle_execution_code()` payload with `python -I -B -c`, followed
by the resolved plugin root, input JSON path and `/workspace/outputs/report.json`. It checks all six
registered file digests and rejects symlinks before compiling/executing the already-verified helper
bytes in the same invocation. Its fixed saved success marker ties execution to approved contents,
not a filename suffix. Only standard Python executable names/system paths are recognized; arbitrary
workspace executables and compound shell commands remain unverified. The first prompt supplies both
the bundle execution and boundary-probe payloads; neither executes in the backend.

The harmless boundary probe is a direct isolated Python command containing the exact `PROBE` code
in `scripts/hosted_smoke.py`. It checks absence of named backend configuration/secret variables and
attempts a two-second TCP connection to `1.1.1.1:443`, printing only a fixed denial marker. Both the
saved command and its successful marker are required; an assistant assertion or `echo` is insufficient.
This is synthetic egress-denial evidence, not a comprehensive network security audit.

SDK assumptions were checked against pinned 3.42.0 and
[official saved-items documentation](https://developers.openai.com/api/docs/guides/agents-api/sessions/events).
Account availability and actual runtime behavior remain unverified until an authorized live run.

## Evidence and recovery

Only aggregate JSON is printed/written to the requested evidence file: status/reason; model and SDK;
bundle version/digest; completed turn/child counts; verified runtime/skill/helper/probe/root/metrics/
follow-up/isolation/clarification flags; accepted cleanup request count; confirmed session removal
count; local cleanup; and, when unresolved, the recovery-directory path. No prompts, reports, tool
payloads, command output, inter-agent content, credentials or remote/private URLs belong in evidence.
No account authorization is inferred from a model name. Record the operator's account/model
capability preflight privately when conducting live acceptance.

Recovery state lives in the ignored service-local `.evidence/hosted-recovery-*` directory (private
directory permissions), including SQLite correlation mappings and private `remote-recovery.json`.
Every submitted run/conversation is tracked immediately. Cleanup stops the worker, discovers sessions
by initial-run correlation, attempts cancellation/reconciliation, deletes artifacts independently,
requests session removal (at most three delete attempts for 409), and confirms 404 absence. Pending
durable runs recover correlations when an accepted application POST loses its run-ID response.
Recovery-file write errors cannot prevent remote cleanup attempts; they still fail acceptance.
Backend shutdown errors also fail acceptance and preserve local state. It then
deletes local conversation records only after all remote outcomes are confirmed. Worker/discovery,
artifact, session or local failures keep the recovery directory and fail acceptance. Accepted session
cleanup does not establish physical sandbox destruction; that aggregate flag always remains false.

For failed cleanup, preserve the directory and credentials in their original ignored location.
Resolve every recorded session and run before removing local recovery state; do not retry the entire
smoke as a substitute for cleanup, copy credentials, delete the DB or replace an expired session.
Do not commit raw live artifacts or recovery/evidence files. Do not merge or deploy from T08.
