# server/task_service.py

认证后业务流程：安全消息收发、任务预留、结果校验、多数表决、信誉更新和连接异常清理。

## choose_majority

```python
def choose_majority(task_results):
```

**用途：** 统计节点结果中每个数值的票数；返回票数达到“已提交节点数的一半再加一”的严格多数值，无严格多数时返回 None。这里只进行表决，不重新计算标准答案。

| 参数 | 含义 |
| --- | --- |
| `task_results` | [输入] 本轮结果字典，格式为 {节点 ID: 计算结果整数}；节点 ID 区分投票者，字典中的结果值用于统计票数。 |

## update_reputation

```python
def update_reputation(task_results, trusted_value, task_state):
```

**用途：** 将各节点结果与多数可信值比较，按配置奖励或扣分并限制信誉在 0～100；错误时累计 wrong_rounds，累计次数恰达阈值时加入恶意集合。正确提交不会清零此前错误次数，所以当前统计的是累计错误轮数。

| 参数 | 含义 |
| --- | --- |
| `task_results` | [输入] 本轮 {节点 ID: 结果值} 字典；逐节点判断结果是否等于 trusted_value。 |
| `trusted_value` | [输入] 本轮严格多数表决选出的结果值，用作奖励或扣分的比较基准，不是本函数独立计算出的标准答案。 |
| `task_state` | [输入／输出] 共享 TaskState 对象；读取旧信誉，并更新 reputation_scores、wrong_rounds 和 malicious_nodes。调用方负责共享状态的并发保护。 |

## finish_task

```python
def finish_task(task_state):
```

**用途：** 对本轮结果做严格多数表决；有多数时保存可信小计、合并总结果、更新信誉和重要任务资格，最后一轮还生成考核报告，并写业务审计，返回 True。无多数时只保存失败审计并返回 False；此函数本身不决定下一轮。

| 参数 | 含义 |
| --- | --- |
| `task_state` | [输入／输出] 包含当前轮次、节点结果、信誉和历史可信小计的共享 TaskState；函数更新 trusted_results、integrated_result、important_task_nodes，必要时更新 evaluation_report，并将相关数据落盘。 |

## _send_secure

```python
def _send_secure(client_socket, session, action, status=STATUS_OK, **values):
```

**用途：** 将 action 与附加字段组成业务对象，经 SecureSession 加密和认证后，以 SECURE 类型协议帧发送给客户端；发送会推进本会话的服务端发送序号。

| 参数 | 含义 |
| --- | --- |
| `client_socket` | [输入／状态变化] 当前客户端的已连接 TCP 套接字，作为发送目标。 |
| `session` | [输入／输出] 当前连接的 SecureSession，提供会话 ID、密钥和发送序号；protect_server_message 会递增其 send_sequence。 |
| `action` | [输入] 加密业务对象的动作名，例如 TASK、WAIT、HEARTBEAT_ACK、ACCEPTED 或 ERROR。 |
| `status` | [输入，可选] 外层协议帧的整数状态码，默认 STATUS_OK（200）；错误响应可以传入 401、409 等错误码。 |
| `**values` | [输入，可变关键字] action 以外的业务字段，如 task_id、retry_after、server_time 或 detail；这些键值被合并进同一个业务对象。 |

## _receive_secure

```python
def _receive_secure(client_socket, session, expected_action):
```

**用途：** 接收并验证一条安全消息，再检查解密后的 action 是否等于预期动作；相符时返回业务字典，不符则抛出 ProtocolError。

| 参数 | 含义 |
| --- | --- |
| `client_socket` | [输入／状态变化] 当前客户端的已连接套接字，函数从中消耗一帧消息。 |
| `session` | [输入／输出] 当前 SecureSession；用于验证客户端会话、序号和消息认证标签，成功接收会推进 receive_sequence。 |
| `expected_action` | [输入] 本步骤唯一允许的业务动作字符串，如 HEARTBEAT 或 RESULT。 |

## _receive_secure_any

