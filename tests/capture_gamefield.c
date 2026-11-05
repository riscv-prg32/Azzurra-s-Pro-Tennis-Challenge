#include <stdio.h>
#include "../game.c"
#include "capture_renderer.h"

static uint32_t capture_input;
uint32_t prg32_input_read(void){return capture_input;}
uint32_t prg32_input_read_player(uint8_t player){(void)player;return 0;}
uint32_t prg32_ticks_ms(void){return frame*33u;}
void prg32_gfx_lock(void){}
void prg32_gfx_unlock(void){}
void prg32_audio_set_master_volume(uint8_t v){(void)v;}
void prg32_audio_note_on_pan(uint8_t c,uint8_t i,uint8_t n,uint8_t v,int8_t p){(void)c;(void)i;(void)n;(void)v;(void)p;}
void prg32_audio_note_off(uint8_t c){(void)c;}
void prg32_multiplayer_init(void){}
bool prg32_multiplayer_available(void){return false;}
int prg32_multiplayer_join(const char*s,uint32_t f){(void)s;(void)f;return -1;}
int prg32_multiplayer_set_input(uint32_t i){(void)i;return 0;}
int prg32_multiplayer_set_local_state(int16_t x,int16_t y,uint16_t s,uint16_t f){(void)x;(void)y;(void)s;(void)f;return 0;}
int prg32_multiplayer_get_peer_count(void){return 0;}
int prg32_multiplayer_get_peer(int i,prg32_player_state_t*out){(void)i;(void)out;return -1;}
void prg32_multiplayer_tick(void){}

int main(void){
  for(int r=0;r<6;r++)for(int g=0;g<6;g++)for(int b=0;b<6;b++){
    uint8_t i=(uint8_t)(16+36*r+6*g+b);prg32_palette_set(i,c565(i));
  }
  azzurra_tennis_init();
  capture_input=PRG32_BTN_A;azzurra_tennis_update();capture_input=0;
  for(int i=0;i<78;i++)azzurra_tennis_update();
  capture_input=PRG32_BTN_A;azzurra_tennis_update();capture_input=0;
  for(int i=0;i<18;i++)azzurra_tennis_update();
  azzurra_tennis_draw();
  printf("P6\n320 200\n255\n");
  for(int y=0;y<200;y++)for(int x=0;x<320;x++){
    uint16_t q=g_fb[(y+PRG32_VIEWPORT_Y)*320+x];
    putchar(((q>>11)&31)*255/31);putchar(((q>>5)&63)*255/63);putchar((q&31)*255/31);
  }
  return ferror(stdout)?1:0;
}
