"""Stage immutable program versions, keep runtime state in place and roll back code."""

import argparse
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")
SCHEMA = 1
sys.path.insert(0, str(ROOT / "server"))
from config import CLIENT_DIR, DATA_DIR
from credential_store import file_sha256

VERSIONS_DIR = Path(os.environ.get("PROJECT13_RELEASE_DIR", ROOT / "releases")).resolve()
POINTER = DATA_DIR / "active-release.json"


def json_write(path, value):
    partial = path.with_suffix(".tmp")
    with partial.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    partial.replace(path)


@contextmanager
def exclusive():
    import msvcrt
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / "release.lock").open("a+b") as lock:
        if lock.tell() == 0:
            lock.write(b".")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise ValueError("Close the running control center before switching a release.") from None
        try:
            yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def path_for(version):
    if not VERSION.fullmatch(version or ""):
        raise ValueError("Use a version such as 1.1.0.")
    return VERSIONS_DIR / version


def package(version):
    destination = path_for(version)
    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError("This version is already staged. Use a new version number.")
    if not all((CLIENT_DIR / name).is_file() for name in ("client.exe", "client_gui.exe")):
        raise ValueError("Build both clients first.")
    # Build beside the destination so the package inherits the release ACL.
    # On Windows TemporaryDirectory grants access only to its creator and
    # privileged accounts. Renaming its subtree would retain that private ACL.
    stage = VERSIONS_DIR / f".staging-{uuid4().hex}"
    stage.mkdir()
    try:
        client = stage / "client"
        server = stage / "server"
        client.mkdir(parents=True)
        server.mkdir()
        for source in (ROOT / "server").glob("*.py"):
            shutil.copy2(source, server)
        for pattern in ("*.c", "*.h"):
            for source in (ROOT / "client").glob(pattern):
                shutil.copy2(source, client)
        shutil.copy2(ROOT / "build.py", stage)
        for name in ("client.exe", "client_gui.exe", "runtime-LICENSE.txt"):
            path = CLIENT_DIR / name
            if path.exists():
                shutil.copy2(path, client)
        for dll in CLIENT_DIR.glob("*.dll"):
            shutil.copy2(dll, client)
        json_write(stage / "allowed_executables.json", {
            name: file_sha256(client / name) for name in ("client.exe", "client_gui.exe")
        })
        payload = {path.relative_to(stage).as_posix(): file_sha256(path)
                   for path in stage.rglob("*") if path.is_file()}
        json_write(stage / "manifest.json", {"version": version, "schema": SCHEMA, "files": payload})
        stage.rename(destination)
    finally:
        if stage.is_dir() and stage.resolve() == stage and stage.parent == VERSIONS_DIR:
            shutil.rmtree(stage)
    print(f"Staged {version}: {destination}")


def verify_release(version):
    folder = path_for(version)
    metadata = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if metadata["schema"] != SCHEMA or metadata["version"] != version:
        raise ValueError("The selected release is incompatible with the runtime state.")
    for name, digest in metadata["files"].items():
        file = (folder / name).resolve()
        if not file.is_relative_to(folder) or file_sha256(file) != digest:
            raise ValueError("Release file integrity verification failed.")
    return folder


def backup():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    folder = DATA_DIR / "backups" / stamp
    folder.mkdir(parents=True)
    for name in ("tasks.sqlite3", "accounts.sqlite3"):
        source = DATA_DIR / name
        if source.exists():
            with closing(sqlite3.connect(source)) as old, closing(sqlite3.connect(folder / name)) as new:
                old.backup(new)
                if new.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Database backup failed the integrity check.")
    for name in ("tls", "issuer", "issuer-tool.json", "task_private_key.json", "allowed_executables.json",
                 "security_audit.jsonl", "runtime.log", "runtime.log.1", "runtime.log.2", "runtime.log.3"):
        source = DATA_DIR / name
        if source.is_dir():
            shutil.copytree(source, folder / name)
        elif source.exists():
            shutil.copy2(source, folder / name)
    public = CLIENT_DIR / "task_public.key"
    if public.exists():
        shutil.copy2(public, folder / public.name)
    return folder


def read_pointer():
    if POINTER.exists():
        return json.loads(POINTER.read_text(encoding="utf-8"))
    return {"current": None, "previous": None}


def switch(version=None):
    with exclusive():
        current = read_pointer()
        selected = version or current["previous"]
        verify_release(selected)
        if current["current"] == selected:
            return
        snapshot = backup()
        update = {"current": selected, "previous": current["current"],
                  "backup": snapshot.name, "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        json_write(POINTER, update)
        with (DATA_DIR / "release-history.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(update) + "\n")
    print(f"Active release: {selected}. Backup: {snapshot.name}")


def launch(check=False):
    with exclusive():
        current = read_pointer()["current"]
        folder = verify_release(current)
        active_client = folder / "client"
        (active_client / "tls").mkdir(exist_ok=True)
        shutil.copy2(DATA_DIR / "tls/trust.pem", active_client / "tls/trust.pem")
        shutil.copy2(CLIENT_DIR / "task_public.key", active_client / "task_public.key")
        environment = os.environ.copy()
        environment.update(PROJECT13_DATA_DIR=str(DATA_DIR), PROJECT13_CLIENT_DIR=str(active_client),
                           PROJECT13_APPROVED_BUILDS=str(folder / "allowed_executables.json"),
                           PROJECT13_VERSION=current)
        command = [sys.executable, "-B", str(folder / "server/gui.py")]
        if check:
            command.append("--check")
        return subprocess.call(command, env=environment)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("stage", "activate"):
        commands.add_parser(action).add_argument("version")
    commands.add_parser("rollback")
    commands.add_parser("launch").add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "stage":
            package(args.version)
        elif args.action == "activate":
            switch(args.version)
        elif args.action == "rollback":
            switch()
        else:
            raise SystemExit(launch(args.check))
    except (OSError, ValueError, sqlite3.Error) as error:
        raise SystemExit(str(error)) from None
