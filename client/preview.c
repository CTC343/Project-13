#define COBJMACROS
#include <winsock2.h>
#include <windows.h>
#include <wincodec.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "network.h"
#include "preview.h"
#include "protocol.h"
#include "security.h"

#define MAX_IMAGE_BYTES (512 * 1024)
#define MAX_WIDTH 960
#define MAX_HEIGHT 720
#define ID_PREVIEW_PERMISSION 110

typedef struct {
    char host[254];
    int port;
    char profile[MAX_PATH];
    char node_id[64];
    char username[64];
    char license_id[64];
    char token[65];
    char executable_hash[65];
    char view_id[33];
} PreviewPeer;

static SRWLOCK lock = SRWLOCK_INIT;
static HWND owner, consent, indicator;
static HANDLE changed;
static int enabled, stopping, streaming;
static PreviewPeer desired;

static int preview_enabled(void)
{
    int status;
    AcquireSRWLockShared(&lock);
    status = enabled;
    ReleaseSRWLockShared(&lock);
    return status;
}

static void offer_preview(const ClientLogin *login, const char *view_id, const char *executable_hash)
{
    if (!changed) return;
    AcquireSRWLockExclusive(&lock);
    if (login && enabled && strlen(view_id) == 32 && strspn(view_id, "0123456789abcdef") == 32) {
        if (strcmp(desired.view_id, view_id) || strcmp(desired.token, login->session_token)) {
            memcpy(desired.host, login->host, sizeof(desired.host));
            memcpy(desired.profile, login->profile, sizeof(desired.profile));
            memcpy(desired.node_id, login->node_id, sizeof(desired.node_id));
            memcpy(desired.username, login->username, sizeof(desired.username));
            memcpy(desired.license_id, login->license_id, sizeof(desired.license_id));
            memcpy(desired.token, login->session_token, sizeof(desired.token));
            memcpy(desired.executable_hash, executable_hash, sizeof(desired.executable_hash));
            memcpy(desired.view_id, view_id, sizeof(desired.view_id));
            desired.port = login->port;
            SetEvent(changed);
        }
    } else if (desired.view_id[0]) {
        clear_sensitive(&desired, sizeof(desired));
        SetEvent(changed);
    }
    ReleaseSRWLockExclusive(&lock);
}

const ClientPreviewHooks window_preview_hooks = {preview_enabled, offer_preview};

static int current_view(const PreviewPeer *peer)
{
    int current;
    AcquireSRWLockShared(&lock);
    current = enabled && !stopping && !strcmp(desired.view_id, peer->view_id) &&
              !strcmp(desired.token, peer->token);
    ReleaseSRWLockShared(&lock);
    return current;
}

static void set_streaming(int value)
{
    AcquireSRWLockExclusive(&lock);
    streaming = value;
    ReleaseSRWLockExclusive(&lock);
    PostMessageW(owner, WM_PREVIEW_STATUS, 0, 0);
}

static ULONG encode_image(IWICImagingFactory *factory, HBITMAP bitmap,
                          UINT width, UINT height, unsigned char *output)
{
    IWICBitmap *source = NULL;
    IWICBitmapScaler *scaler = NULL;
    IWICBitmapEncoder *encoder = NULL;
    IWICBitmapFrameEncode *frame = NULL;
    IStream *stream = NULL;
    STATSTG info;
    LARGE_INTEGER start = {0};
    WICPixelFormatGUID format = GUID_WICPixelFormat24bppBGR;
    ULONG size = 0;

    if (FAILED(IWICImagingFactory_CreateBitmapFromHBITMAP(factory, bitmap, NULL,
                                                         WICBitmapIgnoreAlpha, &source)) ||
        FAILED(IWICImagingFactory_CreateBitmapScaler(factory, &scaler)) ||
        FAILED(IWICBitmapScaler_Initialize(scaler, (IWICBitmapSource *)source,
                                            width, height, WICBitmapInterpolationModeFant)) ||
        FAILED(CreateStreamOnHGlobal(NULL, TRUE, &stream)) ||
        FAILED(IWICImagingFactory_CreateEncoder(factory, &GUID_ContainerFormatPng, NULL, &encoder)) ||
        FAILED(IWICBitmapEncoder_Initialize(encoder, stream, WICBitmapEncoderNoCache)) ||
        FAILED(IWICBitmapEncoder_CreateNewFrame(encoder, &frame, NULL)) ||
        FAILED(IWICBitmapFrameEncode_Initialize(frame, NULL)) ||
        FAILED(IWICBitmapFrameEncode_SetSize(frame, width, height)) ||
        FAILED(IWICBitmapFrameEncode_SetPixelFormat(frame, &format)) ||
        FAILED(IWICBitmapFrameEncode_WriteSource(frame, (IWICBitmapSource *)scaler, NULL)) ||
        FAILED(IWICBitmapFrameEncode_Commit(frame)) ||
        FAILED(IWICBitmapEncoder_Commit(encoder)) ||
        FAILED(IStream_Stat(stream, &info, STATFLAG_NONAME)) ||
        info.cbSize.QuadPart > MAX_IMAGE_BYTES ||
        FAILED(IStream_Seek(stream, start, STREAM_SEEK_SET, NULL))) goto done;
    if (FAILED(IStream_Read(stream, output, (ULONG)info.cbSize.QuadPart, &size)) ||
        size != info.cbSize.QuadPart) size = 0;
done:
    if (frame) IWICBitmapFrameEncode_Release(frame);
    if (encoder) IWICBitmapEncoder_Release(encoder);
    if (stream) IStream_Release(stream);
    if (scaler) IWICBitmapScaler_Release(scaler);
    if (source) IWICBitmap_Release(source);
    return size;
}

