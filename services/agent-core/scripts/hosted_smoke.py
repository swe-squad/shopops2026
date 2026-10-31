"""Bounded synthetic hosted acceptance. Saved execution, never prose, is authoritative."""

import asyncio
import json
import os
import re
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("skills/returns-analysis/SKILL.md", "skills/knowledge-review/SKILL.md")
HELPER = "skills/returns-analysis/scripts/summarize_returns.py"
PROBE = (
    "import os,socket; "
    "assert not any(k in os.environ for k in "
    "('OPENAI_API_KEY','MCP_TOKEN_SIGNING_KEY','AUTH_JWKS_URL','DATABASE_URL')); "
    "s=socket.socket(); s.settimeout(2)\n"
    "try:\n s.connect(('1.1.1.1',443))\n"
    "except OSError:\n print('hosted-boundary-denied')\n"
    "else:\n raise SystemExit(1)\n"
    "finally:\n s.close()"
)


class EvidenceInvalid(Exception):
    """A fixed, content-free acceptance failure."""


def _require(condition: object) -> None:
    if not condition:
        raise EvidenceInvalid("hosted_evidence_incomplete")


def _text(item: dict) -> str:
    return "\n".join(
        c.get("text", "") for c in item.get("content", []) if c.get("type") == "output_text"
    )


def bundle_execution_code() -> str:
    """Verify approved bytes and execute those same bytes in one isolated invocation."""
    manifest = json.loads((ROOT / "runtime-bundles/shopops-hosted-v1/manifest.json").read_text())
    expected = {f["path"].removeprefix("shopops-analysis/"): f["sha256"] for f in manifest["files"]}
    return (
        "import hashlib,sys\nfrom pathlib import Path\n"
        f"expected={expected!r}\n"
        "root=Path(sys.argv[1]); source=sys.argv[2]; output=sys.argv[3]\n"
        "assert root.is_absolute() and root.resolve()==root\n"
        "files={}\n"
        "for name,digest in expected.items():\n"
        " p=root/name\n"
        " assert p.is_file() and not p.is_symlink()\n"
        " assert not any(a.is_symlink() for a in p.parents)\n"
        " data=p.read_bytes()\n"
        " assert hashlib.sha256(data).hexdigest()==digest\n"
        " files[name]=data\n"
        f"helper={HELPER!r}\n"
        "script=str(root/helper)\n"
        "sys.argv=[script,'--input',source,'--output',output]\n"
        "try:\n exec(compile(files[helper],script,'exec'),"
        "{'__name__':'__main__','__file__':script})\n"
        "except SystemExit as error:\n"
        " if error.code not in (None,0): raise\n"
        "print('shopops-bundle-helper-verified')"
    )


