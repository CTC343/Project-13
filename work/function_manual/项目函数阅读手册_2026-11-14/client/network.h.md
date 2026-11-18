# client/network.h

声明客户端底层连接和字节收发接口，其中三个接口当前仅有声明。

## network_start

```c
int network_start(char *error_text, int error_size);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。初始化 Winsock 2.2 网络环境，供后续创建套接字使用。成功返回 1，WSAStartup 失败写错误并返回 0。

| 参数 | 含义 |
| --- | --- |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## network_connect

```c
SOCKET network_connect(const char *server_ip, int server_port, char *error_text, int error_size);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。创建 TCP 套接字，设置收发超时为 5000 毫秒，再连接指定 IPv4 地址和端口。成功返回套接字，失败关闭本次套接字并返回 INVALID_SOCKET；当前没有独立的 connect 超时实现。

| 参数 | 含义 |
| --- | --- |
| `server_ip` | [输入] 点分十进制 IPv4 地址字符串，例如 127.0.0.1；通过 inet_addr 转换，不进行域名解析。 |
| `server_port` | [输入] 服务端监听的 TCP 端口号，例如 8888。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## network_connect_retry

```c
SOCKET network_connect_retry(const char *server_ip, int server_port, int attempts, char *error_text, int error_size);
```

**用途：** 声明带有限重试的 TCP 连接接口，供 run_client 调用。当前 network.c 未提供定义，不能把声明视为已实现的重连逻辑。

| 参数 | 含义 |
| --- | --- |
| `server_ip` | [输入] 目标服务端 IPv4 地址字符串。 |
| `server_port` | [输入] 目标 TCP 端口号。 |
| `attempts` | [输入] 设计上允许的最大连接尝试次数；当前调用处传 3，具体重试间隔尚无实现。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## network_send_bytes

```c
int network_send_bytes(SOCKET server_socket, const char *message, int message_length, char *error_text, int error_size);
```

**用途：** 声明按指定字节数完整发送缓冲区的接口，供协议层发送 Header 和 Body。当前 network.c 未提供定义。

| 参数 | 含义 |
| --- | --- |
| `server_socket` | [输入] 已连接服务端的 Winsock 套接字，用于本函数的网络收发。 |
| `message` | [输入] 待发送数据的起始地址；按长度发送，不应依赖字符串终止符。 |
| `message_length` | [输入] 要发送的数据长度，单位为字节。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## network_send_all

```c
int network_send_all(SOCKET server_socket, const char *message, char *error_text, int error_size);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。按 strlen 得到文本长度，反复调用 send，直到该字符串的全部内容发送完成。成功返回 1，发送错误或连接不能继续发送时写错误并返回 0；不发送结尾空字符。

| 参数 | 含义 |
| --- | --- |
| `server_socket` | [输入] 已连接服务端的 Winsock 套接字，用于本函数的网络收发。 |
| `message` | [输入] 以空字符结尾的待发送文本；因为长度由 strlen 决定，不适合包含中间零字节的二进制数据。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## network_receive_line

```c
int network_receive_line(SOCKET server_socket, char *line, int line_size, char *error_text, int error_size);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。循环收取数据，直到找到换行符，将换行处改为空字符并返回 1；接收失败、断开或空间不足返回 0。当前实现不保存同次 recv 中换行后的额外字节，可能丢失紧接的 Body 数据。

| 参数 | 含义 |
| --- | --- |
| `server_socket` | [输入] 已连接服务端的 Winsock 套接字，用于本函数的网络收发。 |
| `line` | [输出] 保存收到的单行文本，结果不包含换行符。 |
| `line_size` | [输入] line 缓冲区总容量，单位为字节，包含结尾空字符；最多保存 line_size-1 字节。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## network_receive_exact

```c
int network_receive_exact(SOCKET server_socket, char *data, int data_size, char *error_text, int error_size);
```

**用途：** 声明读齐指定字节数的接口，供协议层按 Header 长度读取 Body。当前 network.c 未提供定义；字符串终止符由协议层在收包后追加。

| 参数 | 含义 |
| --- | --- |
| `server_socket` | [输入] 已连接服务端的 Winsock 套接字，用于本函数的网络收发。 |
| `data` | [输出] 接收数据缓冲区，至少可容纳 data_size 字节；协议层另外为结尾空字符预留空间。 |
| `data_size` | [输入] 需要读齐的数据长度，单位为字节，不包含协议层追加的结尾空字符。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## network_close

```c
void network_close(SOCKET server_socket);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。若套接字有效则将其关闭，随后调用 WSACleanup 释放本进程本次使用的 Winsock 环境。

| 参数 | 含义 |
| --- | --- |
| `server_socket` | [输入] 要关闭的套接字；INVALID_SOCKET 时跳过 closesocket，但仍调用 WSACleanup。 |
