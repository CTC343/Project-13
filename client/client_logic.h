#ifndef PROJECT13_CLIENT_LOGIC_H
#define PROJECT13_CLIENT_LOGIC_H

#define CLIENT_LOG_SIZE 16384

#define CLIENT_PROGRESS_CONNECTING 1
#define CLIENT_PROGRESS_AUTHENTICATED 2
#define CLIENT_PROGRESS_HEARTBEAT 3
#define CLIENT_PROGRESS_COMPUTING 4
#define CLIENT_PROGRESS_WAITING 5
#define CLIENT_PROGRESS_BLOCKED 6
#define CLIENT_PROGRESS_ERROR 7
#define CLIENT_PROGRESS_DISCONNECTED 8
#define CLIENT_PROGRESS_RECONNECTING 9

typedef void (*ClientProgressCallback)(int progress_code);

/*
 * 执行一次完整客户端流程。
 * mode 可使用 normal、wrong 或 tamper。
 * 返回 0 表示成功，1 表示通信失败，2 表示任务认证失败。
 */
int run_client(const char *node_id, const char *mode, int keep_online,
               ClientProgressCallback progress_callback,
               char *log_text, int log_size);
void request_client_stop(void);

#endif