def verify_execution(
    *,
    session: dict,
    environment: dict,
    root_turn_id: str,
    turns: list[dict],
    items: list[dict],
    children: list[dict],
    knowledge_references: frozenset[str],
    require_probe: bool = True,
) -> dict:
    """Consume saved SDK records in memory; return only aggregate evidence."""
    env = session.get("environment", {})
    _require(env.get("type") == "openai_hosted" and env.get("id"))
    _require(env.get("network", {}).get("access") == "disabled")
    _require(environment.get("id") == env["id"] and environment.get("status") == "connected")
    _require(environment.get("type") == "openai_hosted")
    roots = [t for t in turns if "subagent_id" in t and t["subagent_id"] is None]
    _require(len(roots) == 1 and roots[0].get("id") == root_turn_id)
    _require(roots[0].get("status") == "completed" and roots[0].get("session_id") == session["id"])
    commands = []
    for item in items:
        if (
            item.get("type") == "command_execution"
            and item.get("turn_id") == root_turn_id
            and item.get("status") == "completed"
            and item.get("exit_code") == 0
            and item.get("id")
        ):
            try:
                words = _command_words(item["command"])
            except ValueError, KeyError:
                continue
            # Compound shell syntax needs a richer verifier; leave it unverified.
            if words and not any(w in {";", "&&", "||", "|"} for w in words):
                commands.append((words, item.get("output", "")))
    verified_roots = {
        w[5]
        for w, output in commands
        if _python(w)
        and len(w) == 8
        and w[1:5] == ["-I", "-B", "-c", bundle_execution_code()]
        and _plain_path(w[5])
        and _plain_path(w[6])
        and w[7] == "/workspace/outputs/report.json"
        and output.strip() == "shopops-bundle-helper-verified"
    }
    _require(verified_roots)
    for skill in SKILLS:
        expected_text = (
            ROOT / "runtime-bundles/shopops-hosted-v1/shopops-analysis" / skill
        ).read_text()
        _require(
            any(
                len(w) == 2
                and w[0] in {"cat", "/bin/cat", "/usr/bin/cat"}
                and any(w[1] == root + "/" + skill for root in verified_roots)
                and output == expected_text
                for w, output in commands
            )
        )
    probe = any(
        _python(w)
        and w[1:] == ["-I", "-B", "-c", PROBE]
        and output.strip() == "hosted-boundary-denied"
        for w, output in commands
    )
    _require(probe or not require_probe)
    identities = set()
    roles = set()
    for child in children:
        _require(child.get("id") and child["id"] not in identities)
        identities.add(child["id"])
        _require(child.get("session_id") == session["id"])
        _require(child.get("parent_agent_id") == session["agent"]["id"])
        completed = {
            t["id"]
            for t in child.get("turns", [])
            if t.get("status") == "completed"
            and t.get("session_id") == session["id"]
            and t.get("subagent_id") == child["id"]
        }
        outputs = "\n".join(
            _text(i)
            for i in child.get("items", [])
            if i.get("turn_id") in completed
            and i.get("type") == "message"
            and i.get("role") == "assistant"
        )
        _require(completed and outputs)
        instructions = _text({"content": child.get("instructions") or []})
        _require(sum(role in instructions for role in ("data-analyst", "knowledge-analyst")) == 1)
        if "data-analyst" in instructions:
            _require(all(re.search(rf"(?<!\d){n}(?!\d)", outputs) for n in (5, 15, 10)))
            roles.add("data-analyst")
        if "knowledge-analyst" in instructions:
            references = set(re.findall(r"knowledge:[A-Za-z0-9._:#-]+", outputs))
            _require(references and references <= knowledge_references)
            roles.add("knowledge-analyst")
    _require(len(identities) >= 2 and roles == {"data-analyst", "knowledge-analyst"})
    return {
        "runtime_type": "openai_hosted",
        "environment_connected": True,
        "skill_reads_verified": True,
        "helper_execution_verified": True,
        "completed_children": len(identities),
        "root_completion_verified": True,
        "boundary_probe_verified": probe,
    }


def _command_words(command: str) -> list[str]:
    """Unwrap one observed system bash invocation; never execute shell text."""
    if not isinstance(command, str):
        return []
    words = shlex.split(command)
    if len(words) == 3 and words[0] in {"/bin/bash", "/usr/bin/bash"} and words[1] == "-lc":
        return shlex.split(words[2])
    return words


def _plain_path(value: str) -> bool:
    return (
        value.startswith("/")
        and ".." not in Path(value).parts
        and not any(c in value for c in ";|&<>$`\n\r")
    )


def _python(words: list[str]) -> bool:
    if not words:
        return False
    executable = words[0]
    return (
        "/" not in executable
        or Path(executable).parent.as_posix() in {"/usr/bin", "/usr/local/bin"}
    ) and re.fullmatch(r"python(?:3(?:\.\d+)?)?", Path(executable).name) is not None


def _dict(value) -> dict:
    return value if isinstance(value, dict) else value.model_dump(mode="json")


async def _records(iterator, limit: int = 300) -> list[dict]:
    result = []
    async for value in iterator:
        _require(len(result) < limit)
        result.append(_dict(value))
    return result


async def collect_execution(
    provider, session_id: str, root_turn_id: str, *, knowledge_references: frozenset[str]
) -> dict:
    """Inspect saved provider records before the first follow-up creates another root."""
    async with asyncio.timeout(30):
        sessions = provider.sessions
        session = _dict(await sessions.retrieve(session_id))
        env_id = session.get("environment", {}).get("id")
        _require(env_id)
        environment = _dict(await provider.client.beta.agents.environments.retrieve(env_id))
        turns = await _records(sessions.turns.list(session_id, limit=100))
        items = await _records(sessions.items.list(session_id, limit=100))
        children = await _records(sessions.subagents.list(session_id, limit=100), 2)
        for child in children:
            child["turns"] = await _records(
                sessions.subagents.turns.list(child["id"], session_id=session_id, limit=100)
            )
            child["items"] = await _records(
                sessions.subagents.items.list(child["id"], session_id=session_id, limit=100)
            )
        return verify_execution(
            session=session,
            environment=environment,
            root_turn_id=root_turn_id,
            turns=turns,
            items=items,
            children=children,
            knowledge_references=knowledge_references,
        )


