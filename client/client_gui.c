/* 原生 Win32 客户端窗口：只负责收集输入和显示 run_client() 的结果。 */
#include <windows.h>
#include <stdio.h>

#include "client_logic.h"
#include "preview.h"
#include "security.h"
#include "watchdog.h"
#include <string.h>
#include <stdlib.h>

#define ID_MODE_COMBO 102
#define ID_RUN_BUTTON 103
#define ID_LOG_EDIT 104
#define ID_STATUS_TEXT 105
#define ID_DISCONNECT_BUTTON 106
#define WM_CLIENT_DONE (WM_APP + 1)
#define WM_CLIENT_PROGRESS (WM_APP + 2)

static HWND server_edit, port_edit, username_edit, password_edit;
static HANDLE stop_event;
static HWND mode_combo;
static HWND run_button;
static HWND log_edit;
static HWND status_text;
static HWND connection_text;
static HWND task_text;
static HWND progress_text;
static HWND disconnect_button;
static HFONT ui_font;
static HWND main_window;
static ClientLogin login;
static char worker_mode[16];
static char worker_log[CLIENT_LOG_SIZE];
static char displayed_log[CLIENT_LOG_SIZE];
static int worker_exit_code;


static void create_controls(HWND window);
static void run_selected_mode(void);
static void use_ui_font(HWND control);
static void update_log_text(const char *text);
static LRESULT CALLBACK window_proc(HWND window, UINT message,
                                    WPARAM w_param, LPARAM l_param);
static DWORD WINAPI client_worker(LPVOID parameter);
static void client_progress(int progress_code, const char *detail);

int WINAPI WinMain(HINSTANCE instance, HINSTANCE previous_instance,
                   LPSTR command_line, int show_command)
{
    const char class_name[] = "Project13ClientWindow";
    WNDCLASSA window_class = {0};
    HWND window;
    MSG message;

    (void)previous_instance;
    if (strcmp(command_line, "--window") != 0) return run_watchdog(show_command);
    stop_event = CreateEventW(NULL, TRUE, FALSE, NULL);
    if (!stop_event) return 1;

    window_class.lpfnWndProc = window_proc;
    window_class.hInstance = instance;
    window_class.lpszClassName = class_name;
    window_class.hCursor = LoadCursor(NULL, IDC_ARROW);
    window_class.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);

    if (!RegisterClassA(&window_class)) {
        MessageBoxA(NULL, "Window registration failed.",
                    "Project13 Client", MB_ICONERROR);
        return 1;
    }

    window = CreateWindowExA(
        0,
        class_name,
        "Project13 Client",
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT,
        CW_USEDEFAULT,
        760,
        680,
        NULL,
        NULL,
        instance,
        NULL
    );

    if (window == NULL) {
        MessageBoxA(NULL, "Window creation failed.",
                    "Project13 Client", MB_ICONERROR);
        return 1;
    }
    main_window = window;

    ShowWindow(window, show_command);
    UpdateWindow(window);

    /* Win32 消息循环负责响应界面输入和后台线程发来的进度通知。 */
    while (GetMessageA(&message, NULL, 0, 0) > 0) {
        TranslateMessage(&message);
        DispatchMessageA(&message);
    }

    return (int)message.wParam;
}

