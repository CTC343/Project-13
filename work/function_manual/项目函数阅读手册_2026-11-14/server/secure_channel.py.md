# server/secure_channel.py

派生会话密钥，以 HMAC 密钥流保护业务 JSON，并校验会话、方向、严格序号和认证标签。

## hmac_hex

```python
def hmac_hex(key, text):
```

**用途：** 把文本按 UTF-8 编码，用指定密钥计算 HMAC-SHA256，返回 64 字符的小写十六进制认证标签。

| 参数 | 含义 |
| --- | --- |
| `key` | [输入] HMAC 使用的密钥原始 bytes；可为节点身份密钥或派生的会话密钥，不是密钥的十六进制文本。 |
| `text` | [输入] 待认证的字符串；函数内部统一编码为 UTF-8。 |

## derive_session_key

```python
def derive_session_key(auth_key, client_nonce, server_nonce, session_id):
```

**用途：** 将客户端随机数、服务端随机数和会话 ID 按 SESSION|... 文本格式绑定，用节点身份密钥做 HMAC-SHA256，返回 32 字节会话密钥。

| 参数 | 含义 |
| --- | --- |
| `auth_key` | [输入] 节点长期身份认证密钥的原始 bytes，通常为 32 字节，双方须持有同一值。 |
| `client_nonce` | [输入] 此次 AUTH 携带的客户端随机数文本，通常为 32 个十六进制字符。 |
| `server_nonce` | [输入] 此次认证成功后服务端生成的随机数文本，通常为 32 个十六进制字符。 |
| `session_id` | [输入] 此次连接的新会话 ID 文本，通常为 24 个十六进制字符，用于区分不同会话。 |

## _keystream

```python
def _keystream(key, direction, session_id, sequence, nonce, size):
```

**用途：** 把方向、会话、8 字节大端序号、原始随机数和 4 字节大端块计数器作为 HMAC 输入，反复生成摘要并截断，返回指定长度的密钥流，供明文／密文异或。

| 参数 | 含义 |
| --- | --- |
| `key` | [输入] 当前会话密钥的原始 bytes，作为生成各密钥流块的 HMAC 密钥。 |
| `direction` | [输入] 消息方向字符串，使用 C2S 或 S2C，并按 ASCII 编码，区分两端发送方向。 |
| `session_id` | [输入] 当前会话 ID 字符串，按 ASCII 编码后纳入密钥流输入。 |
| `sequence` | [输入] 该方向的消息序号整数，编码为 8 字节无符号大端值；正常首条为 1。 |
| `nonce` | [输入] 本条消息的随机数原始 bytes，正常长度为 16 字节；这里接收的是解码后的值而非十六进制文本。 |
| `size` | [输入] 需要生成的密钥流字节数，应等于待异或的明文或密文字节长度。 |

## encrypt_message

```python
def encrypt_message(key, direction, session_id, sequence, payload):
```

**用途：** 将业务字典编码为紧凑 UTF-8 JSON，生成 16 字节随机数，用派生密钥流异或加密，并计算覆盖方向、会话、序号、随机数与密文的 HMAC；返回安全信封字典。本函数不自行增加序号。

| 参数 | 含义 |
| --- | --- |
| `key` | [输入] 此连接派生的会话密钥原始 bytes，用于生成密钥流和认证标签。 |
| `direction` | [输入] 此条消息方向 C2S 或 S2C，参与加密派生与标签计算。 |
| `session_id` | [输入] 当前会话 ID 字符串，写入信封并参与认证。 |
| `sequence` | [输入] 调用方分配的本方向消息序号整数，写入信封并参与加密与认证。 |
| `payload` | [输入] 要保护的业务 JSON 对象，通常是含 action 的字典，如 TASK 或 RESULT 的字段集合。 |

## decrypt_message

```python
def decrypt_message(key, direction, expected_session, expected_sequence, envelope):
```

**用途：** 解析安全信封，检查会话 ID、预期序号和随机数长度，校验 HMAC 后才解密并解析 JSON；成功返回业务字典，信封无效或明文不是 JSON 对象时抛出 ValueError。该函数不保存接收状态。

| 参数 | 含义 |
| --- | --- |
| `key` | [输入] 与发送方一致的会话密钥原始 bytes，用于校验标签并生成解密密钥流。 |
| `direction` | [输入] 接收方预期的消息方向 C2S 或 S2C；与发送时的方向不一致将导致标签验证失败。 |
| `expected_session` | [输入] 当前连接认可的会话 ID，必须等于信封 session_id。 |
| `expected_sequence` | [输入] 当前方向下一条应到达的整数序号，必须与信封 sequence 相等，用于拒绝旧消息或乱序消息。 |
| `envelope` | [输入] 接收到的安全信封字典，应包含 session_id、sequence、nonce、ciphertext 和 tag；nonce、ciphertext、tag 使用十六进制文本。 |

## SecureSession.__init__

```python
def __init__(self, session_id, session_key):
```

**用途：** 保存会话 ID 与密钥，并将服务端发送、接收序号都初始化为 0；之后各方向首条消息使用序号 1。

| 参数 | 含义 |
| --- | --- |
| `self` | [输出] 正在创建的 SecureSession 对象，写入 session_id、session_key、send_sequence 和 receive_sequence。 |
| `session_id` | [输入] 认证成功时生成的本连接会话 ID 文本。 |
| `session_key` | [输入] 由双方随机数和身份密钥派生的 32 字节会话密钥，保存供后续加解密使用。 |

## SecureSession.protect_server_message

```python
def protect_server_message(self, payload):
```

**用途：** 先将服务端发送序号加一，再按 S2C 方向调用 encrypt_message，返回要发给客户端的安全信封。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入／输出] 当前 SecureSession，提供会话和密钥，并递增 send_sequence。 |
| `payload` | [输入] 本次服务端要发送的业务字典，通常含 action 及 TASK、WAIT 等动作的其他字段。 |

## SecureSession.open_client_message

```python
def open_client_message(self, envelope):
```

**用途：** 暂时将接收序号加一，按 C2S 方向校验并解密客户端信封，返回业务字典；若 decrypt_message 抛出 ValueError，则回退本次增加的序号并继续抛出异常。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入／输出] 当前 SecureSession，提供会话 ID、密钥及预期接收序号；成功时 receive_sequence 保持递增后的值。 |
| `envelope` | [输入] 从 SECURE 帧 Body 解析出的客户端安全信封字典，包含会话、序号、随机数、密文和认证标签。 |