async def cleanup_remote(sessions, session_ids: set[str]) -> dict:
    """Attempt every artifact and session independently; uncertain outcomes remain failed."""
    confirmed = 0
    requested = 0
    ok = True
    for sid in sorted(session_ids):
        try:
            async with asyncio.timeout(10):
                artifacts = await _records(sessions.artifacts.list(sid, limit=100))
        except Exception as error:
            artifacts = []
            if getattr(error, "status_code", None) != 404:
                ok = False
        for artifact in artifacts:
            try:
                async with asyncio.timeout(5):
                    result = _dict(await sessions.artifacts.delete(artifact["id"], session_id=sid))
                if result.get("id") != artifact["id"] or result.get("deleted") is not True:
                    ok = False
            except Exception as error:
                if getattr(error, "status_code", None) != 404:
                    ok = False
        accepted = False
        for _ in range(3):
            try:
                async with asyncio.timeout(5):
                    await sessions.delete(sid)
                accepted = True
                requested += 1
                break
            except Exception as error:
                status = getattr(error, "status_code", None)
                if status == 404:
                    accepted = True
                    break
                if status != 409:
                    break
                await asyncio.sleep(0.05)
        absent = False
        try:
            async with asyncio.timeout(5):
                await sessions.retrieve(sid)
        except Exception as error:
            absent = getattr(error, "status_code", None) == 404
        confirmed += int(absent)
        ok = ok and accepted and absent
    return {
        "cleanup": ok,
        "confirmed_session_removals": confirmed,
        "session_cleanup_requests_accepted": requested,
        "physical_sandbox_destruction_confirmed": False,
    }


def run_hosted_smoke(
    *,
    live: bool | None = None,
    hosted: bool | None = None,
    credentials_file: str | None = None,
) -> dict:
    enabled = (live is True and hosted is True) or (
        live is None
        and hosted is None
        and os.environ.get("AGENT_CORE_LIVE") == "1"
        and os.environ.get("AGENT_CORE_LIVE_HOSTED") == "1"
    )
    if not enabled:
        return {
            "status": "skipped",
            "reason": "hosted_opt_in_required",
            "cleanup": True,
            "local_cleanup": True,
        }
    from app.agents.runtime_bundle import build_runtime_bundle
    from app.contracts.runtime import RuntimeProfile
    from app.providers.hosted_runtime import build_hosted_environment

    try:
        manifest = json.loads(
            (ROOT / "runtime-bundles/shopops-hosted-v1/manifest.json").read_text()
        )
        profile = RuntimeProfile(
            profile_id="shopops-hosted-v1",
            environment_type="openai_hosted",
            bundle_id=manifest["bundle_id"],
            bundle_version=manifest["bundle_version"],
            bundle_sha256=manifest["bundle_sha256"],
            container_size="small",
            multi_agent_enabled=True,
            max_concurrent_subagents=2,
        )
        request = build_hosted_environment(profile, build_runtime_bundle(profile))
        _require(
            request.get("type") == "openai_hosted"
            and request.get("network") == {"access": "disabled"}
        )
    except NotImplementedError:
        return {
            "status": "blocked",
            "reason": "t06_hosted_provider_handoff_required",
            "cleanup": True,
            "local_cleanup": True,
        }
    except Exception:
        return {
            "status": "blocked",
            "reason": "hosted_bundle_or_profile_invalid",
            "cleanup": True,
            "local_cleanup": True,
        }
    # Reuse the baseline's explicit key/model-only reader; never copy its source file.
    from scripts.live_smoke import dotenv_values

    try:
        values = dotenv_values(credentials_file) if credentials_file else {}
        key = os.environ.get("OPENAI_API_KEY") or values.get("OPENAI_API_KEY")
        model = os.environ.get("OPENAI_MODEL") or values.get("OPENAI_MODEL")
    except Exception:
        key = model = None
    if not key or not model:
        return {
            "status": "blocked",
            "reason": "missing_key_or_model",
            "cleanup": True,
            "local_cleanup": True,
        }
    return _execute(profile, key, model)