static ULONG capture_window(IWICImagingFactory *factory, unsigned char *output)
{
    RECT rect;
    HDC window_dc, drawing_dc;
    HBITMAP bitmap;
    HGDIOBJ previous;
    DWORD_PTR ignored;
    UINT width, height;
    ULONG size = 0;

    if (IsIconic(owner) || !GetClientRect(owner, &rect) ||
        rect.right <= 0 || rect.bottom <= 0 || rect.right > 4096 || rect.bottom > 4096) return 0;
    window_dc = GetDC(owner);
    if (!window_dc) return 0;
    drawing_dc = CreateCompatibleDC(window_dc);
    bitmap = CreateCompatibleBitmap(window_dc, rect.right, rect.bottom);
    ReleaseDC(owner, window_dc);
    if (drawing_dc && bitmap) {
        previous = SelectObject(drawing_dc, bitmap);
        if (previous) {
            PatBlt(drawing_dc, 0, 0, rect.right, rect.bottom, WHITENESS);
            // Paint this application's client area without copying any overlapping windows.
            if (SendMessageTimeoutW(owner, WM_PRINT, (WPARAM)drawing_dc,
                    PRF_CLIENT | PRF_ERASEBKGND | PRF_CHILDREN,
                    SMTO_ABORTIFHUNG | SMTO_BLOCK, 500, &ignored)) {
                SelectObject(drawing_dc, previous);
                previous = NULL;
                width = (UINT)rect.right;
                height = (UINT)rect.bottom;
                if (width > MAX_WIDTH) {
                    height = height * MAX_WIDTH / width;
                    width = MAX_WIDTH;
                }
                if (height > MAX_HEIGHT) {
                    width = width * MAX_HEIGHT / height;
                    height = MAX_HEIGHT;
                }
                if (width && height) size = encode_image(factory, bitmap, width, height, output);
            }
            if (previous) SelectObject(drawing_dc, previous);
        }
    }
    if (bitmap) DeleteObject(bitmap);
    if (drawing_dc) DeleteDC(drawing_dc);
    return size;
}

static void share_window(const PreviewPeer *peer, IWICImagingFactory *factory, unsigned char *image)
{
    NetworkConnection connection = {INVALID_SOCKET};
    char request[470];
    char response[128], type[32], error[NETWORK_ERROR_SIZE];
    int status;
    int shown = 0;
    if (network_connect(&connection, peer->host, peer->port, peer->profile, error, sizeof(error)) != 1 ||
        !current_view(peer)) goto done;
    snprintf(request, sizeof(request),
             "{\"node_id\":\"%s\",\"username\":\"%s\",\"license_id\":\"%s\","
             "\"token\":\"%s\",\"exe_hash\":\"%s\",\"view_id\":\"%s\"}",
             peer->node_id, peer->username, peer->license_id, peer->token, peer->executable_hash, peer->view_id);
    if (!protocol_send_frame(&connection, "PREVIEW_OPEN", 0, request, error, sizeof(error)) ||
        !protocol_receive_frame(&connection, type, sizeof(type), &status,
                                response, sizeof(response), error, sizeof(error)) ||
        status != 200 || strcmp(type, "PREVIEW_OK")) goto done;
    while (current_view(peer)) {
        ULONG size, wire_length;
        if (!protocol_receive_frame(&connection, type, sizeof(type), &status,
                                    response, sizeof(response), error, sizeof(error)) ||
            status != 200 || strcmp(type, "PREVIEW_PULL") || !current_view(peer)) break;
        if (!shown) {
            shown = 1;
            set_streaming(1);
        }
        size = capture_window(factory, image);
        if (!current_view(peer)) break;
        wire_length = htonl(size);
        if (!network_send_bytes(&connection, (const char *)&wire_length, sizeof(wire_length), error, sizeof(error)) ||
            (size && !network_send_bytes(&connection, (const char *)image, (int)size, error, sizeof(error)))) break;
    }
done:
    if (shown) set_streaming(0);
    clear_sensitive(request, sizeof(request));
    network_close(&connection);
}