static LRESULT CALLBACK window_proc(HWND window, UINT message,
                                    WPARAM w_param, LPARAM l_param)
{
    (void)l_param;

    switch (message) {
    case WM_CREATE:
        create_controls(window);
        return 0;

    case WM_COMMAND:
        if (LOWORD(w_param) == ID_RUN_BUTTON &&
            HIWORD(w_param) == BN_CLICKED) {
            run_selected_mode();
        } else if (LOWORD(w_param) == ID_DISCONNECT_BUTTON &&
                   HIWORD(w_param) == BN_CLICKED) {
            SetEvent(stop_event);
            request_client_stop();
            EnableWindow(disconnect_button, FALSE);
            SetWindowTextA(status_text, "Status: disconnecting...");
        } else {
            preview_handle_command(w_param);
        }
        return 0;

    case WM_PREVIEW_STATUS:
        preview_update_status();
        return 0;

    case WM_CLIENT_PROGRESS:
        /* 后台工作线程通过自定义消息报告进度，由 UI 线程更新控件。 */
        update_log_text(worker_log);
        switch ((int)w_param) {
        case CLIENT_PROGRESS_CONNECTING:
            SetWindowTextA(status_text, "Status: connecting...");
            SetWindowTextA(connection_text, "Authenticating with the server");
            SetWindowTextA(task_text, "Task: not assigned");
            SetWindowTextA(progress_text, (const char *)l_param);
            break;
        case CLIENT_PROGRESS_AUTHENTICATED:
            SetWindowTextA(status_text, "Status: authenticated");
            {
                wchar_t details[256];
                if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, (const char *)l_param, -1,
                                        details, _countof(details)) > 0) {
                    SetWindowTextW(connection_text, details);
                }
            }
            break;
        case CLIENT_PROGRESS_HEARTBEAT:
            SetWindowTextA(status_text, "Status: online - heartbeat OK");
            SetWindowTextA(progress_text, (const char *)l_param);
            break;
        case CLIENT_PROGRESS_COMPUTING:
            SetWindowTextA(status_text, "Status: online - computing task");
            SetWindowTextA(task_text, (const char *)l_param);
            SetWindowTextA(progress_text, "Progress: 25% - task received");
            break;
        case CLIENT_PROGRESS_WAITING:
            SetWindowTextA(status_text,
                           "Status: online - waiting for task");
            SetWindowTextA(progress_text, (const char *)l_param);
            break;
        case CLIENT_PROGRESS_BLOCKED:
            SetWindowTextA(status_text, "Status: security check blocked task");
            SetWindowTextA(progress_text, (const char *)l_param);
            break;
        case CLIENT_PROGRESS_ERROR:
            SetWindowTextA(status_text, "Status: connection failed");
            SetWindowTextA(progress_text, (const char *)l_param);
            break;
        case CLIENT_PROGRESS_RECONNECTING:
            SetWindowTextA(connection_text, "Offline");
            SetWindowTextA(status_text,
                           "Status: connection lost - retrying...");
            SetWindowTextA(progress_text, (const char *)l_param);
            break;
        case CLIENT_PROGRESS_VERIFIED:
        case CLIENT_PROGRESS_COMPUTED:
        case CLIENT_PROGRESS_SUBMITTED:
            SetWindowTextA(progress_text, (const char *)l_param);
            break;
        }
        return 0;

    case WM_CLIENT_DONE:
        update_log_text(worker_log);
        SetWindowTextA(connection_text, "Signed out");
        if (worker_exit_code == 0) {
            SetWindowTextA(status_text, "Status: disconnected");
        } else if (worker_exit_code == 2) {
            SetWindowTextA(status_text, "Status: sign-in or security check failed");
        } else {
            SetWindowTextA(status_text, "Status: failed - check the log");
        }
        EnableWindow(run_button, TRUE);
        EnableWindow(disconnect_button, FALSE);
        EnableWindow(server_edit, TRUE);
        EnableWindow(port_edit, TRUE);
        EnableWindow(username_edit, TRUE);
        EnableWindow(password_edit, TRUE);
        EnableWindow(mode_combo, TRUE);
        return 0;

    case WM_DESTROY:
        preview_shutdown();
        SetEvent(stop_event);
        request_client_stop();
        if (ui_font != NULL) {
            DeleteObject(ui_font);
        }
        PostQuitMessage(0);
        return 0;
    }

    return DefWindowProcA(window, message, w_param, l_param);
}

static HWND login_field(HWND window, const char *label, const char *initial,
                        int x, int y, int width, int maximum, DWORD flags)
{
    HWND text = CreateWindowExA(0, "STATIC", label, WS_CHILD | WS_VISIBLE,
                                x, y + 4, 90, 27, window, NULL, NULL, NULL);
    HWND input = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"",
                                 WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_AUTOHSCROLL | flags,
                                 x + 90, y, width, 30, window, NULL, NULL, NULL);
    if (initial != NULL) SetWindowTextA(input, initial);
    SendMessageW(input, EM_SETLIMITTEXT, (WPARAM)maximum, 0);
    use_ui_font(text);
    use_ui_font(input);
    return input;
}

