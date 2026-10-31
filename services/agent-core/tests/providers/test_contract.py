import asyncio

import pytest

from app.contracts.errors import InvalidTransition
from app.contracts.models import ApplicationResponse, ConfigSnapshot, Source
from app.contracts.tools import ToolResult
from app.providers.fake import FakeProvider, Scenario


@pytest.fixture
def config():
    return ConfigSnapshot(
        revision="r1",
        template_id="shopops",
        model="configured-model",
        knowledge_bundle="returns",
        knowledge_version="1",
        mcp_profile="fixture",
        data_mcp_url="http://localhost:8001",
        knowledge_mcp_url="http://localhost:8002",
        capabilities=("get_return_metrics",),
    )


def test_sessions_turns_tools_and_cleanup(config):
    async def exercise():
        provider = FakeProvider(
            [
                Scenario(
                    tool_name="get_return_metrics",
                    arguments={
                        "sku": "SKU-A",
                        "start_date": "2026-10-01",
                        "end_date": "2026-10-15",
                    },
                )
            ]
        )
        a = await provider.create_session(config, "conversation-a")
        b = await provider.create_session(config, "conversation-b")
        assert a.id != b.id
        assert (await provider.inspect_session(a.id)).root_status == "idle"
        async with provider.stream_events(a.id) as stream:
            await stream.wait_ready()
            turn = await provider.submit_input(a.id, "synthetic request", "run-a")
            snapshot = await provider.inspect_session(a.id)
            assert snapshot.input_run_id == "run-a"
            (call,) = snapshot.pending_calls
            assert call.turn_id == turn
            result = ToolResult(
                data={"summary": "Tỷ lệ hoàn trả tăng từ 5% lên 15%."},
                sources=(Source(type="data", reference="fixture:metrics"),),
            )
            await provider.submit_tool_result(call, result)
            await provider.submit_tool_result(call, result)
            events = []
            async for event in stream:
                events.append(event)
                if event.kind == "completed":
                    break
        assert events[-1].is_root
        items = await provider.list_items(a.id)
        assert len(items) == 1
        assert items[0].response.sources[0].reference == "fixture:metrics"
        assert await provider.list_items(b.id) == ()
        await provider.submit_input(a.id, "follow up", "run-b")
        assert len(await provider.list_items(a.id)) == 2
        await provider.delete_session(a.id)

    asyncio.run(exercise())


def test_cancel_and_busy(config):
    async def exercise():
        p = FakeProvider([Scenario(interrupted=True)])
        s = await p.create_session(config, "c")
        turn = await p.submit_input(s.id, "hello", "r")
        with pytest.raises(InvalidTransition):
            await p.submit_input(s.id, "again", "r2")
        await p.cancel_turn(s.id, turn)
        assert (await p.inspect_session(s.id)).root_status == "cancelled"

    asyncio.run(exercise())


def test_clarification_and_failure(config):
    async def exercise():
        p = FakeProvider(
            [
                Scenario(
                    response=ApplicationResponse(
                        kind="clarification", text="Bạn cho biết SKU và khoảng ngày cần xem?"
                    )
                ),
                Scenario(tool_name="get_return_metrics"),
            ]
        )
        s = await p.create_session(config, "c")
        await p.submit_input(s.id, "question", "r1")
        assert (await p.inspect_session(s.id)).response.kind == "clarification"
        await p.submit_input(s.id, "SKU-A", "r2")
        (call,) = (await p.inspect_session(s.id)).pending_calls
        await p.submit_tool_result(call, ToolResult(error="timeout"))
        assert (await p.inspect_session(s.id)).response.kind == "cannot_answer"

    asyncio.run(exercise())


def test_synthetic_fixture_knowledge_and_replayed_events(config):
    import json
    from pathlib import Path

    async def exercise():
        fixture = json.loads(
            (Path(__file__).parents[2] / "fixtures/provider/scenarios.json").read_text()
        )
        scenarios = [
            Scenario(**dict(row, response=ApplicationResponse.model_validate(row["response"])))
            if row.get("response")
            else Scenario(**row)
            for row in fixture["scenarios"]
        ]
        cfg = config.model_copy(update={"capabilities": ("get_return_metrics", "search_knowledge")})
        p = FakeProvider(scenarios)
        session = await p.create_session(cfg, "fixture")
        for index in range(4):
            await p.submit_input(session.id, "synthetic request", str(index))
            snapshot = await p.inspect_session(session.id)
            if snapshot.pending_calls:
                result = (
                    ToolResult(error="timeout")
                    if index == 3
                    else ToolResult(
                        data={"summary": "Thông tin từ công cụ."},
                        sources=(
                            Source(type="knowledge" if index == 1 else "data", reference="fixture"),
                        ),
                    )
                )
                await p.submit_tool_result(snapshot.pending_calls[0], result)
        async with p.stream_events(session.id) as stream:
            await p.submit_input(session.id, "duplicate", "4")
            events = []
            async for event in stream:
                events.append(event)
                if event.kind == "completed":
                    break
            assert events[0].id == events[1].id
        assert (await p.list_items(session.id))[1].response.sources[0].type == "knowledge"
        assert (await p.list_items(session.id))[3].response.kind == "cannot_answer"

    asyncio.run(exercise())


def test_fake_accepts_structured_tool_data_without_private_summary_field(config):
    async def exercise():
        p = FakeProvider([Scenario(tool_name="get_return_metrics")])
        sid = (await p.create_session(config, "c")).id
        await p.submit_input(sid, "metrics", "run")
        (call,) = (await p.inspect_session(sid)).pending_calls
        await p.submit_tool_result(
            call,
            ToolResult(
                data={"orders": 100, "returns": 15},
                sources=(Source(type="data", reference="fixture:returns"),),
            ),
        )
        response = (await p.inspect_session(sid)).response
        assert response.kind == "answer"
        assert "100" in response.text and "15" in response.text
        assert response.sources[0].reference == "fixture:returns"

    asyncio.run(exercise())
