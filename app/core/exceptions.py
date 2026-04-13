from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.models.enums import WorkspacePlan


class PlanLimitExceeded(Exception):
    def __init__(self, *, current: int, limit: int, plan: WorkspacePlan) -> None:
        self.current = current
        self.limit = limit
        self.plan = plan
        super().__init__(f"Plan limit exceeded for {plan.value}: {current}/{limit}")


async def plan_limit_exceeded_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, PlanLimitExceeded):
        raise TypeError("plan_limit_exceeded_handler received unsupported exception type")

    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": "plan_limit_exceeded",
            "detail": {
                "current": exc.current,
                "limit": exc.limit,
                "plan": exc.plan.value,
            },
        },
    )
