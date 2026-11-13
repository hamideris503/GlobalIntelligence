from backend import cli
from backend.database.models.user import User
from tests.conftest import TestingSession


def test_create_admin_normalizes_username_and_email(monkeypatch) -> None:
    monkeypatch.setattr(cli, "get_session_factory", lambda: TestingSession)

    answers = iter(["  AdminUser  ", "  Admin@Example.COM  "])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "Password123456")

    assert cli._create_admin() == 0

    with TestingSession() as db:
        user = db.query(User).filter(User.username == "adminuser").one_or_none()
        assert user is not None
        assert user.email == "admin@example.com"
        assert user.email_verified is True
