"""NTP lifetime, expiry, timezones and seasonal transitions."""
import unittest
from native_support import ROOT, method
import native_support as native


# Drive the production loop with independent monotonic and network clocks.
SNTP = r"""
const int WL_CONNECTED = 1;
struct Wifi { bool connected = false; int status() { return connected; } } WiFi;
time_t networkEpoch = 0;
uint64_t elapsedUs = 0;
unsigned starts = 0, stops = 0;
bool socketAvailable = true;
bool sntp_enabled() { return socketAvailable; }
const char* configuredServer = nullptr;
void sntp_setservername(unsigned, const char* server) { configuredServer = server; }
void sntp_init() { ++starts; }
void sntp_stop() { ++stops; }
#define time(ptr) networkEpoch
#define micros64() elapsedUs
"""
CLOCK_FIELDS = r"""
unsigned long lastRun = 0;
uint64_t lastSyncUs = 0;
uint32_t ntpTime = 0;
bool ntpRunning = false, syncPending = false;
void tick(uint64_t ms) {
    elapsedUs = ms * 1000;
    loop(static_cast<uint32_t>(ms));
}
void synchronize(time_t epoch, uint64_t ms) {
    networkEpoch = epoch;
    syncPending = true;
    tick(ms);
}
"""


class ClockTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_clock_rules_timezones_and_sync_expiry(self):
        clock = ROOT / "WThermostat/WClock.h"
        text = clock.read_text()
        declarations = text[text.index("typedef struct {"):text.index("const char* ID_CLOCK")]
        defaults = "\n".join(line for line in text.splitlines() if line.startswith("const static char* DEFAULT_"))
        source = '#include "properties.h"\n'
        source += declarations + defaults + SNTP + r"""
struct Log{template<class...T>void trace(T...){}template<class...T>void notice(T...){}template<class...T>void error(T...){}template<class...T>void warning(T...){}};
struct Net{Log value;Log*log(){return &value;}template<class...T>void logHeap(T...){}};
struct Probe{
    RTC Rtc;TIME_T RtcTime{};TimeRule timeRuleDst{},timeRuleStd{};
    int16_t timezone_hours=99,timezone_minutes=0;
""" + CLOCK_FIELDS + r"""
    int64_t lastDiff=0;unsigned notifications=0;
    WProperty validity{"valid","Valid",BOOLEAN},off{"offset","Offset",INTEGER},server{"server","Server",STRING};
    WProperty*validTime=&validity,*offset=&off,*ntpServer=&server;
    Net net;Net*network=&net;
    void notifyOnTimeUpdate(){++notifications;}
"""
        for name in ["resetTimeRule", "parseTimeRule", "parseTimeZone", "parseTimeZoneComponents", "getTimeZoneIntegerToString",
                     "BreakTime", "MakeTime", "RuleToTime", "isValidTime", "getEpochTime", "getUptime", "loop"]:
            source += method(clock, name) + "\n"
        source += r"""
};
int main(){
    Probe p;int16_t hour,minute;TimeRule rule;
    auto legacyZone=&Probe::parseTimeZone;assert((p.*legacyZone)("+00:00",&hour,&minute)&&hour==0&&minute==0);
    assert(p.parseTimeZone("99",&hour,&minute)&&hour==99);
    assert(p.parseTimeZone("-00:30",&hour,&minute)&&hour==0&&minute==-30);
    assert(p.getTimeZoneIntegerToString(hour,minute)=="-00:30");
    assert(p.parseTimeZone("+14:00",&hour,&minute)&&hour==14);
    for(const char* invalid:{":","abc","15:00","-14:30","2:99","2:","2junk"})assert(!p.parseTimeZone(invalid,&hour,&minute));
    assert(p.parseTimeRule(DEFAULT_TIME_DST,&p.timeRuleDst));
    assert(p.parseTimeRule(DEFAULT_TIME_STD,&p.timeRuleStd));
    assert(p.timeRuleDst.dow==1&&p.RuleToTime(p.timeRuleDst,2026)==1774749600);
    assert(!p.parseTimeRule("0,13,0,2,120",&rule));assert(!p.parseTimeRule("garbage",&rule));
    TIME_T leap{};leap.year=2024;leap.month=2;leap.day_of_month=29;leap.hour=12;
    TIME_T roundtrip{};p.BreakTime(p.MakeTime(leap),roundtrip);
    assert(roundtrip.year==2024&&roundtrip.month==2&&roundtrip.day_of_month==29&&roundtrip.hour==12);
    for(unsigned year:{2000,2023,2024,2026}) {
        TIME_T end{};end.year=year;end.month=12;end.day_of_month=31;end.hour=23;end.minute=59;end.second=59;
        p.BreakTime(p.MakeTime(end),roundtrip);
        assert(roundtrip.year==year&&roundtrip.month==12&&roundtrip.day_of_month==31&&roundtrip.hour==23);
    }
    p.server.setString("a-long-custom-ntp.example.org");
    p.tick(1);assert(!p.isValidTime() && !starts);
    WiFi.connected=true;socketAvailable=false;p.tick(1000);p.tick(1200);
    assert(starts==1 && !p.ntpRunning);
    socketAvailable=true;p.tick(2000);
    assert(starts==2 && p.ntpRunning && configuredServer==p.ntpServer->c_str() && !p.isValidTime());
    const uint32_t epoch=1767225600;
    p.synchronize(epoch,21000);
    assert(p.isValidTime() && p.Rtc.time_timezone==3600 && p.notifications==1);
    // An invalid server sample cannot overwrite the accepted clock.
    p.synchronize(42,23000);
    assert(p.getEpochTime()==epoch+2 && p.isValidTime() && p.notifications==1);
    WiFi.connected=false;p.tick(24000);p.tick(25000);assert(stops==1);
    p.tick(21000ULL+48ULL*3600000);assert(!p.isValidTime());
    const uint64_t afterWrap=(1ULL<<32)+22000;
    p.tick(afterWrap);
    assert(!p.isValidTime() && p.getEpochTime()==epoch+(afterWrap-21000)/1000);
    WiFi.connected=true;p.tick(afterWrap+1000);assert(starts==3 && !p.isValidTime());
    p.synchronize(epoch+4295000,afterWrap+1100);assert(p.isValidTime());
    // Sydney's southern-hemisphere rules must keep summer in January.
    Probe south;assert(south.parseTimeRule("1,10,1,2,660",&south.timeRuleDst));
    assert(south.parseTimeRule("1,4,1,3,600",&south.timeRuleStd));
    south.synchronize(1767225600,1);
    assert(south.Rtc.time_timezone==660*60);
    Probe winter;south.timeRuleDst.initialized=true;
    winter.timeRuleDst=south.timeRuleDst;winter.timeRuleStd=south.timeRuleStd;
    winter.synchronize(1782864000,1);assert(winter.Rtc.time_timezone==600*60);
    for(const char* zone:{"-14:00","-05:30","-00:30","+00:00","+05:45","+14:00"}){
        Probe fixed;assert(fixed.parseTimeZone(zone,&fixed.timezone_hours,&fixed.timezone_minutes));
        const long expected=fixed.timezone_hours*3600L+fixed.timezone_minutes*60L*(fixed.timezone_hours<0?-1:1);
        fixed.synchronize(epoch,100);assert(fixed.Rtc.time_timezone==expected);
        fixed.synchronize(epoch+293,300101);assert(fixed.lastDiff==-7);
    }
    Probe wrap;wrap.timezone_hours=0;wrap.synchronize(epoch,(1ULL<<32)-16);
    WiFi.connected=false;wrap.tick((1ULL<<32)+4096);
    assert(wrap.isValidTime() && wrap.getEpochTime()==epoch+4);
    puts("PASS timezone input, signed offsets/delta, DST rules, leap day, NTP expiry and millis wrap");
}
"""
        self.compile_run(source, "clock")

    def test_clock_transition(self):
        clock = ROOT / "WThermostat/WClock.h"
        text = clock.read_text()
        s = '#include "properties.h"\n'
        s += text[text.index("typedef struct {") : text.index("const char* ID_CLOCK")]
        s += SNTP + r"""
        struct Log{template<class...T>void error(T...){}template<class...T>void trace(T...){}template<class...T>void notice(T...){}template<class...T>void warning(T...){} };
        struct Net{Log logger;Log*log(){return &logger;}void logHeap(const char*){}};
        struct Probe{
         Net net;Net*network=&net;int64_t lastDiff=0;
""" + CLOCK_FIELDS + r"""
         WProperty valid{"valid","Valid",BOOLEAN},off{"offset","Offset",INTEGER},server{"server","Server",STRING};
         WProperty*validTime=&valid,*offset=&off,*ntpServer=&server;unsigned notifications=0;
         RTC Rtc;TIME_T RtcTime;TimeRule timeRuleStd,timeRuleDst;int16_t timezone_hours=99,timezone_minutes=0;
         Probe(){valid.setBoolean(true);off.setInteger(0);server.setString("example");parseTimeRule("0,3,0,1,60",&timeRuleDst);parseTimeRule("0,10,0,2,0",&timeRuleStd);Rtc.daylight_saving_time=RuleToTime(timeRuleDst,2026);Rtc.standard_time=RuleToTime(timeRuleStd,2026);}
         void notifyOnTimeUpdate(){++notifications;}
        """
        for name in [
            "loop",
            "getEpochTime",
            "isValidTime",
            "getOffset",
            "getUptime",
            "resetTimeRule",
            "parseTimeRule",
            "getTimeZoneIntegerToString",
            "getTimeRuleToString",
            "BreakTime",
            "MakeTime",
            "RuleToTime",
        ]:
            s += method(clock, name) + "\n"
        s += r"""
        };
        int main(){
         Probe p;p.synchronize(1774745999UL,10000);assert(p.Rtc.time_timezone==0);
         p.tick(12000);
         printf("London spring transition: UTC=01:00:01 actual_offset=%d expected=3600\n",p.Rtc.time_timezone);
         assert(p.Rtc.time_timezone==3600);
         p.tick(3611000);
         printf("Next local whole hour: offset=%d\n",p.Rtc.time_timezone);assert(p.Rtc.time_timezone==3600);
        }
        """
        self.compile_run(s, "clock_transition")

    def test_client_name_limit(self):
        source = r'''
#include "properties.h"
struct Esp {unsigned getChipId(){return 123456;}} ESP;
struct NameProbe {
    String applicationName;
'''+method(ROOT / "lib/WAdapter/WAdapter/WNetwork.h", "getClientName")+r'''
};
int main(){
    NameProbe name;name.applicationName="WThermostat";
    assert(name.getClientName(false)=="WThermostat-123456");
    assert(name.getClientName(true)=="wthermostat-123456");
    name.applicationName="";assert(name.getClientName(false)=="ESP-123456");
    name.applicationName=String(std::string(80,'A'));
    const String client=name.getClientName(true);
    assert(client.length()==32&&client.endsWith("-123456"));
    puts("PASS bounded stable client names");
}
'''
        self.compile_run(source, "warning_lifetimes")

    def test_epoch_property_after_2038(self):
        text = (ROOT / "WThermostat/WClock.h").read_text()
        start = text.index("        this->epochTime = ")
        block = text[start:text.index("        this->epochTimeLocalFormatted =", start)]
        source = r'''
#include "properties.h"
#include "lib/WAdapter/WAdapter/WLongProperty.h"
const char* PROP_EPOCHTIME="epochTime";
struct Probe {
    WProperty* epochTime=nullptr;
    unsigned long now=0;
    unsigned long getEpochTime(){return now;}
    void addProperty(WProperty*){}
    void init(){
'''+block+r'''
    }
    ~Probe(){delete epochTime;}
};
int main(){
    Probe p;p.init();
    assert(p.epochTime->getType()==UNSIGNED_LONG);
    assert(p.epochTime->isReadOnly()&&!strcmp(p.epochTime->getAtType(),ATTYPE_LONG));
    for(unsigned long epoch:{0UL,2147483647UL,2147483648UL,2208988800UL,4294967295UL}){
        p.now=epoch;assert(p.epochTime->toString()==String(epoch));
    }
    puts("PASS epoch property retains unsigned 32-bit range and public metadata");
}
'''
        self.compile_run(source, "warning_epoch")
