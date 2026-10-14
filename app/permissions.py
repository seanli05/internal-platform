"""Authorization: is this (already authenticated) user allowed to do this?

PERMANENT, like tokens.py. get_current_user answers "who are you?" (fail →
401). This layer answers "may you?" (fail → 403). It only ever sees a User,
so it doesn't care whether they logged in with a password or with Google.
"""

from collections.abc import Callable

from fastapi import Depends, HTTPException

from app import models
from app.models import Role
from app.models import Status
from app.tokens import get_current_user
from app.models import has_role


def require_role(minimum: Role) -> Callable[..., models.User]:
    """Build a dependency that only lets through approved users of at least `minimum` rank.

    Usage in a route:
        user: models.User = Depends(require_role(Role.EXEC))

    YOURS TO WRITE. require_role is a *factory*: it runs once, when the route
    is defined, and returns the function FastAPI will call on every request.
      1. Define an inner function that depends on get_current_user
         (so authentication still happens first: no/bad token → 401).
      2. Not approved yet → 403 "Account awaiting approval".
      3. Rank below `minimum` → 403 "Insufficient permissions"
         (models.has_role does the rank comparison).
      4. Return the user.
      5. require_role returns the inner function, not the result of calling it.
    """
    def require_role_callable(user: models.User=Depends(get_current_user)):
      if user.status != Status.APPROVED:
         raise HTTPException(403, "Account awaiting approval")

      if has_role(user, minimum):
         return user

      raise HTTPException(403, "Insufficient permissions")
      

    return require_role_callable
