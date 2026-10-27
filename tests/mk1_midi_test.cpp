#include "controller/mk1_midi.hpp"
#include "audio/midi_output.hpp"
#include <cassert>
#include <vector>
#include <cstring>
#include <poll.h>
using namespace maschineos;
int main(){
 Mk1Midi bridge;assert(bridge.open_port());int client=open(bridge.path().c_str(),O_RDWR|O_NONBLOCK|O_NOCTTY);assert(client>=0);
 const std::array<unsigned char,6> usb{6,0,3,0x90,60,100};assert(bridge.receive(usb));
 pollfd ready{client,POLLIN,0};assert(poll(&ready,1,100)==1);
 unsigned char data[128]{};assert(read(client,data,sizeof(data))==3);assert(data[0]==0x90 && data[1]==60 && data[2]==100);
 assert(!bridge.receive(std::array<unsigned char,4>{6,0,3,0x90}));
 assert(!bridge.receive(std::array<unsigned char,4>{6,1,1,0xf8}));
 assert(!bridge.receive(std::array<unsigned char,3>{6,0,62}));
 const std::array<unsigned char,8> raw{0xf0,0x7d,0,0x7f,0xf7,0xf8,0x80,60};
 assert(write(client,raw.data(),raw.size())==ssize_t(raw.size()));
 pollfd master{bridge.fd(),POLLIN,0};assert(poll(&master,1,100)==1);
 std::array<unsigned char,64> packet{};assert(bridge.outgoing(packet)==11);assert(packet[0]==7 && packet[1]==0 && packet[2]==8);assert(!memcmp(packet.data()+3,raw.data(),8));
 std::vector<unsigned char> sysex(500,42);sysex[0]=0xf0;sysex.back()=0xf7;assert(write(client,sysex.data(),sysex.size())==500);
 std::vector<unsigned char> restored;
 while(restored.size()<500){assert(poll(&master,1,100)==1);int n=bridge.outgoing(packet);assert(n>3 && n<=64);restored.insert(restored.end(),packet.begin()+3,packet.begin()+n);}
 assert(restored==sysex);assert(bridge.received==3);
 // The sequencer's actual background writer must use the same bridge unchanged.
 {maschine::MidiOutput output;assert(output.configure(bridge.path().c_str()));
  std::this_thread::sleep_for(std::chrono::milliseconds(5));
  while(bridge.outgoing(packet)>0){} // initial all-notes-off
  assert(output.send(0,0x92,67,110));assert(poll(&master,1,100)==1);
  int n=bridge.outgoing(packet);assert(n==6 && packet[3]==0x92 && packet[4]==67 && packet[5]==110);
 }
 close(client);
}