def _execute(profile, key: str, model: str) -> dict:
    import secrets
    import shutil
    import socket
    import tempfile

    import httpx
    import openai

    from app.config.settings import Settings
    from app.main import create_app
    from scripts.live_smoke import serve

    evidence = {
        "status": "failed",
        "model": model,
        "sdk_version": openai.__version__,
        "bundle_version": profile.bundle_version,
        "bundle_sha256": profile.bundle_sha256,
        "cleanup": False,
        "local_cleanup": False,
    }
    directory = ROOT / ".evidence"
    directory.mkdir(exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="hosted-recovery-", dir=directory))
    conversations, run_ids = [], []
    try:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(128)
            base = f"http://127.0.0.1:{sock.getsockname()[1]}"
            registry = json.loads((ROOT / "config/registry.json").read_text())
            registry["revisions"] = [
                registry["revisions"][0]
                | {
                    "revision": "hosted-smoke-v1",
                    "model": model,
                    "data_mcp_url": base + "/mcp/data",
                    "knowledge_mcp_url": base + "/mcp/knowledge-memory",
                    "runtime_profile": profile.model_dump(),
                }
            ]
            config = path / "registry.json"
            config.write_text(json.dumps(registry))
            settings = Settings.from_env(
                {
                    "APP_ENV": "local",
                    "AGENT_PROVIDER": "openai_agents",
                    "AUTH_MODE": "fixture",
                    "DATABASE_URL": f"sqlite:///{path / 'runtime.db'}",
                    "CONFIG_PATH": str(config),
                    "DATA_MCP_MODE": "mock",
                    "DATA_MCP_URL": base + "/mcp/data",
                    "KNOWLEDGE_MEMORY_MCP_URL": base + "/mcp/knowledge-memory",
                    "MCP_TOKEN_SIGNING_KEY": secrets.token_urlsafe(32),
                    "OPENAI_API_KEY": key,
                    "OPENAI_MODEL": model,
                }
            )
            app = create_app(settings=settings)
            with (
                serve(app, sock) as loop,
                httpx.Client(
                    base_url=base,
                    headers={"Authorization": "Bearer local-alice"},
                    timeout=10,
                    trust_env=False,
                ) as client,
            ):
                try:
                    _workflow(client, app, loop, conversations, run_ids, evidence)
                    evidence["status"] = "passed"
                except Exception:
                    evidence["error"] = "hosted_acceptance_failed"
                finally:
                    try:
                        evidence.update(
                            asyncio.run_coroutine_threadsafe(
                                _cleanup_app(app, conversations, run_ids, path),
                                loop,
                            ).result(timeout=180)
                        )
                    except Exception:
                        evidence["cleanup"] = evidence["local_cleanup"] = False
    except Exception:
        evidence["status"] = "failed"
        evidence["local_cleanup"] = False
        evidence["error"] = "hosted_startup_or_shutdown_failed"
    if evidence["cleanup"] and evidence["local_cleanup"]:
        try:
            shutil.rmtree(path)
        except OSError:
            evidence["status"] = "failed"
            evidence["local_cleanup"] = False
            evidence["error"] = "local_state_cleanup_failed"
            evidence["recovery_directory"] = str(path)
    else:
        evidence["status"] = "failed"
        evidence["recovery_directory"] = str(path)
    return evidence


