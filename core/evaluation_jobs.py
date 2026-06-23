"""Deduplicated background evaluation jobs shared by the web UI."""
from threading import Lock, Thread


_active_jobs: set[str] = set()
_jobs_lock = Lock()


def schedule_evaluation(session_id: str) -> bool:
    """Schedule one full evaluation per session. Returns False if already running."""
    with _jobs_lock:
        if session_id in _active_jobs:
            return False
        _active_jobs.add(session_id)

    Thread(target=_run_evaluation, args=(session_id,), daemon=True).start()
    return True


def is_evaluation_running(session_id: str) -> bool:
    with _jobs_lock:
        return session_id in _active_jobs


def _run_evaluation(session_id: str) -> None:
    try:
        from core.evaluator import Evaluator

        Evaluator().evaluate(session_id, include_extras=True, extract_phrases=False)
    except Exception as exc:
        print(f"[evaluation] Background job failed for {session_id[:8]}: {exc}", flush=True)
    finally:
        with _jobs_lock:
            _active_jobs.discard(session_id)
