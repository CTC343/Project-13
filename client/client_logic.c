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
#include "merkle.h"
#include "network.h"
#include "operations.h"
#include "protocol.h"
#include "secure_channel.h"
#include "security.h"
#include "signature.h"

#define SERVER_IP "127.0.0.1"
#define SERVER_PORT 8888
#define TEXT_SIZE 8192

static volatile int stop_requested = 0;

static void add_log(char *log_text, int log_size, const char *format, ...);

void request_client_stop(void)
{
    stop_requested = 1;
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

static int receive_secure_any(SOCKET socket_value, SecureSession *session,
                              char *plain, char *action, int action_size,
                              char *error_text, int error_size)
{
    char type[32];
    char envelope[PROTOCOL_BODY_SIZE];
    int status;
    if (!protocol_receive_frame(socket_value, type, sizeof(type), &status,
                                envelope, sizeof(envelope),
                                error_text, error_size)) return 0;
    if (strcmp(type, "SECURE") != 0 ||
        !open_server_message(session, envelope, plain, TEXT_SIZE) ||
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

static int receive_secure(SOCKET socket_value, SecureSession *session,
                          const char *expected_action, char *plain,
                          char *error_text, int error_size)
{
    char action[64];
    if (!receive_secure_any(socket_value, session, plain, action,
                            sizeof(action), error_text, error_size)) return 0;
    if (strcmp(action, expected_action) != 0) {
        snprintf(error_text, error_size, "Expected %s, received %s.",
                 expected_action, action);
        return 0;
    }
    return 1;
}

static int send_secure(SOCKET socket_value, SecureSession *session,
                       const char *plain, char *error_text, int error_size)
{
    char envelope[PROTOCOL_BODY_SIZE];
    if (!protect_client_message(session, plain, envelope, sizeof(envelope))) {
        snprintf(error_text, error_size, "Cannot protect secure message.");
        return 0;
    }
    return protocol_send_frame(socket_value, "SECURE", 0, envelope,
                               error_text, error_size);
}

static int send_heartbeat(SOCKET socket_value, SecureSession *session,
                          char *server_body,
                          char *error_text, int error_size)
{
    char body[128];
    snprintf(body, sizeof(body),
             "{\"action\":\"HEARTBEAT\",\"sent_at\":%ld}",
             (long)time(NULL));
    return send_secure(socket_value, session, body, error_text, error_size) &&
           receive_secure(socket_value, session, "HEARTBEAT_ACK", server_body,
                          error_text, error_size);
}

static int send_logout(SOCKET socket_value, SecureSession *session,
                       char *error_text, int error_size)
{
    const char *body = "{\"action\":\"LOGOUT\"}";
    return send_secure(socket_value, session, body, error_text, error_size);
}

int run_client(const char *node_id, const char *mode, int keep_online,
               ClientProgressCallback progress_callback,
               char *log_text, int log_size)
{
    int simulate_wrong_result = mode != NULL && strcmp(mode, "wrong") == 0;
    int simulate_tampered_task = mode != NULL && strcmp(mode, "tamper") == 0;
    int waiting_logged = 0;
    int completed_task = 0;
    NodeCredential credential;
    SecureSession session;
    unsigned char nonce_bytes[16];
    char client_nonce[33];
    char executable_hash[65];
    char auth_text[512];
    char auth_tag[65];
    char body[TEXT_SIZE];
    char server_body[TEXT_SIZE];
    char message_type[32];
    char server_nonce[33];
    char server_proof[65];
    char expected_proof[65];
    char proof_text[256];
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
    long timestamp;
    long retry_after;
    int status;
    int return_code = 1;
    SOCKET server_socket = INVALID_SOCKET;

    stop_requested = 0;
    memset(&credential, 0, sizeof(credential));
    memset(&session, 0, sizeof(session));
    if (log_text == NULL || log_size <= 0) return 1;
    log_text[0] = '\0';

    if (!valid_node_id(node_id)) {
        add_log(log_text, log_size,
                "Node ID may contain only letters, numbers, '-' and '_'.\r\n");
        goto cleanup;
    }
    if (!load_node_credential(node_id, &credential,
                              network_error, sizeof(network_error))) {
        add_log(log_text, log_size, "License: failed - %s\r\n", network_error);
        goto cleanup;
    }
    add_log(log_text, log_size, "License: loaded for %s, expires %s\r\n",
            credential.node_id, credential.expires);
    if (!current_executable_hash(executable_hash,
                                 network_error, sizeof(network_error))) {
        add_log(log_text, log_size, "%s\r\n", network_error);
        goto cleanup;
    }
    add_log(log_text, log_size, "Executable integrity: hash ready\r\n");

    if (!network_start(network_error, sizeof(network_error))) {
        add_log(log_text, log_size, "%s\r\n", network_error);
        goto cleanup;
    }
    report_progress(progress_callback, CLIENT_PROGRESS_CONNECTING,
                    "Connecting and authenticating");
    add_log(log_text, log_size, "Connection: trying server (up to 3 attempts)\r\n");
    server_socket = network_connect_retry(
        SERVER_IP, SERVER_PORT, 3, network_error, sizeof(network_error)
    );
    if (server_socket == INVALID_SOCKET) {
        add_log(log_text, log_size, "%s\r\n", network_error);
        goto cleanup;
    }
    add_log(log_text, log_size, "Connection: connected\r\n");

    if (!secure_random(nonce_bytes, sizeof(nonce_bytes))) {
        add_log(log_text, log_size, "Secure random generation failed.\r\n");
        goto cleanup;
    }
    bytes_to_hex(nonce_bytes, sizeof(nonce_bytes), client_nonce);
    timestamp = (long)time(NULL);
    snprintf(auth_text, sizeof(auth_text), "%s|%s|%ld|%s|%s|%d",
             node_id, credential.license_id, timestamp,
             client_nonce, executable_hash, keep_online ? 1 : 0);
    if (!hmac_sha256_hex(credential.auth_key, 32, auth_text, auth_tag)) {
        add_log(log_text, log_size, "Identity proof generation failed.\r\n");
        goto cleanup;
    }
    snprintf(body, sizeof(body),
        "{\"node_id\":\"%s\",\"license_id\":\"%s\","
        "\"timestamp\":%ld,\"client_nonce\":\"%s\","
        "\"exe_hash\":\"%s\",\"auth_tag\":\"%s\","
        "\"persistent\":%d}",
        node_id, credential.license_id, timestamp, client_nonce,
        executable_hash, auth_tag, keep_online ? 1 : 0);
    if (!protocol_send_frame(server_socket, "AUTH", 0, body,
                             network_error, sizeof(network_error)) ||
        !protocol_receive_frame(server_socket, message_type,
                                sizeof(message_type), &status,
                                server_body, sizeof(server_body),
                                network_error, sizeof(network_error))) {
        add_log(log_text, log_size, "Login: %s\r\n", network_error);
        goto cleanup;
    }
    if (strcmp(message_type, "AUTH_OK") != 0 || status != 200 ||
        !json_get_string(server_body, "session_id", session.session_id,
                         sizeof(session.session_id)) ||
        !json_get_string(server_body, "server_nonce", server_nonce,
                         sizeof(server_nonce)) ||
        !json_get_string(server_body, "server_proof", server_proof,
                         sizeof(server_proof))) {
        char detail[256] = "authentication rejected";
        json_get_string(server_body, "detail", detail, sizeof(detail));
        add_log(log_text, log_size, "Login: rejected - %s\r\n", detail);
        goto cleanup;
    }
    snprintf(proof_text, sizeof(proof_text), "SERVER|%s|%s|%s",
             session.session_id, client_nonce, server_nonce);
    if (!hmac_sha256_hex(credential.auth_key, 32, proof_text, expected_proof) ||
        !constant_time_equal(server_proof, expected_proof) ||
        !derive_session_key(credential.auth_key, client_nonce, server_nonce,
                            session.session_id, session.key)) {
        add_log(log_text, log_size, "Server identity verification failed.\r\n");
        return_code = 2;
        goto cleanup;
    }
    add_log(log_text, log_size,
            "Login: authenticated; license and executable accepted\r\n");
    add_log(log_text, log_size, "Encrypted session: established\r\n");
    report_progress(progress_callback, CLIENT_PROGRESS_AUTHENTICATED,
                    "Authentication passed");

    if (!send_heartbeat(server_socket, &session, server_body,
                        network_error, sizeof(network_error))) {
        add_log(log_text, log_size, "Heartbeat: %s\r\n", network_error);
        goto cleanup;
    }
    add_log(log_text, log_size, "Heartbeat: acknowledged\r\n");
    report_progress(progress_callback, CLIENT_PROGRESS_HEARTBEAT,
                    "Online; waiting for task");

    while (!stop_requested) {
        if (keep_online) return_code = 1;
        if (!receive_secure_any(server_socket, &session, server_body,
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
            if (!send_heartbeat(server_socket, &session, server_body,
                                network_error, sizeof(network_error))) {
                add_log(log_text, log_size, "Heartbeat: %s\r\n", network_error);
                goto cleanup;
            }
            continue;
        }

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
        if (!send_secure(server_socket, &session, body,
                         network_error, sizeof(network_error)) ||
            !receive_secure(server_socket, &session, "ACCEPTED", server_body,
                            network_error, sizeof(network_error))) {
            add_log(log_text, log_size, "Result submit: %s\r\n", network_error);
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

    if (keep_online && server_socket != INVALID_SOCKET) {
        send_logout(server_socket, &session, network_error, sizeof(network_error));
        add_log(log_text, log_size, "Connection: disconnected by user\r\n");
    }
    return_code = 0;

cleanup:
    if (return_code != 0) {
        report_progress(progress_callback, CLIENT_PROGRESS_ERROR,
                        "Connection ended; retrying if enabled");
    }
    network_close(server_socket);
    clear_sensitive(auth_text, sizeof(auth_text));
    clear_sensitive(auth_tag, sizeof(auth_tag));
    clear_sensitive(expected_proof, sizeof(expected_proof));
    clear_node_credential(&credential);
    clear_secure_session(&session);
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
