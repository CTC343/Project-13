# server/protocol.py

定义 P13/1 帧格式、协议状态码和异常，并实现按长度收发 UTF-8 JSON 对象。

## ProtocolError.__init__

```python
def __init__(self, message, status=STATUS_BAD_REQUEST):
```

**用途：** 创建携带文本说明与协议状态码的异常，供上层按错误种类回复客户端。

| 参数 | 含义 |
| --- | --- |
| `self` | [输出] 正在创建的 ProtocolError 异常实例；继承异常消息并保存 status 字段。 |
| `message` | [输入] 错误原因文本，传给 Exception 初始化；str(error) 会得到它。 |
| `status` | [输入，可选] 要返回的整数协议状态码；默认 STATUS_BAD_REQUEST（400），也可传 401、413 等。 |

## _receive_until_newline

```python
def _receive_until_newline(client_socket):
```

**用途：** 逐字节读取协议头直到 LF，返回不含 LF 的原始 bytes，避免提前读走 Body；连接提前关闭或头部超过实现允许范围时抛出 ProtocolError。

| 参数 | 含义 |
| --- | --- |
| `client_socket` | [输入／状态变化] 要读取协议头的已连接 TCP 套接字；每次 recv(1)，消耗到头部结束换行。 |

## _receive_exact

```python
def _receive_exact(client_socket, body_length):
```

**用途：** 循环接收指定字节数的消息体并返回 bytes，处理一次 recv 只到达部分数据的情况；未收足即断开时抛出 ProtocolError。

| 参数 | 含义 |
| --- | --- |
| `client_socket` | [输入／状态变化] 要读取消息体的已连接套接字；每次最多读取本帧尚缺的字节数。 |
| `body_length` | [输入] 必须接收的 Body 字节总数，来自已解析并检查过的 Header；单位为字节，不是字符。 |

## receive_frame

```python
def receive_frame(client_socket):
```

**用途：** 读取并解析一帧 P13/1 消息，检查版本、类型字符、Body 长度、UTF-8 和顶层 JSON 对象；返回 (message_type, status, body字典)，协议不符时抛出 ProtocolError。

| 参数 | 含义 |
| --- | --- |
| `client_socket` | [输入／状态变化] 当前已连接 TCP 套接字；函数消费恰好一帧的 Header 和 Body，套接字超时由调用方设置。 |

## send_frame

```python
def send_frame(client_socket, message_type, status, body):
```

**用途：** 将业务对象序列化为紧凑 UTF-8 JSON，按实际字节数构造 Header，并用 sendall 发送完整帧；Body 超过上限时抛出 ProtocolError。

| 参数 | 含义 |
| --- | --- |
| `client_socket` | [输入／状态变化] 发送目标的已连接 TCP 套接字。 |
| `message_type` | [输入] Header 中的外层消息类型字符串，例如 AUTH_OK、SECURE 或 ERROR；函数发送时不另做接收端那样的字符校验。 |
| `status` | [输入] Header 中的整数状态码，通常 200 表示成功，其他约定值表示错误。 |
| `body` | [输入] 要编码成 JSON 的消息体，协议约定为字典；SECURE 帧应传加密后的信封，普通响应传对应字段字典。 |

## send_error

```python
def send_error(client_socket, status, detail):
```

**用途：** 发送统一的明文 ERROR 帧，Body 只有 detail 错误说明；安全会话中的加密错误由 task_service._send_secure 处理。

| 参数 | 含义 |
| --- | --- |
| `client_socket` | [输入／状态变化] 接收错误响应的已连接套接字。 |
| `status` | [输入] 错误对应的整数协议状态码，例如 400、401 或 413。 |
| `detail` | [输入] 供客户端读取的错误说明，放入 JSON Body 的 detail 字段。 |