def _workflow(client, app, loop, conversations: list, run_ids: list, evidence: dict) -> None:
    import secrets
    import time

    from app.api.runs import public_error
    from app.contracts.report import RuntimeReport

    def api(method: str, url: str, **kwargs):
        result = client.request(method, "/api/v1" + url, **kwargs)
        result.raise_for_status()
        return result

    def conversation():
        oid = api(
            "POST",
            "/shops/shop-a/orchestrator",
            json={
                "template_id": "shopops",
                "config_revision": "hosted-smoke-v1",
            },
        ).json()["orchestrator_id"]
        cid = api(
            "POST",
            "/shops/shop-a/conversations",
            json={
                "orchestrator_id": oid,
                "client_conversation_id": secrets.token_hex(12),
            },
        ).json()["conversation_id"]
        conversations.append(cid)
        return cid

    def send(cid: str, content: str, mode: str):
        rid = api(
            "POST",
            f"/conversations/{cid}/messages",
            json={
                "client_message_id": secrets.token_hex(12),
                "content": content,
                "output_mode": mode,
            },
        ).json()["run_id"]
        run_ids.append(rid)
        deadline = time.monotonic() + 190
        while time.monotonic() < deadline:
            run = api("GET", f"/runs/{rid}").json()
            evidence["last_run_status"] = (
                run["status"]
                if run["status"]
                in {
                    "queued",
                    "running",
                    "waiting_tool",
                    "reconciling",
                    "completed",
                    "failed",
                    "cancelled",
                }
                else "unknown"
            )
            evidence["last_run_error"] = public_error(run.get("error"))
            if run["status"] in {"completed", "failed", "cancelled"}:
                _require(run["status"] == "completed")
                return rid, run
            time.sleep(0.2)
        raise EvidenceInvalid("hosted_poll_timeout")

    def local(rid):
        return asyncio.run_coroutine_threadsafe(
            app.state.repository.execution_context(rid), loop
        ).result(timeout=10)[0]

    evidence["stage"] = "first_report"
    cid = conversation()
    prompt = (
        "Lập báo cáo tiếng Việt SKU-A từ 2026-10-19 đến 2026-10-25, đối chiếu kỳ trước "
        "và chính sách sizing. Lấy dữ liệu và kiến thức qua công cụ backend, giữ nguồn gốc. "
        "Đọc riêng từng SKILL.md bằng cat, giữ nguyên nội dung. Chạy helper bằng lệnh "
        "python -I -B -c với mã kiểm tra bundle dưới đây và ba đối số: resolved plugin root, "
        "file input JSON, /workspace/outputs/report.json. Mã kiểm tra digest và chạy đúng "
        "các bytes đã kiểm tra. Tạo hai specialist "
        "riêng: data-analyst và knowledge-analyst; ghi tên vai trò vào nhiệm vụ của từng child. "
        "Data specialist phải báo số liệu kỳ trước/kỳ này/chênh lệch; knowledge specialist "
        "phải trích original knowledge reference. Root tổng hợp report.json. "
        "Trước khi lập báo cáo, chạy đúng một lệnh python -I -B -c với mã kiểm tra sau "
        "(chỉ in marker, không in biến môi trường hay giá trị bí mật):\n"
        + PROBE
        + "\nMã kiểm tra bundle và chạy helper:\n"
        + bundle_execution_code()
    )
    rid, run = send(cid, prompt, "report")
    _require(run["response"]["kind"] == "answer")
    first = local(rid)

    async def proof():
        saved = await app.state.repository.get_run(first.scope, rid)
        results = await app.state.repository.load_tool_results(
            first.provider_session_id, saved.provider_turn_id
        )
        knowledge = frozenset(
            s.reference for r in results if not r.error for s in r.sources if s.type == "knowledge"
        )
        return await collect_execution(
            app.state.provider,
            first.provider_session_id,
            saved.provider_turn_id,
            knowledge_references=knowledge,
        )

    evidence["stage"] = "saved_execution_proof"
    evidence.update(asyncio.run_coroutine_threadsafe(proof(), loop).result(timeout=35))
    evidence["stage"] = "artifact_validation"
    files = api("GET", f"/runs/{rid}/artifacts").json()["items"]
    reports = [f for f in files if f["filename"] == "report.json"]
    _require(len(reports) == 1)
    url = f"/artifacts/{reports[0]['id']}/content"
    content = api("GET", url).content
    report = RuntimeReport.model_validate_json(content)
    expected = json.loads((ROOT / "fixtures/runtime/report.json").read_text())
    _require(report.metrics.model_dump() == expected["metrics"])
    _require({s.type for s in report.sources} >= {"data", "knowledge"})
    _require(any(s.reference == expected["sources"][0]["reference"] for s in report.sources))
    for token in ("local-bob", "local-carol"):
        _require(
            client.get("/api/v1" + url, headers={"Authorization": f"Bearer {token}"}).status_code
            == 404
        )
    evidence["stage"] = "same_session_followup"
    followup, answer = send(
        cid,
        "Không gọi tool, dùng ngữ cảnh vừa rồi: tỷ lệ tăng bao nhiêu điểm phần trăm? "
        "Chỉ trả lời văn bản.",
        "text",
    )
    _require(answer["response"]["kind"] == "answer")
    _require(re.search(r"(?<!\d)10(?!\d)|mười", answer["response"]["text"].casefold()))
    _require(local(followup).provider_session_id == first.provider_session_id)
    _require(api("GET", f"/runs/{followup}/artifacts").json()["items"] == [])
    evidence["stage"] = "clarification"
    cid2 = conversation()
    missing, clarification = send(
        cid2,
        "Tôi cần báo cáo hoàn hàng nhưng chưa chọn SKU hoặc ngày nào. Hỏi lại thông tin thiếu.",
        "report",
    )
    _require(clarification["response"]["kind"] == "clarification")
    _require(not clarification["response"]["sources"])
    _require(api("GET", f"/runs/{missing}/artifacts").json()["items"] == [])
    second = local(missing)
    _require(second.provider_session_id != first.provider_session_id)

    async def environments():
        repo = app.state.repository
        return (
            await repo.get_runtime(first.scope, cid),
            await repo.get_runtime(second.scope, cid2),
        )

    evidence["stage"] = "environment_isolation"
    env1, env2 = asyncio.run_coroutine_threadsafe(environments(), loop).result(timeout=10)
    _require(env1 and env2 and env1.id != env2.id)
    evidence.update(
        {
            "execution_verified": True,
            "isolation_verified": True,
            "metrics_verified": True,
            "same_session_followup": True,
            "clarification_verified": True,
            "completed_turns": 3,
            "stage": "verified",
        }
    )


