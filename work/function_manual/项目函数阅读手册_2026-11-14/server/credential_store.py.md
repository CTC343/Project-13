# server/credential_store.py

生成演示节点凭据与程序哈希白名单，校验登录身份，并生成每条连接的会话参数。

## file_sha256

```python
def file_sha256(path):
```

**用途：** 以二进制分块读取文件并计算 SHA-256，返回 64 字符的小写十六进制摘要，用于客户端程序哈希白名单。

| 参数 | 含义 |
| --- | --- |
| `path` | [输入] 要计算摘要的 pathlib.Path 文件路径对象；函数通过 path.open("rb") 打开，不接受未经转换的普通路径字符串。 |

## _read_store

```python
def _read_store():
```

**用途：** 读取固定 STORE_FILE 中的节点凭据 JSON 并返回解析结果；文件不存在、读取失败或 JSON 无效时返回空字典。函数不检查 JSON 内部结构。

**参数：** 无。

## _write_store

```python
def _write_store(store):
```

**用途：** 确保 data 目录存在，再将完整节点凭据表以缩进 JSON 覆盖写入固定 STORE_FILE。此文件含身份密钥，应作为机密保存。

| 参数 | 含义 |
| --- | --- |
| `store` | [输入] 要持久化的完整节点凭据字典，通常为 {节点 ID: 凭据记录}；记录包含 license_id、expires、auth_key 和 allowed_exe_hashes。 |

## _write_client_credential

```python
def _write_client_credential(node_id, record):
```

**用途：** 为指定节点生成固定文本格式的 .cred 授权文件，写入节点 ID、许可证 ID、有效期和身份密钥；路径固定在 client/credentials 下，同名文件会覆盖。

| 参数 | 含义 |
| --- | --- |
| `node_id` | [输入] 要签发凭据的节点 ID，同时用作文件名和文件内 node_id 的值。 |
| `record` | [输入] 此节点的服务端凭据记录字典；读取 license_id、expires 和 auth_key 写入客户端文件，程序白名单不写入该文件。 |

## provision_demo_credentials

```python
def provision_demo_credentials(refresh_hashes=False):
```

**用途：** 确保任务签名密钥存在，读取已有凭据表，为演示节点补生成随机许可证和身份密钥，并根据现有客户端 EXE 计算程序哈希；逐节点重写 .cred 文件、保存凭据表，返回登记节点总数。不会无条件更换已有节点身份密钥。

| 参数 | 含义 |
| --- | --- |
| `refresh_hashes` | [输入，可选] 是否刷新已有节点的 allowed_exe_hashes，默认 False；为 True 且至少找到一个客户端 EXE 时才用本次计算的哈希更新已有白名单，新节点始终使用本次哈希列表。 |

## CredentialStore.__init__

```python
def __init__(self):
```

**用途：** 先补齐演示凭据，再读取节点记录，建立本进程已用登录随机数表和互斥锁。初始化具有写凭据文件的副作用，并非纯读取操作。

| 参数 | 含义 |
| --- | --- |
| `self` | [输出] 正在创建的 CredentialStore；初始化 records、used_nonces 和 lock，供各连接共享认证。 |

## CredentialStore._remove_old_nonces

```python
def _remove_old_nonces(self, now):
```

**用途：** 剔除登记时间早于 now 减去两倍认证时间窗的登录随机数，限制去重表大小；函数内部不加锁，由 authenticate 在持锁时调用。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入／输出] 当前 CredentialStore；用过滤后的字典替换 used_nonces，保留尚在保留期内的随机数。 |
| `now` | [输入] 当前 Unix 秒时间戳整数；用于计算去重记录的保留截止点，比较的是记录的接收时间。 |

## CredentialStore.authenticate

```python
def authenticate(self, request):
```

**用途：** 检查登录字段、节点登记、许可证归属与有效期、±60 秒时间窗、随机数重复、程序哈希白名单及 HMAC；成功登记随机数并返回节点身份密钥 bytes，不通过时抛出 ValueError。当前白名单为空时跳过哈希成员校验，且去重状态仅在当前进程内保存。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入／输出] 共用的 CredentialStore；从 records 取节点凭据，使用 lock 保护 used_nonces 的清理、检查和登记。 |
| `request` | [输入] AUTH 消息体字典，必需字段为 node_id、license_id、timestamp、client_nonce、exe_hash、auth_tag；persistent 可选，用其真假值归一化为 0 或 1，并一并纳入 HMAC 文本。 |

## CredentialStore.create_session

```python
def create_session(self, auth_key, client_nonce):
```

**用途：** 生成随机会话 ID 和服务端随机数，用身份密钥派生会话密钥并计算服务端身份证明；返回 (session_id, server_nonce, server_proof, session_key)，不在凭据对象中登记此会话。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入] 当前 CredentialStore 实例；为统一凭据与会话创建接口而保留，当前函数体不读取或修改实例字段。 |
| `auth_key` | [输入] authenticate 成功后得到的节点长期身份密钥原始 bytes，作为会话派生和服务端身份证明的 HMAC 密钥。 |
| `client_nonce` | [输入] 本次通过认证的客户端随机数文本；绑定到新会话的密钥和服务端证明中，避免与其他登录请求混用。 |
