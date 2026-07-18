# Fix Satellite Pass Recording Pipeline — No WAV Files Produced

## Problem Statement

TLE data is fetched successfully and the UI shows "RECORDING" during a satellite pass, but:
1. **No WAV files** appear in `data/recordings/`
2. **SatDump is never triggered** (no input WAV to decode)
3. **No satellite images** appear on the map

The UI says "RECORDING" because [pass_clock.js](file:///c:/Users/vacha/code/pi_noaa/ui/static/js/pass_clock.js#L45-L59) determines this purely from the AOS/LOS time window — it never checks whether the SDR hardware is actually recording. This is a **cosmetic false positive**, not evidence that recording is occurring.

## Root Cause Analysis

I identified **4 bugs** spanning the recording pipeline. Each one individually could prevent WAV files from being produced; together they guarantee failure.

---

### Bug 1 (Critical): `SDRController` — `rtl_fm` subprocess stderr is silently swallowed, masking startup failures

**File:** [sdr_controller.py](file:///c:/Users/vacha/code/pi_noaa/sdr/sdr_controller.py#L113-L132)

`start_recording()` sets `stderr=subprocess.DEVNULL` for **both** `rtl_fm` and `sox`. If either binary is not installed, has wrong permissions, or can't open the SDR device, the error is silently discarded. The method returns `True` (recording started successfully) because the `Popen` call itself doesn't fail — the child process just exits immediately with a non-zero code.

The subsequent `time.sleep(duration_seconds)` waits the full pass duration while both processes have already exited. When `stop_recording()` is called, `terminate()` is called on dead processes (no-op), and the output WAV is either missing or zero bytes.

**Fix:** 
- Capture stderr from both processes (use `PIPE` instead of `DEVNULL`)
- After launching, wait briefly (1–2 seconds) then check if `rtl_fm` has already exited (poll). If it has, read stderr, log the error, and return `False`
- Log stderr on stop as well for debugging

---

### Bug 2 (Critical): `signal_recorder.record_pass()` creates a **new orphaned `SDRController`** every call

**File:** [signal_recorder.py](file:///c:/Users/vacha/code/pi_noaa/sdr/signal_recorder.py#L38)

Every time `record_pass()` is called, it creates `sdr = SDRController()` — a brand new instance. Meanwhile, the [status.py](file:///c:/Users/vacha/code/pi_noaa/api/routes/status.py#L15) route also creates its own `_sdr_controller = SDRController()` at module level. This means:

1. The `is_recording` property checked by the status API is on a **different instance** than the one actually used for recording
2. The `_recording` flag is never shared — so the status endpoint never sees the recording as active
3. The `is_hardware_present()` check via `rtl_test` in `record_pass()` can **block/interfere** with a recording already in progress on another instance (rtl_test opens the device, which can cause `rtl_fm` to lose the device)

**Fix:** Make `SDRController` a singleton so all code paths share the same instance and state.

---

### Bug 3 (Critical): `pass_orchestrator` blocks the asyncio event loop via `record_pass` which calls `time.sleep()`

**File:** [server.py](file:///c:/Users/vacha/code/pi_noaa/api/server.py#L162-L165)

The orchestrator correctly offloads `record_pass` to an executor:
```python
wav_path = await loop.run_in_executor(None, record_pass, next_pass)
```

But `record_pass` internally calls `time.sleep(duration_seconds)` which can be up to 20 minutes. While `run_in_executor` uses a thread pool, this **blocks one of the default thread pool workers** for the entire pass duration. The default `ThreadPoolExecutor` typically has `min(32, os.cpu_count() + 4)` workers. On a Raspberry Pi 5 with 4 cores, that's only 8 workers. One worker being blocked for 15+ minutes is not ideal but isn't the primary failure.

The real timing issue is more subtle: the orchestrator checks `utc_now >= aos and utc_now < los` but **`get_next_pass()` is called freshly every loop iteration**. This means:
- If the recording takes the full duration until LOS, when the orchestrator resumes, `utc_now >= los`, so it falls to the `else` branch (line 218) and sleeps 10 seconds
- But if `get_next_pass()` returns the **same pass** that's still technically active (LOS hasn't quite passed due to timing skew), it could attempt to **double-record**
- Or if the pass just ended, `get_next_pass()` returns the **next** pass, and the loop correctly waits — but the `continue` at line 215 recalculates `sleep_time = (aos - utc_now).total_seconds()` which can be **negative** when `sleep_time - 5` produces a negative number, causing `min(negative, 30)` to produce a **negative sleep** — `asyncio.sleep()` with a negative value returns immediately, creating a **tight infinite loop** that starves the event loop

**Fix:**
- Clamp sleep time to `max(0, min(sleep_time - 5, 30))`
- After recording completes, sleep past the LOS to avoid re-processing the same pass

---

### Bug 4 (Minor): `_cleanup_processes` terminates `rtl_fm` but doesn't close the stdout pipe, causing sox to hang

**File:** [sdr_controller.py](file:///c:/Users/vacha/code/pi_noaa/sdr/sdr_controller.py#L143-L158)

When `stop_recording()` is called:
1. `self._process.terminate()` sends SIGTERM to `rtl_fm`
2. `self._process.wait(timeout=5)` waits for it to exit
3. But `self._process.stdout` (the pipe feeding sox) is **never closed**
4. `sox` reads from this pipe — if the pipe isn't closed, sox may hang waiting for more data (depending on OS buffering behavior)
5. `self._sox_process.wait(timeout=10)` then times out, and sox is killed
6. When sox is killed mid-write, the WAV file header is never finalized → **corrupt or zero-byte WAV**

**Fix:** Close the `rtl_fm` stdout pipe before waiting for sox. Also, call `sox.terminate()` explicitly rather than just waiting for it to notice EOF.

---

## Proposed Changes

### SDR Controller — Singleton + Robust Process Management

#### [MODIFY] [sdr_controller.py](file:///c:/Users/vacha/code/pi_noaa/sdr/sdr_controller.py)

1. **Singleton pattern**: Add `__new__` override so all callers get the same instance
2. **Capture stderr**: Use `subprocess.PIPE` for stderr on both processes; log it on failure/stop
3. **Startup validation**: After launching `rtl_fm`, poll for 1.5 seconds to verify the process is still alive
4. **Fix cleanup**: Close `rtl_fm` stdout pipe before waiting for sox; terminate sox explicitly
5. **Add `_last_error` property** for status API to report why recording failed

---

### Signal Recorder — Remove duplicate SDRController instantiation

#### [MODIFY] [signal_recorder.py](file:///c:/Users/vacha/code/pi_noaa/sdr/signal_recorder.py)

1. Import the singleton `SDRController()` — no code change needed once SDRController is a singleton
2. Add validation: check the SDR is not already recording before starting

---

### Pass Orchestrator — Fix timing bugs

#### [MODIFY] [server.py](file:///c:/Users/vacha/code/pi_noaa/api/server.py)

1. **Clamp sleep**: `await asyncio.sleep(max(1, min(sleep_time - 5, 30)))` to prevent negative/zero sleeps
2. **Post-recording cooldown**: After recording + decode finishes, sleep past LOS + a small buffer before re-entering the loop
3. **Emit `pass_update` WebSocket event** when recording starts/finishes so the UI can show real recording state

---

### Status Route — Use singleton SDRController

#### [MODIFY] [status.py](file:///c:/Users/vacha/code/pi_noaa/api/routes/status.py)

1. Remove module-level `_sdr_controller = SDRController()` instantiation
2. Use `SDRController()` directly (which is now a singleton)

---

> [!IMPORTANT]
> **No changes to `config.yaml`** — all fixes are in Python code.

## Open Questions

> [!IMPORTANT]
> **Q1:** The `status.py` route calls `shutil.disk_usage("/")` which will fail on Windows during development. Since the app runs on a Pi, should I leave this as-is, or add a platform-aware fallback? (This is unrelated to the recording bug but noticed while investigating.)

> [!IMPORTANT]
> **Q2:** The `keep_raw_recordings: false` config setting means WAV files would be deleted after successful decode. During debugging, do you want me to change this to `true` so you can inspect recordings, or leave config as-is?

## Verification Plan

### Automated Tests

```bash
pytest tests/ -v
```

New test file: `tests/test_sdr_controller.py`
- Test singleton behavior (same instance returned)
- Test that `start_recording` returns `False` when `rtl_fm` exits immediately (mock subprocess)
- Test that cleanup properly closes pipes and terminates both processes
- Test that `is_recording` reflects actual state

New test file: `tests/test_signal_recorder.py`
- Test `record_pass` with mocked SDR controller
- Test failure paths (hardware not present, start fails)

### Manual Verification

On the Raspberry Pi 5:
1. Wait for a satellite pass to begin
2. Check `logs/pi_noaa.log` for `[Orchestrator]` and `SDR recording` messages
3. Verify WAV file appears in `data/recordings/`
4. Verify SatDump runs and images appear in `data/images/`
5. Verify the map shows the decoded image overlay
