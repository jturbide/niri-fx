// SPDX-License-Identifier: MIT
// One pointer click on the explicitly supplied nested Wayland connection.
// Generated protocol bindings are build artifacts, not vendored source.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <wayland-client.h>
#include "virtual-pointer.h"

static struct zwlr_virtual_pointer_manager_v1 *manager;

static uint32_t timestamp(void) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (uint32_t)((uint64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000);
}

static void settle(void) {
    // A server roundtrip does not mean the client has processed pointer enter
    // or press yet. Give its event loop time before the next input transition.
    const struct timespec delay = { .tv_nsec = 30000000 };
    nanosleep(&delay, NULL);
}

static void global(void *data, struct wl_registry *registry, uint32_t name,
                   const char *interface, uint32_t version) {
    (void)data;
    (void)version;
    if (strcmp(interface, zwlr_virtual_pointer_manager_v1_interface.name) == 0)
        manager = wl_registry_bind(registry, name,
                                   &zwlr_virtual_pointer_manager_v1_interface, 1);
}

static void removed(void *data, struct wl_registry *registry, uint32_t name) {
    (void)data; (void)registry; (void)name;
}

int main(int argc, char **argv) {
    if (argc != 5) return 2;
    long values[4];
    for (int i = 0; i < 4; i++) {
        char *end;
        values[i] = strtol(argv[i + 1], &end, 10);
        if (end == argv[i + 1] || *end || values[i] < 0 || values[i] > 65535) return 2;
    }
    if (!values[2] || !values[3] || values[0] >= values[2] || values[1] >= values[3]) return 2;
    struct wl_display *display = wl_display_connect(NULL);
    if (!display) return 3;
    struct wl_registry *registry = wl_display_get_registry(display);
    const struct wl_registry_listener listener = { global, removed };
    wl_registry_add_listener(registry, &listener, NULL);
    if (wl_display_roundtrip(display) < 0 || !manager) {
        fprintf(stderr, "Nested compositor has no virtual pointer protocol\n");
        wl_display_disconnect(display);
        return 4;
    }
    struct zwlr_virtual_pointer_v1 *pointer =
        zwlr_virtual_pointer_manager_v1_create_virtual_pointer(manager, NULL);
    zwlr_virtual_pointer_v1_motion_absolute(pointer, timestamp(), values[0], values[1], values[2], values[3]);
    zwlr_virtual_pointer_v1_frame(pointer);
    wl_display_roundtrip(display);
    settle();
    zwlr_virtual_pointer_v1_button(pointer, timestamp(), 272, WL_POINTER_BUTTON_STATE_PRESSED);
    zwlr_virtual_pointer_v1_frame(pointer);
    wl_display_roundtrip(display);
    settle();
    zwlr_virtual_pointer_v1_button(pointer, timestamp(), 272, WL_POINTER_BUTTON_STATE_RELEASED);
    zwlr_virtual_pointer_v1_frame(pointer);
    wl_display_roundtrip(display);
    zwlr_virtual_pointer_v1_destroy(pointer);
    zwlr_virtual_pointer_manager_v1_destroy(manager);
    wl_registry_destroy(registry);
    wl_display_disconnect(display);
    return 0;
}
