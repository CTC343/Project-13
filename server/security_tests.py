"""Local checks for the deployed credentials, framing and task signatures."""

from datetime import datetime, timezone
import hashlib
import json
import re
import secrets
import socket
import ssl

from accounts import SCRYPT_N, SCRYPT_P, SCRYPT_R, derive
from config import CLIENT_DIR, DATA_DIR, PROJECT_ROOT
from credential_store import CredentialStore, file_sha256
from protocol import ProtocolError, receive_frame, send_frame
from rsa_keys import read_private_key
from signature import SHA256_DIGEST_INFO_PREFIX, sign_task
from tls_transport import server_context

REPORT_FILE = DATA_DIR / "security_tests.json"


def check_tls():
    context = server_context()
    assert context.minimum_version == context.maximum_version == ssl.TLSVersion.TLSv1_3
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.verify_flags & ssl.VERIFY_CRL_CHECK_CHAIN == ssl.VERIFY_CRL_CHECK_CHAIN


def check_scrypt():
    password = secrets.token_bytes(32)
    first, second = secrets.token_bytes(16), secrets.token_bytes(16)
    assert derive(password, first, SCRYPT_N, SCRYPT_R, SCRYPT_P) != derive(password, second, SCRYPT_N, SCRYPT_R, SCRYPT_P)


def check_frames():
    left, right = socket.socketpair()
    with left, right:
        left.settimeout(2)
        right.settimeout(2)
        for chunk in (b"P13/1 ONE 200 ", b"7\n{", b'"n":1}', b"P13/1 TWO 200 2\n{}"):
            left.sendall(chunk)
        assert receive_frame(right) == ("ONE", 200, {"n": 1})
        assert receive_frame(right) == ("TWO", 200, {})
        left.sendall(b"P13/1 AUTH 0 9000\n{}")
        try:
            receive_frame(right)
        except ProtocolError as error:
            assert error.status == 413
        else:
            raise AssertionError("oversized frame accepted")


def check_build_hashes():
    store = CredentialStore()
    for name in ("client.exe", "client_gui.exe"):
        store.verify_executable(file_sha256(CLIENT_DIR / name))


def check_task_signature():
    modulus, exponent, *_ = read_private_key()
    assert modulus.bit_length() == 2048
    text = "task-security-test|SUM_RANGE|1|20"
    signature = int(sign_task(text), 16)
    decoded = pow(signature, exponent, modulus).to_bytes(256, "big")
    tail = SHA256_DIGEST_INFO_PREFIX + hashlib.sha256(text.encode()).digest()
    assert decoded == b"\x00\x01" + b"\xff" * (253 - len(tail)) + b"\x00" + tail


def check_c_calls():
    banned = re.compile(r"\b(?:gets|strcpy|strcat|system|rand)\s*\(")
    for path in (PROJECT_ROOT / "client").glob("*.c"):
        assert not banned.search(path.read_text(encoding="utf-8")), path.name


def create_report():
    cases = (
        ("TLS 1.3 双向证书和吊销配置", check_tls),
        ("scrypt 随机盐差异", check_scrypt),
        ("粘包、拆包和超长帧限制", check_frames),
        ("当前可执行文件白名单", check_build_hashes),
        ("RSA 任务签名", check_task_signature),
        ("危险 C 函数静态扫描", check_c_calls),
    )
    results = []
    for name, test in cases:
        try:
            test()
        except Exception as error:
            results.append({"name": name, "passed": False, "detail": type(error).__name__})
        else:
            results.append({"name": name, "passed": True, "detail": "通过"})
    passed = sum(item["passed"] for item in results)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "passed": passed, "total": len(results), "all_passed": passed == len(results),
              "results": results}
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def read_security_test_report():
    if not REPORT_FILE.exists():
        return {}
    return json.loads(REPORT_FILE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    result = create_report()
    for item in result["results"]:
        print(f"{'PASS' if item['passed'] else 'FAIL'} {item['name']}")
    raise SystemExit(0 if result["all_passed"] else 1)
