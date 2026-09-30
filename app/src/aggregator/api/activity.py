from fastapi import APIRouter, Depends, Response

from aggregator.api.deps import activity
from aggregator.core.activity import ActivityEvent, ActivityLog

router = APIRouter()


@router.get("/activity", response_model=list[ActivityEvent])
async def recent_activity(
    response: Response, log: ActivityLog = Depends(activity)
) -> list[ActivityEvent]:
    response.headers["Cache-Control"] = "no-store"
    return log.recent()
