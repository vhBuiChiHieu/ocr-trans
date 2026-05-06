from __future__ import annotations

import argparse
import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON_EXE = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
API_RUNNER = REPO_ROOT / "services" / "translate_api" / "run.py"
APP_MAIN = REPO_ROOT / "main.py"
API_HEALTH_URL = "http://127.0.0.1:8765/health"


class _ApiStartupFailed(RuntimeError):
    pass


def _is_api_healthy() -> bool:
    try:
        with urlopen(API_HEALTH_URL, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def _wait_for_api_ready(timeout_seconds: float = 20.0) -> tuple[bool, str]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _is_api_healthy():
            return True, "health"
        if _is_port_in_use():
            return True, "port"
        time.sleep(0.4)
    return False, "timeout"


def _is_port_in_use(host: str = "127.0.0.1", port: int = 8765) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def _find_pids_on_port(port: int = 8765) -> list[int]:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    pids: set[int] = set()
    needle = f":{port}"
    for line in result.stdout.splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        if needle not in normalized:
            continue
        parts = normalized.split()
        if len(parts) < 5:
            continue
        local_addr = parts[1]
        state = parts[3].upper()
        pid_text = parts[4]
        if not local_addr.endswith(needle):
            continue
        if state not in {"LISTENING", "ESTABLISHED", "TIME_WAIT", "CLOSE_WAIT"}:
            continue
        if pid_text.isdigit():
            pids.add(int(pid_text))
    return sorted(pids)


def _kill_pid(pid: int) -> bool:
    if pid == os.getpid():
        return False
    result = subprocess.run(
        ["taskkill", "/PID", str(pid), "/F"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.returncode == 0


def _terminate_process(process: subprocess.Popen, name: str) -> None:
    if process.poll() is not None:
        print(f"[{name}] already stopped (exit={process.returncode})")
        return

    print(f"[{name}] stopping...")
    process.terminate()
    try:
        process.wait(timeout=8)
        print(f"[{name}] stopped (exit={process.returncode})")
    except subprocess.TimeoutExpired:
        print(f"[{name}] graceful stop timed out, force killing...")
        process.kill()
        process.wait(timeout=3)
        print(f"[{name}] killed (exit={process.returncode})")


def _start_api_process(env: dict[str, str], force_restart_api: bool) -> tuple[subprocess.Popen | None, bool]:
    if force_restart_api:
        pids = _find_pids_on_port(8765)
        if pids:
            print(f"[launcher] force restart enabled, killing pids on 8765: {pids}")
            for pid in pids:
                killed = _kill_pid(pid)
                if killed:
                    print(f"[launcher] killed pid {pid}")
                else:
                    print(f"[launcher] could not kill pid {pid}")
            time.sleep(0.6)

    if _is_api_healthy() and not force_restart_api:
        print("[launcher] found existing translate API on port 8765, reusing it.")
        return None, True

    if _is_port_in_use():
        raise _ApiStartupFailed(
            "port 8765 is already in use but /health is not responding. Stop the process using this port or use --force-restart-api"
        )

    print(f"[launcher] starting translate API: {API_RUNNER}")
    api_proc = subprocess.Popen([str(PYTHON_EXE), str(API_RUNNER)], cwd=str(REPO_ROOT), env=env)
    print(f"[launcher] translate API pid={api_proc.pid}")
    print("[launcher] waiting for translate API health...")

    if _wait_for_api_ready():
        print("[launcher] translate API is ready.")
        return api_proc, False

    if api_proc.poll() is not None:
        raise _ApiStartupFailed(f"translate API process exited early (exit={api_proc.returncode})")

    _terminate_process(api_proc, "translate-api")
    raise _ApiStartupFailed("translate API did not become ready in time")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force-restart-api",
        action="store_true",
        help="Kill process(es) on port 8765 before starting translate API",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    if not PYTHON_EXE.exists():
        print(f"Missing Python runtime: {PYTHON_EXE}")
        return 1

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    api_proc = None
    api_reused = False
    try:
        api_proc, api_reused = _start_api_process(env, force_restart_api=args.force_restart_api)
        print(f"[launcher] starting app: {APP_MAIN}")
        app_proc = subprocess.Popen([str(PYTHON_EXE), str(APP_MAIN)], cwd=str(REPO_ROOT), env=env)
        print(f"[launcher] app pid={app_proc.pid}")
        try:
            app_exit = app_proc.wait()
            print(f"[launcher] app exited with code {app_exit}")
            return app_exit
        finally:
            _terminate_process(app_proc, "app")
    except _ApiStartupFailed as exc:
        print(f"[launcher] {exc}")
        return 1
    finally:
        if api_proc is not None and not api_reused:
            _terminate_process(api_proc, "translate-api")
        elif api_reused:
            print("[launcher] leaving existing translate API running.")
        print("[launcher] shutdown complete.")


if __name__ == "__main__":
    raise SystemExit(main())
