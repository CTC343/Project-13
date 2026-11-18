# server/security_audit.py

使用写入锁将安全事件追加到独立的 security_audit.jsonl 文件，并提供逐行读取功能。

## record_security_event

```python
def record_security_event(event, node_id='-', address='-', detail=''):
```

**用途：** 生成带当前本地时间的安全事件记录，在线程锁保护下向 data/security_audit.jsonl 追加一行 JSON。

| 参数 | 含义 |
| --- | --- |
| `event` | [输入] 事件类型字符串，例如 LOGIN_OK、LOGIN_REJECTED、REQUEST_REJECTED 或 RESULT_ACCEPTED。 |
| `node_id` | [输入，可选，默认 "-"] 事件涉及的节点 ID；尚未获知节点身份时可保留占位符。 |
| `address` | [输入，可选，默认 "-"] 对端地址文本，调用处通常拼成 IP:端口；未知时使用占位符。 |
| `detail` | [输入，可选，默认空字符串] 补充描述，例如拒绝原因、任务 ID 或登录校验结果；直接作为日志字段保存。 |

## read_security_events

```python
def read_security_events():
```

**用途：** 读取安全事件 JSONL 并按文件顺序返回记录列表；文件不存在时返回空列表，个别 JSON 无法解析的行会被跳过。

**参数：** 无。
