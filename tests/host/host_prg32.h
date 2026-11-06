/*
 * host_prg32.h - the few PRG32 calls the cartridge makes, for the host tests.
 *
 * Two framebuffers are kept, as the two kinds of console do:
 *   fb_direct  RGB565, what QEMU shows (rect_indexed draws palette[cell], a sprite
 *              draws its palette's RGB565 as is);
 *   fb_index   8-bit cells, what the ESP32-C6 keeps (an RGB565 colour is quantised
 *              to its cube cell, exactly as prg32_gfx_index_for_rgb565_unlocked does)
 *              and shows through the system palette.
 * The tests require both to show the same picture.
 */
#ifndef HOST_PRG32_H
#define HOST_PRG32_H

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define HOST_W 320
#define HOST_H 200

static uint16_t fb_direct[HOST_W * HOST_H];
static uint8_t fb_index[HOST_W * HOST_H];
static uint16_t sys_palette[256];
static uint32_t host_input, host_input2, host_ms;
static unsigned host_rects, host_sprites, host_presents, host_pixels;
static unsigned host_notes;

static uint8_t host_cube(uint16_t color) {
    static const uint16_t named[8] = {0x0000, 0xffff, 0xf800, 0x07e0, 0x001f, 0xffe0, 0x07ff, 0xf81f};
    for (uint8_t i = 0; i < 8; ++i)
        if (color == named[i]) return i;
    unsigned r = ((color >> 11) & 31u) * 5u / 31u;
    unsigned g = ((color >> 5) & 63u) * 5u / 63u;
    unsigned b = (color & 31u) * 5u / 31u;
    return (uint8_t)(16u + r * 36u + g * 6u + b);
}

uint32_t prg32_input_read(void) { return host_input; }
uint32_t prg32_input_read_player(uint8_t player) { return player == 1 ? host_input2 : 0; }
uint32_t prg32_ticks_ms(void) { return host_ms; }
void prg32_palette_set(uint8_t index, uint16_t rgb565) { sys_palette[index] = rgb565; }
void prg32_gfx_present(void) { host_presents++; }

void prg32_gfx_rect_indexed(int x, int y, int w, int h, uint8_t index) {
    host_rects++;
    for (int yy = y; yy < y + h; ++yy)
        for (int xx = x; xx < x + w; ++xx) {
            if (xx < 0 || yy < 0 || xx >= HOST_W || yy >= HOST_H) continue;
            fb_direct[yy * HOST_W + xx] = sys_palette[index];
            fb_index[yy * HOST_W + xx] = index;
            host_pixels++;
        }
}

void prg32_sprite_draw_indexed(int x, int y, const prg32_indexed_sprite_t *s, uint32_t frame) {
    (void)frame;
    host_sprites++;
    for (int py = 0; py < s->height; ++py)
        for (int px = 0; px < s->width; ++px) {
            uint8_t i = s->pixels[py * s->width + px];
            int dx = x + px, dy = y + py;
            if ((int)i == s->transparent_index || dx < 0 || dy < 0 || dx >= HOST_W || dy >= HOST_H) continue;
            fb_direct[dy * HOST_W + dx] = s->palette[i];
            fb_index[dy * HOST_W + dx] = host_cube(s->palette[i]);
            host_pixels++;
        }
}

void prg32_audio_note_on_pan(uint8_t c, uint8_t i, uint8_t n, uint8_t v, int8_t p) {
    (void)c; (void)i; (void)n; (void)v; (void)p;
    host_notes++;
}
void prg32_audio_note_off(uint8_t c) { (void)c; }

static void host_write_ppm(const char *path, const uint16_t *fb) {
    FILE *f = fopen(path, "wb");
    if (!f) return;
    fprintf(f, "P6\n%d %d\n255\n", HOST_W, HOST_H);
    for (int i = 0; i < HOST_W * HOST_H; ++i) {
        uint16_t q = fb[i];
        int r = (q >> 11) & 31, g = (q >> 5) & 63, b = q & 31;
        fputc((r * 527 + 23) >> 6, f);
        fputc((g * 259 + 33) >> 6, f);
        fputc((b * 527 + 23) >> 6, f);
    }
    fclose(f);
}

#endif
