"""Create or update the first admin user from ADMIN_EMAIL / ADMIN_PASSWORD (M-D9).

Run from backend/:  python scripts/create_admin.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
from dotenv import load_dotenv

load_dotenv()

from app.services.auth import hash_password  # noqa: E402


async def main() -> None:
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    dsn = os.environ.get("DATABASE_URL", "")
    if not email or not password or not dsn:
        sys.exit("Set ADMIN_EMAIL, ADMIN_PASSWORD and DATABASE_URL in backend/.env first.")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """insert into users (email, password_hash, role) values ($1, $2, 'admin')
               on conflict (email) do update
               set password_hash = excluded.password_hash, role = 'admin', active = true""",
            email,
            hash_password(password),
        )
    finally:
        await conn.close()
    print(f"Admin user ready: {email}")


asyncio.run(main())
