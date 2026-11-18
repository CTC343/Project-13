"""Exercise the shipped MSVC clients and real TLS listener using isolated demo data."""

import argparse
from contextlib import closing
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import queue
import secrets
import re
import signal
import socket
import sqlite3
import ssl
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def wait_for(predicate, seconds=25):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("the expected integration state was not reached; inspect the per-process logs")


def available_ports(host):
    for _ in range(30):
        port = 21000 + secrets.randbelow(25000)
        try:
            with socket.socket() as first, socket.socket() as second:
                first.bind((host, port))
                second.bind((host, port + 1))
                return port
        except OSError:
            continue
    raise RuntimeError("No available consecutive demonstration ports.")


def verify_client_watchdog(executable, directory):
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    environment = os.environ.copy()
    environment["PROJECT13_WATCHDOG_LOG_DIR"] = str(directory)
    parent = subprocess.Popen([str(executable)], startupinfo=startup, env=environment)
    events = directory / "watchdog.log"

    def children():
        if not events.exists():
            return []
        return [int(pid) for pid in re.findall(r"client_started pid=(\d+)", events.read_text(encoding="utf-8-sig"))]

    def close_window(pid):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        predicate = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32.EnumWindows.argtypes = (predicate, wintypes.LPARAM)
        closed = False

        @predicate
        def find(window, _):
            nonlocal closed
            owner = wintypes.DWORD()
            name = ctypes.create_unicode_buffer(80)
            user32.GetWindowThreadProcessId(window, ctypes.byref(owner))
            if owner.value == pid and user32.GetClassNameW(window, name, len(name)):
                if name.value == "Project13ClientWindow":
                    closed = bool(user32.PostMessageW(window, 0x0010, 0, 0))
                    return False
            return True

        user32.EnumWindows(find, 0)
        return closed

    try:
        wait_for(children, seconds=8)
        original = children()[0]
        os.kill(original, signal.SIGTERM)
        wait_for(lambda: len(children()) == 2, seconds=8)
        replacement = children()[-1]
        assert replacement != original
        wait_for(lambda: close_window(replacement), seconds=8)
        assert parent.wait(timeout=8) == 0
        assert "manual_stop" in events.read_text(encoding="utf-8-sig")
    finally:
        if parent.poll() is None:
            parent.terminate()
            parent.wait(timeout=5)
            for pid in children()[-1:]:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass

def run(args):
    host = "127.0.0.2"
    port = available_ports(host)
    root = ROOT / "work/project13-verification" / ("acceptance-" + uuid.uuid4().hex[:8])
    data, client_directory, logs = root / "server", root / "cl", root / "logs"
    logs.mkdir(parents=True)
    os.environ.update(
        PROJECT13_DATA_DIR=str(data), PROJECT13_CLIENT_DIR=str(client_directory),
        PROJECT13_HOST=host, PROJECT13_PORT=str(port), PROJECT13_MAX_CLIENTS="16",
        PROJECT13_OUTBOX_DIR=str(root / "out"), PROJECT13_PROFILE_DIR=str(root / "profiles"),
    )
    sys.path.insert(0, str(ROOT / "server"))
    from accounts import AccountStore
    from process_manager import ProcessManager
    from protocol import receive_frame, send_frame
    from task_state import DATABASE
    from security_tests import create_report

    subprocess.run([sys.executable, "-B", str(ROOT / "build.py"), "--output", str(client_directory)],
                   check=True)
    subprocess.run([sys.executable, "-B", str(ROOT / "server/provision.py"), "init",
                    "--openssl", args.openssl, "--server-name", host], check=True)
    accounts = AccountStore()
    password = secrets.token_urlsafe(24).encode()
    for number in range(10):
        accounts.set_password(f"demo-{number + 1:02d}", "node", None, password)
    accounts.set_password("demo-auditor", "auditor", None, password)
    with closing(accounts.connect()) as db:
        salts = db.execute("SELECT algorithm,salt,digest FROM accounts WHERE role='node'").fetchall()
    assert {row[0] for row in salts} == {"scrypt"}
    assert len({row[1] for row in salts}) == len({row[2] for row in salts}) == 10
    reports = create_report()
    assert reports["all_passed"], reports["results"]

    events = queue.Queue()
    controller = ProcessManager(events)
    processes = []
    workers = []
    evidence = {"host": host, "capacity": 16, "accounts_with_independent_salt": len(salts),
                "client_sha256": {
                    name: hashlib.file_digest((client_directory / name).open("rb"), "sha256").hexdigest()
                    for name in ("client.exe", "client_gui.exe")
                }}

    def launch(username, mode, stay, supplied_password, path, environment=None):
        arguments = [str(client_directory / "client.exe"), username, host, str(port), mode]
        if stay:
            arguments.append("stay")
        with path.open("wb") as output:
            child = subprocess.Popen(arguments, stdin=subprocess.PIPE, stdout=output, stderr=output,
                                     env=environment)
        processes.append(child)
        with child.stdin:
            child.stdin.write(supplied_password + b"\n")
        return child

    def rounds():
        with closing(sqlite3.connect(DATABASE)) as db:
            return [json.loads(item[0]) for item in db.execute("SELECT audit FROM rounds ORDER BY rowid")]

    started_at = None
    try:
        assert controller.start_server() and controller.server_ready.wait(15)
        credentials_missing = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        credentials_missing.load_verify_locations(cafile=data / "tls/trust.pem")
        credentials_missing.minimum_version = ssl.TLSVersion.TLSv1_3
        try:
            with socket.create_connection((host, port), timeout=5) as connection:
                with credentials_missing.wrap_socket(connection, server_hostname=host) as secure:
                    secure.recv(1)
        except (ssl.SSLError, ConnectionError):
            evidence["task_port_rejects_missing_client_certificate"] = True
        else:
            raise AssertionError("the task port did not reject a client without a certificate")
        wrong = launch("demo-unknown", "normal", False, password, logs / "invalid-login.log")
        assert wrong.wait(timeout=10) == 2
        auditor = launch("demo-auditor", "normal", False, password, logs / "role-denied.log")
        assert auditor.wait(timeout=10) == 2
        try:
            controller.submit_batch({}, "demo-auditor", "auditor")
        except PermissionError:
            evidence["role_gate"] = True
        else:
            raise AssertionError("auditor submitted a task")
        with closing(accounts.connect()) as db:
            assert db.execute("SELECT COUNT(*) FROM devices").fetchone()[0] == 0
        for number in range(10):
            label = f"demo-{number + 1:02d}"
            log = logs / f"{label}.log"
            client = launch(label, "wrong" if number == 9 else "normal", True, password, log)
            workers.append(client)
            try:
                wait_for(lambda: client.poll() is not None or b"\xc2\xb7 node-" in log.read_bytes(), seconds=12)
            except AssertionError:
                # The current Windows C runtime may emit the UTF-8 middle dot
                # according to the active console code page. Use the issued DB row too.
                with closing(accounts.connect()) as db:
                    assert db.execute("SELECT 1 FROM devices WHERE username=?", (label,)).fetchone()
            assert client.poll() is None, log.read_text(errors="replace")
        def accepted_count():
            with closing(accounts.connect()) as db:
                return db.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        wait_for(lambda: accepted_count() == 10)
        evidence["auto_registered_nodes"] = accepted_count()
        old = controller.server_process
        started_at = time.monotonic()
        controller.submit_batch(
            {"operation": "SUM_RANGE", "start": 1, "end": 1000, "subtask_count": 5,
             "nodes_per_subtask": 10, "important": False}, "demo-operator", "operator",
        )
        wait_for(lambda: len(rounds()) >= 1)
        old.kill()
        wait_for(lambda: controller.server_ready.is_set() and controller.server_process.pid != old.pid)
        wait_for(lambda: len(rounds()) == 5, seconds=35)
        records = rounds()
        last = records[-1]
        assert last["integrated_result"] == 500500 and last["evaluation"]["accuracy_passed"]
        assert len(last["malicious_nodes"]) == 1 and last["evaluation"]["malicious_detection_passed"]
        assert len({item["task_id"].rsplit("-", 1)[0] for item in records}) == 1
        with closing(sqlite3.connect(DATABASE)) as db:
            assert db.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 50
        evidence.update(
            completed_rounds=len(records), unique_receipts=50, integrated_result=500500,
            detected_nodes=1, security_selfcheck=f"{reports['passed']}/{reports['total']}",
            server_restarted=True, same_batch_recovered=True,
            demo_elapsed_seconds_including_restart=round(time.monotonic() - started_at, 2),
        )

        def new_node_states(offset, state):
            with events.mutex:
                recent = list(events.queue)[offset:]
            prefix = "NODE_STATUS "
            return {line.split()[1] for kind, line in recent if kind == "server_line" and
                    line.startswith(prefix) and f" state={state} " in line}

        # Keep the task port unavailable past the first retry, then mimic the
        # window where TCP accepts connections but TLS is not yet ready.
        controller.stop_server()
        wait_for(lambda: controller.server_process is None)
        time.sleep(3)
        assert all(worker.poll() is None for worker in workers)
        interrupted = 0
        with socket.socket() as starting_port:
            starting_port.bind((host, port))
            starting_port.listen(16)
            starting_port.settimeout(0.2)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    stream, _ = starting_port.accept()
                except TimeoutError:
                    continue
                with stream:
                    stream.settimeout(1)
                    if stream.recv(4096):
                        interrupted += 1
                    stream.shutdown(socket.SHUT_RDWR)
        assert interrupted > 0
        assert all(worker.poll() is None for worker in workers)
        with events.mutex:
            offset = len(events.queue)
        assert controller.start_server() and controller.server_ready.wait(15)
        wait_for(lambda: len(new_node_states(offset, "waiting")) == 10, seconds=30)
        evidence["clients_stayed_up_and_reconnected_after_outage"] = True
        evidence["connections_interrupted_during_tls_startup"] = interrupted

        returning_user = "demo-02"
        stem = hashlib.sha256(f"{host}|{port}|{returning_user}".encode("ascii")).hexdigest()
        returning_identity = Path(os.environ["PROJECT13_PROFILE_DIR"]) / (stem + ".identity")
        returning_node = returning_identity.read_text(encoding="ascii").splitlines()[0]
        service_pid = controller.server_process.pid
        with events.mutex:
            offset = len(events.queue)
        workers[1].kill()
        workers[1].wait(timeout=5)
        wait_for(lambda: returning_node in new_node_states(offset, "offline"))
        assert controller.is_server_running() and controller.server_process.pid == service_pid
        with events.mutex:
            offset = len(events.queue)
        replacement = launch(returning_user, "normal", True, password, logs / "node-restarted.log")
        wait_for(lambda: returning_node in new_node_states(offset, "waiting"))
        assert replacement.poll() is None and controller.server_process.pid == service_pid
        evidence["client_rejoined_with_same_identity_while_server_stayed_up"] = True

        # Stop the simulated workers before replaying the first worker's actual
        # receipt in the supported reconnect flow (e.g. when its ACK was lost).
        for process in processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
        username = "demo-01"
        profile = Path(os.environ["PROJECT13_PROFILE_DIR"]) / hashlib.sha256(
            f"{host}|{port}|{username}".encode("ascii")
        ).hexdigest()
        node, license_id = profile.with_suffix(".identity").read_text(encoding="ascii").splitlines()
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        tls.minimum_version = tls.maximum_version = ssl.TLSVersion.TLSv1_3
        tls.load_verify_locations(cafile=data / "tls/trust.pem")
        tls.verify_flags |= ssl.VERIFY_CRL_CHECK_CHAIN
        tls.load_cert_chain(profile.with_suffix(".pem"), profile.with_suffix(".key"))
        with socket.create_connection((host, port), timeout=5) as stream:
            with tls.wrap_socket(stream, server_hostname=host) as secure:
                send_frame(secure, "AUTH", 0, {
                    "username": username, "node_id": node, "license_id": license_id,
                    "exe_hash": evidence["client_sha256"]["client.exe"],
                    "password_hex": password.hex(), "persistent": True,
                })
                kind, status, _ = receive_frame(secure)
                assert (kind, status) == ("AUTH_OK", 200)
                first = records[0]
                proof = first["proofs"][node]
                send_frame(secure, "SECURE", 0, {
                    "action": "RESULT", "task_id": first["task_id"], "node_id": node,
                    "value": first["results"][node], "merkle_root": proof["root"], "proof_steps": proof["steps"],
                })
                assert receive_frame(secure) == ("SECURE", 200, {
                    "action": "ACCEPTED", "task_id": first["task_id"],
                })
                send_frame(secure, "SECURE", 0, {"action": "LOGOUT"})
        with closing(sqlite3.connect(DATABASE)) as db:
            assert db.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 50
        evidence["reconnect_receipt_is_idempotent"] = True
        environment = os.environ.copy()
        environment["PROJECT13_PROFILE_DIR"] = str(root / "profile-two")
        fresh_log = logs / "same-account-new-device.log"
        extra = launch(username, "normal", True, password, fresh_log, environment)
        wait_for(lambda: b" node-" in fresh_log.read_bytes() or extra.poll() is not None)
        assert extra.poll() is None
        with closing(accounts.connect()) as db:
            assert db.execute("SELECT COUNT(*) FROM devices WHERE username=?", (username,)).fetchone()[0] == 2
        evidence["same_account_added_a_second_device"] = True
        extra.terminate()
        extra.wait(timeout=5)
        controller.stop_server()
        wait_for(lambda: controller.server_process is None)
        evidence["manual_stop_without_relaunch"] = True
        verify_client_watchdog(client_directory / "client_gui.exe", logs)
        evidence["client_watchdog_relaunched_and_honored_window_close"] = True
        os.environ["PROJECT13_RELEASE_DIR"] = str(root / "releases")
        for params in (("stage", "1.1.0"), ("stage", "1.1.1"), ("activate", "1.1.0"),
                       ("activate", "1.1.1"), ("launch", "--check"), ("rollback",), ("launch", "--check")):
            subprocess.run([sys.executable, "-B", str(ROOT / "release.py"), *params], check=True)
        pointer = json.loads((data / "active-release.json").read_text(encoding="utf-8"))
        assert pointer["current"] == "1.1.0" and len(rounds()) == 5
        evidence["release_switch_and_rollback_kept_task_data"] = True
        from account_preview import test_features
        test_features(
            root, client_directory,
            lambda username: launch(username, "normal", True, password, logs / f"{username}-preview-task.log"),
            rounds, evidence,
        )
        (root / "summary.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        print(f"Evidence: {root / 'summary.json'}")
    finally:
        controller.stop_server()
        for process in processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
        with events.mutex:
            snapshots = list(events.queue)
        (logs / "controller.log").write_text(
            "\n".join(f"{kind} {message}" for kind, message in snapshots), encoding="utf-8",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--openssl", required=True)
    run(parser.parse_args())