```python
def _receive_secure_any(client_socket, session):
```

**用途：** 读取一帧并要求外层类型为 SECURE，随后使用会话对象验证、解密，返回业务字典；不限制业务 action。安全信封验证的 ValueError 会转换为状态码 401 的 ProtocolError。

| 参数 | 含义 |
| --- | --- |
| `client_socket` | [输入／状态变化] 要读取客户端消息的已连接 TCP 套接字。 |
| `session` | [输入／输出] 该连接的 SecureSession，负责解密和严格序号验证；成功后接收序号增加。 |

## _try_reserve_task

```python
def _try_reserve_task(node_id, last_round, task_state):
```

**用途：** 加锁检查任务是否未结束、节点是否尚未处理本轮、是否已占用名额以及名额是否已满；满足条件时将节点加入 assigned_nodes，并返回 (任务 ID, 区间起点, 区间终点, 轮次)，否则返回 None。当前函数没有检查信誉分或恶意节点集合。

| 参数 | 含义 |
| --- | --- |
| `node_id` | [输入] 当前已认证节点的唯一标识，用于检查重复领取并记录其占用的本轮名额。 |
| `last_round` | [输入] 此连接最后一次成功提交的轮次；当前轮次必须比它大，防止同一持续连接反复领取同一轮任务。 |
| `task_state` | [输入／输出] 共享 TaskState；读取 completed、round_number 和 assigned_nodes，在其 lock 保护下预留名额。 |

## _store_result

```python
def _store_result(node_id, payload, task_info, task_state):
```

**用途：** 核对结果的任务 ID 与节点身份，检查四步证明与总值、Merkle 根的一致性，并在锁内拒绝过期或重复结果；通过后写入本轮内存集合并返回结果值。收齐规定节点数时调用 finish_task，随后结束或推进轮次。证明一致性本身不证明计算正确，且当前调用方未根据 finish_task 的失败返回值停止推进。

| 参数 | 含义 |
| --- | --- |
| `node_id` | [输入] 从本连接认证流程得到的节点 ID；结果中的 node_id 必须与它相同，不能由结果消息自由指定提交者。 |
| `payload` | [输入] 解密后的 RESULT 业务字典；使用 task_id、node_id、value、merkle_root 和 proof_steps，其中 proof_steps 是四个步骤整数组成的逗号分隔字符串。 |
| `task_info` | [输入] 此连接预留任务时得到的四元组 (task_id, task_start, task_end, assigned_round)；本函数当前仅取第一个元素 task_id 作为任务身份基准。 |
| `task_state` | [输入／输出] 当前共享 TaskState；加锁写 task_results、result_proofs，并在收齐结果时更新信誉、合并结果、完成标记或下一轮状态。 |

## handle_client

```python
def handle_client(client_socket, client_address, task_state, credential_store, node_registry):
```

**用途：** 处理一条客户端连接的完整业务生命周期：认证、会话建立、首次心跳、领取签名任务、校验提交、持续等待或退出；设置 8 秒套接字超时，捕获错误并记录安全事件、尽量回复错误，最后释放尚未提交的任务名额并将节点标为离线。连接套接字本身由外层 run_client 的 with 关闭。

| 参数 | 含义 |
| --- | --- |
| `client_socket` | [输入／状态变化] accept 得到的该客户端已连接 TCP 套接字；用于认证和后续安全消息的全部收发，函数会设置其超时。 |
| `client_address` | [输入] 客户端地址二元组 (IP, 端口)，用于生成日志及节点状态中的地址文本。 |
| `task_state` | [输入／输出] 各连接共享的 TaskState，包含当前轮次、占用名额、结果和信誉；业务更新通过其中的锁协调。 |
| `credential_store` | [输入／输出] 共用的 CredentialStore；验证身份并记录已用登录随机数，再生成本连接会话参数。 |
| `node_registry` | [输入／输出] 共用的 NodeRegistry；登记当前节点的认证、在线、心跳、计算、等待和离线状态。 |
