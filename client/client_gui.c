/* 原生 Win32 客户端窗口：只负责收集输入和显示 run_client() 的结果。 */
#include <windows.h>
#include <stdio.h>

#include "client_logic.h"

#define ID_NODE_EDIT 101
#define ID_MODE_COMBO 102
#define ID_RUN_BUTTON 103
#define ID_LOG_EDIT 104
#define ID_STATUS_TEXT 105
#define ID_DISCONNECT_BUTTON 106
#define WM_CLIENT_DONE (WM_APP + 1)
#define WM_CLIENT_PROGRESS (WM_APP + 2)

static HWND node_edit;
static HWND mode_combo;
static HWND run_button;
static HWND log_edit;
static HWND status_text;
static HWND disconnect_button;
static HFONT ui_font;
static HWND main_window;
static char worker_node[64];
static char worker_mode[16];
static char worker_log[CLIENT_LOG_SIZE];
static int worker_exit_code;
static volatile int manual_stop_requested;

static void create_controls(HWND window);
static void run_selected_mode(void);
static void use_ui_font(HWND control);
static LRESULT CALLBACK window_proc(HWND window, UINT message,
                                    WPARAM w_param, LPARAM l_param);
static DWORD WINAPI client_worker(LPVOID parameter);
static void client_progress(int progress_code);

int WINAPI WinMain(HINSTANCE instance, HINSTANCE previous_instance,
                   LPSTR command_line, int show_command)
{
    const char class_name[] = "Project13ClientWindow";
    WNDCLASSA window_class = {0};
    HWND window;
    MSG message;

    (void)previous_instance;
    (void)command_line;

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
        580,
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
            manual_stop_requested = 1;
            request_client_stop();
            EnableWindow(disconnect_button, FALSE);
            SetWindowTextA(status_text, "Status: disconnecting...");
        }
        return 0;

    case WM_CLIENT_PROGRESS:
        SetWindowTextA(log_edit, worker_log);
        switch ((int)w_param) {
        case CLIENT_PROGRESS_CONNECTING:
            SetWindowTextA(status_text, "Status: connecting...");
            break;
        case CLIENT_PROGRESS_AUTHENTICATED:
            SetWindowTextA(status_text, "Status: authenticated");
            break;
        case CLIENT_PROGRESS_HEARTBEAT:
            SetWindowTextA(status_text, "Status: online - heartbeat OK");
            break;
        case CLIENT_PROGRESS_COMPUTING:
            SetWindowTextA(status_text, "Status: online - computing task");
            break;
        case CLIENT_PROGRESS_WAITING:
            SetWindowTextA(status_text,
                           "Status: online - waiting for task");
            break;
        case CLIENT_PROGRESS_BLOCKED:
            SetWindowTextA(status_text, "Status: security check blocked task");
            break;
        case CLIENT_PROGRESS_ERROR:
            SetWindowTextA(status_text, "Status: connection failed");
            break;
        case CLIENT_PROGRESS_RECONNECTING:
            SetWindowTextA(status_text,
                           "Status: connection lost - retrying...");
            break;
        }
        return 0;

    case WM_CLIENT_DONE:
        SetWindowTextA(log_edit, worker_log);
        if (worker_exit_code == 0) {
            SetWindowTextA(status_text, "Status: disconnected");
        } else if (worker_exit_code == 2) {
            SetWindowTextA(status_text, "Status: security check blocked the task");
        } else {
            SetWindowTextA(status_text, "Status: failed - check the log");
        }
        EnableWindow(run_button, TRUE);
        EnableWindow(disconnect_button, FALSE);
        EnableWindow(node_edit, TRUE);
        EnableWindow(mode_combo, TRUE);
        return 0;

    case WM_DESTROY:
        manual_stop_requested = 1;
        request_client_stop();
        if (ui_font != NULL) {
            DeleteObject(ui_font);
        }
        PostQuitMessage(0);
        return 0;
    }

    return DefWindowProcA(window, message, w_param, l_param);
}

