# client/credentials.h

声明节点凭据读取、自身程序哈希与凭据清理接口。

## load_node_credential

```c
int load_node_credential(const char *node_id, NodeCredential *credential, char *error_text, int error_size);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。定位当前 EXE 旁的 credentials/<node_id>.cred 文件，检查格式标记，读取节点、许可证、到期日和身份密钥，并确认文件节点 ID 与请求一致。成功返回 1，失败写错误并返回 0；此处只读取到期日，真正的过期检查在服务端执行。

| 参数 | 含义 |
| --- | --- |
| `node_id` | [输入] 要加载凭据的节点 ID，用于拼接文件名并核对文件内 node_id。 |
| `credential` | [输出] NodeCredential 结构体地址，写入节点 ID、许可证 ID、到期日期及解码后的 32 字节身份密钥。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## current_executable_hash

```c
int current_executable_hash(char output_hex[65], char *error_text, int error_size);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。取得当前进程 EXE 的完整路径，并计算该文件的 SHA-256 摘要供认证请求上报；成功返回 1，否则写错误并返回 0。

| 参数 | 含义 |
| --- | --- |
| `output_hex` | [输出] 至少 65 字节的字符数组：64 个小写十六进制摘要字符加结尾空字符。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## clear_node_credential

```c
void clear_node_credential(NodeCredential *credential);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。把整个 NodeCredential 结构体清零，包括身份密钥，减少凭据在内存中的残留。

| 参数 | 含义 |
| --- | --- |
| `credential` | [输出／清除] 要清零的 NodeCredential 结构体地址。 |
