"""Require authenticated TLS 1.3 before reading any application frames."""

import hashlib
import ssl

from config import TLS_DIR


def server_context(enrollment=False):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    context.num_tickets = 0
    if not enrollment:
        context.verify_mode = ssl.CERT_REQUIRED
        context.verify_flags |= ssl.VERIFY_CRL_CHECK_CHAIN
        context.load_verify_locations(cafile=TLS_DIR / "trust.pem")
    context.load_cert_chain(TLS_DIR / "server.pem", TLS_DIR / "server.key")
    return context


def node_certificate(socket, node_id):
    certificate = socket.getpeercert()
    if certificate.get("subjectAltName") != (("DNS", node_id),):
        raise ValueError("node does not match certificate name")
    return hashlib.sha256(socket.getpeercert(binary_form=True)).hexdigest()
