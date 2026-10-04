// SPDX-License-Identifier: MIT
// Persistent pointer input for an explicitly named, owned nested Wayland socket.
// The Python harness checks socket ownership before starting this process.
#define _POSIX_C_SOURCE 200809L
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

static void global(void *data, struct wl_registry *registry, uint32_t name,
                   const char *interface, uint32_t version) {
    (void)data; (void)version;
    if (strcmp(interface, zwlr_virtual_pointer_manager_v1_interface.name) == 0)
        manager = wl_registry_bind(registry, name,
                                   &zwlr_virtual_pointer_manager_v1_interface, 1);
}

static void removed(void *data, struct wl_registry *registry, uint32_t name) {
    (void)data; (void)registry; (void)name;
}

static int number(const char *text) {
    char *end;
    long value = strtol(text, &end, 10);
    return end != text && !*end && value > 0 && value <= 65535 ? (int)value : 0;
}

int main(int argc, char **argv) {
    if (argc != 4 || argv[1][0] != '/') return 2;
    const int width = number(argv[2]), height = number(argv[3]);
    if (!width || !height) return 2;
    struct wl_display *display = wl_display_connect(argv[1]);
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
    puts("ready"); fflush(stdout);
    char line[128], extra;
    int pressed = 0, result = 0;
    while (fgets(line, sizeof(line), stdin)) {
        int x, y;
        if (sscanf(line, "motion %d %d %c", &x, &y, &extra) == 2 &&
            x >= 0 && x < width && y >= 0 && y < height) {
            zwlr_virtual_pointer_v1_motion_absolute(pointer, timestamp(), x, y, width, height);
        } else if (!strcmp(line, "press\n") && !pressed) {
            zwlr_virtual_pointer_v1_button(pointer, timestamp(), 272, WL_POINTER_BUTTON_STATE_PRESSED);
            pressed = 1;
        } else if (!strcmp(line, "release\n") && pressed) {
            zwlr_virtual_pointer_v1_button(pointer, timestamp(), 272, WL_POINTER_BUTTON_STATE_RELEASED);
            pressed = 0;
        } else if (!strcmp(line, "quit\n")) {
            break;
        } else {
            fprintf(stderr, "Invalid pointer command\n");
            result = 5;
            break;
        }
        zwlr_virtual_pointer_v1_frame(pointer);
        if (wl_display_roundtrip(display) < 0) { result = 6; break; }
        // This acknowledges protocol dispatch, not presentation on the monitor.
        puts("ok"); fflush(stdout);
    }
    if (pressed) {
        zwlr_virtual_pointer_v1_button(pointer, timestamp(), 272, WL_POINTER_BUTTON_STATE_RELEASED);
        zwlr_virtual_pointer_v1_frame(pointer);
        wl_display_roundtrip(display);
    }
    zwlr_virtual_pointer_v1_destroy(pointer);
    zwlr_virtual_pointer_manager_v1_destroy(manager);
    wl_registry_destroy(registry);
    wl_display_disconnect(display);
    return result;
}
