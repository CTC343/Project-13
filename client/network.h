#ifndef PROJECT13_NETWORK_H
#define PROJECT13_NETWORK_H

#include <winsock2.h>

#define NETWORK_ERROR_SIZE 256

int network_start(char *error_text, int error_size);
SOCKET network_connect(const char *server_ip, int server_port,
                       char *error_text, int error_size);
SOCKET network_connect_retry(const char *server_ip, int server_port,
                             int attempts, char *error_text, int error_size);
int network_send_bytes(SOCKET server_socket, const char *message,
                       int message_length, char *error_text, int error_size);
int network_send_all(SOCKET server_socket, const char *message,
                     char *error_text, int error_size);
int network_receive_line(SOCKET server_socket, char *line, int line_size,
                         char *error_text, int error_size);
int network_receive_exact(SOCKET server_socket, char *data, int data_size,
                          char *error_text, int error_size);
void network_close(SOCKET server_socket);

#endif
