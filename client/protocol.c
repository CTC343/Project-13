/* P13/1 Header + JSON Body；按长度读取，兼容 TCP 粘包和拆包。 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "network.h"
#include "protocol.h"

#define HEADER_SIZE 128

int protocol_send_frame(SOCKET server_socket, const char *message_type,
                        int status, const char *json_body,
                        char *error_text, int error_size)
{
    char header[HEADER_SIZE];
    /* C 字符串是 UTF-8 JSON；strlen 得到发送所需的字节数。 */
    int body_length = (int)strlen(json_body);
    if (body_length < 2 || body_length >= PROTOCOL_BODY_SIZE) {
        snprintf(error_text, error_size, "Protocol body size is invalid.");
        return 0;
    }
    /*
     * Header 格式：版本 消息类型 状态码 Body字节数\n。
     * TCP 没有消息边界，Body 长度告诉接收端本帧何时结束、下一帧从哪开始。
     */
    snprintf(header, sizeof(header), "P13/1 %s %d %d\n",
             message_type, status, body_length);
    /* Header 与 Body 分开发送；TCP 可能分段，接收端会按协议边界读取。 */
    if (!network_send_bytes(server_socket, header, (int)strlen(header),
                            error_text, error_size)) return 0;
    return network_send_bytes(server_socket, json_body, body_length,
                              error_text, error_size);
}

int protocol_receive_frame(SOCKET server_socket, char *message_type,
                           int type_size, int *status,
                           char *json_body, int body_size,
                           char *error_text, int error_size)
{
    char header[HEADER_SIZE];
    char version[16];
    int body_length;
    /* 先读到 Header 的换行符，再解析消息类型、状态码和 Body 长度。 */
    if (!network_receive_line(server_socket, header, sizeof(header),
                              error_text, error_size)) return 0;
    if (sscanf(header, "%15s %31s %d %d", version, message_type,
               status, &body_length) != 4 || strcmp(version, "P13/1") != 0) {
        snprintf(error_text, error_size, "Invalid protocol header.");
        return 0;
    }
    /* 确认输出缓冲区能容纳 Body 及结尾的 '\0'，并拒绝无效长度。 */
    if ((int)strlen(message_type) >= type_size ||
        body_length < 2 || body_length >= body_size) {
        snprintf(error_text, error_size, "Protocol body is too large.");
        return 0;
    }
    /*
     * 按 Header 声明的长度读齐 Body，再补 C 字符串结束符。
     * 接收可能分多次才凑够这些字节，不能假设一次 recv 就能读完整。
     */
    if (!network_receive_exact(server_socket, json_body, body_length,
                               error_text, error_size)) return 0;
    json_body[body_length] = '\0';
    /* 客户端这里做基本对象边界检查；完整 JSON 解析由业务取值函数处理。 */
    if (json_body[0] != '{' || json_body[body_length - 1] != '}') {
        snprintf(error_text, error_size, "Protocol body is not a JSON object.");
        return 0;
    }
    return 1;
}

int json_get_string(const char *json, const char *name,
                    char *value, int value_size)
{
    char pattern[80];
    const char *start;
    const char *end;
    int length;
    snprintf(pattern, sizeof(pattern), "\"%s\":\"", name);
    start = strstr(json, pattern);
    if (start == NULL) return 0;
    start += strlen(pattern);
    end = strchr(start, '"');
    if (end == NULL) return 0;
    length = (int)(end - start);
    if (length <= 0 || length >= value_size) return 0;
    memcpy(value, start, length);
    value[length] = '\0';
    return 1;
}

int json_get_long(const char *json, const char *name, long *value)
{
    char pattern[80];
    char *end;
    const char *start;
    snprintf(pattern, sizeof(pattern), "\"%s\":", name);
    start = strstr(json, pattern);
    if (start == NULL) return 0;
    start += strlen(pattern);
    *value = strtol(start, &end, 10);
    return end != start;
}
