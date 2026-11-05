/* Azzurra's Pro Tennis Challenge -- portable PRG32 128 KiB cartridge. */
#include "prg32.h"
#include <stdint.h>
#include <stddef.h>

#define W 320
#define H 200
#define FP 16
#define ROOM "azzurra-tennis-v1"
#define CI(r,g,b) ((uint8_t)(16 + 36*(r) + 6*(g) + (b)))
#define WHITE CI(5,5,5)
#define BLACK CI(0,0,0)
#define YELLOW CI(5,5,0)
#define BLUE CI(0,2,5)
#define RED CI(5,1,1)

void *memset(void *d,int v,size_t n){uint8_t *p=d;while(n--)*p++=(uint8_t)v;return d;}
void *memcpy(void *d,const void *s,size_t n){uint8_t *a=d;const uint8_t *b=s;while(n--)*a++=*b++;return d;}
static int abs_i(int x){return x<0?-x:x;}
static int clamp(int x,int a,int b){return x<a?a:(x>b?b:x);}
static uint16_t rgb(int r,int g,int b){return (uint16_t)(((r&248)<<8)|((g&252)<<3)|(b>>3));}
static const uint8_t r5[6]={0,7,13,19,25,31},g6[6]={0,13,26,38,51,63};
static uint16_t c565(uint8_t c){int v=c-16;return(v<0||v>=216)?0:(uint16_t)((r5[v/36]<<11)|(g6[(v/6)%6]<<5)|r5[v%6]);}
static void box(int x,int y,int w,int h,uint8_t c){if(x<0){w+=x;x=0;}if(y<0){h+=y;y=0;}if(x+w>W)w=W-x;if(y+h>H)h=H-y;if(w>0&&h>0)prg32_gfx_rect_indexed(x,y,w,h,c);}
static void line(int x0,int y0,int x1,int y1,uint8_t c){int dx=abs_i(x1-x0),sx=x0<x1?1:-1,dy=-abs_i(y1-y0),sy=y0<y1?1:-1,e=dx+dy;for(;;){box(x0,y0,1,1,c);if(x0==x1&&y0==y1)break;int e2=e*2;if(e2>=dy){e+=dy;x0+=sx;}if(e2<=dx){e+=dx;y0+=sy;}}}
static int slen(const char*s){int n=0;while(s[n])n++;return n;}
static void text(int x,int y,const char*s,uint8_t f,uint8_t b){prg32_gfx_text8(x,y,s,c565(f),c565(b));}
static void center(int y,const char*s,uint8_t f,uint8_t b){text((W-slen(s)*8)/2,y,s,f,b);}

enum {P_SKY=232,P_CROWD,P_COURT,P_COURT2,P_LINE,P_NET,P_SHADOW,P_PANEL,P_GOLD,P_CLAY,P_GRASS,P_HARD};
static void palette(void){
  prg32_palette_set(P_SKY,rgb(18,38,82));prg32_palette_set(P_CROWD,rgb(45,38,66));
  prg32_palette_set(P_COURT,rgb(28,104,166));prg32_palette_set(P_COURT2,rgb(20,77,130));
  prg32_palette_set(P_LINE,rgb(235,242,236));prg32_palette_set(P_NET,rgb(190,205,216));
  prg32_palette_set(P_SHADOW,rgb(12,42,65));prg32_palette_set(P_PANEL,rgb(5,15,34));
  prg32_palette_set(P_GOLD,rgb(244,190,40));prg32_palette_set(P_CLAY,rgb(179,82,42));
  prg32_palette_set(P_GRASS,rgb(35,126,68));prg32_palette_set(P_HARD,rgb(46,83,164));
}