static DWORD WINAPI preview_worker(LPVOID unused)
{
    HRESULT init = CoInitializeEx(NULL, COINIT_MULTITHREADED);
    IWICImagingFactory *factory = NULL;
    unsigned char *image = NULL;
    PreviewPeer peer;
    DWORD wait = INFINITE;
    (void)unused;
    if (FAILED(init)) return 1;
    if (FAILED(CoCreateInstance(&CLSID_WICImagingFactory, NULL, CLSCTX_INPROC_SERVER,
                                &IID_IWICImagingFactory, (void **)&factory))) goto done;
    image = malloc(MAX_IMAGE_BYTES);
    if (!image) goto done;
    while (WaitForSingleObject(changed, wait) != WAIT_FAILED) {
        int done;
        AcquireSRWLockShared(&lock);
        peer = desired;
        done = stopping;
        ReleaseSRWLockShared(&lock);
        if (done) break;
        wait = INFINITE;
        if (peer.view_id[0] && current_view(&peer)) {
            share_window(&peer, factory, image);
            wait = 1000;
        }
        clear_sensitive(&peer, sizeof(peer));
    }
done:
    free(image);
    if (factory) IWICImagingFactory_Release(factory);
    CoUninitialize();
    return 0;
}

void preview_attach(HWND window, HFONT font)
{
    HANDLE worker;
    owner = window;
    consent = CreateWindowExW(0, L"BUTTON", L"Allow window preview", WS_CHILD | WS_VISIBLE |
                              WS_TABSTOP | BS_AUTOCHECKBOX, 219, 332, 208, 30,
                              window, (HMENU)ID_PREVIEW_PERMISSION, NULL, NULL);
    indicator = CreateWindowExW(0, L"STATIC", L"", WS_CHILD | WS_VISIBLE,
                                440, 337, 270, 24, window, NULL, NULL, NULL);
    SendMessageW(consent, WM_SETFONT, (WPARAM)font, TRUE);
    SendMessageW(indicator, WM_SETFONT, (WPARAM)font, TRUE);
    changed = CreateEventW(NULL, FALSE, FALSE, NULL);
    worker = changed ? CreateThread(NULL, 0, preview_worker, NULL, 0, NULL) : NULL;
    if (worker) {
        CloseHandle(worker);
    } else {
        EnableWindow(consent, FALSE);
        SetWindowTextW(indicator, L"Window preview unavailable");
    }
}

int preview_handle_command(WPARAM command)
{
    if (LOWORD(command) != ID_PREVIEW_PERMISSION || HIWORD(command) != BN_CLICKED) return 0;
    AcquireSRWLockExclusive(&lock);
    enabled = SendMessageW(consent, BM_GETCHECK, 0, 0) == BST_CHECKED;
    if (!enabled) clear_sensitive(&desired, sizeof(desired));
    ReleaseSRWLockExclusive(&lock);
    if (changed) SetEvent(changed);
    preview_update_status();
    return 1;
}

void preview_update_status(void)
{
    const wchar_t *label;
    AcquireSRWLockShared(&lock);
    label = enabled ? (streaming && desired.view_id[0] ? L"Window is being shared" : L"Preview allowed") : L"";
    ReleaseSRWLockShared(&lock);
    SetWindowTextW(indicator, label);
}

void preview_shutdown(void)
{
    AcquireSRWLockExclusive(&lock);
    stopping = 1;
    enabled = 0;
    clear_sensitive(&desired, sizeof(desired));
    ReleaseSRWLockExclusive(&lock);
    if (changed) SetEvent(changed);
}
