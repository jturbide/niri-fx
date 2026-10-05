// SPDX-License-Identifier: MIT
// Owned synthetic xdg client: explicit nonzero geometry, transparent margins,
// and visible pixels outside that geometry. No desktop configuration or input.
#define _GNU_SOURCE
#include "xdg-shell.h"
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <wayland-client.h>

static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct xdg_wm_base *wm;
static struct wl_surface *surface;
static struct xdg_surface *xdg;
static struct wl_surface *popup_surface;
static struct xdg_surface *popup_xdg;
static bool popup_created = false;
static int width = 400, height = 360;
static bool running = true;
enum { MARGIN = 24 };

struct buffer {
  struct wl_buffer *buffer;
  void *pixels;
  size_t size;
};
static void release(void *data, struct wl_buffer *buffer) {
  struct buffer *owned = data;
  wl_buffer_destroy(buffer);
  munmap(owned->pixels, owned->size);
  free(owned);
}
static const struct wl_buffer_listener buffer_listener = {.release = release};

static void draw_surface(struct wl_surface *target, bool popup) {
  const int sw = popup ? 140 : width + MARGIN * 2;
  const int sh = popup ? 96 : height + MARGIN * 2;
  const size_t size = (size_t)sw * sh * sizeof(uint32_t);
  int fd = memfd_create("nirifx-owned-margin-card", MFD_CLOEXEC);
  if (fd < 0 || ftruncate(fd, (off_t)size) < 0) {
    perror("owned buffer");
    exit(1);
  }
  uint32_t *pixels =
      mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
  if (pixels == MAP_FAILED) {
    perror("owned mmap");
    exit(1);
  }
  for (int y = 0; y < sh; y++)
    for (int x = 0; x < sw; x++) {
      uint32_t color = 0;
      if (x < 8 || y < 8 || x >= sw - 8 || y >= sh - 8)
        color = 0xff348fe4;
      if (x >= MARGIN && y >= MARGIN && x < sw - MARGIN && y < sh - MARGIN) {
        color = 0xfff183c2;
        if ((x - MARGIN) % 80 < 8 || (y - MARGIN) % 72 < 8)
          color = 0xfff6f8fc;
      }
      if (popup)
        color = (x < 8 || y < 8 || x >= sw - 8 || y >= sh - 8) ? 0xff182735
                                                               : 0xffefd46b;
      pixels[(size_t)y * sw + x] = color;
    }
  struct wl_shm_pool *pool = wl_shm_create_pool(shm, fd, (int)size);
  struct buffer *owned = calloc(1, sizeof(*owned));
  if (!owned) {
    perror("owned allocation");
    exit(1);
  }
  owned->pixels = pixels;
  owned->size = size;
  owned->buffer = wl_shm_pool_create_buffer(pool, 0, sw, sh, sw * 4,
                                            WL_SHM_FORMAT_ARGB8888);
  wl_buffer_add_listener(owned->buffer, &buffer_listener, owned);
  wl_shm_pool_destroy(pool);
  close(fd);
  if (!popup)
    xdg_surface_set_window_geometry(xdg, MARGIN, MARGIN, width, height);
  wl_surface_attach(target, owned->buffer, 0, 0);
  wl_surface_damage_buffer(target, 0, 0, sw, sh);
  wl_surface_commit(target);
  if (!popup)
    fprintf(stderr, "NIRIFX_WINDOW_GEOMETRY x=%d y=%d width=%d height=%d\n",
            MARGIN, MARGIN, width, height);
}

static void popup_surface_configure(void *data, struct xdg_surface *object,
                                    uint32_t serial) {
  (void)data;
  xdg_surface_ack_configure(object, serial);
  draw_surface(popup_surface, true);
}
static const struct xdg_surface_listener popup_surface_listener = {
    .configure = popup_surface_configure};
static void popup_configure(void *data, struct xdg_popup *object, int32_t x,
                            int32_t y, int32_t w, int32_t h) {
  (void)data;
  (void)object;
  fprintf(stderr, "NIRIFX_POPUP_CONFIGURED x=%d y=%d width=%d height=%d\n", x,
          y, w, h);
}
static void popup_done(void *data, struct xdg_popup *object) {
  (void)data;
  (void)object;
}
static const struct xdg_popup_listener popup_listener = {
    .configure = popup_configure, .popup_done = popup_done};