async def _cleanup_app(app, conversations: list[str], run_ids: list[str], path: Path) -> dict:
    from app.contracts.identity import Scope

    provider = app.state.provider
    worker = app.state.worker
    stopped = True
    if worker:
        try:
            async with asyncio.timeout(10):
                await worker.stop()
                while worker.heartbeat is not None:
                    await asyncio.sleep(0.01)
        except Exception:
            stopped = False
    sessions = set(provider.created_sessions)
    discovery_ok = True
    # An accepted application POST can lose its response before the caller learns run_id.
    # Recover those correlations from durable active runs before enumerating remote creates.
    if conversations:
        try:
            async with asyncio.timeout(10):
                for run in await app.state.repository.pending_runs():
                    if run.conversation_id in conversations:
                        if run.id not in run_ids:
                            run_ids.append(run.id)
                        conversation, _ = await app.state.repository.execution_context(run.id)
                        if conversation.provider_session_id:
                            sessions.add(conversation.provider_session_id)
        except Exception:
            discovery_ok = False
    # Correlation enumeration also catches accepted creates whose responses were lost.
    try:
        async with asyncio.timeout(15):
            async for raw in provider.sessions.list(limit=100):
                item = _dict(raw)
                if item.get("metadata", {}).get("initial_run_id") in run_ids:
                    sessions.add(item["id"])
    except Exception:
        discovery_ok = False
    recovery_saved = True
    try:
        (path / "remote-recovery.json").write_text(
            json.dumps({"sessions": sorted(sessions), "run_ids": run_ids})
        )
    except OSError:
        recovery_saved = False
    for sid in sessions:
        try:
            async with asyncio.timeout(10):
                snapshot = await provider.inspect_session(sid)
                if snapshot.root_status in {"running", "waiting_tool"}:
                    await provider.cancel_turn(sid, snapshot.root_turn_id)
                for rid in run_ids:
                    c, _ = await app.state.repository.execution_context(rid)
                    if c.provider_session_id == sid and worker:
                        run = await app.state.repository.get_run(c.scope, rid)
                        await worker.reconcile(run)
        except Exception:
            pass  # Remote deletion below is attempted independently for every known session.
    result = await cleanup_remote(provider.sessions, sessions)
    result["cleanup"] = result["cleanup"] and discovery_ok and stopped and recovery_saved
    result["local_cleanup"] = False
    if result["cleanup"]:

        async def removed(sid):
            _require(sid in sessions)

        local_ok = True
        for cid in conversations:
            try:
                await app.state.repository.delete_conversation(
                    Scope(tenant_id="tenant-a", shop_id="shop-a", user_id="alice"),
                    cid,
                    removed,
                )
            except Exception:
                local_ok = False
        result["local_cleanup"] = local_ok
    return result
