"""Settings read from the environment.

load_dotenv() copies KEY=value lines from .env into os.environ (without
overwriting anything already set), so in production you set real
environment variables and there is no .env file at all.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# Signs every access token. Anyone holding this can mint a token for any
# user, so it lives only in .env (gitignored) — never in code.
# Fail at import time rather than at the first login: a missing key is a
# deployment mistake, and a server that starts without one is a trap.
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is not set. Copy .env.example to .env and fill it in."
    )
