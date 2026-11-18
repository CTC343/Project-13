# client/network.c

实现 Winsock 初始化、单次连接、文本发送、按行接收和关闭；部分头文件声明的网络接口尚缺实现。

## network_start

```c
int network_start(char *error_text, int error_size);
```

**用途：** 初始化 Winsock 2.2 网络环境，供后续创建套接字使用。成功返回 1，WSAStartup 失败写错误并返回 0。

| 参数 | 含义 |
| --- | --- |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## network_connect

```c
SOCKET network_connect(const char *server_ip, int server_port, char *error_text, int error_size);
```

**用途：** 创建 TCP 套接字，设置收发超时为 5000 毫秒，再连接指定 IPv4 地址和端口。成功返回套接字，失败关闭本次套接字并返回 INVALID_SOCKET；当前没有独立的 connect 超时实现。

| 参数 | 含义 |
| --- | --- |
| `server_ip` | [输入] 点分十进制 IPv4 地址字符串，例如 127.0.0.1；通过 inet_addr 转换，不进行域名解析。 |
| `server_port` | [输入] 服务端监听的 TCP 端口号，例如 8888。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## network_send_all

```c
int network_send_all(SOCKET server_socket, const char *message, char *error_text, int error_size);
```

**用途：** 按 strlen 得到文本长度，反复调用 send，直到该字符串的全部内容发送完成。成功返回 1，发送错误或连接不能继续发送时写错误并返回 0；不发送结尾空字符。

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

**用途：** 循环收取数据，直到找到换行符，将换行处改为空字符并返回 1；接收失败、断开或空间不足返回 0。当前实现不保存同次 recv 中换行后的额外字节，可能丢失紧接的 Body 数据。

| 参数 | 含义 |
| --- | --- |
| `server_socket` | [输入] 已连接服务端的 Winsock 套接字，用于本函数的网络收发。 |
| `line` | [输出] 保存收到的单行文本，结果不包含换行符。 |
| `line_size` | [输入] line 缓冲区总容量，单位为字节，包含结尾空字符；最多保存 line_size-1 字节。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## network_close

```c
void network_close(SOCKET server_socket);
```

**用途：** 若套接字有效则将其关闭，随后调用 WSACleanup 释放本进程本次使用的 Winsock 环境。

| 参数 | 含义 |
| --- | --- |
| `server_socket` | [输入] 要关闭的套接字；INVALID_SOCKET 时跳过 closesocket，但仍调用 WSACleanup。 |
