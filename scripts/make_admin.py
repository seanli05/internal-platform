"""Promote an existing user to approved admin. Bootstraps the first admin.

    python -m scripts.make_admin you@example.com

The API can't do this: making an admin requires an admin. So the very first
one is made by someone with direct access to the database. That's the trust
boundary: whoever can run this script could edit the DB anyway.
"""

import sys

from app import models
from app.db import SessionLocal
from app.models import Role, Status


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m scripts.make_admin <email>")
    email = sys.argv[1].strip().lower()

    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email=email).first()
        if user is None:
            sys.exit(f"No user with email {email!r}. Register first, then run this.")
        user.role = Role.ADMIN
        user.status = Status.APPROVED
        db.commit()
    print(f"{email} is now an approved admin.")


if __name__ == "__main__":
    main()