static void create_controls(HWND window)
{
    HWND control;
    const char *host = getenv("PROJECT13_HOST");
    const char *port = getenv("PROJECT13_PORT");

    ui_font = CreateFontA(
        -18, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH, "Segoe UI"
    );

    control = CreateWindowExA(
        0, "STATIC", "Project13 Compute Client",
        WS_CHILD | WS_VISIBLE,
        24, 20, 360, 30,
        window, NULL, NULL, NULL
    );
    use_ui_font(control);


    control = CreateWindowExA(
        0, "STATIC", "Run mode",
        WS_CHILD | WS_VISIBLE,
        380, 158, 100, 26,
        window, NULL, NULL, NULL
    );
    use_ui_font(control);

    mode_combo = CreateWindowExA(
        0, "COMBOBOX", "",
        WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST,
        480, 154, 230, 150,
        window, (HMENU)ID_MODE_COMBO, NULL, NULL
    );
    SendMessageA(mode_combo, CB_ADDSTRING, 0, (LPARAM)"Normal result");
    SendMessageA(mode_combo, CB_ADDSTRING, 0, (LPARAM)"Wrong result test");
    SendMessageA(mode_combo, CB_ADDSTRING, 0, (LPARAM)"Tampered task test");
    SendMessageA(mode_combo, CB_SETCURSEL, 0, 0);
    use_ui_font(mode_combo);
    if (getenv("PROJECT13_DEMO_MODE") == NULL) {
        ShowWindow(control, SW_HIDE);
        ShowWindow(mode_combo, SW_HIDE);
    }

    server_edit = login_field(window, "Server", host ? host : "127.0.0.1", 24, 62, 240, 253, 0);
    port_edit = login_field(window, "Port", port ? port : "8888", 380, 62, 80, 5, ES_NUMBER);
    username_edit = login_field(window, "Account", NULL, 24, 108, 240, 63, 0);
    password_edit = login_field(window, "Password", NULL, 380, 108, 240, 256, ES_PASSWORD);

    connection_text = CreateWindowExW(0, L"STATIC", L"Signed out",
                                      WS_CHILD | WS_VISIBLE | SS_PATHELLIPSIS,
                                      24, 158, 340, 26, window, NULL, NULL, NULL);
    use_ui_font(connection_text);

    run_button = CreateWindowExA(
        0, "BUTTON", "Log in and Connect",
        WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
        24, 208, 200, 38,
        window, (HMENU)ID_RUN_BUTTON, NULL, NULL
    );
    use_ui_font(run_button);

    disconnect_button = CreateWindowExA(
        0, "BUTTON", "Disconnect",
        WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON | WS_DISABLED,
        236, 208, 140, 38,
        window, (HMENU)ID_DISCONNECT_BUTTON, NULL, NULL
    );
    use_ui_font(disconnect_button);

    status_text = CreateWindowExA(
        0, "STATIC", "Status: waiting",
        WS_CHILD | WS_VISIBLE,
        392, 216, 318, 26,
        window, (HMENU)ID_STATUS_TEXT, NULL, NULL
    );
    use_ui_font(status_text);

    task_text = CreateWindowExA(
        0, "STATIC", "Task: not assigned",
        WS_CHILD | WS_VISIBLE,
        24, 265, 686, 26,
        window, NULL, NULL, NULL
    );
    use_ui_font(task_text);

    progress_text = CreateWindowExA(
        0, "STATIC", "Progress: waiting for connection",
        WS_CHILD | WS_VISIBLE,
        24, 295, 686, 26,
        window, NULL, NULL, NULL
    );
    use_ui_font(progress_text);

    control = CreateWindowExA(
        0, "STATIC", "Execution log",
        WS_CHILD | WS_VISIBLE,
        24, 334, 180, 26,
        window, NULL, NULL, NULL
    );
    use_ui_font(control);

    log_edit = CreateWindowExA(
        WS_EX_CLIENTEDGE, "EDIT", "",
        WS_CHILD | WS_VISIBLE | WS_VSCROLL |
        ES_LEFT | ES_MULTILINE | ES_AUTOVSCROLL | ES_READONLY,
        24, 364, 686, 245,
        window, (HMENU)ID_LOG_EDIT, NULL, NULL
    );
    use_ui_font(log_edit);
    preview_attach(window, ui_font);
}

static void run_selected_mode(void)
{
    const char *modes[] = {"normal", "wrong", "tamper"};
    int selected_mode;
    HANDLE worker;

    wchar_t password[257];
    char port_text[8], *end;
    long port;
    int password_size;

    GetWindowTextA(server_edit, login.host, sizeof(login.host));
    GetWindowTextA(username_edit, login.username, sizeof(login.username));
    GetWindowTextA(port_edit, port_text, sizeof(port_text));
    port = strtol(port_text, &end, 10);
    GetWindowTextW(password_edit, password, _countof(password));
    password_size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, password, -1,
                                        login.password, sizeof(login.password), NULL, NULL);
    clear_sensitive(password, sizeof(password));
    SetWindowTextW(password_edit, L"");
    if (password_size <= 1 || !login.username[0] || !login.host[0] ||
        end == port_text || *end || port < 1 || port >= 65535) {
        clear_sensitive(&login, sizeof(login));
        SetWindowTextA(status_text, "Enter server, port, account and password.");
        return;
    }
    login.port = (int)port;
    selected_mode = (int)SendMessageA(mode_combo, CB_GETCURSEL, 0, 0);
    if (selected_mode < 0 || selected_mode > 2) {
        selected_mode = 0;
    }

    EnableWindow(run_button, FALSE);
    EnableWindow(disconnect_button, TRUE);
    EnableWindow(mode_combo, FALSE);
    ResetEvent(stop_event);
    reset_client_stop();
    EnableWindow(server_edit, FALSE);
    EnableWindow(port_edit, FALSE);
    EnableWindow(username_edit, FALSE);
    EnableWindow(password_edit, FALSE);
    snprintf(worker_mode, sizeof(worker_mode), "%s", modes[selected_mode]);
    SetWindowTextA(status_text, "Status: connecting and authenticating...");
    update_log_text("");
    UpdateWindow(GetParent(run_button));

    /* 网络流程放到工作线程运行，避免连接和等待任务阻塞窗口消息循环。 */
    worker = CreateThread(NULL, 0, client_worker, NULL, 0, NULL);
    if (worker == NULL) {
        clear_sensitive(&login, sizeof(login));
        SetWindowTextA(status_text, "Status: cannot start worker thread");
        EnableWindow(run_button, TRUE);
        EnableWindow(disconnect_button, FALSE);
        EnableWindow(server_edit, TRUE);
        EnableWindow(port_edit, TRUE);
        EnableWindow(username_edit, TRUE);
        EnableWindow(password_edit, TRUE);
        EnableWindow(mode_combo, TRUE);
        return;
    }
    CloseHandle(worker);
}

