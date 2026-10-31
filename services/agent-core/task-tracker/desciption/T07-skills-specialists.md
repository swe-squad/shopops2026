# T07 Versioned Skills and Specialist Roles

> **For agentic workers:** Use `superpowers:executing-plans` for inline execution or `superpowers:subagent-driven-development` when delegation is selected. Track work with checkboxes.

**Goal:** Package approved executable skills and specialist instructions so the managed harness can generate a grounded report and perform real delegation.

**Architecture:** A deterministic service-local skill-only plugin supplies SKILL.md files, a Python standard-library report helper and role references. The root obtains scoped MCP evidence; harness-created children analyze supplied data without function tools.

**Tech Stack:** Python 3.14, FastAPI, SQLite, official OpenAI SDK, pytest, Docker and existing MCP transport.

**Spec:** [Managed runtime extension](../../agents_api_managed_runtime_spec.md), [main spec](../../agents_api_template_spec.md), [tracker](../task_list.md#hosted-runtime-extension-t05t08).

**Status:** Ready for integration. **Difficulty:** D4 — Hard. Bundle integrity, executable skills, shared-workspace roles and actual API tool restrictions must agree across offline and hosted paths.

## Global constraints

Read the root and service AGENTS.md, the main template spec, runtime extension spec, and the tracker's **Hosted runtime extension (T05–T08)** section first. All paths below are relative to `services/agent-core/`; root workflows/templates/scripts and other services are read-only. Use Python 3.14, pinned dependencies, Ruff line length 100, one SQLite owner/worker/replica and existing API scopes. Keep default CI offline except loopback. You are not alone in the codebase: preserve other owners' changes and import shared amendments from T05 rather than copying files.

Do not copy env files between worktrees or print credentials, prompts, model output, tool data or command output in logs/evidence. Existing `none` live evidence is not hosted acceptance. Work in the assigned separate worktree and keep a private venv/DB/evidence directory. Use commits `type(agent-core): message` and preserve the workspace until the lead integrates the committed handoff. Do not merge, deploy or change another service.

## Worktree and dependencies

Use `feat/agent-core-t07-skills-specialists`, label `agent-core-t07`; Git fallback `/tmp/shopops2026-agent-core/T07`. Start from the published T05 runtime foundation SHA. Work in parallel with T06 against shared bundle/profile doubles; live discovery/delegation requires T06 and T08 integration.

## File ownership

- New `app/agents/runtime_bundle.py`; existing `app/agents/{instructions,capabilities}.py`.
- `runtime-bundles/shopops-hosted-v1/manifest.json` and its `shopops-analysis/` skill-only plugin tree, exactly as in the spec.
- `tests/agents/test_runtime_bundle.py`, `tests/agents/test_hosted_instructions.py`, `tests/agents/test_report_skill.py`.

T05 owns runtime/report contracts, settings/registry and Docker packaging; request amendments there. T06 owns SDK request translation. Do not add an MCP connection, credentials or network installer to the plugin.

## Interfaces

Consume RuntimeProfile/RuntimeBundle and `contracts/runtime-report.schema.json` from T05. Produce synchronous `build_runtime_bundle(profile: RuntimeProfile) -> RuntimeBundle`, returning a verified deterministic ZIP wrapped in the documented inline plugin payload.

Use existing `build_instructions(config)` and capability selection to preserve baseline behavior and add hosted-only root instructions. Keep `delegation_targets(config)` as a configuration helper returning the two approved role labels for hosted mode and an empty tuple for legacy mode; it does not launch agents. The managed harness owns create/message/wait execution.

## Review focus

- Identical bundle input must produce identical archive bytes/digest across machines.
- A symlink/traversal/duplicate ZIP entry or changed file must fail closed.
- Main-agent function tools are unavailable to children; role instructions cannot invent access.
- Source IDs in artifacts must come from root-validated ToolResults, not generated prose.
- A role label or SKILL.md included in a prompt alone cannot establish real execution.

## Steps

- [x] **1. Write bundle validation regressions and verify RED.** Cover manifest sorted-path hashing excluding itself, plugin name/description consistency, symlinks, absolute/parent paths, extra/missing/duplicate files, digest mismatch and the 262144-byte uncompressed limit. Assert repeat builds are byte-identical. Run `.venv/bin/pytest tests/agents/test_runtime_bundle.py -v`.
- [x] **2. Implement registered plugin packaging.** Add build_runtime_bundle, reviewed SKILL.md files and role references. Keep bundle contents inside the registered root, exclude all env/key/cache/DB files, and use stable ZIP timestamps/order. Package only approved standard-library helpers.
- [x] **3. Write report helper regressions and verify RED.** The report helper consumes the existing metrics shape and bounded policy findings/source references, recomputes 5%/15% and 10 percentage points, rejects inconsistent counts/missing sources, and emits exactly the frozen JSON schema. Run `.venv/bin/pytest tests/agents/test_report_skill.py -v`. Local execution of this trusted helper is unit evidence only.
- [x] **4. Implement executable skills and role policy.** returns-analysis instructs the root to read the skill and invoke its bundled script; knowledge-review requires references/versioned policy evidence. The root retrieves MCP results, passes bounded evidence to data-analyst and knowledge-analyst, waits for both and writes the canonical report. Children use separate scratch directories and do not acquire a new trust scope.
- [x] **5. Write instruction/profile regressions and verify RED.** Assert legacy profile has no hosted/delegation instructions; hosted profile requests two harness-created specialists, denies fictional child function calls, never embeds tokens/private MCP URLs, requires Vietnamese synthesis/source reuse, and allows clarification/simple text-only answers without forced metrics retrieval, report generation or specialist creation. Run `.venv/bin/pytest tests/agents/test_hosted_instructions.py -v`, then implement the minimal conditional instructions/capability helpers.
- [x] **6. Verify and hand off.** Run `.venv/bin/pytest tests/agents -v` and `make lint`; hand T06 the exact manifest/version/digest and T08 deterministic expected report/skill markers. Commit `feat(agent-core): package hosted analysis skills`. Do not mark AC17/AC18 passed until real saved skill/script/subagent evidence is reviewed.


## Handoff record

- Actual worktree: `/tmp/shopops2026-agent-core/T07`; branch: `feat/agent-core-t07-skills-specialists`.
- Base/imported T05 foundation: `1e45865` (`feat(agent-core): publish hosted runtime contracts`). No uncommitted T05 changes were imported.
- Implementation commit: `c955460` (`feat(agent-core): package hosted analysis skills`). Changed paths are limited to the owned `app/agents/` modules, registered bundle tree, three `tests/agents/` files, and this task description; no central tracker/shared wiring changes.
- Validation: Python 3.14.7; bundle RED (unimplemented builder/missing bundle), report RED (missing helper), instruction RED (3 failed) followed by `tests/agents` **58 passed** and `make lint` PASS. Both skills pass skill-creator `quick_validate.py`. `PATH="$PWD/.venv/bin:$PATH" make ci` PASS: **263 passed, 1 skipped** in 31.07s, Ruff lint/format PASS. The skip is the explicit opt-in live test. Sandbox TestClient hangs were isolated to the execution environment; the complete offline CI ran outside the sandbox with its external-network test guard active. Independent static review found no P0/P1; it did not rerun CI.
- `graphify update .` completed in this service's ignored graph directory. SQL extraction is partial because `tree_sitter_sql` is unavailable; no semantic/API extraction ran.
- AC17/AC18 remain **UNVERIFIED**: no hosted OpenAI call, saved SKILL.md read, hosted Python command or child IDs were produced. Local helper execution and prompt assertions are offline module evidence only. Requires T06 provider and T08 integrated hosted acceptance.
- T05 integration requests: copy `runtime-bundles/` into the runtime image (current foundation Dockerfile does not), register the bundle/version/digest below in a new hosted revision, wire the builder into T06, and coordinate any non-default `RUNTIME_BUNDLE_PATH` with the builder's service-relative `BUNDLE_ROOT`. Shared settings, registry and packaging were left to T05.
- No credentials, root env files, runtime DBs or graph outputs are committed. No merge, push or deployment was performed.

Update this description only for your handoff; the runtime integration lead updates the central task table. Mark Ready for integration after module verification, not Done until required integration evidence is accepted.


### Bundle and consumer handoff

- Bundle ID `shopops-hosted-v1`, version `1.0.0`; plugin `shopops-analysis`.
- Aggregate SHA-256: `a0fa0d1149fd7f8cccefc4fe1c0da05d7108cb404d458b5a2b9353bb600b718a`.
- Aggregate encoding: UTF-8 concatenation of `path + NUL + lowercase_file_sha256 + LF` for the sorted six manifest records. `manifest.json` is excluded. This digest pins the file inventory/content, rather than the transport ZIP bytes.
- ZIP retains `shopops-analysis/` as its sole top-level plugin folder. Files are sorted with fixed 1980 timestamps, Unix regular-file mode 0644, no extra fields and ZIP_STORED compression, preventing filesystem/zlib differences. Inline payload uses SDK 3.42.0 `HostedPluginParam` (`inline`, matching name/description, base64 application/zip source). Layout checked against [official plugin documentation](https://developers.openai.com/api/docs/guides/agents-api/tools/plugins).
- T08 markers: reads of `skills/returns-analysis/SKILL.md` and `skills/knowledge-review/SKILL.md`, successful Python command invoking `skills/returns-analysis/scripts/summarize_returns.py`, two real distinct children using the role references, then a root-owned `/workspace/outputs/report.json`. Markers in prompt text alone are insufficient.
- Helper input is UTF-8 JSON (at most 32 KiB) with exactly `metrics`, `knowledge_findings`, `sources`. Invoke with `python -I -B <resolved-script> --input <root-input> --output /workspace/outputs/report.json`; the root creates the directory. No dependencies/network/credentials are required. It emits exactly the frozen RuntimeReport fields. Sources/finding membership are checked locally; stored ToolResult provenance remains root/worker responsibility.
- Deterministic synthetic test oracle: baseline 100 orders/5 returns => 5%; current 100/15 => 15%; change +10 percentage points. Tests compare actual helper output with `RuntimeReport`; these numbers are never substituted for retrieved live metrics.

- Final portability regression: Python 3.10 grammar rejects the formatter's Python-3.14-only exception syntax (RED); binding the caught exception preserves portable syntax (GREEN). The helper remains standard-library-only; hosted interpreter availability is verified by T08. The refreshed manifest above is authoritative.
- Final changed-path audit: `git diff --name-only 1e45865...HEAD` contains only the 13 T07 implementation/test/bundle paths; this handoff adds only the owned T07 description. `git diff --check` passes. Worktree/branch retained for the integration lead; central tracker changes remain T05-owned.
