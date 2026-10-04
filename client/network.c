/* Winsock 相关操作集中在这里，业务代码不直接处理底层收发细节。 */
#include <winsock2.h>
#include <stdio.h>
#include <string.h>

#include "network.h"

#define SOCKET_TIMEOUT_MS 5000

int network_start(char *error_text, int error_size)
{
    WSADATA winsock_data;
    int error_code;

    error_code = WSAStartup(MAKEWORD(2, 2), &winsock_data);
    if (error_code != 0) {
        snprintf(error_text, error_size,
                 "WSAStartup failed: %d", error_code);
        return 0;
    }
    return 1;
}

SOCKET network_connect(const char *server_ip, int server_port,
                       char *error_text, int error_size)
{
    SOCKET server_socket;
    struct sockaddr_in server_address = {0};
    DWORD timeout = SOCKET_TIMEOUT_MS;

    server_socket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (server_socket == INVALID_SOCKET) {
        snprintf(error_text, error_size,
                 "socket failed: %d", WSAGetLastError());
        return INVALID_SOCKET;
    }

    setsockopt(server_socket, SOL_SOCKET, SO_RCVTIMEO,
               (const char *)&timeout, sizeof(timeout));
    setsockopt(server_socket, SOL_SOCKET, SO_SNDTIMEO,
               (const char *)&timeout, sizeof(timeout));

    server_address.sin_family = AF_INET;
    server_address.sin_port = htons(server_port);
    server_address.sin_addr.s_addr = inet_addr(server_ip);

    if (connect(server_socket,
                (struct sockaddr *)&server_address,
                sizeof(server_address)) == SOCKET_ERROR) {
        snprintf(error_text, error_size,
                 "connect failed: %d. Start server first.",
                 WSAGetLastError());
        closesocket(server_socket);
        return INVALID_SOCKET;
    }

    return server_socket;
}

SOCKET network_connect_retry(const char *server_ip, int server_port,
                             int attempts, char *error_text, int error_size)
{
    SOCKET server_socket = INVALID_SOCKET;
    int attempt;
    for (attempt = 1; attempt <= attempts; attempt++) {
        server_socket = network_connect(
            server_ip, server_port, error_text, error_size
        );
        if (server_socket != INVALID_SOCKET) return server_socket;
        if (attempt < attempts) Sleep((DWORD)(250 * attempt));
    }
    return INVALID_SOCKET;
}

int network_send_bytes(SOCKET server_socket, const char *message,
                       int message_length, char *error_text, int error_size)
{
    int sent_length = 0;
    while (sent_length < message_length) {
        int sent_now = send(server_socket, message + sent_length,
                            message_length - sent_length, 0);
        if (sent_now == SOCKET_ERROR || sent_now == 0) {
            snprintf(error_text, error_size,
                     "send failed: %d", WSAGetLastError());
            return 0;
        }
        sent_length += sent_now;
    }
    return 1;
}

int network_send_all(SOCKET server_socket, const char *message,
                     char *error_text, int error_size)
{
    return network_send_bytes(server_socket, message, (int)strlen(message),
                              error_text, error_size);
}

int network_receive_line(SOCKET server_socket, char *line, int line_size,
                         char *error_text, int error_size)
{
    int received_length = 0;

    while (received_length < line_size - 1) {
        int received_now;
        char *newline;

        received_now = recv(server_socket, line + received_length, 1, 0);

        if (received_now == SOCKET_ERROR) {
            snprintf(error_text, error_size,
                     "recv failed: %d", WSAGetLastError());
            return 0;
        }
        if (received_now == 0) {
            snprintf(error_text, error_size,
                     "Server closed before a complete reply.");
            return 0;
        }

        received_length += received_now;
        line[received_length] = '\0';
        newline = strchr(line, '\n');
        if (newline != NULL) {
            *newline = '\0';
            return 1;
        }
    }

    snprintf(error_text, error_size, "Reply is too long.");
    return 0;
}

int network_receive_exact(SOCKET server_socket, char *data, int data_size,
                          char *error_text, int error_size)
{
    int received_length = 0;
    while (received_length < data_size) {
        int received_now = recv(server_socket, data + received_length,
                                data_size - received_length, 0);
        if (received_now == SOCKET_ERROR) {
            snprintf(error_text, error_size,
                     "recv failed: %d", WSAGetLastError());
            return 0;
        }
        if (received_now == 0) {
            snprintf(error_text, error_size,
                     "Server closed before complete body.");
            return 0;
        }
        received_length += received_now;
    }
    return 1;
}

void network_close(SOCKET server_socket)
{
    if (server_socket != INVALID_SOCKET) {
        closesocket(server_socket);
    }
    WSACleanup();
}