static DWORD WINAPI client_worker(LPVOID parameter)
{
    DWORD delay = 1000;
    char retry_message[100];
    (void)parameter;
    do {
        ULONGLONG started = GetTickCount64();
        worker_exit_code = run_client(&login, worker_mode, 1, client_progress, &window_preview_hooks,
                                      worker_log, sizeof(worker_log));
        if (WaitForSingleObject(stop_event, 0) == WAIT_OBJECT_0 || worker_exit_code != 1) break;
        if (GetTickCount64() - started > 30000) delay = 1000;
        snprintf(retry_message, sizeof(retry_message),
                 "Offline. Reconnecting in %lu seconds.", delay / 1000);
        client_progress(CLIENT_PROGRESS_RECONNECTING, retry_message);
        if (WaitForSingleObject(stop_event, delay) == WAIT_OBJECT_0) break;
        if (delay < 16000) delay *= 2;
    } while (1);
    if (WaitForSingleObject(stop_event, 0) == WAIT_OBJECT_0) worker_exit_code = 0;
    clear_sensitive(&login, sizeof(login));
    PostMessageA(main_window, WM_CLIENT_DONE, 0, 0);
    return 0;
}

static void client_progress(int progress_code, const char *detail)
{
    /* SendMessage 同步等待 UI 线程处理，detail 指针在调用期间保持有效。 */
    SendMessageA(main_window, WM_CLIENT_PROGRESS,
                 (WPARAM)progress_code, (LPARAM)detail);
}

static void update_log_text(const char *text)
{
    SCROLLINFO scroll = {sizeof(scroll), SIF_RANGE | SIF_PAGE | SIF_POS};
    DWORD selection_start = 0, selection_end = 0;
    LRESULT first_visible;
    BOOL follow_tail;

    /* Heartbeats can report progress without changing the log. */
    if (strcmp(displayed_log, text) == 0) return;
    first_visible = SendMessageA(log_edit, EM_GETFIRSTVISIBLELINE, 0, 0);
    SendMessageA(log_edit, EM_GETSEL, (WPARAM)&selection_start, (LPARAM)&selection_end);
    follow_tail = selection_start == selection_end &&
        (!GetScrollInfo(log_edit, SB_VERT, &scroll) ||
         scroll.nPos >= scroll.nMax - (int)scroll.nPage + 1);

    SendMessageA(log_edit, WM_SETREDRAW, FALSE, 0);
    if (SetWindowTextA(log_edit, text)) {
        DWORD length = (DWORD)GetWindowTextLengthA(log_edit);
        LRESULT visible_after_update;
        memcpy(displayed_log, text, strlen(text) + 1);
        if (selection_start > length) selection_start = length;
        if (selection_end > length) selection_end = length;
        SendMessageA(log_edit, EM_SETSEL, selection_start, selection_end);
        if (follow_tail) {
            SendMessageA(log_edit, EM_SCROLL, SB_BOTTOM, 0);
        } else {
            visible_after_update = SendMessageA(log_edit, EM_GETFIRSTVISIBLELINE, 0, 0);
            SendMessageA(log_edit, EM_LINESCROLL, 0, first_visible - visible_after_update);
        }
    }
    SendMessageA(log_edit, WM_SETREDRAW, TRUE, 0);
    RedrawWindow(log_edit, NULL, NULL, RDW_INVALIDATE | RDW_ERASE | RDW_FRAME);
}

static void use_ui_font(HWND control)
{
    SendMessageA(control, WM_SETFONT, (WPARAM)ui_font, TRUE);
}
