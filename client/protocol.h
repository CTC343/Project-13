#ifndef PROJECT13_PROTOCOL_H
#define PROJECT13_PROTOCOL_H

#include <winsock2.h>

#define PROTOCOL_BODY_SIZE 8192

int protocol_send_frame(SOCKET server_socket, const char *message_type,
                        int status, const char *json_body,
                        char *error_text, int error_size);
int protocol_receive_frame(SOCKET server_socket, char *message_type,
                           int type_size, int *status,
                           char *json_body, int body_size,
                           char *error_text, int error_size);
int json_get_string(const char *json, const char *name,
                    char *value, int value_size);
int json_get_long(const char *json, const char *name, long *value);

#endif