typedef struct {int x,y,vx,vy,z,vz;uint8_t last,served,bounces;} Ball;
typedef struct {int x,y;uint8_t team,human,flash;} Player;
enum {TITLE,ROUND_INTRO,PLAY,POINT_BANNER,ROUND_RESULT,CUP};
static Ball ball;
static Player p[4];
static uint32_t last_input,frame,rng=0xA22A1987u;
static int screen=TITLE,round_no,server,serve_side,rally,net_ok,point_timer;
static uint8_t points[2],games[2],sets[2],match_winner;
static uint32_t remote_input;
static uint8_t player_pixels[2][12*20],ball_pixels[7*7];
static uint16_t player_palette[2][8],ball_palette[4];
static prg32_indexed_sprite_t player_sprite[2],ball_sprite;
static const char round_names[14][18]={
  "NAPOLI BAY","ROME CLASSIC","PARIS CLAY","CHICAGO WIND",
  "LONDON GRASS","NEW YORK NIGHT","TOKYO LIGHTS","CAIRO OPEN",
  "MADRID MASTERS","BARCELONA CUP","BERLIN CLASSIC","VENICE CANAL",
  "SYDNEY OPEN","ATHENS FINAL"};
static const char rivals[14][18]={
  "VESUVIO VOLLEYS","ROMAN ACES","PARIS TOPSPIN","WINDY SMASH",
  "ROYAL VOLLEYS","METRO POWER","NEON SERVERS","NILE ACES",
  "CASTILLA PAIR","CATALAN SPIN","BERLIN WALL","LAGOON LOBS",
  "HARBOUR ACES","OLYMPUS PAIR"};
static const uint8_t surfaces[14]={P_CLAY,P_CLAY,P_CLAY,P_HARD,P_GRASS,P_HARD,P_HARD,P_CLAY,P_CLAY,P_CLAY,P_HARD,P_CLAY,P_HARD,P_CLAY};
static const char sponsors[5][14]={"RISC-V","UNIPARTHENOPE","PRG32","OPEN-HW","OPEN-SW"};

static uint32_t rnd(void){rng=rng*1664525u+1013904223u;return rng>>16;}
static void init_sprites(void){
  memset(player_pixels,0,sizeof player_pixels);memset(ball_pixels,0,sizeof ball_pixels);
  for(int team=0;team<2;team++){
    uint8_t *q=player_pixels[team];
    for(int y=1;y<6;y++)for(int x=4;x<8;x++)q[y*12+x]=2;
    for(int y=6;y<13;y++)for(int x=2;x<10;x++)q[y*12+x]=3;
    for(int y=8;y<15;y++){q[y*12+1]=2;q[y*12+10]=2;}
    for(int y=13;y<19;y++){q[y*12+3]=4;q[y*12+4]=4;q[y*12+7]=4;q[y*12+8]=4;}
    q[19*12+2]=q[19*12+3]=q[19*12+4]=5;q[19*12+7]=q[19*12+8]=q[19*12+9]=5;
    q[3*12+3]=q[4*12+3]=1;q[7*12+10]=q[8*12+11]=6;q[6*12+11]=7;
    player_palette[team][0]=0;player_palette[team][1]=c565(CI(1,0,0));player_palette[team][2]=c565(CI(5,3,2));
    player_palette[team][3]=c565(team?RED:BLUE);player_palette[team][4]=c565(WHITE);player_palette[team][5]=c565(BLACK);
    player_palette[team][6]=c565(CI(4,4,4));player_palette[team][7]=c565(WHITE);
    player_sprite[team].pixels=q;player_sprite[team].palette=player_palette[team];player_sprite[team].width=12;player_sprite[team].height=20;
    player_sprite[team].frame_count=1;player_sprite[team].palette_count=8;player_sprite[team].bits_per_pixel=8;player_sprite[team].transparent_index=0;
  }
  for(int y=0;y<7;y++)for(int x=0;x<7;x++){int dx=x-3,dy=y-3;if(dx*dx+dy*dy<=10)ball_pixels[y*7+x]=(x+y<5)?2:1;}
  ball_palette[0]=0;ball_palette[1]=c565(YELLOW);ball_palette[2]=c565(WHITE);ball_palette[3]=c565(BLACK);
  ball_sprite.pixels=ball_pixels;ball_sprite.palette=ball_palette;ball_sprite.width=7;ball_sprite.height=7;ball_sprite.frame_count=1;ball_sprite.palette_count=4;ball_sprite.bits_per_pixel=8;ball_sprite.transparent_index=0;
}
static void silence(void){for(int i=0;i<8;i++)prg32_audio_note_off((uint8_t)i);}
static void chord(int root){static const int8_t pan[8]={-64,64,-44,44,-22,22,-8,8};static const uint8_t iv[8]={0,7,12,16,19,24,28,31};for(int i=0;i<8;i++)prg32_audio_note_on_pan((uint8_t)i,(uint8_t)(i&3),(uint8_t)(root+iv[i]),(uint8_t)(80+i*8),pan[i]);}
static void sfx_hit(int side){prg32_audio_note_on_pan((uint8_t)(side?5:2),(uint8_t)(side?1:2),(uint8_t)(55+(rally&7)),220,(int8_t)(side?44:-44));}
static void sfx_bounce(void){prg32_audio_note_on_pan(6,3,42,110,(int8_t)clamp((ball.x-160)/2,-60,60));}
static void sfx_point(int win){prg32_audio_note_on_pan(0,0,(uint8_t)(win?76:45),240,0);prg32_audio_note_on_pan(7,2,(uint8_t)(win?83:40),190,0);}

