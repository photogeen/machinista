// Full-frame-only MK3 encoder. stdin RGB, stdout bounded packet. No device I/O.
#include <vector>
#include <cstdint>
#include <cstring>
#include <cerrno>
#include <unistd.h>
#include <sys/resource.h>
#include "mk3_pixels.cpp"
namespace {
bool read_all(uint8_t* p,size_t n){while(n){ssize_t r=read(0,p,n);if(r<0&&errno==EINTR)continue;if(r<=0)return false;p+=r;n-=size_t(r);}return true;}
bool write_all(const uint8_t* p,size_t n){while(n){ssize_t r=write(1,p,n);if(r<0&&errno==EINTR)continue;if(r<=0)return false;p+=r;n-=size_t(r);}return true;}
void be32(uint8_t* p,size_t n){p[0]=uint8_t(n>>24);p[1]=uint8_t(n>>16);p[2]=uint8_t(n>>8);p[3]=uint8_t(n);}
}
int main(){
 struct rlimit memory{128*1024*1024,128*1024*1024};setrlimit(RLIMIT_AS,&memory);
 struct rlimit core{0,0};setrlimit(RLIMIT_CORE,&core);
 constexpr size_t bytes=480*272*2;
 std::vector<uint8_t> rgb(480*272*3),pixels(bytes),runs(bytes*2+4),packet(bytes+28);
 uint8_t request[4];
 while(read_all(request,4)){
  if(request[0]>1||request[1]>1||request[2]||request[3])return 2;
  if(!read_all(rgb.data(),rgb.size()))return 3;
  machinista_rgb565(rgb.data(),pixels.data(),480*272,request[1]);
  size_t count=machinista_mk3_runs(pixels.data(),pixels.size(),runs.data(),runs.size());
  const uint8_t header[]={0x84,0,request[0],0x60,0,0,0,0,0,0,0,0,1,0xe0,1,0x10};
  std::memcpy(packet.data(),header,16);size_t used=16;
  if(count && count<bytes+4){std::memcpy(packet.data()+used,runs.data(),count);used+=count;}
  else {be32(packet.data()+used,480*272/2);used+=4;std::memcpy(packet.data()+used,pixels.data(),bytes);used+=bytes;}
  const uint8_t footer[]={3,0,0,0,0x40,0,0,0};std::memcpy(packet.data()+used,footer,8);used+=8;
  uint8_t length[4];be32(length,used);
  if(!write_all(length,4)||!write_all(packet.data(),used))return 4;
 }
 return 0;
}
