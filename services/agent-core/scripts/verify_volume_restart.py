"""Opt-in Docker verification. Default pytest/CI never invokes the Docker daemon."""

import json
import subprocess
from uuid import uuid4

PROGRAM = """import asyncio, json
from pathlib import Path
from app.config.registry import Registry
from app.contracts.identity import Scope
from app.contracts.models import ApplicationResponse
from app.storage.database import Database
from app.storage.repositories import SQLiteRepository
async def check():
    database = Database(Path('/data/volume-check.db'))
    await database.initialize()
    repo = SQLiteRepository(database, Registry.load('config/registry.json'))
    scope = Scope(tenant_id='synthetic', shop_id='synthetic', user_id='synthetic')
    orchestrator = await repo.provision(scope, 'shopops', 'returns-v1')
    conversation = (await repo.create_conversation(scope, orchestrator.record.id, 'check')).record
    first = await repo.enqueue_message(scope, conversation.id, 'completed', 'synthetic')
    if first.created:
        claim = await repo.claim_next_run()
        await repo.save_session_mapping(claim.id, 'synthetic-provider-session')
        await repo.mark_submission(claim.id, 'submitted', 'synthetic-turn')
        await repo.complete_run(claim.id, 'synthetic-turn', 'synthetic-item',
            ApplicationResponse(kind='answer', text='Kiem tra luu tru.'))
    queued = await repo.enqueue_message(scope, conversation.id, 'queued', 'synthetic follow-up')
    history = await repo.get_history(scope, conversation.id)
    current = await repo.get_conversation(scope, conversation.id)
    run = await repo.get_run(scope, queued.run.id)
    assert run.state == 'queued' and len(history.items) == 3
    assert current.provider_session_id == 'synthetic-provider-session'
    print(json.dumps({'orchestrator': orchestrator.record.id, 'conversation': conversation.id,
        'completed_run': first.run.id, 'queued_run': queued.run.id,
        'mapping': current.provider_session_id, 'history': [m.content for m in history.items],
        'revision': current.config.revision, 'queued_state': run.state}, sort_keys=True))
asyncio.run(check())
"""


def main() -> None:
    volume = "agent-core-t01-" + uuid4().hex[:12]
    subprocess.run(["docker", "volume", "create", volume], check=True, capture_output=True)
    try:
        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--mount",
            f"type=volume,source={volume},target=/data",
            "agent-core",
            "python",
            "-c",
            PROGRAM,
        ]
        first = subprocess.run(command, check=True, capture_output=True, text=True)
        second = subprocess.run(command, check=True, capture_output=True, text=True)
        if json.loads(first.stdout) != json.loads(second.stdout):
            raise RuntimeError("Volume persistence mismatch")
        print(
            "PASS: two network-isolated UID1001 containers preserve "
            "IDs/mapping/history/config/queue"
        )
    finally:
        subprocess.run(["docker", "volume", "rm", volume], check=True, capture_output=True)


if __name__ == "__main__":
    main()
