// Lossless MK3 pixel conversion and full-frame run encoding. No device/audio I/O.
#include <cstdint>
#include <cstddef>
#include <cstring>
extern "C" {
void machinista_rgb565(const uint8_t* rgb, uint8_t* out, size_t pixels, int invert) {
 for(size_t i=0;i<pixels;++i){
  uint16_t v=uint16_t((rgb[i*3]&248)<<8)|uint16_t((rgb[i*3+1]&252)<<3)|uint16_t(rgb[i*3+2]>>3);
  if(invert)v=uint16_t(~v);
  out[i*2]=uint8_t(v>>8);out[i*2+1]=uint8_t(v);
 }
}
// Capacity n + four bytes per pair suffices even for the worst input. Literal
// runs are never split by a skip command: every frame writes every pixel.
size_t machinista_mk3_runs(const uint8_t* src,size_t n,uint8_t* out,size_t capacity){
 if(n%4 || capacity<n+n/4*4+4)return 0;
 const size_t pairs=n/4;size_t pos=0,lit=0,used=0;
 auto command=[&](uint8_t op,size_t count){out[used++]=op;out[used++]=uint8_t(count>>16);out[used++]=uint8_t(count>>8);out[used++]=uint8_t(count);};
 auto literal=[&](size_t end){if(end>lit){command(0,end-lit);std::memcpy(out+used,src+lit*4,(end-lit)*4);used+=(end-lit)*4;}};
 while(pos<pairs){
  size_t end=pos+1;
  while(end<pairs && std::memcmp(src+pos*4,src+end*4,4)==0)++end;
  if(end-pos>=4){literal(pos);command(1,end-pos);std::memcpy(out+used,src+pos*4,4);used+=4;pos=end;lit=pos;}
  else pos=end;
 }
 literal(pairs);return used;
}
}
