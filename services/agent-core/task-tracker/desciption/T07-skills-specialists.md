# T07 Versioned Skills and Specialist Roles

> **For agentic workers:** Use `superpowers:executing-plans` for inline execution or `superpowers:subagent-driven-development` when delegation is selected. Track work with checkboxes.

**Goal:** Package approved executable skills and specialist instructions so the managed harness can generate a grounded report and perform real delegation.

**Architecture:** A deterministic service-local skill-only plugin supplies SKILL.md files, a Python standard-library report helper and role references. The root obtains scoped MCP evidence; harness-created children analyze supplied data without function tools.

**Tech Stack:** Python 3.14, FastAPI, SQLite, official OpenAI SDK, pytest, Docker and existing MCP transport.

**Spec:** [Managed runtime extension](../../agents_api_managed_runtime_spec.md), [main spec](../../agents_api_template_spec.md), [tracker](../task_list.md#hosted-runtime-extension-t05t08).

**Status:** Not started. **Difficulty:** D4 — Hard. Bundle integrity, executable skills, shared-workspace roles and actual API tool restrictions must agree across offline and hosted paths.

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

- [ ] **1. Write bundle validation regressions and verify RED.** Cover manifest sorted-path hashing excluding itself, plugin name/description consistency, symlinks, absolute/parent paths, extra/missing/duplicate files, digest mismatch and the 262144-byte uncompressed limit. Assert repeat builds are byte-identical. Run `.venv/bin/pytest tests/agents/test_runtime_bundle.py -v`.
- [ ] **2. Implement registered plugin packaging.** Add build_runtime_bundle, reviewed SKILL.md files and role references. Keep bundle contents inside the registered root, exclude all env/key/cache/DB files, and use stable ZIP timestamps/order. Package only approved standard-library helpers.
- [ ] **3. Write report helper regressions and verify RED.** The report helper consumes the existing metrics shape and bounded policy findings/source references, recomputes 5%/15% and 10 percentage points, rejects inconsistent counts/missing sources, and emits exactly the frozen JSON schema. Run `.venv/bin/pytest tests/agents/test_report_skill.py -v`. Local execution of this trusted helper is unit evidence only.
- [ ] **4. Implement executable skills and role policy.** returns-analysis instructs the root to read the skill and invoke its bundled script; knowledge-review requires references/versioned policy evidence. The root retrieves MCP results, passes bounded evidence to data-analyst and knowledge-analyst, waits for both and writes the canonical report. Children use separate scratch directories and do not acquire a new trust scope.
- [ ] **5. Write instruction/profile regressions and verify RED.** Assert legacy profile has no hosted/delegation instructions; hosted profile requests two harness-created specialists, denies fictional child function calls, never embeds tokens/private MCP URLs, requires Vietnamese synthesis/source reuse, and allows clarification/simple text-only answers without forced metrics retrieval, report generation or specialist creation. Run `.venv/bin/pytest tests/agents/test_hosted_instructions.py -v`, then implement the minimal conditional instructions/capability helpers.
- [ ] **6. Verify and hand off.** Run `.venv/bin/pytest tests/agents -v` and `make lint`; hand T06 the exact manifest/version/digest and T08 deterministic expected report/skill markers. Commit `feat(agent-core): package hosted analysis skills`. Do not mark AC17/AC18 passed until real saved skill/script/subagent evidence is reviewed.


## Handoff record

- Actual worktree / branch: not recorded.
- Base SHA / imported T05 foundation SHA: not recorded.
- Result commit SHA / changed-path audit: not recorded.
- Scoped test commands/results / relevant acceptance IDs: not recorded.
- Live evidence or exact missing prerequisite / unresolved integration issues: not recorded.

Update this description only for your handoff; the runtime integration lead updates the central task table. Mark Ready for integration after module verification, not Done until required integration evidence is accepted.
