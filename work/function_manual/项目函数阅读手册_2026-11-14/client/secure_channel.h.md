# client/secure_channel.h

声明会话密钥派生、消息加解密与会话清理接口。

## derive_session_key

```c
int derive_session_key(const unsigned char auth_key[32], const char *client_nonce, const char *server_nonce, const char *session_id, unsigned char output[32]);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。按 SESSION|client_nonce|server_nonce|session_id 拼接文本，以节点身份密钥计算 HMAC-SHA256，得到双方一致的 32 字节会话密钥；成功返回非零。

| 参数 | 含义 |
| --- | --- |
| `auth_key` | [输入] 凭据文件中解码得到的 32 字节节点身份密钥。 |
| `client_nonce` | [输入] 客户端认证时生成的随机数的十六进制文本，当前为 32 个字符。 |
| `server_nonce` | [输入] 服务端 AUTH_OK 返回的随机数十六进制文本，当前为 32 个字符。 |
| `session_id` | [输入] 服务端为本次认证生成的会话 ID 文本。 |
| `output` | [输出] 至少 32 字节的数组，接收原始会话密钥，不附加字符串终止符。 |

## protect_client_message

```c
int protect_client_message(SecureSession *session, const char *plain_json, char *envelope, int envelope_size);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。递增客户端发送序号，为业务 JSON 生成随机数、密文和 C2S 方向的 HMAC 标签，输出 JSON 安全信封。成功返回 1，随机数、加密、认证或输出容量失败返回 0。

| 参数 | 含义 |
| --- | --- |
| `session` | [输入／输出] 保存会话 ID、32 字节密钥和双向序号的结构体；此函数会先递增 send_sequence，即使后续封装失败也不回退。 |
| `plain_json` | [输入] 以空字符结尾的待发送业务 JSON 明文。 |
| `envelope` | [输出] 保存 session_id、sequence、nonce、ciphertext、tag 的 JSON 安全信封字符串。 |
| `envelope_size` | [输入] envelope 总容量，单位为字节，包含结尾空字符；密文使用十六进制后会扩展到明文字节数的两倍。 |

## open_server_message

```c
int open_server_message(SecureSession *session, const char *envelope, char *plain_json, int plain_size);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。从服务端安全信封提取字段，校验会话 ID、下一接收序号、随机数、HMAC 标签，再按 S2C 方向解密。成功追加明文空字符、更新接收序号并返回 1；失败返回 0。

| 参数 | 含义 |
| --- | --- |
| `session` | [输入／输出] 当前会话结构体；提供密钥、ID 和预期序号，仅在验证和解密成功时更新 receive_sequence。 |
| `envelope` | [输入] 服务端返回的 JSON 安全信封字符串。 |
| `plain_json` | [输出] 接收解密后业务 JSON 明文的字符缓冲区。 |
| `plain_size` | [输入] plain_json 总容量，单位为字节，必须容纳密文字节数对应的明文及一个结尾空字符。 |

## clear_secure_session

```c
void clear_secure_session(SecureSession *session);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。将整个 SecureSession 结构体清零，包括会话 ID、密钥和双向消息序号。

| 参数 | 含义 |
| --- | --- |
| `session` | [输出／清除] 要清零的会话结构体地址。 |
