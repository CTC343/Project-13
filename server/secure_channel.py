"""会话消息的加密、完整性校验和序号防重放。"""

import hashlib
import hmac
import json
import secrets


def hmac_hex(key, text):
    return hmac.new(key, text.encode("utf-8"), hashlib.sha256).hexdigest()


def derive_session_key(auth_key, client_nonce, server_nonce, session_id):
    material = f"SESSION|{client_nonce}|{server_nonce}|{session_id}"
    return hmac.new(auth_key, material.encode("utf-8"), hashlib.sha256).digest()


def _keystream(key, direction, session_id, sequence, nonce, size):
    output = bytearray()
    counter = 0
    # 8 字节序号和 16 字节 nonce 一并参与 HMAC，绑定本消息且避免密钥流复用。
    prefix = (
        direction.encode("ascii")
        + b"|"
        + session_id.encode("ascii")
        + b"|"
        + sequence.to_bytes(8, "big")
        + nonce
    )

    while len(output) < size:
        # SHA-256 每次输出 32 字节；4 字节计数器区分同一消息内的密钥流块。
        block = hmac.new(
            key, prefix + counter.to_bytes(4, "big"), hashlib.sha256
        ).digest()
        output.extend(block)
        counter += 1

    return bytes(output[:size])


def encrypt_message(key, direction, session_id, sequence, payload):
    plaintext = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    # 每帧使用 16 字节（128 位）随机 nonce，改变对应的密钥流输入。
    nonce = secrets.token_bytes(16)
    stream = _keystream(
        key, direction, session_id, sequence, nonce, len(plaintext)
    )
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream))
    nonce_hex = nonce.hex()
    ciphertext_hex = ciphertext.hex()
    tag_text = (
        f"{direction}|{session_id}|{sequence}|{nonce_hex}|{ciphertext_hex}"
    )

    return {
        "session_id": session_id,
        "sequence": sequence,
        "nonce": nonce_hex,
        "ciphertext": ciphertext_hex,
        "tag": hmac_hex(key, tag_text),
    }


def decrypt_message(key, direction, expected_session, expected_sequence, envelope):
    try:
        session_id = envelope["session_id"]
        sequence = int(envelope["sequence"])
        nonce_hex = envelope["nonce"]
        ciphertext_hex = envelope["ciphertext"]
        received_tag = envelope["tag"]
        nonce = bytes.fromhex(nonce_hex)
        ciphertext = bytes.fromhex(ciphertext_hex)
    except (KeyError, TypeError, ValueError):
        raise ValueError("invalid secure envelope") from None

    if session_id != expected_session:
        raise ValueError("session id does not match")
    if sequence != expected_sequence:
        raise ValueError("message sequence is replayed or out of order")
    # nonce 长度固定为 16 字节，与加密端生成长度一致。
    if len(nonce) != 16:
        raise ValueError("invalid message nonce")

    tag_text = (
        f"{direction}|{session_id}|{sequence}|{nonce_hex}|{ciphertext_hex}"
    )
    expected_tag = hmac_hex(key, tag_text)
    if not hmac.compare_digest(received_tag, expected_tag):
        raise ValueError("message authentication failed")

    stream = _keystream(
        key, direction, session_id, sequence, nonce, len(ciphertext)
    )
    plaintext = bytes(a ^ b for a, b in zip(ciphertext, stream))
    try:
        value = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("decrypted body is not valid JSON") from None

    if not isinstance(value, dict):
        raise ValueError("decrypted body must be a JSON object")
    return value


class SecureSession:
    def __init__(self, session_id, session_key):
        self.session_id = session_id
        self.session_key = session_key
        self.send_sequence = 0
        self.receive_sequence = 0

    def protect_server_message(self, payload):
        self.send_sequence += 1
        return encrypt_message(
            self.session_key, "S2C", self.session_id,
            self.send_sequence, payload
        )

    def open_client_message(self, envelope):
        self.receive_sequence += 1
        try:
            return decrypt_message(
                self.session_key, "C2S", self.session_id,
                self.receive_sequence, envelope
            )
        except ValueError:
            self.receive_sequence -= 1
            raise
