"""CLI امن برای مدیریت حساب‌های اولیه.

مثال:
    python -m backend.cli create-admin
"""
from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from backend.auth.passwords import hash_password
from backend.core.logging import get_logger
from backend.database.models.user import User
from backend.database.session import get_session_factory

logger = get_logger(__name__)


def _create_admin() -> int:
    username = input("Admin username: ").strip().lower()
    if not username:
        print("username is required", file=sys.stderr)
        return 2
    email = input("Admin email (optional): ").strip().lower() or None
    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("passwords do not match", file=sys.stderr)
        return 2
    if len(password) < 12:
        print("password must be at least 12 characters", file=sys.stderr)
        return 2

    factory = get_session_factory()
    db = factory()
    try:
        existing = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if existing is not None:
            print("user already exists", file=sys.stderr)
            return 1
        if email:
            dup = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if dup is not None:
                print("email already in use", file=sys.stderr)
                return 1
        user = User(
            username=username,
            email=email,
            email_verified=bool(email),
            password_hash=hash_password(password),
            role="admin",
            active=True,
        )
        db.add(user)
        db.commit()
        print(f"admin created: {username}")
        return 0
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backend.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("create-admin", help="Create the first admin account securely")
    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return _create_admin()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())