from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.db import get_session

# Declaring `session: SessionDep` in an endpoint gives it a DB session for the request.
SessionDep = Annotated[Session, Depends(get_session)]
