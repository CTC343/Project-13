/* 客户端主流程：认证后保持连接，周期心跳并持续等待任务。 */
#include <ctype.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <winsock2.h>
#include <windows.h>

#include "client_logic.h"
#include "credentials.h"
#include "device.h"
#include "merkle.h"
#include "network.h"
#include "operations.h"
#include "protocol.h"
#include "outbox.h"
#include "security.h"
#include "signature.h"

#define TEXT_SIZE 8192

static volatile LONG stop_requested = 0;

static void add_log(char *log_text, int log_size, const char *format, ...);

void reset_client_stop(void)
{
    InterlockedExchange(&stop_requested, 0);
}

void request_client_stop(void)
{
    InterlockedExchange(&stop_requested, 1);
}

static void report_progress(ClientProgressCallback callback, int progress_code,
                            const char *detail)
{
    if (callback != NULL) callback(progress_code, detail);
}

static int valid_node_id(const char *node_id)
{
    int index;
    if (node_id == NULL || node_id[0] == '\0' || strlen(node_id) >= 64) return 0;
    for (index = 0; node_id[index] != '\0'; index++) {
        if (!isalnum((unsigned char)node_id[index]) &&
            node_id[index] != '-' && node_id[index] != '_') return 0;
    }
    return 1;
}

static int receive_secure_any(NetworkConnection *connection,
                              char *plain, char *action, int action_size,
                              char *error_text, int error_size)
{
    char type[32];
    int status;
    if (!protocol_receive_frame(connection, type, sizeof(type), &status,
                                plain, TEXT_SIZE,
                                error_text, error_size)) return 0;
    if (strcmp(type, "SECURE") != 0 ||
        !json_get_string(plain, "action", action, action_size)) {
        snprintf(error_text, error_size,
                 "Secure response authentication failed.");
        return 0;
    }
    if (status != 200) {
        char detail[256] = "request rejected";
        json_get_string(plain, "detail", detail, sizeof(detail));
        snprintf(error_text, error_size, "Server rejected request: %s", detail);
        return 0;
    }
    return 1;
}

static int receive_secure(NetworkConnection *connection,  const char *expected_action, char *plain,  char *error_text, int error_size)
{
    char action[64];
    if (!receive_secure_any(connection, plain, action,
                            sizeof(action), error_text, error_size)) return 0;
    if (strcmp(action, expected_action) != 0) {
        snprintf(error_text, error_size, "Expected %s, received %s.",
                 expected_action, action);
        return 0;
    }
    return 1;
}


static int send_secure(NetworkConnection *connection,
                       const char *plain, char *error_text, int error_size)
{
    return protocol_send_frame(connection, "SECURE", 0, plain, error_text, error_size);
}

static int send_heartbeat(NetworkConnection *connection,
                          const ClientLogin *login, const char *executable_hash,
                          const ClientPreviewHooks *preview, char *server_body,
                          char *error_text, int error_size)
{
    char body[128];
    int enabled = preview && preview->enabled();
    snprintf(body, sizeof(body),
             "{\"action\":\"HEARTBEAT\",\"sent_at\":%ld,\"preview_enabled\":%d}",
             (long)time(NULL), enabled);
    if (!send_secure(connection, body, error_text, error_size) ||
        !receive_secure(connection, "HEARTBEAT_ACK", server_body, error_text, error_size)) return 0;
    if (preview) {
        char view_id[33] = "";
        if (enabled) json_get_string(server_body, "preview_id", view_id, sizeof(view_id));
        preview->offer(login, view_id, executable_hash);
    }
    return 1;
}

static int send_logout(NetworkConnection *connection,
                       char *error_text, int error_size)
{
    const char *body = "{\"action\":\"LOGOUT\"}";
    return send_secure(connection, body, error_text, error_size);
}



