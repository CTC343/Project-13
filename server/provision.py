"""Provision the demonstration CA, certificate bundles, licenses and named accounts."""

import argparse
import csv
import getpass
import ipaddress
import json
import os
import re
from pathlib import Path
import shutil
import sqlite3
import subprocess
from tempfile import TemporaryDirectory

from accounts import ACCOUNT_ID, AccountStore, ROLES
from config import CLIENT_DIR, DATA_DIR, TLS_DIR
from credential_store import approve_clients
from rsa_keys import ensure_task_signing_keys


def restrict_directory(path):
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        who = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True).strip()
        account_sid = next(csv.reader([who]))[1]
        subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r",
                        f"*{account_sid}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"],
                       check=True, stdout=subprocess.DEVNULL)
    else:
        path.chmod(0o700)


class Issuer:
    def __init__(self, openssl, initialize=True):
        self.openssl = str(Path(openssl).resolve())
        self.directory = DATA_DIR / "issuer"
        self.config = self.directory / "issuer.cnf"
        if not initialize:
            if not all(path.exists() for path in
                       (self.config, self.directory / "ca.pem", self.directory / "ca.key")):
                raise ValueError("Enrollment issuer is not provisioned.")
            return
        restrict_directory(self.directory)
        self.config.write_text("""
[ ca ]
default_ca = project13
[ project13 ]
database = index.txt
serial = serial
crlnumber = crlnumber
new_certs_dir = issued
certificate = ca.pem
private_key = ca.key
default_md = sha256
default_days = 30
default_crl_days = 7
policy = issuance
unique_subject = no
[ issuance ]
commonName = supplied
""".lstrip(), encoding="ascii")
        (self.directory / "issued").mkdir(exist_ok=True)
        for name, initial in (("index.txt", ""), ("serial", "1000\n"), ("crlnumber", "1000\n")):
            path = self.directory / name
            if not path.exists():
                path.write_text(initial, encoding="ascii")
        if not (self.directory / "ca.pem").exists():
            if (self.directory / "ca.key").exists():
                raise ValueError("Incomplete CA. Recover the existing CA certificate before continuing.")
            self.run("req", "-x509", "-newkey", "rsa:3072", "-noenc", "-sha256", "-days", "365",
                     "-subj", "/CN=Project13 classroom CA", "-keyout", "ca.key", "-out", "ca.pem",
                     "-addext", "basicConstraints=critical,CA:TRUE,pathlen:0",
                     "-addext", "keyUsage=critical,keyCertSign,cRLSign")

    def run(self, *args):
        result = subprocess.run([self.openssl, *args], cwd=self.directory, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace"))

    def issue(self, name, identities, leaf_dir, purpose):
        cert_path = leaf_dir / f"{name}.pem"
        key_path = leaf_dir / f"{name}.key"
        if cert_path.exists() or key_path.exists():
            if not cert_path.exists() or not key_path.exists():
                raise ValueError(f"Incomplete certificate pair for {name}. Restore or rotate it explicitly.")
            output = subprocess.check_output(
                [self.openssl, "x509", "-in", str(cert_path), "-noout", "-ext", "subjectAltName"],
                encoding="ascii",
            )
            for identity in identities.split(","):
                expected = identity.replace("IP:", "IP Address:")
                if expected not in output:
                    raise ValueError(f"Existing certificate for {name} has a different address. Rotate it explicitly.")
            return
        with TemporaryDirectory(dir=self.directory) as temporary:
            work = Path(temporary)
            extension = work / "leaf.cnf"
            extension.write_text(f"""[leaf]
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage={purpose}
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
subjectAltName={identities}
""", encoding="ascii")
            self.run("req", "-new", "-newkey", "rsa:2048", "-noenc", "-keyout",
                     str(work / "leaf.key"), "-out", str(work / "leaf.csr"), "-subj", f"/CN={name}")
            self.run("ca", "-batch", "-config", str(self.config), "-notext",
                     "-in", str(work / "leaf.csr"), "-out", str(work / "leaf.pem"),
                     "-extfile", str(extension), "-extensions", "leaf")
            (work / "leaf.key").replace(key_path)
            (work / "leaf.pem").replace(cert_path)

    def publish_trust(self):
        self.run("ca", "-config", str(self.config), "-gencrl", "-out", "current.crl")
        bundle = (self.directory / "ca.pem").read_bytes() + (self.directory / "current.crl").read_bytes()
        for folder in (TLS_DIR, CLIENT_DIR / "tls"):
            temporary = folder / "trust.tmp"
            temporary.write_bytes(bundle)
            temporary.replace(folder / "trust.pem")

    def enroll(self, node, csr):
        devices = TLS_DIR / "devices"
        devices.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=self.directory) as temporary:
            work = Path(temporary)
            request = work / "device.csr"
            request.write_bytes(csr)
            self.run("req", "-in", str(request), "-noout", "-verify")
            extension = work / "leaf.cnf"
            extension.write_text(f"""[leaf]
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=clientAuth
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
subjectAltName=DNS:{node}
""", encoding="ascii")
            cert = devices / f"{node}.pem"
            self.run("ca", "-batch", "-config", str(self.config), "-notext",
                     "-subj", f"/CN={node}", "-in", str(request), "-out", str(cert),
                     "-extfile", str(extension), "-extensions", "leaf")
            return cert.read_text(encoding="ascii")