static void player_reset(void){
  p[0]=(Player){116,171,0,1,0};p[1]=(Player){204,145,0,0,0};
  p[2]=(Player){204,70,1,0,0};p[3]=(Player){116,91,1,0,0};
}
static void begin_point(void){
  player_reset();rally=0;point_timer=0;serve_side=(points[0]+points[1]+games[0]+games[1])&1;
  ball.x=p[server].x+(server<2?8:-8);ball.y=p[server].y+(server<2?-3:3);ball.z=12*FP;ball.vx=ball.vy=ball.vz=0;ball.served=0;ball.bounces=0;ball.last=(uint8_t)(server<2?1:0);
}
static void begin_round(void){memset(points,0,2);memset(games,0,2);memset(sets,0,2);server=round_no&1?2:0;match_winner=2;begin_point();screen=ROUND_INTRO;point_timer=0;chord(43+round_no*2);}

static void award_point(int team){
  sfx_point(team==0);points[team]++;
  if(points[team]>=4&&points[team]>=points[1-team]+2){games[team]++;points[0]=points[1]=0;server=(server+1)&3;}
  if(games[team]>=4&&games[team]>=games[1-team]+2){sets[team]++;games[0]=games[1]=0;}
  if(sets[team]>=1){match_winner=(uint8_t)team;screen=ROUND_RESULT;point_timer=0;chord(team==0?60:36);}
  else {screen=POINT_BANNER;point_timer=0;}
}
static void strike(int i,int lob){
  int team=p[i].team,dir=team?1:-1,target=(i&1)?110:210;
  target+=(int)(rnd()%41)-20;ball.vx=(target-ball.x)*FP/18;ball.vy=dir*(lob?50:68);ball.vz=lob?47:28;
  ball.last=(uint8_t)team;ball.bounces=0;ball.served=1;rally++;p[i].flash=6;sfx_hit(team);
}
static int near_ball(int i){return abs_i(ball.x-p[i].x)<22&&abs_i(ball.y-p[i].y)<18&&ball.z<28*FP;}
static void control_player(int i,uint32_t in){
  int speed=2;if(in&PRG32_BTN_LEFT)p[i].x-=speed;if(in&PRG32_BTN_RIGHT)p[i].x+=speed;
  if(in&PRG32_BTN_UP)p[i].y-=speed;if(in&PRG32_BTN_DOWN)p[i].y+=speed;
  p[i].x=clamp(p[i].x,54,266);if(p[i].team==0)p[i].y=clamp(p[i].y,116,181);else p[i].y=clamp(p[i].y,39,104);
  if(!ball.served&&i==server&&(in&(PRG32_BTN_A|PRG32_BTN_B)))strike(i,(in&PRG32_BTN_B)!=0);
  else if(near_ball(i)&&(in&(PRG32_BTN_A|PRG32_BTN_B)))strike(i,(in&PRG32_BTN_B)!=0);
}
static void ai_player(int i){
  int team=p[i].team,coming=(ball.last!=team),tx=(i&1)?205:115,ty=team?((i&1)?70:91):((i&1)?145:171);
  if(coming){tx=ball.x;ty=ball.y+(team?-5:5);}
  if(p[i].x<tx-2)p[i].x+=2;if(p[i].x>tx+2)p[i].x-=2;if(p[i].y<ty-2)p[i].y+=2;if(p[i].y>ty+2)p[i].y-=2;
  if(!ball.served&&i==server&&point_timer>35)strike(i,0);else if(coming&&near_ball(i))strike(i,(rnd()&7)==0);
}
static void update_ball(void){
  if(!ball.served){ball.x=p[server].x+(server<2?8:-8);ball.y=p[server].y+(server<2?-3:3);point_timer++;return;}
  ball.x+=ball.vx/FP;ball.y+=ball.vy/FP;ball.z+=ball.vz;ball.vz-=3;
  if(ball.z<=0){ball.z=0;ball.vz=-ball.vz*3/5;ball.bounces++;sfx_bounce();if(ball.x<50||ball.x>270||ball.y<31||ball.y>188){award_point(1-ball.last);return;}if(ball.bounces>1){award_point(ball.last);return;}}
  if((ball.y<111&&ball.y-ball.vy/FP>=111)||(ball.y>111&&ball.y-ball.vy/FP<=111)){
    if(ball.z<13*FP){ball.vy=-ball.vy/3;ball.vz=8;prg32_audio_note_on_pan(4,3,35,180,0);}
  }
  if(ball.y<-8||ball.y>208||ball.x<-8||ball.x>328)award_point(1-ball.last);
}

