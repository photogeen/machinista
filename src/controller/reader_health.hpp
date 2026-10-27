#pragma once
#include <cstdint>
#include <cstdio>

namespace maschineos {
// Both supported controllers continuously send 0x20 pad scans even at rest.
// Keep raw USB scan progress separate from process liveness and decoded events.
class ReaderHealth {
    std::uint64_t reports_=0,rejected_=0,pad_reports_=0;
    std::int64_t next_=0,last_report_=0,last_pad_report_=0;
public:
    void report(bool valid,std::int64_t now,bool pad=false){++reports_;if(!valid)++rejected_;last_report_=now;if(valid && pad){++pad_reports_;last_pad_report_=now;}}
    void tick(std::int64_t now){
        if(now<next_)return;
        next_=now+1000000000;
        std::printf("{\"kind\":\"reader_health\",\"reports\":%llu,\"rejected\":%llu,\"last_report_ns\":%lld,\"monotonic_ns\":%lld,\"pad_reports\":%llu,\"last_pad_report_ns\":%lld}\n",
                    static_cast<unsigned long long>(reports_),static_cast<unsigned long long>(rejected_),
                    static_cast<long long>(last_report_),static_cast<long long>(now),
                    static_cast<unsigned long long>(pad_reports_),static_cast<long long>(last_pad_report_));
        std::fflush(stdout);
    }
};
}
