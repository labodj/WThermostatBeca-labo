"""Compile production headers/methods against small host API substitutes.

No copied algorithm is tested: extraction takes each method from the current
working tree. ASan/UBSan catch the firmware's array and lifetime regressions.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BECA = ROOT / "WThermostat/WBecaDevice.h"
NETWORK = ROOT / "lib/WAdapter/WAdapter/WNetwork.h"


def method(path, name):
    text = path.read_text()
    match = re.search(r"(?m)^[ \t]*(?!return\b)(?:virtual\s+)?(?:[\w:<>&*]+[ \t]+)+" + re.escape(name) + r"\s*\(", text)
    if not match:
        raise AssertionError(f"Missing production method: {path}:{name}")
    opening = text.index("{", match.end())
    depth = 0
    tokens = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]', re.S)
    for token in tokens.finditer(text, opening):
        if token.group() == "{":
            depth += 1
        elif token.group() == "}":
            depth -= 1
            if depth == 0:
                header = re.sub(r"\boverride\b(?=\s*$)", "", text[match.start():opening])
                return header + text[opening:token.end()]
    raise AssertionError(f"Unclosed production method: {name}")


class NativeTests(unittest.TestCase):
    def compile_run(self, source, name):
        with tempfile.TemporaryDirectory(prefix="wthermostat-tests-") as temp:
            path = Path(temp)
            if source is None:
                cpp = ROOT / "tests/native" / (name + ".cpp")
            else:
                cpp = path / f"{name}.cpp"
                cpp.write_text(source)
            binary = path / name
            subprocess.run([os.environ.get("CXX", "g++"), "-std=c++17", "-DESP8266",
                            "-I", str(ROOT / "tests/native"), "-I", str(ROOT),
                            "-g", "-O1", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                            str(cpp), "-o", str(binary)], check=True, cwd=ROOT)
            subprocess.run([str(binary)], check=True, cwd=ROOT, timeout=30)

    def test_json_properties_mqtt_and_stream(self):
        self.compile_run(None, "parsers")

    def test_eeprom_layout_and_roundtrip(self):
        self.compile_run(None, "settings")

    def test_schedules_serial_and_persistence(self):
        source = r'''
#include "properties.h"
const char SCHEDULES_PERIODS[]="123456", SCHEDULES_DAYS[]="wau";
const char* SCHEDULES_MODE_OFF="off",*SCHEDULES_MODE_AUTO="auto";
const int MODEL_BAC_002_ALW=1;
const byte BECABITS1_SWITCHBACKOFF=16;
const unsigned char COMMAND_START[]={0x55,0xaa};
struct Clock {
    byte day=0; unsigned minute=0;
    byte getWeekDay(){return day;} bool isValidTime(){return true;}
    bool isTimeEarlierThan(byte h,byte m){return minute<h*60U+m;}
    bool isTimeLaterThan(byte h,byte m){return minute>=h*60U+m;}
    bool isTimeBetween(byte h,byte m,byte hh,byte mm){return isTimeLaterThan(h,m)&&isTimeEarlierThan(hh,mm);}
};
struct Log{template<class...T>void notice(T...){}};
struct Net{Log value;Log*log(){return &value;}};
struct Probe {
    byte schedules[54]{};
    bool schedulesChanged=false;
    byte offset=0,model=0;
    float factor=2;
    int currentSchedulePeriod=-1,receiveIndex=-1,commandLength=-1,frames=0;
    unsigned char receivedCommand[1024];
    unsigned long lastSerialByte=0,lastMcuReceived=0;
    Clock clock;Clock*wClock=&clock;Net net;Net*network=&net;
    WProperty autoBack{"auto","Auto",BOOLEAN},mode{"mode","Mode",STRING},bits{"bits","Bits",BYTE};
    WProperty*switchBackToAuto=&autoBack,*schedulesMode=&mode,*becaBits1=&bits;
    bool receivedSchedules(){return true;}
    byte getSchedulesDayOffset(){return offset;}
    byte getThermostatModel(){return model;}
    float getTemperatureFactor(){return factor;}
    void updateTargetTemperature(){}
    void resetAll(){receiveIndex=-1;commandLength=-1;}
    void processSerialCommand(unsigned long){++frames;}
'''
        for name in ["getSchedulesPeriod", "getSchedulesStartAddress", "getSchedulesValue",
                     "validSchedulesKeyValue", "validSchedulesOrder", "processSchedulesKeyValue",
                     "updateCurrentSchedulePeriod", "saveSettings", "serviceSerial"]:
            source += method(BECA, name) + "\n"
        source += r'''
};
int main(){
    Probe p; p.mode.setString("auto"); p.autoBack.setBoolean(false);
    for(unsigned d=0;d<3;++d)for(unsigned n=0;n<6;++n){p.schedules[d*18+n*3+1]=n+1;p.schedules[d*18+n*3+2]=40;}
    for(unsigned day=0;day<7;++day)for(unsigned offset=0;offset<7;++offset){
        p.clock.day=day;p.offset=offset;p.clock.minute=0;p.updateCurrentSchedulePeriod();
        unsigned previous=(day+offset+6)%7;
        assert(p.currentSchedulePeriod==(previous==0?36:previous==6?18:0)+15);
    }
    const auto before=p.schedules[2];
    for(const char* key:{"w7t","x1t","w1x","","w1","w11t"})assert(!p.processSchedulesKeyValue(key,"20"));
    assert(p.schedules[2]==before);
    assert(!p.processSchedulesKeyValue("w1h","99:99"));assert(!p.processSchedulesKeyValue("w1h","-1:00"));
    assert(!p.processSchedulesKeyValue("w1h","aa:bb"));assert(!p.processSchedulesKeyValue("w1t","garbage"));
    assert(!p.processSchedulesKeyValue("w1t","nan"));assert(!p.processSchedulesKeyValue("w1t","999"));
    assert(p.processSchedulesKeyValue("w1h","0:30"));assert(p.processSchedulesKeyValue("w1t","20.5"));
    assert(p.schedules[0]==30&&p.schedules[1]==0&&p.schedules[2]==41);
    assert(p.validSchedulesOrder());assert(!p.processSchedulesKeyValue("w1t","20.1"));
    p.factor=1;p.schedules[2]=21;assert(p.getSchedulesValue("w1t").toDouble()==21);
    unsigned saves=0;p.bits.setByte(0xa5);p.bits.setSettingsNotification([&](WProperty*){++saves;});
    p.autoBack.setBoolean(false);p.saveSettings(nullptr);assert(p.bits.getByte()==0xb5);
    p.autoBack.setBoolean(true);p.saveSettings(nullptr);assert(p.bits.getByte()==0xa5&&saves==2);
    // Oversize, bad checksum, partial frame timeout, resynchronization and bursts.
    Serial.input={0x55,0xaa,0,7,0xff,0xff};Serial.input.resize(1100,0);Serial.position=0;p.serviceSerial(1);assert(p.frames==0);
    Serial.input={0x55,0xaa,0,3,0,0,2};Serial.position=0;p.serviceSerial(2);assert(p.frames==1);
    Serial.input={0x55,0xaa,0,3,0,0,99};Serial.position=0;p.serviceSerial(3);assert(p.frames==1);
    Serial.input={0x55,0xaa,0,3,0};Serial.position=0;p.serviceSerial(4);
    Serial.input={0x55,0x55,0xaa,0,3,0,0,2};Serial.position=0;p.serviceSerial(2000);assert(p.frames==2);
    Serial.input={0x55,0xaa,0,3,0,0,2,0x55,0xaa,0,3,0,0,2};Serial.position=0;p.serviceSerial(2001);assert(p.frames==4);
    puts("PASS schedule matrix, input validation, precision, persistence and UART recovery");
}
'''
        self.compile_run(source, "schedules")

    def test_http_authorization_and_request_isolation(self):
        source = r'''
#include "Arduino.h"
#include <map>
const int HTTP_GET=1,HTTP_POST=2,HTTP_PUT=4;
const char* CT_TEXT_PLAIN="text/plain",*URI_FIRMWARE="/firmware";
const size_t SIZE_JSON_PACKET=3096;
enum class wnWifiMode{WIFIMODE_AP,WIFIMODE_FALLBACK,WIFIMODE_STATION};
struct Parameter{String text;String value(){return text;}};
struct AsyncWebServerRequest{
    void*_tempObject=nullptr;bool sent=false,authenticated=true;int status=0,verb=HTTP_PUT;
    String path="/things/thermostat/properties",hostname="thermostat";
    std::map<std::string,Parameter>headers,params;
    ~AsyncWebServerRequest(){free(_tempObject);}
    bool isSent(){return sent;}void send(int s,const char* =nullptr,const char* =nullptr){sent=true;status=s;}
    bool hasHeader(const char*s){return headers.count(s);}Parameter*getHeader(const char*s){return &headers.at(s);}
    bool hasParam(const char*s,bool){return params.count(s);}Parameter*getParam(const char*s,bool){return &params.at(s);}
    String host(){return hostname;}String url(){return path;}int method(){return verb;}
    bool authenticate(const char*,const char*){return authenticated;}
    struct Client{int ip=1;int localIP(){return ip;}} connection;
    Client*client(){return &connection;}
    void requestAuthentication(const char*){send(401);}
};
struct Wifi{int softAPIP(){return 1;}} WiFi;
struct Probe{
    bool updating=false;AsyncWebServerRequest*updateRequest=nullptr;
    bool isUpdateRunning(){return updating;}
    bool localRecoveryActive=false;unsigned long localRecoveryStartedAt=0;
    void requestAdminLogin(AsyncWebServerRequest* r){r->requestAuthentication("WThermostat");}
    struct HttpBody{size_t capacity,received;char data[1];};
    String csrfToken="token",ssid="wifi",password="test-pass";bool ap=false,authRequired=true;
    bool isAuthenticationRequired(){return authRequired;}
    wnWifiMode wifiModeRunning=wnWifiMode::WIFIMODE_STATION;
    bool isSoftAP(){return ap;}const char*getSsid(){return ssid.c_str();}const char*getPassword(){return password.c_str();}
'''
        for name in ["isLocalRecoveryRequest", "authorize", "handlePutBody", "handlePutBodyDone"]:
            source += method(NETWORK, name) + "\n"
        source += r'''
};
int main(){
    Probe network;uint8_t small[4]={'1','2','3','4'},large[24]{};
    AsyncWebServerRequest a,b;
    network.handlePutBody(&a,small,2,0,4);network.handlePutBody(&b,large,24,0,24);
    network.handlePutBody(&a,small+2,2,2,4);
    auto*one=static_cast<Probe::HttpBody*>(a._tempObject);auto*two=static_cast<Probe::HttpBody*>(b._tempObject);
    assert(one!=two&&one->received==4&&two->received==24&&!strcmp(one->data,"1234"));
    network.handlePutBodyDone(&a);assert(a._tempObject==nullptr);
    AsyncWebServerRequest denied;denied.authenticated=false;network.handlePutBody(&denied,small,4,0,4);assert(denied.status==401&&!denied._tempObject);
    AsyncWebServerRequest huge;network.handlePutBody(&huge,small,4,0,3097);assert(huge.status==413&&!huge._tempObject);
    AsyncWebServerRequest order;network.handlePutBody(&order,small,2,0,4);network.handlePutBody(&order,small,2,1,4);assert(order.status==400);
    AsyncWebServerRequest evil;evil.headers["Origin"]={"http://evil.example"};assert(!network.authorize(&evil,true)&&evil.status==403);
    AsyncWebServerRequest form;form.verb=HTTP_POST;form.path="/save_network";assert(!network.authorize(&form,true)&&form.status==403);
    form.sent=false;form.params["csrf"]={"token"};assert(network.authorize(&form,true));
    AsyncWebServerRequest setup;setup.authenticated=false;network.ap=true;network.ssid="";assert(network.authorize(&setup));
    network.ssid="wifi";network.wifiModeRunning=wnWifiMode::WIFIMODE_FALLBACK;assert(!network.authorize(&setup)&&setup.status==401);
    setup.sent=false;setup.authenticated=true;assert(network.authorize(&setup));
    network.localRecoveryActive=true;network.localRecoveryStartedAt=100;testMillis=100;
    setup.sent=false;setup.authenticated=false;network.wifiModeRunning=wnWifiMode::WIFIMODE_AP;
    assert(network.authorize(&setup));
    setup.connection.ip=2;assert(!network.authorize(&setup)&&setup.status==401);
    setup.sent=false;setup.connection.ip=1;testMillis=300100;assert(!network.authorize(&setup)&&setup.status==401);
    network.updating=true;network.updateRequest=&setup;setup.sent=false;assert(network.authorize(&setup));
    AsyncWebServerRequest newcomer;newcomer.authenticated=false;assert(!network.authorize(&newcomer)&&newcomer.status==401);
    network.updating=false;network.updateRequest=nullptr;
    testMillis=100;setup.sent=false;setup.verb=HTTP_POST;assert(!network.authorize(&setup,true)&&setup.status==403);
    setup.sent=false;setup.params["csrf"]={"token"};assert(network.authorize(&setup,true));
    network.localRecoveryActive=false;
    network.authRequired=false;network.ap=false;network.password="";
    AsyncWebServerRequest open;open.authenticated=false;assert(network.authorize(&open));
    open.verb=HTTP_POST;assert(!network.authorize(&open,true)&&open.status==403);
    open.sent=false;open.params["csrf"]={"token"};assert(network.authorize(&open,true));
    AsyncWebServerRequest cross;cross.authenticated=false;cross.headers["Origin"]={"http://evil.example"};
    assert(!network.authorize(&cross,true)&&cross.status==403);
    puts("PASS authentication, CSRF, body size/order, concurrent requests and provisioning");
}
'''
        self.compile_run(source, "http")

    def test_ota_ownership_authorization_and_disconnect(self):
        source = r"""
