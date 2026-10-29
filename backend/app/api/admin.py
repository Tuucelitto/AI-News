from fastapi import APIRouter, Response, status

from app.api.deps import AdminDep

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/check", status_code=status.HTTP_204_NO_CONTENT, dependencies=[AdminDep])
def check_admin_key() -> Response:
    """Lets the frontend verify an admin key right away, without changing anything."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)
