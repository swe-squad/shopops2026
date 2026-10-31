"""Opt-in Docker verification. Default pytest/CI never invokes the Docker daemon."""

import json
import subprocess
from uuid import uuid4

PROGRAM = """import asyncio, json
from pathlib import Path
from app.config.registry import Registry
from app.contracts.identity import Scope
from app.contracts.models import ApplicationResponse
from app.contracts.runtime import RuntimeProfile, ProviderEnvironment, ArtifactRecord
import hashlib
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
    profile = RuntimeProfile(profile_id='shopops-hosted-v1', environment_type='openai_hosted',
        bundle_id='shopops-hosted-v1', bundle_version='1', bundle_sha256='a'*64,
        container_size='small', multi_agent_enabled=True, max_concurrent_subagents=2)
    original = repo.registry.get('shopops', 'returns-v1')
    repo.registry.register(original.model_copy(update={'revision':'hosted-check',
        'runtime_profile':profile}))
    hosted_scope = scope.model_copy(update={'shop_id':'hosted'})
    hosted_o = await repo.provision(hosted_scope, 'shopops', 'hosted-check')
    hosted_c = (await repo.create_conversation(hosted_scope, hosted_o.record.id, 'hosted')).record
    hosted_run = await repo.enqueue_message(hosted_scope, hosted_c.id, 'm', 'synthetic')
    if hosted_run.created:
        await repo.transition_run(hosted_run.run.id, ('queued',), 'running')
        await repo.save_session_mapping(hosted_run.run.id, 'hosted-session')
        await repo.mark_submission(hosted_run.run.id, 'submitted', 'hosted-root')
        await repo.save_runtime(hosted_scope, hosted_c.id,
            ProviderEnvironment(id='hosted-env', state='connected'))
        record = ArtifactRecord(id='11111111-1111-4111-8111-111111111111',
            provider_id='published-file', session_id='hosted-session', turn_id='hosted-root',
            path='/workspace/outputs/note.md', size=2, media_type='text/markdown',
            scope=hosted_scope, conversation_id=hosted_c.id, run_id=hosted_run.run.id,
            sha256=hashlib.sha256(b'OK').hexdigest())
        await repo.save_artifacts(hosted_scope, hosted_run.run.id, (record,))
        await repo.complete_run(hosted_run.run.id, 'hosted-root', 'hosted-item',
            ApplicationResponse(kind='answer', text='Synthetic'))
    artifacts = await repo.list_artifacts(hosted_scope, hosted_run.run.id)
    assert len(artifacts.items) == 1
    assert (await repo.get_runtime(hosted_scope, hosted_c.id)).id == 'hosted-env'
    assert hosted_c.config.runtime_profile == profile
    print(json.dumps({'hosted_profile': profile.bundle_sha256,
        'artifact_digest': artifacts.items[0].sha256, 'orchestrator': orchestrator.record.id,
        'conversation': conversation.id,
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
            "IDs/mapping/history/config/queue/runtime/artifact metadata"
        )
    finally:
        subprocess.run(["docker", "volume", "rm", volume], check=True, capture_output=True)


if __name__ == "__main__":
    main()