#include "Arduino.h"
const char* CT_TEXT_PLAIN="text/plain";
struct AsyncWebServerRequest {
    int status=0;bool sent=false,allowed=true;std::function<void()>disconnect;
    bool isSent(){return sent;}void send(int s,const char* =nullptr,const char* =nullptr){sent=true;status=s;}
    void onDisconnect(std::function<void()>f){disconnect=f;}
};
struct ESPType{uint32_t getFreeSketchSpace(){return 500000;}}ESP;
struct Updater{
    bool running=false,error=false;unsigned written=0,ends=0;
    void runAsync(bool){}bool begin(unsigned){running=true;error=false;written=0;return true;}
    size_t write(uint8_t*,size_t n){written+=n;return n;}bool hasError(){return error;}
    bool isRunning(){return running;}bool end(bool final){++ends;running=false;return final&&!error;}
}Update;
struct Probe{
    bool updateRunning=false,updateSucceeded=false,restarted=false;const __FlashStringHelper*firmwareUpdateError=nullptr;
    AsyncWebServerRequest*updateRequest=nullptr;
    bool authorize(AsyncWebServerRequest*r,bool){if(!r->allowed){r->send(401);return false;}return true;}
    void disconnectMqtt(){}void setFirmwareUpdateError(const char*){Update.error=true;}
    void restart(AsyncWebServerRequest*r,const __FlashStringHelper*){restarted=true;r->send(200);}
"""
        for name in ["handleHttpFirmwareUpdateProgress", "handleHttpFirmwareUpdateFinished"]:
            source += method(NETWORK, name) + "\n"
        source += r"""
};
int main(){
    uint8_t bytes[8]{};Probe network;
    AsyncWebServerRequest denied;denied.allowed=false;
    network.handleHttpFirmwareUpdateProgress(&denied,"x",0,bytes,8,true);
    assert(denied.status==401&&Update.written==0&&!network.updateRunning);
    AsyncWebServerRequest a,b;network.handleHttpFirmwareUpdateProgress(&a,"x",0,bytes,4,false);
    assert(network.updateRunning&&Update.written==4);
    network.handleHttpFirmwareUpdateProgress(&b,"x",0,bytes,8,true);
    assert(b.status==409&&Update.written==4);
    network.handleHttpFirmwareUpdateFinished(&b);assert(!network.restarted);
    a.disconnect();assert(!network.updateRunning&&!Update.running);
    AsyncWebServerRequest c;network.handleHttpFirmwareUpdateProgress(&c,"x",0,bytes,8,true);
    network.handleHttpFirmwareUpdateFinished(&c);assert(c.status==200&&network.restarted);
    network.restarted=false;
    AsyncWebServerRequest d;network.handleHttpFirmwareUpdateProgress(&d,"x",0,bytes,8,false);
    Update.error=true;network.handleHttpFirmwareUpdateFinished(&d);
    assert(d.status==400&&!network.restarted&&!Update.running);
    puts("PASS OTA rejects unauthorized/concurrent requests and handles interruption/failure");
}
"""
        self.compile_run(source, "ota")

    def test_clock_rules_timezones_and_sync_expiry(self):
        clock = ROOT / "WThermostat/WClock.h"
        text = clock.read_text()
        declarations = text[text.index("typedef struct {"):text.index("WiFiUDP ntpUDP")]
        defaults = "\n".join(line for line in text.splitlines() if line.startswith("const static char* DEFAULT_"))
        source = '#include "properties.h"\n#define SECS_PER_DAY 86400UL\n#define SECS_PER_HOUR 3600UL\n#define SECS_PER_MIN 60UL\n'
        source += declarations + defaults + r"""
