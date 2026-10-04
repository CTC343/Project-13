"""P13/1 协议：固定 Header 描述 JSON Body 长度，解决粘包和拆包。"""

import json

from config import MAX_BODY, MAX_HEADER, PROTOCOL_VERSION


STATUS_OK = 200
STATUS_BAD_REQUEST = 400
STATUS_UNAUTHORIZED = 401
STATUS_FORBIDDEN = 403
STATUS_CONFLICT = 409
STATUS_TOO_LARGE = 413
STATUS_UNPROCESSABLE = 422
STATUS_SERVER_ERROR = 500


class ProtocolError(Exception):
    def __init__(self, message, status=STATUS_BAD_REQUEST):
        super().__init__(message)
        self.status = status


def _receive_until_newline(client_socket):
    data = bytearray()
    while len(data) <= MAX_HEADER:
        chunk = client_socket.recv(1)
        if not chunk:
            raise ProtocolError("connection closed before header")
        if chunk == b"\n":
            return bytes(data)
        data.extend(chunk)
    raise ProtocolError("header is too long", STATUS_TOO_LARGE)


def _receive_exact(client_socket, body_length):
    data = bytearray()
    while len(data) < body_length:
        chunk = client_socket.recv(body_length - len(data))
        if not chunk:
            raise ProtocolError("connection closed before body")
        data.extend(chunk)
    return bytes(data)


def receive_frame(client_socket):
    header = _receive_until_newline(client_socket)
    try:
        version, message_type, status_text, length_text = header.decode(
            "ascii"
        ).split()
        status = int(status_text)
        body_length = int(length_text)
    except (UnicodeDecodeError, ValueError):
        raise ProtocolError("invalid protocol header") from None

    if version != PROTOCOL_VERSION:
        raise ProtocolError("unsupported protocol version")
    if not message_type.replace("_", "").isalnum():
        raise ProtocolError("invalid message type")
    if body_length < 2 or body_length > MAX_BODY:
        raise ProtocolError("invalid body length", STATUS_TOO_LARGE)

    body_bytes = _receive_exact(client_socket, body_length)
    try:
        body = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProtocolError("body is not valid JSON") from None
    if not isinstance(body, dict):
        raise ProtocolError("body must be a JSON object")
    return message_type, status, body


def send_frame(client_socket, message_type, status, body):
    body_bytes = json.dumps(
        body, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    if len(body_bytes) > MAX_BODY:
        raise ProtocolError("response body is too large", STATUS_TOO_LARGE)
    header = (
        f"{PROTOCOL_VERSION} {message_type} {status} {len(body_bytes)}\n"
    ).encode("ascii")
    client_socket.sendall(header + body_bytes)


def send_error(client_socket, status, detail):
    send_frame(client_socket, "ERROR", status, {"detail": detail})
