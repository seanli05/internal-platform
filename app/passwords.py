"""The proof step: check that someone knows a password.

THROWAWAY. When Google OAuth arrives, Google does the proving and this file
(plus the register/login routes in auth.py) is deleted. Nothing in tokens.py
depends on it.
"""

import bcrypt

# bcrypt only looks at the first 72 bytes of its input. bcrypt 5 raises
# rather than silently truncating, so the register route rejects longer
# passwords up front with a clear message.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    # gensalt() makes 16 random bytes and records the cost factor (default
    # 12 → 2^12 rounds, ~250ms). Both are embedded in the returned string,
    # e.g. "$2b$12$<22-char salt><31-char hash>", so one column holds
    # everything verify needs.
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    # checkpw reads the salt + cost back out of the stored hash, hashes the
    # candidate the same way, and compares in constant time.
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# A real hash of a random string. Login verifies against this when the email
# is unknown, so "no such user" takes the same ~250ms as "wrong password".
# Without it, the generic error message would still leak through timing.
DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")