static void network(uint32_t in){
  remote_input=0;if(!net_ok)return;prg32_multiplayer_set_input(in&0x7fu);prg32_multiplayer_set_local_state((int16_t)p[0].x,(int16_t)p[0].y,(uint16_t)screen,(uint16_t)round_no);
  int n=prg32_multiplayer_get_peer_count();for(int i=0;i<n;i++){prg32_player_state_t q;if(prg32_multiplayer_get_peer(i,&q)==0)remote_input|=q.input;}prg32_multiplayer_tick();
}
void azzurra_tennis_init(void){palette();init_sprites();last_input=frame=round_no=0;screen=TITLE;player_reset();prg32_audio_set_master_volume(160);chord(48);prg32_multiplayer_init();net_ok=prg32_multiplayer_available()&&prg32_multiplayer_join(ROOM,PRG32_MP_FLAG_ENABLE)==0;}
void azzurra_tennis_update(void){
  uint32_t in=prg32_input_read(),press=in&~last_input;last_input=in;frame++;network(in);
  if(screen==TITLE){if((frame%150)==0)chord(48+(frame/150%3)*5);if(press&(PRG32_BTN_A|PRG32_BTN_START)){round_no=0;begin_round();}return;}
  if(screen==ROUND_INTRO){if(++point_timer>75||press&PRG32_BTN_A){silence();screen=PLAY;point_timer=0;}return;}
  if(screen==PLAY){uint32_t p2=prg32_input_read_player(1);control_player(0,in);if(p2)control_player(1,p2);else ai_player(1);if(remote_input)control_player(2,remote_input);else ai_player(2);ai_player(3);update_ball();return;}
  if(screen==POINT_BANNER){if(++point_timer>40){begin_point();screen=PLAY;}return;}
  if(screen==ROUND_RESULT){if(++point_timer>100||press&PRG32_BTN_A){if(match_winner==0){round_no++;if(round_no>=14)screen=CUP;else begin_round();}else{screen=TITLE;round_no=0;} }return;}
  if(screen==CUP&&(press&(PRG32_BTN_A|PRG32_BTN_START))){screen=TITLE;round_no=0;chord(48);}
  if(press&PRG32_BTN_SELECT){screen=TITLE;round_no=0;chord(48);}
}