static void create_controls(HWND window)
{
    HWND control;

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
        0, "STATIC", "Node ID",
        WS_CHILD | WS_VISIBLE,
        24, 70, 100, 26,
        window, NULL, NULL, NULL
    );
    use_ui_font(control);

    node_edit = CreateWindowExA(
        WS_EX_CLIENTEDGE, "EDIT", "node-ui",
        WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL,
        130, 66, 220, 30,
        window, (HMENU)ID_NODE_EDIT, NULL, NULL
    );
    use_ui_font(node_edit);

    control = CreateWindowExA(
        0, "STATIC", "Run mode",
        WS_CHILD | WS_VISIBLE,
        380, 70, 100, 26,
        window, NULL, NULL, NULL
    );
    use_ui_font(control);

    mode_combo = CreateWindowExA(
        0, "COMBOBOX", "",
        WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST,
        480, 66, 230, 150,
        window, (HMENU)ID_MODE_COMBO, NULL, NULL
    );
    SendMessageA(mode_combo, CB_ADDSTRING, 0, (LPARAM)"Normal result");
    SendMessageA(mode_combo, CB_ADDSTRING, 0, (LPARAM)"Wrong result test");
    SendMessageA(mode_combo, CB_ADDSTRING, 0, (LPARAM)"Tampered task test");
    SendMessageA(mode_combo, CB_SETCURSEL, 0, 0);
    use_ui_font(mode_combo);

    run_button = CreateWindowExA(
        0, "BUTTON", "Connect and Stay Online",
        WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
        24, 120, 200, 38,
        window, (HMENU)ID_RUN_BUTTON, NULL, NULL
    );
    use_ui_font(run_button);

    disconnect_button = CreateWindowExA(
        0, "BUTTON", "Disconnect",
        WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON | WS_DISABLED,
        236, 120, 140, 38,
        window, (HMENU)ID_DISCONNECT_BUTTON, NULL, NULL
    );
    use_ui_font(disconnect_button);

    status_text = CreateWindowExA(
        0, "STATIC", "Status: waiting",
        WS_CHILD | WS_VISIBLE,
        392, 128, 318, 26,
        window, (HMENU)ID_STATUS_TEXT, NULL, NULL
    );
    use_ui_font(status_text);

    control = CreateWindowExA(
        0, "STATIC", "Execution log",
        WS_CHILD | WS_VISIBLE,
        24, 180, 180, 26,
        window, NULL, NULL, NULL
    );
    use_ui_font(control);

    log_edit = CreateWindowExA(
        WS_EX_CLIENTEDGE, "EDIT", "",
        WS_CHILD | WS_VISIBLE | WS_VSCROLL |
        ES_LEFT | ES_MULTILINE | ES_AUTOVSCROLL | ES_READONLY,
        24, 212, 686, 310,
        window, (HMENU)ID_LOG_EDIT, NULL, NULL
    );
    use_ui_font(log_edit);
}

static void run_selected_mode(void)
{
    const char *modes[] = {"normal", "wrong", "tamper"};
    int selected_mode;
    HANDLE worker;

    GetWindowTextA(node_edit, worker_node, sizeof(worker_node));
    selected_mode = (int)SendMessageA(mode_combo, CB_GETCURSEL, 0, 0);
    if (selected_mode < 0 || selected_mode > 2) {
        selected_mode = 0;
    }

    EnableWindow(run_button, FALSE);
    EnableWindow(disconnect_button, TRUE);
    EnableWindow(node_edit, FALSE);
    EnableWindow(mode_combo, FALSE);
    manual_stop_requested = 0;
    snprintf(worker_mode, sizeof(worker_mode), "%s", modes[selected_mode]);
    SetWindowTextA(status_text, "Status: connecting and authenticating...");
    SetWindowTextA(log_edit, "");
    UpdateWindow(GetParent(run_button));

    worker = CreateThread(NULL, 0, client_worker, NULL, 0, NULL);
    if (worker == NULL) {
        SetWindowTextA(status_text, "Status: cannot start worker thread");
        EnableWindow(run_button, TRUE);
        EnableWindow(disconnect_button, FALSE);
        EnableWindow(node_edit, TRUE);
        EnableWindow(mode_combo, TRUE);
        return;
    }
    CloseHandle(worker);
}

static DWORD WINAPI client_worker(LPVOID parameter)
{
    (void)parameter;
    do {
        worker_exit_code = run_client(
            worker_node, worker_mode, 1, client_progress,
            worker_log, CLIENT_LOG_SIZE
        );
        if (manual_stop_requested || worker_exit_code == 2) break;

        client_progress(CLIENT_PROGRESS_RECONNECTING);
        Sleep(2000);
    } while (!manual_stop_requested);

    if (manual_stop_requested) worker_exit_code = 0;
    PostMessageA(main_window, WM_CLIENT_DONE, 0, 0);
    return 0;
}

static void client_progress(int progress_code)
{
    PostMessageA(main_window, WM_CLIENT_PROGRESS,
                 (WPARAM)progress_code, 0);
}

static void use_ui_font(HWND control)
{
    SendMessageA(control, WM_SETFONT, (WPARAM)ui_font, TRUE);
}