def server_name(value):
    try:
        return f"IP:{ipaddress.ip_address(value)}"
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", value):
            raise ValueError(f"invalid server DNS name: {value}") from None
        return f"DNS:{value}"


def provision(args):
    if not all((CLIENT_DIR / name).is_file() for name in ("client.exe", "client_gui.exe")):
        raise ValueError("Build both clients before provisioning.")
    restrict_directory(DATA_DIR)
    (CLIENT_DIR / "tls").mkdir(exist_ok=True)
    restrict_directory(TLS_DIR)
    approve_clients()
    ensure_task_signing_keys()
    issuer = Issuer(args.openssl)
    addresses = args.server_name or ["localhost", "127.0.0.1"]
    issuer.issue("server", ",".join(server_name(name) for name in addresses), TLS_DIR, "serverAuth")
    issuer.publish_trust()
    AccountStore()
    (DATA_DIR / "issuer-tool.json").write_text(json.dumps({"openssl": issuer.openssl}), encoding="utf-8")
    print("Service and trust bundle ready. Create user accounts with the account command.")


def cli():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "refresh-crl", "revoke", "rotate"):
        command = commands.add_parser(name)
        command.add_argument("--openssl", default=os.environ.get("PROJECT13_OPENSSL", shutil.which("openssl")))
        if name in ("revoke", "rotate"):
            command.add_argument("identity")
        if name in ("init", "rotate"):
            command.add_argument("--server-name", action="append")
    account = commands.add_parser("account")
    account.add_argument("username")
    account.add_argument("role", choices=ROLES)
    args = parser.parse_args()
    if args.command == "account":
        if not (DATA_DIR / "accounts.sqlite3").is_file():
            raise ValueError(f"账号库尚未初始化或当前账号无法访问 {DATA_DIR}。")
        first = getpass.getpass("New password (12-256 UTF-8 bytes): ")
        if first != getpass.getpass("Confirm password: "):
            raise ValueError("Passwords do not match.")
        try:
            AccountStore().set_password(args.username, args.role, None, first.encode("utf-8"))
        except sqlite3.OperationalError as error:
            raise ValueError(f"无法写入账号库 {DATA_DIR / 'accounts.sqlite3'}：{error}") from None
        print("Account saved.")
        return
    if not args.openssl:
        raise ValueError("Set PROJECT13_OPENSSL or pass --openssl with an installed OpenSSL 3 executable.")
    if args.command == "init":
        provision(args)
        return
    issuer = Issuer(args.openssl)
    if args.command in ("revoke", "rotate"):
        if not ACCOUNT_ID.fullmatch(args.identity):
            raise ValueError("invalid certificate identity")
        is_server = args.identity == "server"
        if args.command == "rotate" and not is_server:
            raise ValueError("Revoke the old device, then sign in with a fresh client profile to enroll again.")
        folder = TLS_DIR if is_server else TLS_DIR / "devices"
        cert = folder / f"{args.identity}.pem"
        key = folder / f"{args.identity}.key"
        issuer.run("ca", "-config", str(issuer.config), "-revoke", str(cert))
        issuer.publish_trust()
        if args.command == "rotate":
            archive = issuer.directory / "retired"
            archive.mkdir(exist_ok=True)
            name = f"{args.identity}-{os.stat(cert).st_mtime_ns}"
            cert.replace(archive / (name + ".pem"))
            key.replace(archive / (name + ".key"))
            identities = ",".join(server_name(name) for name in (args.server_name or ["localhost", "127.0.0.1"]))
            issuer.issue(args.identity, identities if is_server else f"DNS:{args.identity}",
                         folder, "serverAuth" if is_server else "clientAuth")
    issuer.publish_trust()
    print("Trust bundle published. Redeploy it to clients and restart the service to apply it.")


if __name__ == "__main__":
    try:
        cli()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
