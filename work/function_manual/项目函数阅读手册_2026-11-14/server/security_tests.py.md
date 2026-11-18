# server/security_tests.py

运行不依赖正在监听的业务服务端的基础安全自检，并生成 JSON 报告；覆盖范围有限，不能证明系统不存在高危漏洞。

## check

```python
def check(name, function):
```

**用途：** 执行一个无参数测试函数：正常结束视为通过，捕获 Exception 后记录失败，返回含 name、passed 和 detail 的单项结果字典。

| 参数 | 含义 |
| --- | --- |
| `name` | [输入] 测试项的展示名称，用于报告中的 name 字段。 |
| `function` | [输入] 待执行的可调用对象，应能无参数调用；失败时通过抛出异常报告，返回值本身不会被此包装器检查。 |

## test_encrypted_roundtrip

```python
def test_encrypted_roundtrip():
```

**用途：** 生成随机会话密钥，将示例对象加密后再解密，检查能否还原原始对象；不一致则抛出 AssertionError。

**参数：** 无。

## test_tamper_rejected

```python
def test_tamper_rejected():
```

**用途：** 修改合法安全信封中密文的第一个十六进制字符，确认解密校验抛出 ValueError；若篡改后仍被接受则测试失败。

**参数：** 无。

## test_replay_rejected

```python
def test_replay_rejected():
```

**用途：** 先按序号 1 接收一条安全消息，再以预期序号 2 检查同一信封，确认旧序号被拒绝；这是解密接口的序号用例，不是完整网络重放演练。

**参数：** 无。

## make_auth_request

```python
def make_auth_request(store, node_id, nonce, tag_override=None):
```

**用途：** 从节点凭据中取许可证、密钥和首个允许的程序哈希，使用当前时间、指定 nonce 和 persistent=0 构造认证请求字典；可用指定标签替代正确 HMAC，便于负向测试。

| 参数 | 含义 |
| --- | --- |
| `store` | [输入] CredentialStore 对象；从 records 字典读取指定节点的 license_id、auth_key 和 allowed_exe_hashes。 |
| `node_id` | [输入] 要构造请求的节点 ID，必须已在 store.records 中登记。 |
| `nonce` | [输入] 放入 client_nonce 的随机数字符串；测试调用通常传入 secrets.token_hex(16)，即 32 个十六进制字符。 |
| `tag_override` | [输入，可选，默认 None] 用于覆盖正确身份 HMAC 的标签；为非空值时直接采用它，为 None 或其他假值时自动计算正确标签。 |

## test_identity_spoof_rejected

```python
def test_identity_spoof_rejected():
```

**用途：** 为 node-01 构造带全零伪造 HMAC 的登录请求，确认凭据认证拒绝该请求；若成功认证则测试失败。创建 CredentialStore 时可能触发演示凭据准备。

**参数：** 无。

## test_auth_replay_rejected

```python
def test_auth_replay_rejected():
```

**用途：** 对同一份合法认证请求连续认证两次，确认第二次因 nonce 重复而被拒绝；测试复用同一个内存凭据仓库，不覆盖服务端重启后的重放行为。

**参数：** 无。

## test_sticky_and_fragmented_frames

```python
def test_sticky_and_fragmented_frames():
```

**用途：** 通过 socketpair 连续发送 ONE 和 TWO 两帧，确认 Python 接收端能分别解析。虽然名称包含 fragmented，当前函数没有主动把一帧切成多次发送，也没有测试 C 客户端。

**参数：** 无。

## test_oversized_body_rejected

```python
def test_oversized_body_rejected():
```

**用途：** 发送声明 Body 长度为 9000 的 Header，确认 Python 协议解析器在读取超限 Body 前拒绝，并使用状态码 413。

**参数：** 无。

## test_executable_allowlist

```python
def test_executable_allowlist():
```

**用途：** 读取 node-01 的允许程序哈希，将本地现有 client.exe 和 client_gui.exe 的 SHA-256 与其比较；文件不存在时跳过该文件。它不验证这些 EXE 是否由当前源码编译。

**参数：** 无。

## test_rsa_task_signature

```python
def test_rsa_task_signature():
```

**用途：** 检查 RSA 模数至少 2048 位，给测试文本签名后做公开指数模幂，检查结果的 00 01 FF 前缀及 SHA-256 DigestInfo 后缀。当前用例没有逐字节验证中间全部 PKCS#1 填充，也不是 C 端验签联调。

**参数：** 无。

## test_no_dangerous_calls

```python
def test_no_dangerous_calls():
```

**用途：** 扫描 client 目录下所有 .c 文本，用正则查找 gets、strcpy、strcat、system、rand 的直接调用形式，发现匹配则失败。这是有限规则扫描，不是完整静态安全分析，也不能证明不存在内存漏洞。

**参数：** 无。

## create_report

```python
def create_report():
```

**用途：** 依次运行注册的 10 个自检，汇总通过数量和明细，加上生成时间，覆盖写入 data/security_tests.json 并返回报告字典；部分用例会读取或准备演示凭据和签名密钥。

**参数：** 无。

## read_security_test_report

```python
def read_security_test_report():
```

**用途：** 读取 data/security_tests.json 并返回解析后的报告；文件不存在时返回空字典，解析错误由调用方处理。

**参数：** 无。
