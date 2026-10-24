"""Local runtime supervisor for Kev/Laya (Stage86/87).

Manages owned subprocesses for Kev (kev.serve) and Laya (laya_wrapper.py).
Enforces single-loaded-model policy via a lock. Supports idle unload timers.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass
from enum import Enum

# ---- runtime paths (overridable via env) ----
KEV_PYTHON = os.environ.get("KEV_RUNTIME_PYTHON",
    r"H:\GIRuntime\labeling\reviewed\stage79_kev_runtime_20261022T201408Z\venv\Scripts\python.exe")
KEV_SNAPSHOT = os.environ.get("KEV_RUNTIME_SNAPSHOT",
    r"H:\GIRuntime\model-cache\hf\hub\models--jaredpalmer--kev-0.8b\snapshots\bf75a6a8848ea6960ff2ed108d9ed44c2941174f")
KEV_PORT = int(os.environ.get("KEV_RUNTIME_PORT", "8123"))

LAYA_PYTHON = os.environ.get("LAYA_RUNTIME_PYTHON",
    r"H:\GIRuntime\labeling\reviewed\stage83_laya_runtime_20261023T110256Z\venv\Scripts\python.exe")
LAYA_SNAPSHOT = os.environ.get("LAYA_RUNTIME_SNAPSHOT",
    r"H:\GIRuntime\model-cache\hf\hub\models--convaiinnovations--laya\snapshots\7b928d828b7b0e022f929d9bd2e44165aa270148\multilingual")
LAYA_WRAPPER = os.environ.get("LAYA_RUNTIME_WRAPPER",
    r"H:\GIRuntime\labeling\reviewed\stage87_runtime_lifecycle_20261023T123441Z\laya_wrapper.py")
LAYA_PORT = int(os.environ.get("LAYA_RUNTIME_PORT", "8124"))

IDLE_UNLOAD_DEFAULT = 300
# Both runtimes import their checkpoint before the probe port opens; Stage87
# measured Laya at 94.4s and Kev at 50.0s, so the probe budget must exceed the
# slower one. A shorter budget marked a healthy worker ERROR.
STARTUP_PROBE_SECONDS = 180


class RuntimeState(str, Enum):
    DISABLED = "DISABLED"
    ENABLED_NOT_LOADED = "ENABLED_NOT_LOADED"
    STARTING = "STARTING"
    READY = "READY"
    BUSY = "BUSY"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


@dataclass
class RuntimeStatus:
    name: str
    enabled: bool
    state: RuntimeState
    pid: int | None = None
    started_at: float | None = None
    load_time_ms: float | None = None
    last_inference_ms: float | None = None
    last_error: str | None = None
    idle_timer_active: bool = False


class LocalRuntimeSupervisor:
    def __init__(self, idle_unload_seconds: int = IDLE_UNLOAD_DEFAULT):
        self._lock = threading.RLock()
        self._single_loaded: str | None = None  # name of currently loaded model
        self._kev_proc: subprocess.Popen | None = None
        self._laya_proc: subprocess.Popen | None = None
        self._kev_status = RuntimeStatus("kev", False, RuntimeState.DISABLED)
        self._laya_status = RuntimeStatus("laya", False, RuntimeState.DISABLED)
        self._idle_unload_seconds = idle_unload_seconds
        self._idle_timers: dict[str, threading.Timer | None] = {"kev": None, "laya": None}
        self._inflight: dict[str, int] = {"kev": 0, "laya": 0}
        # A disable/switch requested while inference is in flight must not kill
        # the worker. The unload is deferred until mark_idle (Stage89 §8).
        self._pending_unload: dict[str, bool] = {"kev": False, "laya": False}

    # ---- settings ----
    def set_idle_unload(self, seconds: int) -> None:
        with self._lock:
            self._idle_unload_seconds = max(0, seconds)

    def set_enabled(self, name: str, enabled: bool) -> RuntimeStatus:
        with self._lock:
            st = self._status_obj(name)
            st.enabled = enabled
            if not enabled:
                if self._inflight.get(name, 0) > 0:
                    # Never terminate a busy worker. New jobs stop immediately
                    # because enabled=False; the process exits on mark_idle.
                    self._pending_unload[name] = True
                    self._cancel_idle_timer(name)
                else:
                    self._unload(name, reason="disabled")
                    st.state = RuntimeState.DISABLED
            else:
                self._pending_unload[name] = False
                if st.state in (RuntimeState.DISABLED,):
                    st.state = RuntimeState.ENABLED_NOT_LOADED
            return self._copy(st)

    def status(self, name: str) -> RuntimeStatus:
        with self._lock:
            st = self._status_obj(name)
            proc = self._proc(name)
            if proc is not None and proc.poll() is not None:
                # unexpected exit
                if st.state not in (RuntimeState.DISABLED, RuntimeState.ENABLED_NOT_LOADED):
                    st.state = RuntimeState.ERROR
                    st.last_error = f"process exited code {proc.returncode}"
                self._clear_proc(name)
                if self._single_loaded == name:
                    self._single_loaded = None
            # probe health if ready/starting
            if proc is not None and proc.poll() is None and st.state in (RuntimeState.STARTING, RuntimeState.READY):
                port = KEV_PORT if name == "kev" else LAYA_PORT
                try:
                    url = (f"http://127.0.0.1:{port}/v1/models" if name == "kev"
                           else f"http://127.0.0.1:{port}/health")
                    with urllib.request.urlopen(url, timeout=2.0) as r:
                        if r.getcode() == 200:
                            st.state = RuntimeState.READY
                        else:
                            st.state = RuntimeState.ERROR
                            st.last_error = f"health HTTP {r.getcode()}"
                except Exception:  # noqa: BLE001
                    # not ready yet
                    pass
            return self._copy(st)

    def all_status(self) -> dict:
        return {"kev": self.status("kev").__dict__, "laya": self.status("laya").__dict__}

    # ---- internal helpers ----
    def _status_obj(self, name: str) -> RuntimeStatus:
        if name == "kev":
            return self._kev_status
        if name == "laya":
            return self._laya_status
        raise ValueError(f"unknown model: {name}")

    def _proc(self, name: str) -> subprocess.Popen | None:
        return self._kev_proc if name == "kev" else self._laya_proc

    def _set_proc(self, name: str, proc: subprocess.Popen | None) -> None:
        if name == "kev":
            self._kev_proc = proc
        else:
            self._laya_proc = proc

    def _clear_proc(self, name: str) -> None:
        self._set_proc(name, None)

    def _cancel_idle_timer(self, name: str) -> None:
        t = self._idle_timers.get(name)
        if t is not None:
            t.cancel()
        self._idle_timers[name] = None

    def _start_idle_timer(self, name: str) -> None:
        self._cancel_idle_timer(name)
        if self._idle_unload_seconds <= 0:
            return
        st = self._status_obj(name)
        if not st.enabled:
            return

        def _cb():
            with self._lock:
                # only unload if idle and no in-flight
                if self._inflight.get(name, 0) > 0:
                    self._start_idle_timer(name)
                    return
                st2 = self._status_obj(name)
                if st2.enabled and st2.state == RuntimeState.READY:
                    self._unload(name, reason="idle_timeout")
                    st2.state = RuntimeState.ENABLED_NOT_LOADED if st2.enabled else RuntimeState.DISABLED

        timer = threading.Timer(self._idle_unload_seconds, _cb)
        timer.daemon = True
        self._idle_timers[name] = timer
        st.idle_timer_active = True
        timer.start()

    def _unload(self, name: str, reason: str = "") -> bool:
        """Stop the owned process; returns True only when exit is verified.

        A busy worker is never terminated: the unload is deferred to mark_idle.
        """
        if self._inflight.get(name, 0) > 0:
            self._pending_unload[name] = True
            return False
        proc = self._proc(name)
        st = self._status_obj(name)
        if proc is not None:
            st.state = RuntimeState.STOPPING
            exited = False
            try:
                proc.terminate()
                proc.wait(timeout=15)
                exited = True
            except Exception:  # noqa: BLE001
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                    exited = True
                except Exception:  # noqa: BLE001
                    exited = proc.poll() is not None
            if not exited:
                # Exit is not verified; keep the handle so a later attempt can
                # stop it and the caller must not start another model.
                st.state = RuntimeState.ERROR
                st.last_error = "process did not exit after terminate/kill"
                return False
            self._clear_proc(name)
        # cancel idle timer
        self._cancel_idle_timer(name)
        st.idle_timer_active = False
        st.pid = None
        self._pending_unload[name] = False
        if self._single_loaded == name:
            self._single_loaded = None
        return True

    def ensure_loaded(self, name: str) -> RuntimeStatus:
        with self._lock:
            st = self._status_obj(name)
            if not st.enabled:
                st.state = RuntimeState.DISABLED
                return self._copy(st)
            if st.state == RuntimeState.READY:
                self._cancel_idle_timer(name)
                return self._copy(st)
            # single-model policy: unload other
            other = "laya" if name == "kev" else "kev"
            if self._single_loaded is not None and self._single_loaded != name:
                if self._inflight.get(other, 0) > 0:
                    # Do not kill an in-flight inference to switch models.
                    st.state = RuntimeState.ENABLED_NOT_LOADED
                    st.last_error = f"switch deferred: {other} is busy"
                    return self._copy(st)
                if not self._unload(other, reason="switch"):
                    st.state = RuntimeState.ERROR
                    st.last_error = f"cannot switch: {other} did not exit"
                    return self._copy(st)
                other_st = self._status_obj(other)
                if other_st.enabled:
                    other_st.state = RuntimeState.ENABLED_NOT_LOADED
            # cancel idle timer for self
            self._cancel_idle_timer(name)
            st.state = RuntimeState.STARTING
            st.last_error = None
            t0 = time.time()
            # launch
            if name == "kev":
                env = dict(os.environ)
                env["HF_HUB_OFFLINE"] = "1"
                env["TRANSFORMERS_OFFLINE"] = "1"
                env["HF_HOME"] = r"H:\GIRuntime\model-cache\hf"
                try:
                    proc = subprocess.Popen(
                        [KEV_PYTHON, "-m", "kev.serve", "--run", KEV_SNAPSHOT, "--port", str(KEV_PORT)],
                        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as exc:  # noqa: BLE001
                    st.state = RuntimeState.ERROR
                    st.last_error = str(exc)[:300]
                    return self._copy(st)
                self._set_proc("kev", proc)
                st.pid = proc.pid
                st.started_at = t0
                # health probe
                ready = False
                for _ in range(STARTUP_PROBE_SECONDS):
                    time.sleep(1.0)
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{KEV_PORT}/v1/models", timeout=2.0) as r:
                            if r.getcode() == 200:
                                ready = True
                                break
                    except Exception:  # noqa: BLE001
                        pass
                if ready:
                    st.state = RuntimeState.READY
                    st.load_time_ms = (time.time() - t0) * 1000
                    self._single_loaded = "kev"
                else:
                    self._unload("kev", reason="startup_timeout")
                    st.state = RuntimeState.ERROR
                    st.last_error = "health probe timeout"
                    st.pid = None
            else:  # laya
                env = dict(os.environ)
                env["HF_HUB_OFFLINE"] = "1"
                env["TRANSFORMERS_OFFLINE"] = "1"
                env["HF_HOME"] = r"H:\GIRuntime\model-cache\hf"
                try:
                    proc = subprocess.Popen(
                        [LAYA_PYTHON, LAYA_WRAPPER, "--port", str(LAYA_PORT)],
                        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as exc:  # noqa: BLE001
                    st.state = RuntimeState.ERROR
                    st.last_error = str(exc)[:300]
                    return self._copy(st)
                self._set_proc("laya", proc)
                st.pid = proc.pid
                st.started_at = t0
                ready = False
                for _ in range(STARTUP_PROBE_SECONDS):
                    time.sleep(1.0)
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{LAYA_PORT}/health", timeout=2.0) as r:
                            if r.getcode() == 200:
                                ready = True
                                break
                    except Exception:  # noqa: BLE001
                        pass
                if ready:
                    st.state = RuntimeState.READY
                    st.load_time_ms = (time.time() - t0) * 1000
                    self._single_loaded = "laya"
                else:
                    self._unload("laya", reason="startup_timeout")
                    st.state = RuntimeState.ERROR
                    st.last_error = "health probe timeout"
                    st.pid = None
            return self._copy(st)

    def stop(self, name: str) -> RuntimeStatus:
        with self._lock:
            st = self._status_obj(name)
            self._cancel_idle_timer(name)
            if self._inflight.get(name, 0) > 0:
                # Explicit stop still never kills an in-flight request.
                st.enabled = False
                self._pending_unload[name] = True
                st.last_error = "stop deferred: request in flight"
                return self._copy(st)
            st.state = RuntimeState.STOPPING
            if not self._unload(name, reason="explicit_stop"):
                return self._copy(st)
            st.idle_timer_active = False
            st.pid = None
            if st.enabled:
                st.state = RuntimeState.ENABLED_NOT_LOADED
            else:
                st.state = RuntimeState.DISABLED
            return self._copy(st)

    def mark_busy(self, name: str) -> None:
        with self._lock:
            # Cancel a pending unload before the request starts.
            self._cancel_idle_timer(name)
            self._inflight[name] = self._inflight.get(name, 0) + 1
            st = self._status_obj(name)
            if st.state == RuntimeState.READY:
                st.state = RuntimeState.BUSY

    def mark_idle(self, name: str) -> None:
        with self._lock:
            self._inflight[name] = max(0, self._inflight.get(name, 0) - 1)
            if self._inflight[name] > 0:
                return  # another request still holds this runtime
            st = self._status_obj(name)
            if self._pending_unload.get(name) or not st.enabled:
                # The disable/switch waited for this request; now unload.
                if self._unload(name, reason="deferred"):
                    st.state = (RuntimeState.ENABLED_NOT_LOADED if st.enabled
                                else RuntimeState.DISABLED)
                return
            if st.state == RuntimeState.BUSY:
                st.state = RuntimeState.READY
            self._start_idle_timer(name)

    def _copy(self, st: RuntimeStatus) -> RuntimeStatus:
        import copy
        return copy.copy(st)


# module-level singleton
supervisor = LocalRuntimeSupervisor()


def get_supervisor() -> LocalRuntimeSupervisor:
    return supervisor
