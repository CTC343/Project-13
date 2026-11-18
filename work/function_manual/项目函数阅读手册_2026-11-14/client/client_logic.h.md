# client/client_logic.h

声明公共客户端入口、停止接口与进度回调类型，供控制台或其他调用者使用。

## ClientProgressCallback（回调类型）

```c
typedef void (*ClientProgressCallback)(int progress_code, const char *detail);
```

**用途：** 定义进度通知函数的类型，供公共客户端流程把当前阶段和文字说明交给调用者。它是回调类型声明，不是一个具有函数体的函数。

| 参数 | 含义 |
| --- | --- |
| `progress_code` | [输入] 当前阶段编号，对应 CLIENT_PROGRESS_* 常量，例如连接、认证完成、计算完成和提交完成。 |
| `detail` | [输入] 本次阶段的说明字符串；接收者如需稍后使用，应在回调期间自行复制。 |

## run_client

```c
int run_client(const char *node_id, const char *mode, int keep_online, ClientProgressCallback progress_callback, char *log_text, int log_size);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。执行公共客户端主流程：读取凭据、计算自身程序哈希、连接认证、验证服务端证明、建立安全会话、心跳、接收和验签任务、计算并提交证明，最后清理资源。持续模式可等待后续任务。返回 0 表示正常结束，1 表示流程或通信失败，2 表示身份／任务认证失败。当前调用的 network_connect_retry 等底层函数尚缺定义，不能据此说明源码已可完整链接运行。

| 参数 | 含义 |
| --- | --- |
| `node_id` | [输入] 本次连接使用的已签发节点 ID；也用于定位程序目录下 credentials/<node_id>.cred 凭据文件。 |
| `mode` | [输入] 行为模式：normal 正常计算；wrong 故意修改步骤结果；tamper 在验签前修改任务范围以验证拦截。NULL 或其他值不会启用这两种模拟。 |
| `keep_online` | [输入] 非零时在认证中声明持续在线，完成任务后继续心跳并等待；0 表示完成一次任务后结束。 |
| `progress_callback` | [输入] ClientProgressCallback 类型的通知函数，用于接收阶段和说明；可以为 NULL。 |
| `log_text` | [输出／追加] 存放本次流程日志的字符缓冲区；函数开始时清空，再逐步追加日志。 |
| `log_size` | [输入] log_text 的总容量，单位为字节，包含结尾空字符；必须大于 0。 |

## request_client_stop

```c
void request_client_stop(void);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。把本模块的停止标志设为 1，让客户端循环在后续检查时退出；此函数本身不立即中断正在阻塞的网络收发。

**参数：** 无。
