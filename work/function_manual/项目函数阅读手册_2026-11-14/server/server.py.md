# server/server.py

服务端启动入口：检查任务配置，创建 TCP 监听器，并用线程池处理客户端连接。

## create_server

```python
def create_server():
```

**用途：** 创建 IPv4/TCP 套接字，设置地址复用，绑定配置中的 HOST 和 PORT 后开始监听，返回监听套接字。

**参数：** 无。

## serve

```python
def serve(server_socket):
```

**用途：** 创建共享任务状态、凭据库和节点登记表；用 select 等待新连接，再把每个连接交给线程池中的 run_client 处理。该函数持续运行，不主动结束。

| 参数 | 含义 |
| --- | --- |
| `server_socket` | [输入／状态变化] 已完成 bind 和 listen 的 TCP 监听套接字；函数在其上等待可读事件并 accept 新连接，不是某个客户端的通信连接。 |

## serve.run_client

```python
def run_client(sock=client_socket, address=client_address):
```

**用途：** serve 内部的连接处理函数：在套接字上下文中调用 handle_client，处理结束后自动关闭该客户端连接；默认参数把本次 accept 的连接和地址固定下来。

| 参数 | 含义 |
| --- | --- |
| `sock` | [输入／状态变化] 本次 accept 返回的客户端通信套接字；默认取定义本函数时的 client_socket，交给 handle_client 收发消息，退出 with 时关闭。 |
| `address` | [输入] 与 sock 对应的客户端地址元组 (IP 字符串, 端口整数)；默认取本次 client_address，用于节点登记及日志。 |

## validate_settings

```python
def validate_settings():
```

**用途：** 检查配置的运算是否支持、区间与子任务数是否合法、每个子任务是否至少可分成四段、每轮冗余节点数是否至少为 3；不符合时抛出 ValueError。配置来自模块常量，不通过参数传入。

**参数：** 无。

## main

```python
def main():
```

**用途：** 先验证配置，再创建监听器、输出启动信息并进入 serve 主循环；监听器在退出上下文时关闭。直接运行此文件时由模块入口调用。

**参数：** 无。
