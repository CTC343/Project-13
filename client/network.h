#ifndef PROJECT13_NETWORK_H
#define PROJECT13_NETWORK_H

#include <winsock2.h>

#define NETWORK_ERROR_SIZE 256

typedef struct ssl_ctx_st SSL_CTX;
typedef struct ssl_st SSL;

typedef struct {
    SOCKET socket_value;
    SSL_CTX *tls_context;
    SSL *tls;
    char buffer[8192];
    int buffer_start;
    int buffer_end;
    int started;
    int security_error;
} NetworkConnection;

/* 1 means connected, 0 means retryable transport failure, -1 means TLS/configuration failure. */
int network_connect(NetworkConnection *connection, const char *host, int port,
                    const char *profile, char *error_text, int error_size);
int network_send_bytes(NetworkConnection *connection, const char *message,
                       int message_length, char *error_text, int error_size);
int network_receive_line(NetworkConnection *connection, char *line,
                         int line_size, char *error_text, int error_size);
int network_receive_exact(NetworkConnection *connection, char *data,
                          int data_size, char *error_text, int error_size);
void network_close(NetworkConnection *connection);

#endif
