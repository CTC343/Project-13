/* 控制台入口：读取参数，调用公共客户端流程，打印运行日志。 */
#include <stdio.h>
#include <string.h>

#include "client_logic.h"

int main(int argc, char *argv[])
{
    const char *node_id = "node-1";
    const char *mode = "normal";
    int keep_online = 0;
    char log_text[CLIENT_LOG_SIZE];
    int exit_code;

    if (argc >= 2) {
        node_id = argv[1];
    }
    if (argc >= 3) {
        mode = argv[2];
    }
    if (argc >= 4 && strcmp(argv[3], "stay") == 0) {
        keep_online = 1;
    }

    exit_code = run_client(
        node_id, mode, keep_online, NULL, log_text, CLIENT_LOG_SIZE
    );
    printf("%s", log_text);
    return exit_code;
}
