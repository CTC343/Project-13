"""One requested window preview, transported through a separate mTLS connection."""

from dataclasses import dataclass
import json
import mmap
import re
import secrets
import struct
import threading
import time

from accounts import ACCOUNT_ID
from config import DATA_DIR
from protocol import ProtocolError, send_error, send_frame
from security_audit import record_security_event
from tls_transport import node_certificate

REQUEST = DATA_DIR / "window-preview.json"
VIEW_ID = re.compile(r"[0-9a-f]{32}\Z")
FRAME_INTERVAL = 1.0
LEASE_SECONDS = 3
MAX_IMAGE_BYTES = 512 * 1024
MAX_WIDTH, MAX_HEIGHT = 960, 720
PNG_HEADER = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"
LEASE = struct.Struct("<d")
SEQUENCE = struct.Struct("<Q")
FRAME = struct.Struct("<QId")
LENGTH = struct.Struct("!I")
IMAGE_OFFSET = LEASE.size + FRAME.size


def open_mapping(view_id):
    return mmap.mmap(-1, IMAGE_OFFSET + MAX_IMAGE_BYTES, tagname=f"Local\\Project13Window-{view_id}")


def selected_view():
    try:
        with REQUEST.open("rb") as stream:
            request = json.loads(stream.read(512))
        view_id, node_id = request["view_id"], request["node_id"]
        if VIEW_ID.fullmatch(view_id) and ACCOUNT_ID.fullmatch(node_id):
            return view_id, node_id
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


class PreviewSource:
    """The local control center owns the lease and keeps image data in memory."""

    def __init__(self, node_id):
        if not ACCOUNT_ID.fullmatch(node_id):
            raise ValueError("invalid node")
        self.view_id = secrets.token_hex(16)
        self.mapping = open_mapping(self.view_id)
        request = REQUEST.with_name(f".window-preview-{self.view_id}.tmp")
        try:
            self.renew()
            request.write_text(json.dumps({"view_id": self.view_id, "node_id": node_id}), encoding="ascii")
            request.replace(REQUEST)
        except OSError:
            self.mapping.close()
            request.unlink(missing_ok=True)
            raise

    def renew(self):
        LEASE.pack_into(self.mapping, 0, time.monotonic() + LEASE_SECONDS)

    def frame(self):
        sequence, size, captured = FRAME.unpack_from(self.mapping, LEASE.size)
        if not sequence or sequence % 2 or size > MAX_IMAGE_BYTES:
            return None
        image = self.mapping[IMAGE_OFFSET:IMAGE_OFFSET + size]
        if SEQUENCE.unpack_from(self.mapping, LEASE.size)[0] != sequence:
            return None
        return sequence, captured, image

    def close(self):
        LEASE.pack_into(self.mapping, 0, 0)
        self.mapping.close()


@dataclass
class View:
    view_id: str
    node_id: str
    mapping: mmap.mmap
    stream_active: bool = False


class PreviewBroker:
    """Routes only the selected, consenting node to the local viewer."""

    def __init__(self):
        self._lock = threading.Lock()
        self._selection = None
        self._view = None
        self._allowed = set()

    def refresh(self):
        selection = selected_view()
        with self._lock:
            if selection == self._selection:
                if self._view and not LEASE.unpack_from(self._view.mapping)[0]:
                    self._view.mapping.close()
                    self._view = None
                return
            self._selection = selection
            if self._view:
                self._view.mapping.close()
                self._view = None
            if selection:
                try:
                    self._view = View(*selection, open_mapping(selection[0]))
                except OSError:
                    pass

    def offer(self, node_id, allowed):
        with self._lock:
            if allowed:
                self._allowed.add(node_id)
            else:
                self._allowed.discard(node_id)
            view = self._view
            return view.view_id if view and self._live(view, node_id) else ""

    def _live(self, view, node_id):
        return (self._view is view and view.node_id == node_id and node_id in self._allowed
                and LEASE.unpack_from(view.mapping)[0] > time.monotonic())

    def _publish(self, view, node_id, data):
        with self._lock:
            if not self._live(view, node_id):
                return False
            sequence = (SEQUENCE.unpack_from(view.mapping, LEASE.size)[0] & ~1) + 2
            SEQUENCE.pack_into(view.mapping, LEASE.size, sequence - 1)
            view.mapping[IMAGE_OFFSET:IMAGE_OFFSET + len(data)] = data
            FRAME.pack_into(view.mapping, LEASE.size, sequence - 1, len(data), time.monotonic())
            SEQUENCE.pack_into(view.mapping, LEASE.size, sequence)
            return True

    def serve(self, connection, status, request, accounts, credentials):
        view = None
        node_id = request.get("node_id")
        try:
            if status != 0 or not isinstance(node_id, str) or not ACCOUNT_ID.fullmatch(node_id):
                raise ValueError("invalid preview request")
            certificate = node_certificate(connection, node_id)
            credentials.verify_executable(request.get("exe_hash"))
            username, token = request.get("username"), request.get("token")
            accounts.verify_device(node_id, username, request.get("license_id"), certificate)
            accounts.resume(token, username, node_id, certificate)
            with self._lock:
                candidate = self._view
                if (candidate is None or candidate.view_id != request.get("view_id") or
                        not self._live(candidate, node_id) or candidate.stream_active):
                    raise ValueError("preview not available")
                view = candidate
                view.stream_active = True
            send_frame(connection, "PREVIEW_OK", 200, {})
            record_security_event("WINDOW_SHARE_STARTED", node_id)
            while True:
                with self._lock:
                    if not self._live(view, node_id):
                        break
                accounts.resume(token, username, node_id, certificate)
                started = time.monotonic()
                send_frame(connection, "PREVIEW_PULL", 200, {})
                data = receive_image(connection)
                if not self._publish(view, node_id, data):
                    break
                time.sleep(max(0, FRAME_INTERVAL - (time.monotonic() - started)))
            send_frame(connection, "PREVIEW_STOPPED", 200, {})
        except (ValueError, ProtocolError):
            try:
                send_error(connection, 403, "preview not authorized or invalid frame")
            except OSError:
                pass
        except OSError:
            pass
        finally:
            if view:
                with self._lock:
                    view.stream_active = False
                record_security_event("WINDOW_SHARE_STOPPED", node_id)


def receive_image(connection):
    # A bounded binary image record follows the small P13 control frames.
    def read_exact(size):
        data = bytearray(size)
        position = 0
        while position < size:
            received = connection.recv_into(memoryview(data)[position:])
            if not received:
                raise OSError("preview connection closed")
            position += received
        return data

    size = LENGTH.unpack(read_exact(LENGTH.size))[0]
    if not size:
        return b""
    if not 33 <= size <= MAX_IMAGE_BYTES:
        raise ValueError("invalid image size")
    data = read_exact(size)
    if not data.startswith(PNG_HEADER):
        raise ValueError("invalid PNG")
    width, height = struct.unpack_from("!II", data, len(PNG_HEADER))
    if not 1 <= width <= MAX_WIDTH or not 1 <= height <= MAX_HEIGHT:
        raise ValueError("invalid image dimensions")
    return data
