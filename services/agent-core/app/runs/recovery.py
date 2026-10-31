from app.contracts.models import Run
from app.contracts.provider import ProviderSnapshot


def matches_root(run: Run, snapshot: ProviderSnapshot) -> bool:
    if not snapshot.root_turn_id:
        return False
    if run.provider_turn_id is not None:
        return snapshot.root_turn_id == run.provider_turn_id and snapshot.input_run_id in (
            None,
            run.id,
        )
    return snapshot.input_run_id == run.id