int run_client(ClientLogin *login, const char *mode, int keep_online,
               ClientProgressCallback progress_callback, const ClientPreviewHooks *preview,
               char *log_text, int log_size)
{
    int simulate_wrong_result = mode != NULL && strcmp(mode, "wrong") == 0;
    int simulate_tampered_task = mode != NULL && strcmp(mode, "tamper") == 0;
    int waiting_logged = 0;
    int completed_task = 0;
    char executable_hash[65];
    char body[TEXT_SIZE];
    char server_body[TEXT_SIZE];
    char message_type[32];
    char action[64];
    char task_id[64];
    char operation[32];
    char proof_steps[128];
    char merkle_root[65];
    char network_error[NETWORK_ERROR_SIZE];
    char signature_hex[513];
    char progress_text[256];
    long range_start;
    long range_end;
    long result;
    long retry_after;
    int status;
    int return_code = 1;
    NetworkConnection connection = {INVALID_SOCKET};
    const char *node_id = login->node_id;
    char password_hex[513] = {0};
    Outbox outbox = {0};
    int connection_status;
    int pending_status;
    int authenticated = 0;

    if (log_text == NULL || log_size <= 0) return 1;
    log_text[0] = '\0';

    /* 准备阶段：检查节点 ID，读取授权信息，并计算客户端程序哈希。 */
    if (!valid_node_id(login->username) || login->host[0] == 0 || login->port < 1 || login->port >= 65535) {
        return_code = 2;
        add_log(log_text, log_size,
                "Invalid login fields. Account IDs use letters, digits, dash or underscore.\r\n");
        goto cleanup;
    }
    if (!current_executable_hash(executable_hash,
                                 network_error, sizeof(network_error))) {
        add_log(log_text, log_size, "%s\r\n", network_error);
        goto cleanup;
    }
    add_log(log_text, log_size, "Executable integrity: hash ready\r\n");

    report_progress(progress_callback, CLIENT_PROGRESS_CONNECTING, "Signing in over TLS");
    connection_status = device_prepare(login, executable_hash, network_error, sizeof(network_error));
    if (connection_status != 1 || !valid_node_id(node_id) || !valid_node_id(login->license_id)) {
        add_log(log_text, log_size, "Device setup: %s\r\n", network_error);
        if (connection_status != 0) return_code = 2;
        goto cleanup;
    }
    connection_status = network_connect(&connection, login->host, login->port, login->profile,
                                        network_error, sizeof(network_error));
    if (connection_status != 1) {
        add_log(log_text, log_size, "%s\r\n", network_error);
        if (connection_status < 0) return_code = 2;
        goto cleanup;
    }
    bytes_to_hex((const unsigned char *)login->password, (int)strlen(login->password), password_hex);
    snprintf(body, sizeof(body),
        "{\"node_id\":\"%s\",\"license_id\":\"%s\",\"exe_hash\":\"%s\","
        "\"username\":\"%s\",\"password_hex\":\"%s\",\"token\":\"%s\",\"persistent\":%d}",
        node_id, login->license_id, executable_hash, login->username,
        password_hex, login->session_token, keep_online ? 1 : 0);
    if (!protocol_send_frame(&connection, "AUTH", 0, body, network_error, sizeof(network_error))) {
        add_log(log_text, log_size, "Login: %s\r\n", network_error);
        goto cleanup;
    }
    clear_sensitive(body, sizeof(body));
    clear_sensitive(password_hex, sizeof(password_hex));
    if (!protocol_receive_frame(&connection, message_type, sizeof(message_type), &status,
                                server_body, sizeof(server_body), network_error, sizeof(network_error))) {
        add_log(log_text, log_size, "TLS login did not receive a reply. Check the node certificate.\r\n");
        return_code = 1;
        goto cleanup;
    }
    if (strcmp(message_type, "AUTH_OK") != 0 || status != 200 ||
        !json_get_string(server_body, "token", login->session_token, sizeof(login->session_token))) {
        char detail[160] = "authentication rejected";
        json_get_string(server_body, "detail", detail, sizeof(detail));
        add_log(log_text, log_size, "Login: %s\r\n", detail);
        return_code = status == 409 || status == 503 ? 1 : 2;
        goto cleanup;
    }
    clear_sensitive(server_body, sizeof(server_body));
    clear_sensitive(login->password, sizeof(login->password));
    authenticated = 1;
    snprintf(progress_text, sizeof(progress_text), "%s:%d · %s", login->host, login->port, node_id);
    add_log(log_text, log_size, "Login accepted by %s over TLS 1.3.\r\n", progress_text);
    report_progress(progress_callback, CLIENT_PROGRESS_AUTHENTICATED, progress_text);

    if (!outbox_init(login, &outbox)) {
        add_log(log_text, log_size, "Cannot open the local result outbox.\r\n");
        return_code = 2;
        goto cleanup;
    }
    pending_status = outbox_load(&outbox, body, sizeof(body));
    if (pending_status < 0) {
        add_log(log_text, log_size, "Pending result requires local recovery.\r\n");
        return_code = 2;
        goto cleanup;
    }
    if (pending_status > 0) {
        if (!json_get_string(body, "task_id", task_id, sizeof(task_id)) ||
            !send_secure(&connection, body, network_error, sizeof(network_error)) ||
            !receive_secure_any(&connection, server_body, action, sizeof(action),
                                network_error, sizeof(network_error))) {
            add_log(log_text, log_size, "Pending result kept for retry.\r\n");
            goto cleanup;
        }
        if (!json_get_string(server_body, "task_id", progress_text, sizeof(progress_text)) ||
            strcmp(progress_text, task_id) != 0 ||
            (strcmp(action, "ACCEPTED") != 0 && strcmp(action, "RETAIN") != 0) ||
            !outbox_resolve(&outbox, task_id, strcmp(action, "ACCEPTED") == 0)) {
            add_log(log_text, log_size, "Pending result could not be reconciled.\r\n");
            return_code = 2;
            goto cleanup;
        }
        add_log(log_text, log_size, "Pending result reconciled: %s\r\n", action);
    }

    /* 在线阶段：先发送一次心跳，确认连接可用后开始等待任务。 */
    if (!send_heartbeat(&connection, login, executable_hash, preview, server_body,
                        network_error, sizeof(network_error))) {
        add_log(log_text, log_size, "Heartbeat: %s\r\n", network_error);
        goto cleanup;
    }
    add_log(log_text, log_size, "Heartbeat: acknowledged\r\n");
    report_progress(progress_callback, CLIENT_PROGRESS_HEARTBEAT,
                    "Online; waiting for task");

    /* 任务循环：持续接收服务器消息；收到 WAIT 就等待并定期心跳，收到 TASK 就进入任务处理。 */
    while (!stop_requested) {
        if (keep_online) return_code = 1;
        if (!receive_secure_any(&connection, server_body,
                                action, sizeof(action),
                                network_error, sizeof(network_error))) {
            add_log(log_text, log_size, "Server message: %s\r\n", network_error);
            goto cleanup;
        }

        if (strcmp(action, "WAIT") == 0) {
            retry_after = 2;
            json_get_long(server_body, "retry_after", &retry_after);
            if (!waiting_logged) {
                add_log(log_text, log_size,
                        "Online: waiting for the next task; heartbeat active\r\n");
                waiting_logged = 1;
            }
            report_progress(
                progress_callback,
                CLIENT_PROGRESS_WAITING,
                completed_task
                    ? "Progress: 100% - completed; waiting for next task"
                    : "No task assigned; waiting online"
            );
            if (retry_after < 1 || retry_after > 5) retry_after = 2;
            Sleep((DWORD)(retry_after * 1000));
            if (stop_requested) break;
            if (!send_heartbeat(&connection, login, executable_hash, preview, server_body,
                                network_error, sizeof(network_error))) {
                add_log(log_text, log_size, "Heartbeat: %s\r\n", network_error);
                goto cleanup;
            }
            continue;
        }

        /* 任务处理：解析任务参数，检查操作类型和范围，再验证服务器签名。 */
        if (strcmp(action, "TASK") != 0 ||
            !json_get_string(server_body, "task_id", task_id, sizeof(task_id)) ||
            !json_get_string(server_body, "operation", operation, sizeof(operation)) ||
            !json_get_long(server_body, "start", &range_start) ||
            !json_get_long(server_body, "end", &range_end) ||
            !json_get_string(server_body, "signature", signature_hex,
                             sizeof(signature_hex))) {
            add_log(log_text, log_size, "Task receive: invalid task body.\r\n");
            goto cleanup;
        }
        waiting_logged = 0;
        snprintf(progress_text, sizeof(progress_text),
                 "Task %s: %s, range %ld to %ld",
                 task_id, operation, range_start, range_end);
        report_progress(progress_callback, CLIENT_PROGRESS_COMPUTING,
                        progress_text);
        if (!is_operation_supported(operation) || range_start > range_end) {
            add_log(log_text, log_size, "Task validation: unsupported task.\r\n");
            goto cleanup;
        }
        if (simulate_tampered_task) {
            range_end += 1;
            add_log(log_text, log_size,
                    "Test: task range changed before signature check.\r\n");
        }
        snprintf(body, sizeof(body), "%s|%s|%ld|%ld",
                 task_id, operation, range_start, range_end);
        if (!verify_task_signature(body, signature_hex)) {
            add_log(log_text, log_size,
                    "Task signature: failed; task was not executed.\r\n");
            report_progress(progress_callback, CLIENT_PROGRESS_BLOCKED,
                            "Task signature failed; task blocked");
            return_code = 2;
            goto cleanup;
        }
        add_log(log_text, log_size, "Task signature: OK\r\n");
        report_progress(progress_callback, CLIENT_PROGRESS_VERIFIED,
                        "Progress: 50% - task signature verified");

        /* 计算阶段：执行任务并生成结果证明，随后向服务器提交并等待接受确认。 */
        if (!create_result_proof(operation, range_start, range_end,
                                 simulate_wrong_result, &result,
                                 proof_steps, sizeof(proof_steps), merkle_root)) {
            add_log(log_text, log_size, "Merkle proof generation failed.\r\n");
            goto cleanup;
        }
        add_log(log_text, log_size, "Computation: result %ld\r\n", result);
        add_log(log_text, log_size, "Merkle proof: %s\r\n", merkle_root);
        snprintf(progress_text, sizeof(progress_text),
                 "Progress: 75%% - computed result %ld", result);
        report_progress(progress_callback, CLIENT_PROGRESS_COMPUTED,
                        progress_text);

        snprintf(body, sizeof(body),
            "{\"action\":\"RESULT\",\"task_id\":\"%s\","
            "\"node_id\":\"%s\",\"value\":%ld,"
            "\"merkle_root\":\"%s\",\"proof_steps\":\"%s\"}",
            task_id, node_id, result, merkle_root, proof_steps);
        if (!outbox_save(&outbox, body)) {
            add_log(log_text, log_size, "Result could not be saved locally (system code %lu).\r\n", GetLastError());
            return_code = 2;
            goto cleanup;
        }
        if (!send_secure(&connection, body,
                         network_error, sizeof(network_error)) ||
            !receive_secure(&connection, "ACCEPTED", server_body,
                            network_error, sizeof(network_error))) {
            add_log(log_text, log_size, "Result submit: %s\r\n", network_error);
            goto cleanup;
        }
        if (!json_get_string(server_body, "task_id", progress_text, sizeof(progress_text)) ||
            strcmp(progress_text, task_id) != 0 || !outbox_resolve(&outbox, task_id, 1)) {
            add_log(log_text, log_size, "Cannot retire pending result; it remains on disk.\r\n");
            return_code = 2;
            goto cleanup;
        }
        add_log(log_text, log_size, "Result submit: accepted\r\n");
        report_progress(progress_callback, CLIENT_PROGRESS_SUBMITTED,
                        "Progress: 100% - result accepted by server");
        completed_task = 1;
        return_code = 0;
        if (!keep_online) break;
        report_progress(
            progress_callback,
            CLIENT_PROGRESS_WAITING,
            "Progress: 100% - completed; waiting for next task"
        );
    }

    /* 退出阶段：持续在线模式在用户停止时通知服务器注销，然后统一关闭连接并清理敏感数据。 */
    if (keep_online && authenticated && stop_requested) {
        send_logout(&connection, network_error, sizeof(network_error));
        add_log(log_text, log_size, "Connection: disconnected by user\r\n");
    }
    return_code = 0;

cleanup:
    if (preview) preview->offer(NULL, "", "");
    if (return_code == 1 && connection.security_error) return_code = 2;
    if (return_code != 0) {
        report_progress(progress_callback, CLIENT_PROGRESS_ERROR, return_code == 1 ?
                        "Connection interrupted" : "Sign-in or security check needs attention");
    }
    network_close(&connection);
    clear_sensitive(body, sizeof(body));
    clear_sensitive(server_body, sizeof(server_body));
    clear_sensitive(password_hex, sizeof(password_hex));
    clear_sensitive(&outbox, sizeof(outbox));
    if (return_code == 0) {
        report_progress(progress_callback, CLIENT_PROGRESS_DISCONNECTED,
                        "Disconnected by user");
    }
    return return_code;
}

static void add_log(char *log_text, int log_size, const char *format, ...)
{
    int used_length = (int)strlen(log_text);
    int remaining_length = log_size - used_length;
    va_list arguments;
    if (remaining_length <= 1) return;
    va_start(arguments, format);
    vsnprintf(log_text + used_length, remaining_length, format, arguments);
    va_end(arguments);
}
