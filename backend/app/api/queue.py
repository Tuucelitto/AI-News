from fastapi import APIRouter, Request
from sqlmodel import col, func, select

from app.api.deps import AdminDep, SessionDep
from app.config import settings
from app.models import Article, Feed, SummaryStatus, utc_now
from app.scheduler import FETCH_JOB_ID, BackgroundJobs
from app.schemas import ModelStatus, QueueStatus
from app.services.rate_limiter import RateLimiter, next_quota_reset

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("/status", dependencies=[AdminDep])
def queue_status(request: Request, session: SessionDep) -> QueueStatus:
    now = utc_now()
    jobs: BackgroundJobs | None = getattr(request.app.state, "jobs", None)
    worker = jobs.worker if jobs else None

    rows = session.exec(
        select(Article.summary_status, func.count()).group_by(Article.summary_status)
    ).all()
    counts = {status: 0 for status in SummaryStatus} | dict(rows)

    configured = [("primary", settings.gemini_model, settings.gemini_daily_limit)]
    if settings.gemini_fallback_model:
        configured.append(
            ("fallback", settings.gemini_fallback_model, settings.gemini_fallback_daily_limit)
        )
    # Pauses live in the worker's memory; daily usage is read from the database.
    slots = {"primary": worker.primary, "fallback": worker.fallback} if worker else {}
    models = []
    for role, model, daily_limit in configured:
        slot = slots.get(role)
        models.append(
            ModelStatus(
                model=model,
                role=role,
                requests_today=RateLimiter(model, 1, daily_limit).requests_today(session, now),
                daily_limit=daily_limit,
                quota_resets_at=next_quota_reset(now),
                paused_until=slot.paused_until if slot and slot.paused_until else None,
            )
        )

    fetch_job = jobs.scheduler.get_job(FETCH_JOB_ID) if jobs else None
    return QueueStatus(
        counts=counts,
        models=models,
        scheduler_running=bool(jobs and jobs.scheduler.running),
        last_fetch_at=session.exec(select(func.max(col(Feed.last_fetched_at)))).one(),
        next_fetch_at=fetch_job.next_run_time if fetch_job else None,
    )
