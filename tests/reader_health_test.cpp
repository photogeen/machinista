#include "controller/reader_health.hpp"
#include <string>
#include <unistd.h>
int main(){
    auto* capture=std::tmpfile();if(!capture)return 2;
    const int original=dup(fileno(stdout));if(original<0)return 2;
    if(dup2(fileno(capture),fileno(stdout))<0)return 2;
    maschineos::ReaderHealth health;
    health.tick(10000000000LL);
    health.report(true,10100000000LL,true);
    health.report(false,10200000000LL);
    health.tick(10999999999LL);
    health.tick(11000000000LL);
    health.tick(11000000001LL);
    std::fflush(stdout);dup2(original,fileno(stdout));close(original);
    std::rewind(capture);std::string actual;char buffer[1024];
    while(auto count=std::fread(buffer,1,sizeof(buffer),capture))actual.append(buffer,count);
    std::fclose(capture);std::fputs(actual.c_str(),stdout);
    const std::string expected=
      "{\"kind\":\"reader_health\",\"reports\":0,\"rejected\":0,\"last_report_ns\":0,\"monotonic_ns\":10000000000,\"pad_reports\":0,\"last_pad_report_ns\":0}\n"
      "{\"kind\":\"reader_health\",\"reports\":2,\"rejected\":1,\"last_report_ns\":10200000000,\"monotonic_ns\":11000000000,\"pad_reports\":1,\"last_pad_report_ns\":10100000000}\n";
    return actual==expected?0:1;
}