static int sx(int x,int y){return 160+(x-160)*(60+y)/170;}
static int sy(int y){return 31+y*157/200;}
static void city_background(int city){
  box(0,16,W,26,P_SKY);box(0,35,W,7,P_CROWD);
  for(int x=0;x<W;x+=18)box(x,29-(x*7%12),13,13+(x*7%12),P_CROWD);
  switch(city){
    case 0: line(10,35,54,20,P_SHADOW);line(54,20,91,35,P_SHADOW);box(43,26,19,9,P_SHADOW);box(0,37,110,2,P_COURT);break; /* Vesuvio */
    case 1: box(28,23,62,14,P_SHADOW);for(int x=34;x<85;x+=13)box(x,29,7,8,P_SKY);box(112,25,24,12,P_SHADOW);line(112,25,124,17,P_SHADOW);line(124,17,136,25,P_SHADOW);break;
    case 2: line(151,17,132,36,P_SHADOW);line(151,17,170,36,P_SHADOW);line(140,28,162,28,P_SHADOW);box(148,17,6,20,P_SHADOW);break;
    case 3: box(38,18,18,19,P_SHADOW);box(60,24,22,13,P_SHADOW);box(86,16,15,21,P_SHADOW);box(105,27,34,10,P_SHADOW);break;
    case 4: box(41,18,14,19,P_SHADOW);box(44,15,8,3,P_SHADOW);box(46,12,4,4,P_GOLD);box(88,25,2,12,P_NET);for(int a=0;a<16;a++)box(89+(a<8?a:15-a),20+abs_i(7-a),1,1,P_NET);break;
    case 5: box(42,17,10,20,P_SHADOW);box(55,23,18,14,P_SHADOW);box(77,14,16,23,P_SHADOW);box(98,20,13,17,P_SHADOW);box(124,25,5,12,P_SHADOW);line(126,25,132,18,P_SHADOW);break;
    case 6: line(73,36,91,15,P_SHADOW);line(91,15,108,36,P_SHADOW);line(80,27,101,27,P_GOLD);box(89,12,4,25,P_GOLD);box(144,24,28,13,P_SHADOW);line(144,24,158,17,P_SHADOW);line(158,17,172,24,P_SHADOW);break;
    case 7: line(24,36,52,18,P_GOLD);line(52,18,80,36,P_GOLD);line(72,36,101,22,P_SHADOW);line(101,22,129,36,P_SHADOW);break;
    case 8: box(36,23,58,14,P_SHADOW);box(42,27,12,10,P_SKY);box(76,27,12,10,P_SKY);line(48,23,65,17,P_SHADOW);line(65,17,82,23,P_SHADOW);break;
    case 9: for(int x=46;x<110;x+=16){box(x,20+(x&8),9,17-(x&8),P_SHADOW);line(x,20+(x&8),x+4,13+(x&8),P_SHADOW);line(x+8,20+(x&8),x+4,13+(x&8),P_SHADOW);}break;
    case 10: for(int x=45;x<116;x+=14)box(x,21,9,16,P_SHADOW);box(40,18,81,4,P_SHADOW);box(66,14,28,5,P_SHADOW);break;
    case 11: box(45,17,11,20,P_SHADOW);box(48,13,5,4,P_GOLD);box(84,24,26,13,P_SHADOW);line(84,24,97,16,P_SHADOW);line(97,16,110,24,P_SHADOW);box(0,37,180,2,P_COURT);break;
    case 12: for(int x=42;x<108;x+=16){line(x,35,x+10,20,P_LINE);line(x+10,20,x+18,35,P_LINE);}box(117,17,4,20,P_SHADOW);line(119,17,131,29,P_SHADOW);break;
    default: for(int x=48;x<118;x+=13)box(x,21,8,16,P_LINE);box(43,18,82,4,P_LINE);line(43,18,84,12,P_LINE);line(84,12,125,18,P_LINE);break;
  }
  for(int i=0;i<3;i++){int x=1+i*106,w=104;const char *s=sponsors[(city+i)%5];box(x,34,w,8,P_PANEL);text(x+(w-slen(s)*8)/2,34,s,(i&1)?YELLOW:WHITE,BLACK);}
}
static void court(void){
  box(0,0,W,H,P_SKY);city_background(clamp(round_no,0,13));
  box(0,42,W,158,surfaces[clamp(round_no,0,13)]);
  int ax=sx(42,0),bx=sx(278,0),ay=sy(0),cx=sx(42,200),dx=sx(278,200),cy=sy(200);
  line(ax,ay,bx,ay,P_LINE);line(ax,ay,cx,cy,P_LINE);line(bx,ay,dx,cy,P_LINE);line(cx,cy,dx,cy,P_LINE);
  for(int yy=38;yy<=162;yy+=62)line(sx(42,yy),sy(yy),sx(278,yy),sy(yy),P_LINE);
  line(sx(92,0),sy(0),sx(92,200),sy(200),P_LINE);line(sx(228,0),sy(0),sx(228,200),sy(200),P_LINE);
  line(sx(160,38),sy(38),sx(160,162),sy(162),P_LINE);
  int ny=sy(100);box(21,ny,278,2,P_NET);for(int x=24;x<298;x+=6)box(x,ny-5,1,7,P_NET);box(18,ny-8,3,11,WHITE);box(299,ny-8,3,11,WHITE);
}
static void draw_player(int i){
  int x=sx(p[i].x,p[i].y),y=sy(p[i].y);box(x-5,y+1,11,2,P_SHADOW);
  prg32_sprite_draw_indexed(x-6,y-19,&player_sprite[p[i].team],0);if(p[i].flash)p[i].flash--;
}
static void draw_ball(void){int x=sx(ball.x,ball.y),ground=sy(ball.y),y=ground-ball.z/(12*FP);box(x-2,ground,5,2,P_SHADOW);prg32_sprite_draw_indexed(x-3,y-3,&ball_sprite,0);}
static void score_text(char *s,int team){static const char pts[5][3]={"0","15","30","40","AD"};int other=1-team,k=0;s[k++]=(char)(team?'R':'A');s[k++]=' ';s[k++]=(char)('0'+sets[team]);s[k++]=' ';s[k++]=(char)('0'+games[team]);s[k++]=' ';int v=points[team];if(v>=3&&points[other]>=3)v=points[team]>points[other]?4:3;for(int i=0;pts[v][i];i++)s[k++]=pts[v][i];s[k]=0;}
static void hud(void){char a[16],b[16];box(0,0,W,16,P_PANEL);score_text(a,0);score_text(b,1);text(6,4,a,WHITE,BLACK);text(250,4,b,WHITE,BLACK);center(4,round_names[clamp(round_no,0,13)],YELLOW,BLACK);}
static void logo(void){
  box(0,0,W,H,P_SKY);for(int y=0;y<80;y+=8)box(0,120+y,W,8,(uint8_t)(P_COURT+(y/8&1)));
  center(24,"AZZURRA'S",YELLOW,BLACK);center(45,"PRO TENNIS",WHITE,BLACK);center(66,"CHALLENGE",YELLOW,BLACK);
  box(139,89,42,4,WHITE);box(158,82,4,65,WHITE);box(146,104,28,24,BLUE);box(151,92,18,14,CI(5,3,2));line(174,106,205,73,CI(5,3,2));box(201,64,9,15,BLACK);
  center(158,"A / START - SERVE",WHITE,BLACK);center(174,"A DRIVE  B LOB",CI(3,5,5),BLACK);center(188,"1-2 PLAYERS + NETWORK",YELLOW,BLACK);
}
static void overlay(const char *top,const char *bottom){box(34,71,252,56,P_PANEL);box(38,75,244,48,P_COURT2);center(84,top,YELLOW,BLACK);center(104,bottom,WHITE,BLACK);}
void azzurra_tennis_draw(void){
  if(screen==TITLE){logo();return;}court();for(int i=0;i<4;i++)draw_player(i);if(screen==PLAY||screen==POINT_BANNER)draw_ball();hud();
  if(screen==ROUND_INTRO)overlay(round_names[round_no],rivals[round_no]);
  else if(screen==POINT_BANNER)overlay(ball.last==0?"AZZURRA PAIR":"RIVAL PAIR",points[0]==points[1]&&points[0]>=3?"DEUCE":"POINT");
  else if(screen==ROUND_RESULT)overlay(match_winner==0?"ROUND WON!":"CHALLENGE LOST",match_winner==0?"NEXT GRAND SLAM":"A TO TRY AGAIN");
  else if(screen==CUP){box(0,0,W,H,P_PANEL);center(18,"GRAND SLAM CHAMPION",YELLOW,BLACK);box(136,52,48,12,P_GOLD);box(143,64,34,45,P_GOLD);box(151,109,18,27,P_GOLD);box(130,136,60,8,P_GOLD);line(143,67,119,58,P_GOLD);line(177,67,201,58,P_GOLD);center(158,"AZZURRA LIFTS THE CUP!",WHITE,BLACK);center(180,"PRESS A",YELLOW,BLACK);}
}
