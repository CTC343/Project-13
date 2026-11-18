# client/protocol.c

封装与读取 P13/1 消息帧，提供轻量 JSON 字段取值。

## protocol_send_frame

```c
int protocol_send_frame(SOCKET server_socket, const char *message_type, int status, const char *json_body, char *error_text, int error_size);
```

**用途：** 检查 JSON Body 长度，生成 P13/1 消息头，再分别发送 Header 和 Body。成功返回非零，格式长度或发送失败返回 0；实际依赖尚缺定义的 network_send_bytes。

| 参数 | 含义 |
| --- | --- |
| `server_socket` | [输入] 已连接服务端的 Winsock 套接字，用于本函数的网络收发。 |
| `message_type` | [输入] 外层帧类型，例如 AUTH 或 SECURE。 |
| `status` | [输入] 写入帧头的整数状态，客户端请求通常为 0。 |
| `json_body` | [输入] 以空字符结尾的 UTF-8 JSON 文本；发送长度按 strlen 的字节数计算，需为 2～8191 字节。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## protocol_receive_frame

```c
int protocol_receive_frame(SOCKET server_socket, char *message_type, int type_size, int *status, char *json_body, int body_size, char *error_text, int error_size);
```

**用途：** 读取并解析 P13/1 Header，核对版本和 Body 长度，随后按长度读取 Body、追加空字符并检查首尾花括号。成功返回 1，失败返回 0；当前依赖缺失的 network_receive_exact，且只做基本 JSON 对象边界检查。

| 参数 | 含义 |
| --- | --- |
| `server_socket` | [输入] 已连接服务端的 Winsock 套接字，用于本函数的网络收发。 |
| `message_type` | [输出] 保存 Header 中消息类型的字符缓冲区。当前 sscanf 固定使用 %31s，调用者应至少提供 32 字节；后续 type_size 检查不能替代此要求。 |
| `type_size` | [输入] message_type 缓冲区容量，单位为字节，包含结尾空字符。 |
| `status` | [输出] int 指针，接收 Header 中的状态码。 |
| `json_body` | [输出] 保存原始 JSON Body 文本的缓冲区；在收到指定长度后追加空字符。 |
| `body_size` | [输入] json_body 总容量，单位为字节，包含结尾空字符；Body 长度必须小于该值。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## json_get_string

```c
int json_get_string(const char *json, const char *name, char *value, int value_size);
```

**用途：** 在紧凑 JSON 文本中查找指定字符串键，复制紧随其后的字符串内容；找到非空且容得下的值时返回 1，否则返回 0。这是文本模式查找，不支持完整 JSON 转义或一般空白格式解析。

| 参数 | 含义 |
| --- | --- |
| `json` | [输入] 待搜索的、以空字符结尾的 JSON 文本，当前要求键值附近符合紧凑格式。 |
| `name` | [输入] 要查找的字段名，不含引号，例如 action 或 session_id。 |
| `value` | [输出] 保存找到的字符串内容，不包含 JSON 引号。 |
| `value_size` | [输入] value 容量，单位为字节，包含结尾空字符；字符串长度必须小于此值。 |

## json_get_long

```c
int json_get_long(const char *json, const char *name, long *value);
```

**用途：** 查找指定键后的数字文本并用 strtol 转为 long，只要至少读出一个数字就返回非零；不做完整 JSON 语法、数值末尾或溢出检查。

| 参数 | 含义 |
| --- | --- |
| `json` | [输入] 待搜索的、以空字符结尾的紧凑 JSON 文本。 |
| `name` | [输入] 要查找的整数键名，不含引号，例如 start 或 sequence。 |
| `value` | [输出] long 指针，接收 strtol 转换得到的数值。 |
