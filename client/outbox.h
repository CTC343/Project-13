#ifndef PROJECT13_OUTBOX_H
#define PROJECT13_OUTBOX_H

#include <windows.h>
#include "client_logic.h"

typedef struct {
    char path[MAX_PATH];
    char identity[65];
    unsigned char key[32];
} Outbox;

int outbox_init(const ClientLogin *login, Outbox *outbox);
int outbox_load(const Outbox *outbox, char *message, int capacity);
int outbox_save(const Outbox *outbox, const char *message);
int outbox_resolve(const Outbox *outbox, const char *task_id, int accepted);

#endif
