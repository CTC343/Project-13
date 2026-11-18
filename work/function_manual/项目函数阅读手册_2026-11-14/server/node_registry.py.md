# server/node_registry.py

线程安全地记录节点的认证、地址、在线、心跳和工作状态，并输出供控制中心读取的状态行。

## NodeRegistry.__init__

```python
def __init__(self):
```

**用途：** 建立节点表及互斥锁；每个节点的状态以后由 update 写入。

| 参数 | 含义 |
| --- | --- |
| `self` | [输出] 正在初始化的 NodeRegistry 实例；写入 _lock 和空的 _nodes 节点字典。 |

## NodeRegistry.update

```python
def update(self, node_id, address, login_status, state, persistent=None):
```

**用途：** 加锁创建或更新一个节点的地址、认证状态、工作状态及最后活动时间；心跳状态会刷新心跳时间，最后输出 NODE_STATUS 行。该方法只登记状态，不自行校验身份。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入／输出] 当前 NodeRegistry；使用 _lock 保护 _nodes 并修改指定节点记录。 |
| `node_id` | [输入] 节点 ID，作为 _nodes 字典键；不存在时创建该节点记录。 |
| `address` | [输入] 节点地址文本，通常是“IP:端口”，用于展示本次连接来源。 |
| `login_status` | [输入] 认证状态文本，例如 authenticated、rejected 或 signed_out。 |
| `state` | [输入] 工作或在线状态文本，例如 online、heartbeat、computing、waiting、completed 或 offline；等于 heartbeat 时刷新 last_heartbeat。 |
| `persistent` | [输入，可选] 是否持续在线等待任务；非 None 时写入 bool(persistent)，默认 None 表示保留已有值，新节点未设置时为 False。 |

## NodeRegistry.snapshot

```python
def snapshot(self):
```

**用途：** 在锁内复制节点表及每个节点的记录字典并返回，供调用者查看当前状态；修改返回的节点字典不会直接修改登记表。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入] 要读取快照的 NodeRegistry；读取其 _nodes，并使用 _lock 防止复制期间记录被并发更新。 |
