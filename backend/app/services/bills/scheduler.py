import asyncio
import logging

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.bills.reminder_service import ReminderService

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """
    Lightweight PostgreSQL-backed asyncio scheduler for due bill reminders.
    Durable state lives in `bill_reminders`, allowing seamless recovery across restarts
    and multi-worker coordination via FOR UPDATE SKIP LOCKED.
    """

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._service = ReminderService()

    async def _loop(self) -> None:
        interval = max(10, settings.REMINDER_SCHEDULER_INTERVAL_SECONDS)
        logger.info("Bill reminder scheduler started (interval=%ss).", interval)
        while not self._stop_event.is_set():
            try:
                db = SessionLocal()
                try:
                    self._service.process_due_reminders(db)
                finally:
                    db.close()
            except Exception as exc:
                logger.error("Bill reminder scheduler cycle error: %s", exc)

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except TimeoutError:
                pass

    def start(self) -> None:
        if (
            not settings.REMINDER_SCHEDULER_ENABLED
            or settings.ENVIRONMENT.lower() == "test"
            or self._task is not None
        ):
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=5.0)
        except Exception:
            self._task.cancel()
        self._task = None


reminder_scheduler = ReminderScheduler()
