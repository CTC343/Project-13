#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <stdio.h>
#include <string.h>

#include "network.h"
#include "openssl_api.h"
#include "security.h"

#define SOCKET_TIMEOUT_MS 5000

static int connect_with_timeout(SOCKET socket_value, const struct addrinfo *address)
{
    u_long nonblocking = 1;
    u_long blocking = 0;
    int result;
    if (ioctlsocket(socket_value, FIONBIO, &nonblocking) != 0) return 0;
    result = connect(socket_value, address->ai_addr, (int)address->ai_addrlen);
    if (result != 0 && WSAGetLastError() == WSAEWOULDBLOCK) {
        fd_set writable, failed;
        struct timeval limit = {SOCKET_TIMEOUT_MS / 1000, 0};
        int socket_error = 0;
        int length = sizeof(socket_error);
        FD_ZERO(&writable);
        FD_ZERO(&failed);
        FD_SET(socket_value, &writable);
        FD_SET(socket_value, &failed);
        result = select(0, NULL, &writable, &failed, &limit) > 0 &&
                 FD_ISSET(socket_value, &writable) &&
                 getsockopt(socket_value, SOL_SOCKET, SO_ERROR,
                            (char *)&socket_error, &length) == 0 &&
                 socket_error == 0 ? 0 : SOCKET_ERROR;
    }
    return ioctlsocket(socket_value, FIONBIO, &blocking) == 0 && result == 0;
}

static SOCKET connect_tcp(const char *host, int port)
{
    struct addrinfo hints = {0};
    struct addrinfo *addresses, *address;
    char service[8];
    SOCKET connected = INVALID_SOCKET;
    DWORD timeout = SOCKET_TIMEOUT_MS;
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_protocol = IPPROTO_TCP;
    snprintf(service, sizeof(service), "%d", port);
    if (getaddrinfo(host, service, &hints, &addresses) != 0) return INVALID_SOCKET;
    for (address = addresses; address != NULL; address = address->ai_next) {
        SOCKET candidate = socket(address->ai_family, address->ai_socktype, address->ai_protocol);
        if (candidate == INVALID_SOCKET) continue;
        if (setsockopt(candidate, SOL_SOCKET, SO_RCVTIMEO, (const char *)&timeout, sizeof(timeout)) == 0 &&
            setsockopt(candidate, SOL_SOCKET, SO_SNDTIMEO, (const char *)&timeout, sizeof(timeout)) == 0 &&
            connect_with_timeout(candidate, address)) {
            connected = candidate;
            break;
        }
        closesocket(candidate);
    }
    freeaddrinfo(addresses);
    return connected;
}

static int interrupted_tls(SSL *tls, int result)
{
    int kind = SSL_get_error(tls, result);
    unsigned long reason;
    switch (kind) {
    case SSL_ERROR_WANT_READ:
    case SSL_ERROR_WANT_WRITE:
    case SSL_ERROR_SYSCALL:
    case SSL_ERROR_ZERO_RETURN:
        return 1;
    case SSL_ERROR_SSL:
        reason = ERR_peek_last_error();
        return ((reason >> ERR_LIB_OFFSET) & ERR_LIB_MASK) == ERR_LIB_SSL &&
               (reason & ERR_REASON_MASK) == SSL_R_UNEXPECTED_EOF_WHILE_READING;
    default:
        return 0;
    }
}

