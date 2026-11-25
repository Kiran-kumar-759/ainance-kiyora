import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories.intelligence.intelligence_repository import IntelligenceRepository
from app.schemas.intelligence import IntelligenceRunRequest
from app.services.ai.intelligence_service import IntelligenceService

logger = logging.getLogger(__name__)


class AiIntelligenceWorker:
    """
    PostgreSQL-backed background worker for Phase 8 AI Expense Intelligence jobs.
    Uses FOR UPDATE SKIP LOCKED and respects ENVIRONMENT=test safety rules.
    """

    def __init__(self):
        self._repo = IntelligenceRepository()
        self._service = IntelligenceService()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai-worker")
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    def process_pending_batch(self, *, max_jobs: int = 3) -> int:
        processed = 0
        for _ in range(max_jobs):
            with SessionLocal() as db:
                job = self._repo.claim_next_queued_job(db)
                if job is None:
                    break
                try:
                    self._service.execute_full_pipeline_for_user(
                        db,
                        job.user_id,
                        IntelligenceRunRequest(reanalyze_all=False, use_ai_fallback=True, train_model=True),
                        existing_job=job,
                    )
                    processed += 1
                except Exception as exc:
                    logger.warning("AI job %s failed: %s", job.id, type(exc).__name__)
        return processed

    async def _loop(self) -> None:
        loop = asyncio.get_running_loop()
        while not self._stop_event.is_set():
            try:
                await loop.run_in_executor(self._executor, self.process_pending_batch)
            except Exception as exc:
                logger.warning("AI worker loop error: %s", type(exc).__name__)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=max(5, settings.AI_WORKER_INTERVAL_SECONDS),
                )
            except TimeoutError:
                pass

    def start(self) -> None:
        if settings.ENVIRONMENT == "test" or not settings.AI_WORKER_ENABLED:
            return
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(self._loop(), name="ai-intelligence-worker")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=3.0)
            except TimeoutError:
                self._task.cancel()
        self._executor.shutdown(wait=False)


ai_intelligence_worker = AiIntelligenceWorker()
