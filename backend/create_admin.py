"""Create or promote the operator account. Run this before the site is public.

From the backend directory:

    ADMIN_EMAIL=you@example.com ADMIN_USERNAME=operator ADMIN_PASSWORD='a long password' python create_admin.py
"""

import asyncio
import os
import sys

from schemas import UserCreate
from services.async_auth_service import async_auth_service


def _required(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


async def main() -> None:
    from database import get_database, init_db

    email = _required("ADMIN_EMAIL")
    username = _required("ADMIN_USERNAME")
    password = _required("ADMIN_PASSWORD")
    if len(password) < 8:
        raise SystemExit("ADMIN_PASSWORD must be at least 8 characters")

    await init_db()
    db = get_database()
    existing = await async_auth_service.get_user_by_email(db, email)
    if existing:
        await db.users.update_one(
            {"user_id": existing.get("user_id")},
            {"$set": {"is_admin": True, "is_active": True}},
        )
        print(f"Promoted {email} to admin")
        return

    created = await async_auth_service.create_user(
        db,
        UserCreate(
            email=email,
            username=username,
            password=password,
            full_name=os.environ.get("ADMIN_FULL_NAME") or username,
        ),
    )
    await db.users.update_one(
        {"user_id": created.get("user_id")},
        {"$set": {"is_admin": True}},
    )
    print(f"Created admin {email}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"Admin bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc