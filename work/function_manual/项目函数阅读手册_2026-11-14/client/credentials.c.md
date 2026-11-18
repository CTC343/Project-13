# client/credentials.c

定位当前程序旁的节点凭据、读取身份密钥、计算 EXE 哈希并清理凭据内存。

## read_value

```c
static int read_value(FILE *file, const char *name, char *value, int value_size);
```

**用途：** 从凭据文件当前读取位置向后逐行查找 name=value 项，将等号后的内容复制到输出并去除行尾换行。找到时返回 1，否则返回 0；不自动回到文件开头。

| 参数 | 含义 |
| --- | --- |
| `file` | [输入／输出] 已打开的凭据文件流；读取会推进文件位置，需要重新查找时由调用者 rewind。 |
| `name` | [输入] 要读取的键名，例如 node_id、license_id、expires 或 auth_key，不含等号。 |
| `value` | [输出] 保存读取到的字段文本的字符缓冲区；字段过长时 snprintf 按容量截断。 |
| `value_size` | [输入] value 缓冲区容量，单位为字节，包含结尾空字符。 |

## executable_directory

```c
static int executable_directory(char *directory, int directory_size, char *executable, int executable_size);
```

**用途：** 调用 GetModuleFileNameA 取得当前进程可执行文件路径，并在副本中去掉最后一个反斜杠及文件名，得到其所在目录；成功返回 1，路径读取失败或没有目录分隔符时返回 0。

| 参数 | 含义 |
| --- | --- |
| `directory` | [输出] 保存当前 EXE 所在目录的字符缓冲区，输出不带末尾反斜杠。 |
| `directory_size` | [输入] directory 容量，单位为字节，包含结尾空字符。 |
| `executable` | [输出] 保存当前进程 EXE 完整路径的字符缓冲区。 |
| `executable_size` | [输入] executable 容量，单位为字节，包含结尾空字符；直接传给 GetModuleFileNameA。 |

## load_node_credential

```c
int load_node_credential(const char *node_id, NodeCredential *credential, char *error_text, int error_size);
```

**用途：** 定位当前 EXE 旁的 credentials/<node_id>.cred 文件，检查格式标记，读取节点、许可证、到期日和身份密钥，并确认文件节点 ID 与请求一致。成功返回 1，失败写错误并返回 0；此处只读取到期日，真正的过期检查在服务端执行。

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

**用途：** 取得当前进程 EXE 的完整路径，并计算该文件的 SHA-256 摘要供认证请求上报；成功返回 1，否则写错误并返回 0。

| 参数 | 含义 |
| --- | --- |
| `output_hex` | [输出] 至少 65 字节的字符数组：64 个小写十六进制摘要字符加结尾空字符。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## clear_node_credential

```c
void clear_node_credential(NodeCredential *credential);
```

**用途：** 把整个 NodeCredential 结构体清零，包括身份密钥，减少凭据在内存中的残留。

| 参数 | 含义 |
| --- | --- |
| `credential` | [输出／清除] 要清零的 NodeCredential 结构体地址。 |
