"""Tests for the Stage86 local runtime supervisor (offline, mocked subprocess)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.ai.local_runtimes.supervisor import (
    LocalRuntimeSupervisor,
    RuntimeState,
)


def test_defaults_disabled():
    sup = LocalRuntimeSupervisor()
    assert sup.status("kev").state == RuntimeState.DISABLED
    assert sup.status("laya").state == RuntimeState.DISABLED
    assert sup.status("kev").enabled is False
    assert sup.status("laya").enabled is False


def test_independent_enable():
    sup = LocalRuntimeSupervisor()
    sup.set_enabled("kev", True)
    assert sup.status("kev").enabled is True
    assert sup.status("laya").enabled is False
    sup.set_enabled("laya", True)
    assert sup.status("kev").enabled is True
    assert sup.status("laya").enabled is True


def test_disable_one_does_not_affect_other():
    sup = LocalRuntimeSupervisor()
    sup.set_enabled("kev", True)
    sup.set_enabled("laya", True)
    sup.set_enabled("kev", False)
    assert sup.status("kev").enabled is False
    assert sup.status("laya").enabled is True


def test_laya_enabled_sets_not_loaded():
    sup = LocalRuntimeSupervisor()
    st = sup.set_enabled("laya", True)
    assert st.state == RuntimeState.ENABLED_NOT_LOADED
    assert st.enabled is True


def test_unknown_model():
    sup = LocalRuntimeSupervisor()
    with pytest.raises(ValueError):
        sup.status("nope")
    with pytest.raises(ValueError):
        sup.set_enabled("nope", True)
    with pytest.raises(ValueError):
        sup.stop("nope")


def test_kev_start_failure_surfaces_error():
    sup = LocalRuntimeSupervisor()
    sup.set_enabled("kev", True)
    with patch("backend.ai.local_runtimes.supervisor.subprocess.Popen") as mock_popen:
        mock_popen.side_effect = OSError("boom")
        st = sup.ensure_loaded("kev")
    assert st.state == RuntimeState.ERROR
    assert "boom" in (st.last_error or "")


def test_kev_stop_terminates_owned_process():
    sup = LocalRuntimeSupervisor()
    sup.set_enabled("kev", True)
    fake = MagicMock()
    fake.poll.return_value = None
    fake.pid = 12345
    sup._kev_proc = fake
    sup._kev_status.state = RuntimeState.READY
    sup._kev_status.enabled = True
    st = sup.stop("kev")
    fake.terminate.assert_called_once()
    fake.wait.assert_called_once()
    assert sup._kev_proc is None
    assert st.pid is None


def test_kev_stop_does_not_kill_unrelated():
    sup = LocalRuntimeSupervisor()
    sup.set_enabled("kev", True)
    fake = MagicMock()
    fake.poll.return_value = None
    sup._kev_proc = fake
    sup._kev_status.state = RuntimeState.READY
    sup._kev_status.enabled = True
    sup.stop("kev")
    # only terminate on the owned process
    fake.kill.assert_not_called()


def test_single_model_policy_flag():
    sup = LocalRuntimeSupervisor()
    assert sup._single_loaded is None


def test_idle_timer_cancels_on_new_request():
    sup = LocalRuntimeSupervisor(idle_unload_seconds=10)
    sup.set_enabled("kev", True)
    # simulate a ready model
    sup._kev_proc = None
    sup._kev_status.state = RuntimeState.READY
    sup._kev_status.enabled = True
    sup.mark_idle("kev")
    assert sup._idle_timers["kev"] is not None
    sup.mark_busy("kev")
    # timer should be cancelled
    assert sup._idle_timers["kev"] is None or sup._idle_timers["kev"].finished.is_set() if hasattr(sup._idle_timers["kev"], "finished") else True

def test_disable_unloads_without_idle_wait():
    sup = LocalRuntimeSupervisor(idle_unload_seconds=1000)
    sup.set_enabled("kev", True)
    fake = MagicMock()
    fake.poll.return_value = None
    sup._kev_proc = fake
    sup._kev_status.state = RuntimeState.READY
    sup._kev_status.enabled = True
    sup.set_enabled("kev", False)
    fake.terminate.assert_called_once()
    assert sup._kev_proc is None

def test_all_status():
    sup = LocalRuntimeSupervisor()
    s = sup.all_status()
    assert "kev" in s and "laya" in s


def test_startup_budget_covers_observed_load_time():
    """Stage87 measured Laya at 94.4s; the probe budget must exceed it."""
    from backend.ai.local_runtimes.supervisor import STARTUP_PROBE_SECONDS

    assert STARTUP_PROBE_SECONDS > 94.4


def test_mark_busy_idle_reference_count():
    """Concurrent requests must not clear BUSY while another is in flight."""
    sup = LocalRuntimeSupervisor(idle_unload_seconds=1000)
    sup.set_enabled("kev", True)
    sup._kev_status.state = RuntimeState.READY
    sup.mark_busy("kev")
    sup.mark_busy("kev")
    assert sup.status("kev").state == RuntimeState.BUSY
    sup.mark_idle("kev")
    assert sup.status("kev").state == RuntimeState.BUSY
    sup.mark_idle("kev")
    assert sup.status("kev").state == RuntimeState.READY
    assert sup._inflight["kev"] == 0
    sup._cancel_idle_timer("kev")


def test_mark_busy_cancels_pending_idle_unload():
    sup = LocalRuntimeSupervisor(idle_unload_seconds=1000)
    sup.set_enabled("kev", True)
    sup._kev_status.state = RuntimeState.READY
    sup.mark_idle("kev")
    assert sup._idle_timers["kev"] is not None
    sup.mark_busy("kev")
    assert sup._idle_timers["kev"] is None
    sup.mark_idle("kev")
    sup._cancel_idle_timer("kev")


# --- Stage89 lifecycle guarantees ------------------------------------------

def test_disable_while_busy_defers_unload_until_idle():
    sup = LocalRuntimeSupervisor(idle_unload_seconds=1000)
    fake = MagicMock()
    fake.poll.return_value = None
    fake.pid = 4242
    sup._kev_proc = fake
    sup._kev_status.enabled = True
    sup._kev_status.state = RuntimeState.READY
    sup._single_loaded = "kev"
    sup.mark_busy("kev")

    st = sup.set_enabled("kev", False)
    assert st.enabled is False
    fake.terminate.assert_not_called()
    assert sup._kev_proc is fake  # still serving the in-flight request

    sup.mark_idle("kev")
    fake.terminate.assert_called_once()
    assert sup._kev_proc is None
    assert sup._kev_status.state == RuntimeState.DISABLED


def test_switch_is_blocked_while_other_model_is_busy():
    sup = LocalRuntimeSupervisor(idle_unload_seconds=1000)
    fake = MagicMock()
    fake.poll.return_value = None
    fake.pid = 5252
    sup._kev_proc = fake
    sup._kev_status.enabled = True
    sup._kev_status.state = RuntimeState.READY
    sup._laya_status.enabled = True
    sup._single_loaded = "kev"
    sup.mark_busy("kev")

    with patch("backend.ai.local_runtimes.supervisor.subprocess.Popen") as popen:
        st = sup.ensure_loaded("laya")
    popen.assert_not_called()
    fake.terminate.assert_not_called()
    assert st.state == RuntimeState.ENABLED_NOT_LOADED
    assert "busy" in (st.last_error or "")
    sup.mark_idle("kev")


def test_idle_unload_never_stops_busy_worker():
    sup = LocalRuntimeSupervisor(idle_unload_seconds=1000)
    fake = MagicMock()
    fake.poll.return_value = None
    fake.pid = 6262
    sup._kev_proc = fake
    sup._kev_status.enabled = True
    sup._kev_status.state = RuntimeState.READY
    sup.mark_busy("kev")
    assert sup._unload("kev", reason="idle_timeout") is False
    fake.terminate.assert_not_called()
    assert sup._pending_unload["kev"] is True
    sup.mark_idle("kev")
    fake.terminate.assert_called_once()
