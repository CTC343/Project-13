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
    # Header 以换行符结束；逐字节读取，避免提前读走后续 Body 数据。
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
    # recv 可能只返回当前已到达的一部分数据；循环读取到指定长度才算收完整帧。
    data = bytearray()
    while len(data) < body_length:
        chunk = client_socket.recv(body_length - len(data))
        if not chunk:
            raise ProtocolError("connection closed before body")
        data.extend(chunk)
    return bytes(data)


def receive_frame(client_socket):
    # TCP 不提供消息边界；Header 中的 Body 长度用于判断本帧结束位置，
    # 否则无法区分一帧的结尾和下一帧的开头。
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
    # 限制消息类型字符，避免无效类型进入业务处理。
    if not message_type.replace("_", "").isalnum():
        raise ProtocolError("invalid message type")
    # Body 长度必须合理，避免读取空内容或超出协议上限。
    if body_length < 2 or body_length > MAX_BODY:
        raise ProtocolError("invalid body length", STATUS_TOO_LARGE)

    body_bytes = _receive_exact(client_socket, body_length)
    try:
        body = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProtocolError("body is not valid JSON") from None
    # 协议约定业务消息的 Body 必须是 JSON 对象。
    if not isinstance(body, dict):
        raise ProtocolError("body must be a JSON object")
    return message_type, status, body


def send_frame(client_socket, message_type, status, body):
    # 长度按 UTF-8 字节计算，而不是字符数；接收端靠它确定本帧边界。
    body_bytes = json.dumps(
        body, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    if len(body_bytes) > MAX_BODY:
        raise ProtocolError("response body is too large", STATUS_TOO_LARGE)
    # Header 格式：版本 消息类型 状态码 Body字节数\n，之后紧跟 JSON Body。
    header = (
        f"{PROTOCOL_VERSION} {message_type} {status} {len(body_bytes)}\n"
    ).encode("ascii")
    # sendall 会持续发送，直到全部字节交给系统发送；send 可能只发出一部分。
    client_socket.sendall(header + body_bytes)


def send_error(client_socket, status, detail):
    # 错误也使用同一帧格式发送，便于客户端按统一协议解析。
    send_frame(client_socket, "ERROR", status, {"detail": detail})
