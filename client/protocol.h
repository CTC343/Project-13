#ifndef PROJECT13_PROTOCOL_H
#define PROJECT13_PROTOCOL_H

#include <winsock2.h>

/* JSON Body 缓冲区上限；接收时还需额外预留一个字节存放 '\0'。 */
#define PROTOCOL_BODY_SIZE 8192

/*
 * 将 JSON 消息封装成 P13/1 帧并发送。
 * server_socket: 已连接的服务端套接字。
 * message_type: 消息类型，例如 "AUTH" 或 "SECURE"。
 * status: HTTP 风格的状态码。
 * json_body: 要发送的 JSON 对象字符串。
 * error_text: 发生错误时写入错误描述的缓冲区。
 * error_size: error_text 缓冲区的大小（字节）。
 * 返回值：成功返回非零，失败返回 0。
 */
int protocol_send_frame(SOCKET server_socket, const char *message_type,
                        int status, const char *json_body,
                        char *error_text, int error_size);

/*
 * 从服务端接收一帧，并分别输出消息类型、状态码和 JSON Body。
 * server_socket: 已连接的服务端套接字。
 * message_type: 输出消息类型的缓冲区。
 * type_size: message_type 缓冲区的大小（字节）。
 * status: 输出状态码的指针。
 * json_body: 输出 JSON Body 的缓冲区，函数会追加 '\0'。
 * body_size: json_body 缓冲区的大小（字节，包含 '\0' 所需空间）。
 * error_text: 发生错误时写入错误描述的缓冲区。
 * error_size: error_text 缓冲区的大小（字节）。
 * 返回值：成功返回非零，失败返回 0。
 */
int protocol_receive_frame(SOCKET server_socket, char *message_type,
                           int type_size, int *status,
                           char *json_body, int body_size,
                           char *error_text, int error_size);

/*
 * 从 JSON 文本中读取指定字符串字段（轻量级查找，不是完整 JSON 解析器）。
 * json: 要搜索的 JSON 文本。
 * name: 字段名。
 * value: 输出字段值的缓冲区。
 * value_size: value 缓冲区的大小（字节）。
 * 返回值：找到且能写入缓冲区时返回非零，否则返回 0。
 */
int json_get_string(const char *json, const char *name,
                    char *value, int value_size);

/*
 * 从 JSON 文本中读取指定整数数值字段。
 * json: 要搜索的 JSON 文本。
 * name: 字段名。
 * value: 输出整数值的指针。
 * 返回值：找到并转换出整数时返回非零，否则返回 0。
 */
int json_get_long(const char *json, const char *name, long *value);

#endif
