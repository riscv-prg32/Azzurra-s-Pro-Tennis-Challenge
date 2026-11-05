#!/usr/bin/env python3
"""Render an actual gameplay frame with PRG32's host software rasterizer."""
import os,re,subprocess,tempfile
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
SDK=Path(os.environ.get("PRG32_REPO",ROOT.parent/"PRG32")).resolve()

def function(src,name):
    m=re.search(r'^(?:static )?[^\n;{}]*\b'+name+r'\([^;{}]*\)\s*\{.*?\n\}',src,re.M|re.S)
    if not m: raise RuntimeError(name)
    return m.group(0)

def main():
    display=(SDK/"components/prg32/prg32_display_qemu_rgb.c").read_text()
    font=re.search(r'static const uint8_t g_font8\[96\]\[8\].*?\n};',display,re.S).group(0).replace(' PRG32_FLASH_RODATA','')
    parts=['#include "prg32.h"','#define PRG32_VIEWPORT_Y 20',
      'static uint16_t g_fb[PRG32_LCD_W*PRG32_LCD_H];','static uint16_t g_palette[256];',
      'static int g_fullscreen,g_band_color_set,g_band_area_valid;',
      'static uint16_t g_band_color,g_last_band_color;',
      'static int g_band_cache_valid[2];','static int g_dirty_x0,g_dirty_y0,g_dirty_x1,g_dirty_y1;',font]
    for n in ['dirty_add_raw','logical_h','logical_y_to_raw','dirty_add','font_glyph','fill_raw_rect',
              'prg32_gfx_rect','prg32_gfx_text8']:
        parts.append(function(display,n))
    parts+=['void prg32_palette_set(uint8_t i,uint16_t c){g_palette[i]=c;}',
            'void prg32_gfx_rect_indexed(int x,int y,int w,int h,uint8_t i){prg32_gfx_rect(x,y,w,h,g_palette[i]);}',
            'void prg32_sprite_draw_indexed(int x,int y,const prg32_indexed_sprite_t*s,uint32_t f){(void)f;for(int py=0;py<s->height;py++)for(int px=0;px<s->width;px++){uint8_t i=s->pixels[py*s->width+px];int dx=x+px,dy=y+py;if(i!=s->transparent_index&&dx>=0&&dx<320&&dy>=0&&dy<200)g_fb[(dy+20)*320+dx]=s->palette[i];}}']
    with tempfile.TemporaryDirectory(prefix='azzurra-capture-') as td:
        td=Path(td);(td/'capture_renderer.h').write_text('\n'.join(parts))
        exe=td/'capture';ppm=td/'screen.ppm'
        inc=[SDK/'components/prg32/include',SDK/'components/prg32_audio/include',SDK/'components/prg32_metrics/include',SDK/'components/prg32_multiplayer/include']
        cmd=[os.environ.get('CC','cc'),'-std=c99','-Wall','-Wextra']
        for p in inc:cmd+=['-I',str(p)]
        cmd+=['-I',str(td),str(ROOT/'tests/capture_gamefield.c'),'-o',str(exe)]
        subprocess.run(cmd,check=True);ppm.write_bytes(subprocess.check_output([str(exe)]))
        out=ROOT/'assets/gamefield.png';out.parent.mkdir(exist_ok=True)
        with Image.open(ppm) as im:im.resize((960,600),Image.Resampling.NEAREST).save(out)
        print(out)
if __name__=='__main__':main()