static void create_popup(void) {
  if (popup_created || !getenv("NIRIFX_POPUP"))
    return;
  popup_created = true;
  popup_surface = wl_compositor_create_surface(compositor);
  popup_xdg = xdg_wm_base_get_xdg_surface(wm, popup_surface);
  xdg_surface_add_listener(popup_xdg, &popup_surface_listener, NULL);
  struct xdg_positioner *positioner = xdg_wm_base_create_positioner(wm);
  xdg_positioner_set_size(positioner, 140, 96);
  xdg_positioner_set_anchor_rect(positioner, width - 80, 40, 80, 40);
  xdg_positioner_set_anchor(positioner, XDG_POSITIONER_ANCHOR_BOTTOM_RIGHT);
  xdg_positioner_set_gravity(positioner, XDG_POSITIONER_GRAVITY_BOTTOM_RIGHT);
  struct xdg_popup *popup = xdg_surface_get_popup(popup_xdg, xdg, positioner);
  xdg_popup_add_listener(popup, &popup_listener, NULL);
  xdg_positioner_destroy(positioner);
  wl_surface_commit(popup_surface);
}
static void configure(void *data, struct xdg_surface *object, uint32_t serial) {
  (void)data;
  xdg_surface_ack_configure(object, serial);
  draw_surface(surface, false);
  create_popup();
}
static const struct xdg_surface_listener surface_listener = {.configure =
                                                                 configure};
static void size_configure(void *data, struct xdg_toplevel *top, int32_t w,
                           int32_t h, struct wl_array *states) {
  (void)data;
  (void)top;
  (void)states;
  if (w > 0)
    width = w;
  if (h > 0)
    height = h;
}
static void close_requested(void *data, struct xdg_toplevel *top) {
  (void)data;
  (void)top;
  running = false;
}
static const struct xdg_toplevel_listener top_listener = {
    .configure = size_configure, .close = close_requested};
static void ping(void *data, struct xdg_wm_base *base, uint32_t serial) {
  (void)data;
  xdg_wm_base_pong(base, serial);
}
static const struct xdg_wm_base_listener wm_listener = {.ping = ping};
static void global(void *data, struct wl_registry *registry, uint32_t name,
                   const char *interface, uint32_t version) {
  (void)data;
  if (!strcmp(interface, wl_compositor_interface.name))
    compositor = wl_registry_bind(registry, name, &wl_compositor_interface,
                                  version < 4 ? version : 4);
  else if (!strcmp(interface, wl_shm_interface.name))
    shm = wl_registry_bind(registry, name, &wl_shm_interface, 1);
  else if (!strcmp(interface, xdg_wm_base_interface.name))
    wm = wl_registry_bind(registry, name, &xdg_wm_base_interface, 1);
}
static void removed(void *data, struct wl_registry *registry, uint32_t name) {
  (void)data;
  (void)registry;
  (void)name;
}
static const struct wl_registry_listener registry_listener = {
    .global = global, .global_remove = removed};
int main(void) {
  display = wl_display_connect(NULL);
  if (!display) {
    fprintf(stderr, "Cannot connect to owned Wayland display\n");
    return 1;
  }
  struct wl_registry *registry = wl_display_get_registry(display);
  wl_registry_add_listener(registry, &registry_listener, NULL);
  wl_display_roundtrip(display);
  if (!compositor || !shm || !wm) {
    fprintf(stderr, "Required owned Wayland globals missing\n");
    return 1;
  }
  xdg_wm_base_add_listener(wm, &wm_listener, NULL);
  surface = wl_compositor_create_surface(compositor);
  xdg = xdg_wm_base_get_xdg_surface(wm, surface);
  xdg_surface_add_listener(xdg, &surface_listener, NULL);
  struct xdg_toplevel *top = xdg_surface_get_toplevel(xdg);
  xdg_toplevel_add_listener(top, &top_listener, NULL);
  xdg_toplevel_set_title(top, "NiriFX pointer / Protected / geometry margins");
  xdg_toplevel_set_app_id(top, "nirifx-owned-margin-card");
  wl_surface_commit(surface);
  while (running && wl_display_dispatch(display) >= 0) {
  }
  wl_display_disconnect(display);
  return 0;
}
