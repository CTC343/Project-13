#ifndef PROJECT13_NETWORK_H
#define PROJECT13_NETWORK_H

#include <winsock2.h>

#define NETWORK_ERROR_SIZE 256

int network_start(char *error_text, /* 错误信息输出缓冲区 */
                  int error_size);  /* 错误信息缓冲区最大容量 */

SOCKET network_connect(const char *server_ip, /* 服务器 IP 地址 */
                       int server_port,       /* 服务器端口号 */
                       char *error_text,      /* 错误信息输出缓冲区 */
                       int error_size);       /* 错误信息缓冲区最大容量 */

SOCKET network_connect_retry(const char *server_ip, /* 服务器 IP 地址 */
                             int server_port,       /* 服务器端口号 */
                             int attempts,          /* 最大重试次数 */
                             char *error_text,      /* 错误信息输出缓冲区 */
                             int error_size);       /* 错误信息缓冲区最大容量 */

int network_send_bytes(SOCKET server_socket, /* 目标连接套接字 */
                       const char *message,  /* 待发送数据缓冲区 */
                       int message_length,   /* 待发送字节数 */
                       char *error_text,     /* 错误信息输出缓冲区 */
                       int error_size);      /* 错误信息缓冲区最大容量 */

int network_send_all(SOCKET server_socket, /* 目标连接套接字 */
                     const char *message,  /* 待发送字符串 */
                     char *error_text,     /* 错误信息输出缓冲区 */
                     int error_size);      /* 错误信息缓冲区最大容量 */

int network_receive_line(SOCKET server_socket, /* 目标连接套接字 */
                         char *line,           /* 接收单行的输出缓冲区 */
                         int line_size,        /* 接收缓冲区最大容量（含 '\0'） */
                         char *error_text,     /* 错误信息输出缓冲区 */
                         int error_size);      /* 错误信息缓冲区最大容量 */

int network_receive_exact(SOCKET server_socket, /* 目标连接套接字 */
                          char *data,           /* 接收数据的输出缓冲区 */
                          int data_size,        /* 期望接收的准确字节数 */
                          char *error_text,     /* 错误信息输出缓冲区 */
                          int error_size);      /* 错误信息缓冲区最大容量 */

void network_close(SOCKET server_socket); /* 需关闭的套接字 */

#endif