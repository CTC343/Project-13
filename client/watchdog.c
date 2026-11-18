#include <windows.h>
#include <stdio.h>
#include <wchar.h>

#include "watchdog.h"

static void record_event(const wchar_t *event, DWORD pid, DWORD exit_code)
{
    wchar_t path[MAX_PATH];
    DWORD size = GetEnvironmentVariableW(L"PROJECT13_WATCHDOG_LOG_DIR", path, MAX_PATH);
    SYSTEMTIME now;
    FILE *log;
    if (size == 0) {
        size = GetEnvironmentVariableW(L"LOCALAPPDATA", path, MAX_PATH);
        if (size == 0 || size >= MAX_PATH - 26) return;
        swprintf_s(path + size, MAX_PATH - size, L"\\Project13");
    } else if (size >= MAX_PATH - 14) {
        return;
    }
    CreateDirectoryW(path, NULL);
    wcscat_s(path, MAX_PATH, L"\\watchdog.log");
    if (_wfopen_s(&log, path, L"a, ccs=UTF-8") != 0) return;
    GetLocalTime(&now);
    fwprintf(log, L"%04d-%02d-%02d %02d:%02d:%02d %ls pid=%lu code=%lu\n",
             now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute, now.wSecond,
             event, pid, exit_code);
    fclose(log);
}

int run_watchdog(int show_command)
{
    wchar_t path[MAX_PATH], command[MAX_PATH + 24];
    DWORD size = GetModuleFileNameW(NULL, path, MAX_PATH);
    DWORD delay = 1000;
    if (size == 0 || size >= MAX_PATH) return 1;
    for (;;) {
        STARTUPINFOW startup = {0};
        PROCESS_INFORMATION process = {0};
        DWORD exit_code = 1;
        ULONGLONG started = GetTickCount64();
        startup.cb = sizeof(startup);
        startup.dwFlags = STARTF_USESHOWWINDOW;
        startup.wShowWindow = (WORD)show_command;
        swprintf_s(command, _countof(command), L"\"%ls\" --window", path);
        if (!CreateProcessW(path, command, NULL, NULL, FALSE, 0, NULL, NULL, &startup, &process)) {
            record_event(L"launch_failed", 0, GetLastError());
            return 1;
        }
        CloseHandle(process.hThread);
        record_event(L"client_started", process.dwProcessId, 0);
        if (WaitForSingleObject(process.hProcess, INFINITE) == WAIT_OBJECT_0) {
            GetExitCodeProcess(process.hProcess, &exit_code);
        }
        CloseHandle(process.hProcess);
        if (exit_code == 0) {
            record_event(L"manual_stop", process.dwProcessId, 0);
            return 0;
        }
        record_event(L"client_exited_restart_pending", process.dwProcessId, exit_code);
        if (GetTickCount64() - started > 60000) delay = 1000;
        Sleep(delay);
        if (delay < 16000) delay *= 2;
    }
}
