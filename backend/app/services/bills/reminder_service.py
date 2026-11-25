import datetime as dt
import uuid
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bills import Bill, BillReminder, Notification
from app.models.user import User
from app.repositories.bills.bill_repository import BillRepository
from app.schemas.bills import ProcessRemindersResponse
from app.services.bills.sms_service import sms_service
from app.services.bills.status_engine import (
    compute_bill_derived_status,
    get_effective_target_amount,
    resolve_user_today,
    resolve_user_zone,
)
from app.services.email_service import email_service


class ReminderService:
    """
    Manages durable reminder schedules, idempotent delivery across channels
    (in-app notifications, SMTP email, SMS adapter), retries, and cancellation.
    """

    def __init__(self):
        self.bill_repo = BillRepository()

    def _compute_reminder_at_utc(
        self, due_date: dt.date, offset_days: int, user_timezone: str | None
    ) -> dt.datetime:
        tz = resolve_user_zone(user_timezone)
        target_date = due_date - dt.timedelta(days=offset_days)
        local_dt = dt.datetime.combine(
            target_date,
            dt.time(hour=settings.REMINDER_DEFAULT_HOUR_IST, minute=0),
            tzinfo=tz,
        )
        return local_dt.astimezone(dt.UTC)

    def _selected_channel_list(self, channels_cfg: dict | None) -> list[str]:
        cfg = channels_cfg or {"in_app": True, "email": False, "sms": False}
        selected = [ch for ch in ("in_app", "email", "sms") if cfg.get(ch, False)]
        return selected or ["in_app"]

    def sync_reminders_for_bill(
        self, db: Session, bill: Bill, user_timezone: str | None = "Asia/Kolkata"
    ) -> None:
        """
        Reconciles durable BillReminder records for a bill:
        - Cancels pending reminders if bill is paid, archived, or reminders disabled.
        - Cancels obsolete due_date/offset reminders when schedule changes.
        - Creates missing reminders idempotently using unique idempotency_key.
        """
        existing = self.bill_repo.list_reminders_for_bill(db, bill.id)
        channels = self._selected_channel_list(bill.notification_channels)

        if (
            not bill.is_active
            or bill.stored_status in {"paid", "archived"}
            or not bill.reminder_enabled
        ):
            for rem in existing:
                if rem.delivery_status in {"pending", "failed"}:
                    rem.delivery_status = "cancelled"
                    rem.is_enabled = False
                    db.add(rem)
            db.flush()
            return

        user_today = resolve_user_today(user_timezone)
        raw_offsets = sorted(
            {int(d) for d in (bill.reminder_days_before or [7, 3, 1, 0]) if 0 <= int(d) <= 60},
            reverse=True,
        )
        if bill.due_date < user_today:
            # Already overdue: schedule a single day-0 overdue reminder rather than backdated offsets
            desired_offsets = [0]
        else:
            desired_offsets = [
                d for d in raw_offsets if (bill.due_date - dt.timedelta(days=d)) >= user_today
            ] or [0]
        desired_keys = {
            f"{bill.id}:{offset}:{bill.due_date.isoformat()}": offset
            for offset in desired_offsets
        }

        existing_by_key = {r.idempotency_key: r for r in existing}

        # Cancel stale pending/failed reminders that no longer apply to current due_date/offsets
        for rem in existing:
            if rem.idempotency_key not in desired_keys and rem.delivery_status in {
                "pending",
                "failed",
            }:
                rem.delivery_status = "cancelled"
                rem.is_enabled = False
                db.add(rem)

        # Create or update active reminders
        for key, offset in desired_keys.items():
            rem_at = self._compute_reminder_at_utc(bill.due_date, offset, user_timezone)
            if key in existing_by_key:
                rem = existing_by_key[key]
                if rem.delivery_status == "pending":
                    rem.channels = channels
                    rem.reminder_at = rem_at
                    rem.is_enabled = True
                    db.add(rem)
            else:
                db.add(
                    BillReminder(
                        user_id=bill.user_id,
                        bill_id=bill.id,
                        offset_days=offset,
                        reminder_at=rem_at,
                        channels=channels,
                        is_enabled=True,
                        delivery_status="pending",
                        idempotency_key=key,
                    )
                )
        db.flush()

    def _format_amount_text(self, bill: Bill) -> str:
        target = get_effective_target_amount(bill)
        if target is None:
            return "Variable amount (amount pending)"
        return f"₹{target:,.2f}"

    def _build_reminder_copy(self, bill: Bill, offset_days: int, user_today: dt.date) -> tuple[str, str, str]:
        amt_txt = self._format_amount_text(bill)
        due_txt = bill.due_date.strftime("%d/%m/%Y")
        days_left = (bill.due_date - user_today).days

        if days_left < 0:
            notif_type = "bill_overdue"
            title = f"Overdue Bill: {bill.bill_name}"
            note = f"Overdue by {abs(days_left)} day(s)"
        elif days_left == 0:
            notif_type = "bill_due_soon"
            title = f"Bill Due Today: {bill.bill_name}"
            note = "Due today"
        elif days_left == 1:
            notif_type = "bill_due_soon"
            title = f"Bill Due Tomorrow: {bill.bill_name}"
            note = "Due tomorrow"
        else:
            notif_type = "bill_reminder"
            title = f"Upcoming Bill: {bill.bill_name} due in {days_left} days"
            note = f"Due in {days_left} days"

        provider = f" ({bill.provider_name})" if bill.provider_name else ""
        msg = (
            f"{bill.bill_name}{provider} of {amt_txt} is due on {due_txt} ({note})."
        )
        return notif_type, title, msg

    def process_due_reminders(
        self,
        db: Session,
        user_id: uuid.UUID | None = None,
        now_utc: dt.datetime | None = None,
    ) -> ProcessRemindersResponse:
        """
        Atomically claims due reminders with FOR UPDATE SKIP LOCKED and dispatches
        enabled channels with idempotency and retry tracking.
        """
        ref_now = now_utc or dt.datetime.now(dt.UTC)
        claimed = self.bill_repo.claim_due_reminders(db, ref_now, user_id=user_id, limit=100)

        delivered_count = 0
        partial_count = 0
        unavailable_count = 0
        failed_count = 0
        notifications_created = 0

        for rem in claimed:
            bill = self.bill_repo.get_bill(db, rem.bill_id, rem.user_id)
            user = db.get(User, rem.user_id)
            user_tz = (
                user.preferences.timezone
                if user and user.preferences
                else "Asia/Kolkata"
            )
            user_today = ref_now.astimezone(ZoneInfo(user_tz or "Asia/Kolkata")).date() if user_tz else resolve_user_today()

            # Never send reminders for paid, archived, or inactive bills
            if not bill or not bill.is_active or bill.stored_status in {"paid", "archived"}:
                rem.delivery_status = "cancelled"
                rem.is_enabled = False
                db.add(rem)
                continue

            derived = compute_bill_derived_status(bill, today=user_today)
            if derived == "paid":
                rem.delivery_status = "cancelled"
                rem.is_enabled = False
                db.add(rem)
                continue

            notif_type, title, body = self._build_reminder_copy(bill, rem.offset_days, user_today)
            outcomes: dict[str, dict[str, str]] = dict(rem.channel_outcomes or {})
            channels = rem.channels or ["in_app"]

            any_delivered = False
            any_failed = False
            any_unavailable = False

            # 1. In-app notification channel (dedupe once per bill, type & calendar day in user timezone)
            if "in_app" in channels:
                dedupe = f"bill-alert:{bill.id}:{user_today.isoformat()}:{notif_type}"
                existing_notif = self.bill_repo.get_notification_by_dedupe(db, dedupe)
                if not existing_notif:
                    self.bill_repo.create_notification(
                        db,
                        Notification(
                            user_id=rem.user_id,
                            title=title,
                            message=body,
                            notification_type=notif_type,
                            related_bill_id=bill.id,
                            dedupe_key=dedupe,
                        ),
                    )
                    notifications_created += 1
                outcomes["in_app"] = {
                    "status": "delivered",
                    "detail": "In-app notification persisted.",
                }
                any_delivered = True

            # 2. Email reminder channel
            if "email" in channels:
                prefs = (user.preferences.notification_preferences if user and user.preferences else {}) or {}
                email_allowed = prefs.get("email_reminders_enabled", True)
                if not user or not email_allowed:
                    outcomes["email"] = {
                        "status": "unavailable",
                        "detail": "Email reminders disabled in user notification preferences.",
                    }
                    any_unavailable = True
                else:
                    ok, st, det = email_service.send_bill_reminder_email(
                        to_email=user.email,
                        full_name=user.full_name,
                        bill_name=bill.bill_name,
                        amount_display=self._format_amount_text(bill),
                        due_date_display=bill.due_date.strftime("%d/%m/%Y"),
                        status_note=body,
                    )
                    outcomes["email"] = {"status": st, "detail": det}
                    if st == "delivered" and ok:
                        any_delivered = True
                    elif st == "failed":
                        any_failed = True
                    else:
                        any_unavailable = True

            # 3. SMS reminder channel
            if "sms" in channels:
                prefs = (user.preferences.notification_preferences if user and user.preferences else {}) or {}
                sms_opted_in = bool(prefs.get("sms_reminders_enabled", False))
                phone_num = prefs.get("phone_number")
                res = sms_service.send_reminder_sms(phone_num, sms_opted_in, body)
                outcomes["sms"] = {"status": res.status, "detail": res.detail, "provider": res.provider}
                if res.delivered:
                    any_delivered = True
                elif res.status == "failed":
                    any_failed = True
                else:
                    any_unavailable = True

            rem.last_attempt_at = ref_now
            rem.channel_outcomes = outcomes

            if any_failed:
                rem.retry_count += 1
                rem.delivery_status = "failed"
                rem.next_retry_at = ref_now + dt.timedelta(minutes=5 * rem.retry_count)
                failed_count += 1
            elif any_delivered and any_unavailable:
                rem.delivery_status = "partial"
                rem.delivered_at = ref_now
                partial_count += 1
            elif any_delivered:
                rem.delivery_status = "delivered"
                rem.delivered_at = ref_now
                delivered_count += 1
            else:
                rem.delivery_status = "unavailable"
                unavailable_count += 1

            db.add(rem)

        db.commit()
        return ProcessRemindersResponse(
            processed_count=len(claimed),
            delivered_count=delivered_count,
            partial_count=partial_count,
            unavailable_count=unavailable_count,
            failed_count=failed_count,
            notifications_created=notifications_created,
            email_configured=bool(settings.SMTP_ENABLED),
            sms_configured=sms_service.is_configured(),
        )