const int WL_CONNECTED=1;
struct Wifi{bool connected=false;int status(){return connected?1:0;}}WiFi;
struct Ntp{uint32_t epoch=1767225600,next=0;bool success=false;bool update(){if(success&&next){epoch=next;next=0;}return success;}uint32_t getEpochTime(){return epoch;}}ntpClient;
struct Log{template<class...T>void trace(T...){}template<class...T>void notice(T...){}template<class...T>void error(T...){}template<class...T>void warning(T...){}};
struct Net{Log value;Log*log(){return &value;}template<class...T>void logHeap(T...){}};
struct Probe{
    RTC Rtc;TIME_T RtcTime{};TimeRule timeRuleDst{},timeRuleStd{};
    int16_t timezone_hours=99,timezone_minutes=0;
    unsigned long lastTry=0,lastNtpSync=0,ntpTime=0,lastRun=0;
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
    testMillis=1;p.loop(millis());assert(!p.isValidTime()&&p.lastNtpSync==0);
    WiFi.connected=true;ntpClient.success=true;testMillis=21000;p.loop(millis());
    assert(p.isValidTime()&&p.lastNtpSync==21000&&p.Rtc.time_timezone==3600&&p.notifications==1);
    WiFi.connected=false;testMillis+=48UL*60*60*1000+1;p.loop(millis());assert(!p.isValidTime());
    // Sydney's southern-hemisphere rules must keep summer in January.
    Probe south;assert(south.parseTimeRule("1,10,1,2,660",&south.timeRuleDst));
    assert(south.parseTimeRule("1,4,1,3,600",&south.timeRuleStd));
    WiFi.connected=true;testMillis=1;ntpClient.epoch=1767225600;south.loop(millis());
    assert(south.Rtc.time_timezone==660*60);
    Probe winter;south.timeRuleDst.initialized=true;
    winter.timeRuleDst=south.timeRuleDst;winter.timeRuleStd=south.timeRuleStd;
    testMillis=1;ntpClient.epoch=1782864000;winter.loop(millis());assert(winter.Rtc.time_timezone==600*60);
    for(const char* zone:{"-14:00","-05:30","-00:30","+00:00","+05:45","+14:00"}){
        Probe fixed;assert(fixed.parseTimeZone(zone,&fixed.timezone_hours,&fixed.timezone_minutes));
        const long expected=fixed.timezone_hours*3600L+fixed.timezone_minutes*60L*(fixed.timezone_hours<0?-1:1);
        testMillis=100;ntpClient.epoch=1767225600;fixed.loop(millis());assert(fixed.Rtc.time_timezone==expected);
        ntpClient.next=ntpClient.epoch-7;testMillis+=300001;fixed.loop(millis());assert(fixed.lastDiff==-7);
    }
    if(sizeof(unsigned long)==4){
        Probe wrap;wrap.timezone_hours=0;testMillis=0xfffffff0UL;ntpClient.epoch=1767225600;wrap.loop(millis());
        WiFi.connected=false;testMillis=0x1000UL;wrap.loop(millis());assert(wrap.isValidTime());
    }
    puts("PASS timezone input, signed offsets/delta, DST rules, leap day, NTP expiry and millis wrap");
}
"""
        self.compile_run(source, "clock")

    def test_mcu_handshake_readiness_and_numeric_protocol(self):
        source = r"""
