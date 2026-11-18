#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "client_logic.h"
#include "security.h"

static int read_password(char password[257])
{
    HANDLE input = GetStdHandle(STD_INPUT_HANDLE);
    DWORD mode, length = 0;
    wchar_t wide[259] = {0};
    int success;
    if (!GetConsoleMode(input, &mode)) {
        if (!fgets(password, 257, stdin)) return 0;
        if (strcspn(password, "\r\n") == 256 && !feof(stdin)) {
            int end = getchar();
            if (end != '\r' && end != '\n' && end != EOF) return 0;
        }
        password[strcspn(password, "\r\n")] = '\0';
        return password[0] != '\0';
    }
    fputs("Password: ", stderr);
    if (!SetConsoleMode(input, mode & ~ENABLE_ECHO_INPUT)) return 0;
    success = ReadConsoleW(input, wide, 258, &length, NULL);
    SetConsoleMode(input, mode);
    fputc('\n', stderr);
    while (length > 0 && (wide[length - 1] == L'\r' || wide[length - 1] == L'\n')) wide[--length] = 0;
    success = success && length > 0 &&
        WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide, -1, password, 257, NULL, NULL) > 0;
    clear_sensitive(wide, sizeof(wide));
    return success;
}

static void progress(int code, const char *detail)
{
    if (code != CLIENT_PROGRESS_HEARTBEAT && code != CLIENT_PROGRESS_WAITING) {
        printf("%s\n", detail);
        fflush(stdout);
    }
}

int main(int argc, char *argv[])
{
    ClientLogin login = {0};
    char log_text[CLIENT_LOG_SIZE], *end = NULL;
    const char *operation = argc > 4 ? argv[4] : "normal";
    const char *host = argc > 2 ? argv[2] : getenv("PROJECT13_HOST");
    const char *port = argc > 3 ? argv[3] : getenv("PROJECT13_PORT");
    long numeric_port = port == NULL ? 8888 : strtol(port, &end, 10);
    int stay = argc > 5 && strcmp(argv[5], "stay") == 0;
    int result = 2;
    DWORD delay = 1000;
    if (host == NULL) host = "127.0.0.1";
    if (argc < 2 || strlen(argv[1]) >= sizeof(login.username) || strlen(host) >= sizeof(login.host) ||
        (end != NULL && (*end != '\0' || end == port)) || numeric_port < 1 || numeric_port >= 65535) {
        fputs("Usage: client USER [HOST] [PORT] [normal|wrong|tamper] [stay]\n", stderr);
        return result;
    }
    snprintf(login.username, sizeof(login.username), "%s", argv[1]);
    snprintf(login.host, sizeof(login.host), "%s", host);
    login.port = (int)numeric_port;
    if (read_password(login.password)) {
        do {
            result = run_client(&login, operation, stay, progress, NULL, log_text, sizeof(log_text));
            fputs(log_text, stdout);
            fflush(stdout);
            if (!stay || result != 1) break;
            Sleep(delay);
            if (delay < 16000) delay *= 2;
        } while (1);
    }
    clear_sensitive(&login, sizeof(login));
    return result;
}