int network_connect(NetworkConnection *connection, const char *host, int port,
                    const char *profile, char *error_text, int error_size)
{
    WSADATA data;
    char directory[MAX_PATH];
    char trust[MAX_PATH + 96], cert[MAX_PATH + 96], key[MAX_PATH + 96];
    unsigned char binary_address[16];
    char *separator;
    X509_VERIFY_PARAM *verify;
    int is_ip;
    int handshake;
    DWORD size;

    connection->socket_value = INVALID_SOCKET;
    if (WSAStartup(MAKEWORD(2, 2), &data) != 0) {
        snprintf(error_text, error_size, "Winsock startup failed.");
        return -1;
    }
    connection->started = 1;
    size = GetModuleFileNameA(NULL, directory, sizeof(directory));
    if (size == 0 || size >= sizeof(directory) ||
        (separator = strrchr(directory, '\\')) == NULL) {
        snprintf(error_text, error_size, "Cannot locate client deployment directory.");
        return -1;
    }
    *separator = '\0';
    snprintf(trust, sizeof(trust), "%s\\tls\\trust.pem", directory);
    snprintf(error_text, error_size, "TLS setup failed. Check trust bundle and the node certificate/key.");
    connection->tls_context = SSL_CTX_new(TLS_client_method());
    if (connection->tls_context == NULL ||
        !SSL_CTX_ctrl(connection->tls_context, SSL_CTRL_SET_MIN_PROTO_VERSION, TLS1_3_VERSION, NULL) ||
        !SSL_CTX_ctrl(connection->tls_context, SSL_CTRL_SET_MAX_PROTO_VERSION, TLS1_3_VERSION, NULL) ||
        !SSL_CTX_set_ciphersuites(connection->tls_context, "TLS_AES_256_GCM_SHA384:TLS_AES_128_GCM_SHA256") ||
        !SSL_CTX_load_verify_locations(connection->tls_context, trust, NULL)) return -1;
    if (profile != NULL) {
        snprintf(cert, sizeof(cert), "%s.pem", profile);
        snprintf(key, sizeof(key), "%s.key", profile);
        if (!SSL_CTX_use_certificate_chain_file(connection->tls_context, cert) ||
            !SSL_CTX_use_PrivateKey_file(connection->tls_context, key, SSL_FILETYPE_PEM) ||
            !SSL_CTX_check_private_key(connection->tls_context)) return -1;
    }
    SSL_CTX_set_verify(connection->tls_context, SSL_VERIFY_PEER, NULL);
    connection->tls = SSL_new(connection->tls_context);
    if (connection->tls == NULL) return -1;
    verify = SSL_get0_param(connection->tls);
    if (!X509_VERIFY_PARAM_set_flags(verify, X509_V_FLAG_CRL_CHECK | X509_V_FLAG_CRL_CHECK_ALL)) return -1;
    X509_VERIFY_PARAM_set_hostflags(verify, X509_CHECK_FLAG_NEVER_CHECK_SUBJECT);
    is_ip = InetPtonA(AF_INET, host, binary_address) == 1 || InetPtonA(AF_INET6, host, binary_address) == 1;
    if (is_ip) {
        if (!X509_VERIFY_PARAM_set1_ip_asc(verify, host)) return -1;
    } else if (!SSL_set1_host(connection->tls, host) ||
               !SSL_ctrl(connection->tls, SSL_CTRL_SET_TLSEXT_HOSTNAME, 0, (void *)host)) {
        return -1;
    }
    connection->socket_value = connect_tcp(host, port);
    if (connection->socket_value == INVALID_SOCKET) {
        snprintf(error_text, error_size, "Server unreachable at %s:%d.", host, port);
        return 0;
    }
    if (!SSL_set_fd(connection->tls, (int)connection->socket_value)) return -1;
    ERR_clear_error();
    handshake = SSL_connect(connection->tls);
    if (handshake != 1 && interrupted_tls(connection->tls, handshake) &&
        SSL_get_verify_result(connection->tls) == 0) {
        snprintf(error_text, error_size, "Connection interrupted before sign-in.");
        return 0;
    }
    if (handshake != 1 || SSL_get_verify_result(connection->tls) != 0) {
        snprintf(error_text, error_size, "TLS handshake rejected. Check certificates, service identity and time.");
        return -1;
    }
    return 1;
}

int network_send_bytes(NetworkConnection *connection, const char *message,
                       int message_length, char *error_text, int error_size)
{
    while (message_length > 0) {
        int written;
        ERR_clear_error();
        written = SSL_write(connection->tls, message, message_length);
        if (written <= 0) {
            connection->security_error = !interrupted_tls(connection->tls, written);
            snprintf(error_text, error_size, "%s", connection->security_error ?
                     "TLS rejected the connection." : "Connection lost while sending.");
            return 0;
        }
        message += written;
        message_length -= written;
    }
    return 1;
}

static int fill_buffer(NetworkConnection *connection, char *error_text, int error_size)
{
    if (connection->buffer_start < connection->buffer_end) return 1;
    connection->buffer_start = 0;
    ERR_clear_error();
    connection->buffer_end = SSL_read(connection->tls, connection->buffer, sizeof(connection->buffer));
    if (connection->buffer_end > 0) return 1;
    connection->security_error = !interrupted_tls(connection->tls, connection->buffer_end);
    snprintf(error_text, error_size, "%s", connection->security_error ?
             "TLS rejected the connection." : "Connection closed or timed out.");
    return 0;
}

int network_receive_line(NetworkConnection *connection, char *line,
                         int line_size, char *error_text, int error_size)
{
    int length = 0;
    while (length < line_size - 1) {
        char value;
        if (!fill_buffer(connection, error_text, error_size)) return 0;
        value = connection->buffer[connection->buffer_start++];
        if (value == '\n') {
            line[length] = '\0';
            return 1;
        }
        line[length++] = value;
    }
    snprintf(error_text, error_size, "Protocol header is too long.");
    return 0;
}

int network_receive_exact(NetworkConnection *connection, char *data,
                          int data_size, char *error_text, int error_size)
{
    while (data_size > 0) {
        int count;
        if (!fill_buffer(connection, error_text, error_size)) return 0;
        count = connection->buffer_end - connection->buffer_start;
        if (count > data_size) count = data_size;
        memcpy(data, connection->buffer + connection->buffer_start, count);
        connection->buffer_start += count;
        data += count;
        data_size -= count;
    }
    return 1;
}

void network_close(NetworkConnection *connection)
{
    SSL_free(connection->tls);
    SSL_CTX_free(connection->tls_context);
    if (connection->socket_value != INVALID_SOCKET) closesocket(connection->socket_value);
    if (connection->started) WSACleanup();
    clear_sensitive(connection, sizeof(*connection));
}
