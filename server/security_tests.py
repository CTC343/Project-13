"""不依赖正在运行的服务端，检查主要安全边界并保存 JSON 报告。"""

import json
import re
import secrets
import socket
import time
from pathlib import Path

from credential_store import CredentialStore, PROJECT_ROOT, file_sha256
from protocol import ProtocolError, receive_frame, send_frame
from secure_channel import decrypt_message, encrypt_message, hmac_hex
from rsa_keys import read_private_key
from signature import SHA256_DIGEST_INFO_PREFIX, sign_task
import hashlib


REPORT_FILE = PROJECT_ROOT / "data" / "security_tests.json"


def check(name, function):
    try:
        function()
        return {"name": name, "passed": True, "detail": "防护生效"}
    except Exception as error:
        return {"name": name, "passed": False, "detail": str(error)}


def test_encrypted_roundtrip():
    key = secrets.token_bytes(32)
    envelope = encrypt_message(key, "C2S", "session-test", 1, {"value": 7})
    body = decrypt_message(key, "C2S", "session-test", 1, envelope)
    if body != {"value": 7}:
        raise AssertionError("解密结果不一致")


def test_tamper_rejected():
    key = secrets.token_bytes(32)
    envelope = encrypt_message(key, "C2S", "session-test", 1, {"value": 7})
    old = envelope["ciphertext"]
    envelope["ciphertext"] = ("0" if old[0] != "0" else "1") + old[1:]
    try:
        decrypt_message(key, "C2S", "session-test", 1, envelope)
    except ValueError:
        return
    raise AssertionError("篡改消息未被拒绝")


def test_replay_rejected():
    key = secrets.token_bytes(32)
    envelope = encrypt_message(key, "C2S", "session-test", 1, {"value": 7})
    decrypt_message(key, "C2S", "session-test", 1, envelope)
    try:
        decrypt_message(key, "C2S", "session-test", 2, envelope)
    except ValueError:
        return
    raise AssertionError("旧序号消息未被拒绝")


def make_auth_request(store, node_id, nonce, tag_override=None):
    record = store.records[node_id]
    exe_hashes = record.get("allowed_exe_hashes", [])
    exe_hash = exe_hashes[0] if exe_hashes else "0" * 64
    timestamp = int(time.time())
    auth_text = (
        f"{node_id}|{record['license_id']}|{timestamp}|{nonce}|{exe_hash}|0"
    )
    key = bytes.fromhex(record["auth_key"])
    return {
        "node_id": node_id,
        "license_id": record["license_id"],
        "timestamp": timestamp,
        "client_nonce": nonce,
        "exe_hash": exe_hash,
        "auth_tag": tag_override or hmac_hex(key, auth_text),
        "persistent": 0,
    }


def test_identity_spoof_rejected():
    store = CredentialStore()
    request = make_auth_request(store, "node-01", secrets.token_hex(16), "0" * 64)
    try:
        store.authenticate(request)
    except ValueError:
        return
    raise AssertionError("伪造身份未被拒绝")


def test_auth_replay_rejected():
    store = CredentialStore()
    request = make_auth_request(store, "node-01", secrets.token_hex(16))
    store.authenticate(request)
    try:
        store.authenticate(request)
    except ValueError:
        return
    raise AssertionError("重复登录随机数未被拒绝")


def test_sticky_and_fragmented_frames():
    left, right = socket.socketpair()
    try:
        send_frame(left, "ONE", 200, {"number": 1})
        send_frame(left, "TWO", 200, {"number": 2})
        first = receive_frame(right)
        second = receive_frame(right)
        if first[0] != "ONE" or second[0] != "TWO":
            raise AssertionError("连续协议帧边界错误")
    finally:
        left.close()
        right.close()


def test_oversized_body_rejected():
    left, right = socket.socketpair()
    try:
        left.sendall(b"P13/1 AUTH 0 9000\n{}")
        try:
            receive_frame(right)
        except ProtocolError as error:
            if error.status == 413:
                return
        raise AssertionError("超长消息未被拒绝")
    finally:
        left.close()
        right.close()


def test_executable_allowlist():
    store = CredentialStore()
    allowed = set(store.records["node-01"].get("allowed_exe_hashes", []))
    for name in ("client.exe", "client_gui.exe"):
        path = PROJECT_ROOT / "client" / name
        if path.exists() and file_sha256(path) not in allowed:
            raise AssertionError(f"{name} 不在完整性白名单")


def test_rsa_task_signature():
    modulus, public_exponent, _, _, _ = read_private_key()
    if modulus.bit_length() < 2048:
        raise AssertionError("任务签名密钥不足 2048 位")
    text = "task-security-test|SUM_RANGE|1|20"
    signature = int(sign_task(text), 16)
    key_size = (modulus.bit_length() + 7) // 8
    encoded = pow(signature, public_exponent, modulus).to_bytes(
        key_size, "big"
    )
    expected_tail = SHA256_DIGEST_INFO_PREFIX + hashlib.sha256(
        text.encode("utf-8")
    ).digest()
    if not encoded.startswith(b"\x00\x01\xff") or not encoded.endswith(expected_tail):
        raise AssertionError("RSA 任务签名验证失败")


def test_no_dangerous_calls():
    banned = ("gets", "strcpy", "strcat", "system", "rand")
    source_files = list((PROJECT_ROOT / "client").glob("*.c"))
    findings = []
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        for token in banned:
            if re.search(rf"\b{token}\s*\(", text):
                findings.append(f"{path.name}:{token}")
    if findings:
        raise AssertionError("发现危险调用 " + ", ".join(findings))


def create_report():
    cases = [
        ("安全会话加解密", test_encrypted_roundtrip),
        ("消息篡改拦截", test_tamper_rejected),
        ("会话重放拦截", test_replay_rejected),
        ("伪造节点身份拦截", test_identity_spoof_rejected),
        ("登录随机数重放拦截", test_auth_replay_rejected),
        ("TCP 粘包/拆包处理", test_sticky_and_fragmented_frames),
        ("非法超长输入拦截", test_oversized_body_rejected),
        ("客户端程序完整性", test_executable_allowlist),
        ("RSA-2048 任务签名", test_rsa_task_signature),
        ("危险 C 函数静态扫描", test_no_dangerous_calls),
    ]
    results = [check(name, function) for name, function in cases]
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "passed": sum(item["passed"] for item in results),
        "total": len(results),
        "all_passed": all(item["passed"] for item in results),
        "results": results,
    }
    REPORT_FILE.parent.mkdir(exist_ok=True)
    REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def read_security_test_report():
    if not REPORT_FILE.exists():
        return {}
    return json.loads(REPORT_FILE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    result = create_report()
    for item in result["results"]:
        print(f"{'PASS' if item['passed'] else 'FAIL'} {item['name']}: {item['detail']}")
    raise SystemExit(0 if result["all_passed"] else 1)
