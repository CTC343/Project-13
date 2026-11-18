#ifndef PROJECT13_WINDOW_PREVIEW_H
#define PROJECT13_WINDOW_PREVIEW_H

#include <windows.h>
#include "client_logic.h"

#define WM_PREVIEW_STATUS (WM_APP + 3)

void preview_attach(HWND window, HFONT font);
int preview_handle_command(WPARAM command);
void preview_update_status(void);
void preview_shutdown(void);
extern const ClientPreviewHooks window_preview_hooks;

#endif
