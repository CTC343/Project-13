# client/client_logic.c

实现不依赖具体界面布局的认证、心跳、任务验签、计算、提交和资源清理流程。

## request_client_stop

```c
void request_client_stop(void);
```

**用途：** 把本模块的停止标志设为 1，让客户端循环在后续检查时退出；此函数本身不立即中断正在阻塞的网络收发。

**参数：** 无。

## report_progress

```c
static void report_progress(ClientProgressCallback callback, int progress_code, const char *detail);
```

**用途：** 当回调不为空时调用它，统一向调用者报告客户端阶段；回调为空时不做处理。

| 参数 | 含义 |
| --- | --- |
| `callback` | [输入] 进度通知函数指针；可以为 NULL，表示无需报告进度。 |
| `progress_code` | [输入] 要报告的阶段编号，对应 CLIENT_PROGRESS_* 常量。 |
| `detail` | [输入] 与该阶段一起传递的说明字符串。 |

## valid_node_id

```c
static int valid_node_id(const char *node_id);
```

**用途：** 检查节点 ID 是否非空、长度少于 64 字节，并且每个字符都是 isalnum 接受的字母数字、短横线或下划线；符合时返回 1，否则返回 0。

| 参数 | 含义 |
| --- | --- |
| `node_id` | [输入] 待检查的、以空字符结尾的节点 ID 字符串；NULL 会被拒绝。 |

## receive_secure_any

```c
static int receive_secure_any(SOCKET socket_value, SecureSession *session, char *plain, char *action, int action_size, char *error_text, int error_size);
```

**用途：** 接收一帧 SECURE 消息，验证并解密安全信封，取出 action，并检查外层状态是否为 200。成功返回 1；收包、认证、解析或服务端状态失败时返回 0。

| 参数 | 含义 |
| --- | --- |
| `socket_value` | [输入] 已连接服务端的 Winsock 套接字，用于读取响应帧。 |
| `session` | [输入／输出] 当前安全会话，提供密钥、会话 ID 和接收序号；成功验证后更新接收序号。 |
| `plain` | [输出] 保存解密后业务 JSON 的字符缓冲区。此函数按 TEXT_SIZE（8192 字节）传入容量，调用者必须提供至少这么大的空间。 |
| `action` | [输出] 保存明文中 action 字段的字符缓冲区。 |
| `action_size` | [输入] action 缓冲区容量，单位为字节，包含结尾空字符所需空间。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## receive_secure

```c
static int receive_secure(SOCKET socket_value, SecureSession *session, const char *expected_action, char *plain, char *error_text, int error_size);
```

**用途：** 在 receive_secure_any 的基础上要求业务 action 等于指定动作，例如 HEARTBEAT_ACK 或 ACCEPTED；符合时返回 1，否则记录错误并返回 0。

| 参数 | 含义 |
| --- | --- |
| `socket_value` | [输入] 已连接服务端的 Winsock 套接字。 |
| `session` | [输入／输出] 当前安全会话；接收时校验并更新接收序号。 |
| `expected_action` | [输入] 期望收到的业务动作名称，必须与解密后的 action 字段完全相同。 |
| `plain` | [输出] 解密后业务 JSON 缓冲区，调用者应提供至少 TEXT_SIZE（8192）字节。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## send_secure

```c
static int send_secure(SOCKET socket_value, SecureSession *session, const char *plain, char *error_text, int error_size);
```

**用途：** 把业务 JSON 加密并附加认证标签，封装成类型 SECURE、状态 0 的协议帧发送；成功返回非零，失败返回 0。

| 参数 | 含义 |
| --- | --- |
| `socket_value` | [输入] 已连接服务端的 Winsock 套接字。 |
| `session` | [输入／输出] 当前安全会话，提供密钥和会话 ID；封装消息时递增发送序号。 |
| `plain` | [输入] 要发送的、以空字符结尾的业务 JSON 对象字符串，通常包含 action 字段。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## send_heartbeat

```c
static int send_heartbeat(SOCKET socket_value, SecureSession *session, char *server_body, char *error_text, int error_size);
```

**用途：** 以当前 Unix 秒时间生成 HEARTBEAT 业务消息并加密发送，然后等待并验证 HEARTBEAT_ACK；两个步骤都成功才返回非零。

| 参数 | 含义 |
| --- | --- |
| `socket_value` | [输入] 已连接服务端的 Winsock 套接字。 |
| `session` | [输入／输出] 当前安全会话，发送和接收时分别更新相应序号。 |
| `server_body` | [输出] 保存解密后的 HEARTBEAT_ACK JSON；应提供至少 TEXT_SIZE（8192）字节。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## send_logout

```c
static int send_logout(SOCKET socket_value, SecureSession *session, char *error_text, int error_size);
```

**用途：** 发送加密的 LOGOUT 业务消息，通知服务端客户端请求退出；本函数不等待单独的退出确认，也不负责关闭套接字。

| 参数 | 含义 |
| --- | --- |
| `socket_value` | [输入] 已连接服务端的 Winsock 套接字。 |
| `session` | [输入／输出] 当前安全会话，封装退出消息时递增发送序号。 |
| `error_text` | [输出] 失败时写入可读错误信息的字符缓冲区；成功时不保证重写其原有内容。 |
| `error_size` | [输入] error_text 缓冲区容量，单位为字节，包含结尾空字符。 |

## run_client

```c
int run_client(const char *node_id, const char *mode, int keep_online, ClientProgressCallback progress_callback, char *log_text, int log_size);
```

**用途：** 执行公共客户端主流程：读取凭据、计算自身程序哈希、连接认证、验证服务端证明、建立安全会话、心跳、接收和验签任务、计算并提交证明，最后清理资源。持续模式可等待后续任务。返回 0 表示正常结束，1 表示流程或通信失败，2 表示身份／任务认证失败。当前调用的 network_connect_retry 等底层函数尚缺定义，不能据此说明源码已可完整链接运行。

| 参数 | 含义 |
| --- | --- |
| `node_id` | [输入] 本次连接使用的已签发节点 ID；也用于定位程序目录下 credentials/<node_id>.cred 凭据文件。 |
| `mode` | [输入] 行为模式：normal 正常计算；wrong 故意修改步骤结果；tamper 在验签前修改任务范围以验证拦截。NULL 或其他值不会启用这两种模拟。 |
| `keep_online` | [输入] 非零时在认证中声明持续在线，完成任务后继续心跳并等待；0 表示完成一次任务后结束。 |
| `progress_callback` | [输入] ClientProgressCallback 类型的通知函数，用于接收阶段和说明；可以为 NULL。 |
| `log_text` | [输出／追加] 存放本次流程日志的字符缓冲区；函数开始时清空，再逐步追加日志。 |
| `log_size` | [输入] log_text 的总容量，单位为字节，包含结尾空字符；必须大于 0。 |

## add_log

```c
static void add_log(char *log_text, int log_size, const char *format, ...);
```

**用途：** 把一条按 printf 规则格式化的日志追加到现有日志字符串末尾，并按剩余容量限制写入。空间不足时截断或不再追加。

| 参数 | 含义 |
| --- | --- |
| `log_text` | [输入／输出] 已经以空字符结尾的日志缓冲区，保留旧内容并在末尾追加。 |
| `log_size` | [输入] log_text 总容量，单位为字节，包含结尾空字符。 |
| `format` | [输入] printf 风格的格式字符串，例如包含 %s、%ld 等占位符。 |
| `...` | [输入] 与 format 占位符一一对应的可变参数。 |