#include "properties.h"
#define STATE_COMPLETE 6
#define SECONDS_DIVIDER 1
struct Clock {
    bool valid=false;bool isValidTime(){return valid;}
    unsigned long getEpochTime(){return 1704067200;}unsigned long getEpochTimeLocal(){return getEpochTime();}
    byte getYear(unsigned long){return 24;}byte getMonth(unsigned long){return 1;}byte getDay(unsigned long){return 1;}
    byte getHours(unsigned long){return 12;}byte getMinutes(unsigned long){return 10;}byte getSeconds(unsigned long){return 30;}
};
struct Log{template<class...T>void notice(T...){}template<class...T>void warning(T...){}template<class...T>void trace(T...){}bool isEnabled(int){return false;}};
struct Net{Log value;Log*log(){return &value;}bool isDebug(){return false;}};
const int LOG_LEVEL_TRACE=5;
struct Probe{
    Net net;Net*network=&net;Clock clock;Clock*wClock=&clock;
    bool mcuInitialized=false,receivingDataFromMcu=false,receivedStates[STATE_COMPLETE]{};
    int mcuInitializeState=0;unsigned long lastMcuAttempt=0,lastMcuReceived=0,lastTimeSent=0;
    unsigned mcuRetryCount=0;
    bool timeIsRequested=false,timeIsRequestedLocaltime=false,timeIsRequestedSendZeroSecs=false;
    unsigned char receivedCommand[1024];double targetTemperatureManualMode=35;float factor=10;
    float getTemperatureFactor(){return factor;}byte getSchedulesDayOffset(){return 0;}byte getDayOfWeek(){return 1;}
    void updateTargetTemperature(){}void updateModeAndAction(){}
"""
        for name in ["getCommandAsString", "commandCharsToSerial", "queryAllDPs", "startMcuInitialize",
                     "mcuInitialize", "isDeviceStateComplete", "decodeMcuValue", "targetTemperatureManualModeToMcu",
                     "sendActualTimeToBecaRequested", "sendActualTimeToBeca"]:
            source += method(BECA, name) + "\n"
        source += r"""
};
int main(){
    Probe p;testMillis=1;p.startMcuInitialize();p.mcuInitialize();
    assert(p.mcuInitializeState==2&&Serial.output.size()==7);
    testMillis=2000;p.mcuInitialize();assert(Serial.output.size()==7);
    testMillis=4001;p.mcuInitialize();assert(Serial.output.size()==14);
    p.mcuInitializeState=5;p.mcuInitialize();assert(p.mcuInitializeState==6&&Serial.output.size()==21);
    p.mcuInitialized=true;p.lastMcuReceived=millis();assert(!p.isDeviceStateComplete());
    for(bool& state:p.receivedStates)state=true;
    assert(p.isDeviceStateComplete());testMillis+=60001;assert(!p.isDeviceStateComplete());
    p.startMcuInitialize();for(bool state:p.receivedStates)assert(!state);
    byte positive[]={0,0,0,128},negative[]={255,255,255,246},large[]={0,0,1,94};
    assert(p.decodeMcuValue(positive)==128);assert(p.decodeMcuValue(negative)==-10);assert(p.decodeMcuValue(large)==350);
    Serial.output.clear();p.targetTemperatureManualModeToMcu();assert(Serial.output.size()==15);
    assert(Serial.output[10]==0&&Serial.output[11]==0&&Serial.output[12]==1&&Serial.output[13]==94);
    byte checksum=0;for(unsigned i=0;i<14;++i)checksum+=Serial.output[i];assert(checksum==Serial.output[14]);
    Serial.output.clear();p.sendActualTimeToBeca(true);assert(Serial.output.empty()&&p.timeIsRequested);
    p.clock.valid=true;p.sendActualTimeToBeca(true);assert(Serial.output.size()==15&&Serial.output[3]==0x1c&&Serial.output[6]==1&&Serial.output[7]==24);
    assert(Serial.output[12]==30/SECONDS_DIVIDER);
    Serial.output.clear();p.sendActualTimeToBeca(false);assert(Serial.output[3]==0x0c&&Serial.output[12]==30);
    p.timeIsRequestedSendZeroSecs=true;Serial.output.clear();p.sendActualTimeToBeca(true);assert(Serial.output[12]==0);
    puts("PASS MCU retry/readiness, full-width signed values, setpoint encoding, checksum and deferred time");
}
"""
        self.compile_run(source, "mcu")
        self.compile_run(source.replace("#define SECONDS_DIVIDER 1", "#define SECONDS_DIVIDER 4"), "mcu_divisor4")

    def test_discovery_serialization_and_identifiers(self):
        from test_homeassistant import discovery_records
        import json
        for case, topic, retained, payload in discovery_records():
            if case >= 24 or not topic.startswith("homeassistant/") or not payload:
                continue
            value = json.loads(payload)
            self.assertTrue(retained)
            self.assertTrue(value["unique_id"].startswith("room_A-1_"))
            self.assertEqual("home/room_A-1", value["~"])
            if "/climate/" in topic:
                self.assertEqual("room_A-1", value["dev"]["name"])
                self.assertEqual("all", value["avty_mode"])
                self.assertEqual(2, len(value["avty"]))


if __name__ == "__main__":
    unittest.main()
