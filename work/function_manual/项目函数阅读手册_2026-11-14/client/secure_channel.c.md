# client/secure_channel.c

使用 HMAC 派生密钥流保护业务消息，并通过会话 ID、方向、序号和认证标签校验消息。

## write_u64_big_endian

```c
static void write_u64_big_endian(unsigned char output[8], uint64_t value);
```

**用途：** 把一个 64 位无符号整数编码为固定八字节的大端序，供密钥流序号编码使用。

| 参数 | 含义 |
| --- | --- |
| `output` | [输出] 至少八字节的数组，写入从最高有效字节到最低有效字节的编码；不是字符串。 |
| `value` | [输入] 要编码的 uint64_t 整数。 |

## make_keystream

```c
static int make_keystream(const unsigned char key[32], const char *direction, const char *session_id, long sequence, const unsigned char nonce[16], unsigned char *output, int output_size);
```

**用途：** 把方向、会话 ID、八字节序号、随机数和四字节分块计数器组成输入，用 HMAC-SHA256 连续产生足够长的密钥流。成功返回 1，HMAC 失败返回 0。

| 参数 | 含义 |
| --- | --- |
| `key` | [输入] 32 字节会话密钥。 |
| `direction` | [输入] 消息方向字符串，当前使用 C2S 或 S2C，防止两方向使用相同的密钥流输入。 |
| `session_id` | [输入] 当前会话 ID 的文本表示，用于把密钥流绑定到本次会话。 |
| `sequence` | [输入] 该方向本条消息的序号，转为八字节大端序参与生成。 |
| `nonce` | [输入] 本条消息的 16 字节原始随机数，不是十六进制字符串。 |
| `output` | [输出] 接收密钥流的二进制缓冲区，至少有 output_size 字节。 |
| `output_size` | [输入] 需要生成的密钥流长度，单位为字节。 |

## derive_session_key

```c
int derive_session_key(const unsigned char auth_key[32], const char *client_nonce, const char *server_nonce, const char *session_id, unsigned char output[32]);
```

**用途：** 按 SESSION|client_nonce|server_nonce|session_id 拼接文本，以节点身份密钥计算 HMAC-SHA256，得到双方一致的 32 字节会话密钥；成功返回非零。

| 参数 | 含义 |
| --- | --- |
| `auth_key` | [输入] 凭据文件中解码得到的 32 字节节点身份密钥。 |
| `client_nonce` | [输入] 客户端认证时生成的随机数的十六进制文本，当前为 32 个字符。 |
| `server_nonce` | [输入] 服务端 AUTH_OK 返回的随机数十六进制文本，当前为 32 个字符。 |
| `session_id` | [输入] 服务端为本次认证生成的会话 ID 文本。 |
| `output` | [输出] 至少 32 字节的数组，接收原始会话密钥，不附加字符串终止符。 |

## crypt_message

```c
static int crypt_message(const unsigned char key[32], const char *direction, const char *session_id, long sequence, const unsigned char nonce[16], const unsigned char *input, int input_size, unsigned char *output);
```

**用途：** 生成与输入等长的密钥流，逐字节异或输入得到输出，随后清理临时密钥流；同样的运算既用于加密也用于解密。成功返回 1，分配或 HMAC 失败返回 0。

| 参数 | 含义 |
| --- | --- |
| `key` | [输入] 32 字节会话密钥。 |
| `direction` | [输入] 方向标识 C2S 或 S2C，必须与生成该消息密钥流时一致。 |
| `session_id` | [输入] 当前会话 ID 文本。 |
| `sequence` | [输入] 当前消息序号，必须与对端使用的序号一致。 |
| `nonce` | [输入] 本条消息的 16 字节原始随机数。 |
| `input` | [输入] 明文或密文的起始地址，按 input_size 读取。 |
| `input_size` | [输入] 待处理的字节数，也是输出数据长度。 |
| `output` | [输出] 接收异或结果的缓冲区，至少可容纳 input_size 字节；本函数不追加空字符。 |

## protect_client_message

```c
int protect_client_message(SecureSession *session, const char *plain_json, char *envelope, int envelope_size);
```

**用途：** 递增客户端发送序号，为业务 JSON 生成随机数、密文和 C2S 方向的 HMAC 标签，输出 JSON 安全信封。成功返回 1，随机数、加密、认证或输出容量失败返回 0。

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

**用途：** 从服务端安全信封提取字段，校验会话 ID、下一接收序号、随机数、HMAC 标签，再按 S2C 方向解密。成功追加明文空字符、更新接收序号并返回 1；失败返回 0。

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

**用途：** 将整个 SecureSession 结构体清零，包括会话 ID、密钥和双向消息序号。

| 参数 | 含义 |
| --- | --- |
| `session` | [输出／清除] 要清零的会话结构体地址。 |
