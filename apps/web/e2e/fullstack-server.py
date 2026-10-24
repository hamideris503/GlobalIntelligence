"""Full-stack E2E server: the REAL FastAPI app on a throwaway SQLite database.

Started by `playwright.fullstack.config.ts` only — never by the app itself.

Local-only and fail-closed:
- the configured Postgres URL is replaced by a SQLite file inside
  `.e2e-fullstack/` (re-created on every start, gitignored, never the real DB);
- `MOCK_MODE=true`, so the gateway answers from the mock provider and no
  provider credential is needed (none is used);
- all credentials come from process env; `.env` is never read (dotenv is
  cwd-relative: we refuse to start if one would be picked up);
- any outbound socket connect or DNS lookup outside loopback raises, and the
  attempt is appended to `.e2e-fullstack/network-guard.log` (asserted empty by
  the spec), so "no external request" is enforced, not assumed.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import socket
import sys

HERE = pathlib.Path(__file__).resolve().parent
WEB = HERE.parent                      # apps/web
REPO = WEB.parents[1]                  # repo root
ART = WEB / ".e2e-fullstack"
PORT = 8010
# Frontend port chosen by playwright.fullstack.config.ts (E2E_FRONTEND_PORT, default
# 4174) so the CORS allow-list below matches the browser origin exactly — never "*".
FRONTEND_PORT = int(os.environ.get("E2E_FRONTEND_PORT", "4174"))
API_KEY = "e2e-local-fake-api-key"

if pathlib.Path(".env").exists():  # pydantic-settings loads `.env` from the cwd
    sys.exit(f"[e2e] refusing to start: {pathlib.Path('.env').resolve()} would be loaded")

shutil.rmtree(ART, ignore_errors=True)
ART.mkdir(parents=True, exist_ok=True)
GUARD_LOG = ART / "network-guard.log"
DB_PATH = ART / "e2e.db"
_LOOPBACK = ("127.0.0.1", "::1", "localhost", "", "0.0.0.0")


def _record(what: str) -> None:
    with GUARD_LOG.open("a", encoding="utf-8") as fh:
        fh.write(what + "\n")


_real_connect = socket.socket.connect


def _guarded_connect(self, address):  # noqa: ANN001
    host = address[0] if isinstance(address, tuple) else str(address)
    if host not in _LOOPBACK:
        _record(f"connect {host}")
        raise OSError(f"[e2e] outbound connection blocked: {host}")
    return _real_connect(self, address)


_real_getaddrinfo = socket.getaddrinfo


def _guarded_getaddrinfo(host, *args, **kwargs):  # noqa: ANN001
    if isinstance(host, str) and host not in _LOOPBACK:
        _record(f"dns {host}")
        raise OSError(f"[e2e] DNS lookup blocked: {host}")
    return _real_getaddrinfo(host, *args, **kwargs)


socket.socket.connect = _guarded_connect
socket.getaddrinfo = _guarded_getaddrinfo

sys.path.insert(0, str(REPO))

from cryptography.fernet import Fernet  # noqa: E402  (after sys.path setup)

os.environ.update({
    "APP_ENV": "development",
    "LOG_LEVEL": "WARNING",
    "MOCK_MODE": "true",
    "AI_DEFAULT_PROVIDER": "mock",
    "API_KEY": API_KEY,
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": "admin",
    "APP_ENCRYPTION_KEY": Fernet.generate_key().decode(),  # test-only, per process
    "DATABASE_URL": f"sqlite+pysqlite:///{DB_PATH.as_posix()}",
    "ALLOWED_ORIGINS": f"http://127.0.0.1:{FRONTEND_PORT},http://localhost:{FRONTEND_PORT}",
})

import uvicorn  # noqa: E402

from backend.database.base import Base  # noqa: E402
from backend.database.session import get_engine  # noqa: E402
from backend.main import app  # noqa: E402

engine = get_engine()
Base.metadata.create_all(bind=engine)
print(f"[e2e] sqlite={DB_PATH} tables={len(Base.metadata.tables)} "
      f"guard={GUARD_LOG}", flush=True)
uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
