"""Render production UI methods with fake device data, without a thermostat.

This preview never forwards requests to a device. POST requests are rejected.
"""
import argparse
import configparser
import json
import os
import re
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from test_regressions import BECA, NETWORK, ROOT, method


def raw_asset(path, name):
    match = re.search(re.escape(name) + r'\[\].*?R"=====\((.*?)\)=====";', path.read_text(), re.DOTALL)
    if not match:
        raise ValueError(f"Missing production asset {name}")
    return match.group(1)


def render_pages(response_heap_budget=0, largest_heap_block=24000, response_allocation_fails=False, fail_header_write=False):
    beca = BECA.read_text()
    network = NETWORK.read_text()
    log = ROOT / "WThermostat/WLogDevice.h"
    clock = ROOT / "WThermostat/WClock.h"
    source = r'''
#include "Arduino.h"
#include "Stream.h"
#include <map>
#include "lib/WAdapter/WAdapter/WPageResponse.h"
size_t allocationBudget=HEAP_BUDGET?HEAP_BUDGET:SIZE_MAX;
void*operator new(size_t size,const std::nothrow_t&)noexcept{
    if(FAIL_RESPONSE || size>MAX_BLOCK || size>allocationBudget || (FAIL_HEADER_WRITE && size>200))return nullptr;
    allocationBudget-=size;return ::operator new(size);
}
struct AsyncWebServerRequest{
    void removeHeaders(){}
    struct Client{int localIP(){return 1;}};Client*client(){return nullptr;}
    std::string body;int status=0;
    AsyncWebServerRequest(){allocationBudget=HEAP_BUDGET?HEAP_BUDGET:SIZE_MAX;}
    void send(WPageResponse*r){
        assert(r->_sourceValid());r->startForTest();uint8_t data[536];
        while(size_t size=r->_fillBuffer(data,sizeof(data)))body.append(reinterpret_cast<char*>(data),size);
        assert(body.size()==r->contentLength());status=200;delete r;
    }
    void send(int code){status=code;body.clear();}
    void send(int code,const char*,const char*){send(code);}
};
#include "lib/WAdapter/WAdapter/WHtmlPages.h"
#include "lib/WAdapter/WAdapter/WPage.h"
struct Ip{bool isSet()const{return true;}String toString()const{return "192.0.2.10";}};
using IPAddress=Ip;
struct Wifi{int softAPIP(){return 1;}Ip localIP(){return {};}Ip subnetMask(){return {};}Ip gatewayIP(){return {};}Ip dnsIP(int){return {};}
String macAddress(){return "AA:BB:CC:DD:EE:FF";}String BSSIDstr(){return "02:11:22:33:44:55";}int RSSI(){return -62;}}WiFi;
struct Chip{unsigned getChipId(){return 12345;}unsigned getFlashChipId(){return 123;}
unsigned getFlashChipSize(){return 1048576;}unsigned getFlashChipRealSize(){return 1048576;}
unsigned getSketchSize(){return 472112;}unsigned getFreeSketchSpace(){return 552960;}
String getResetReason(){return "Software/System restart";}String getResetInfo(){return "No exception";}unsigned getFreeHeap(){return 33000;}unsigned getMaxFreeBlockSize(){return MAX_BLOCK;}unsigned getHeapFragmentation(){return 3;}}ESP;
struct Log{template<class...T>void notice(T...){}};
enum class wnWifiMode{WIFIMODE_STATION,WIFIMODE_FALLBACK};using wnWifiMode_t=wnWifiMode;
const char*CT_TEXT_HTML="text/html",*CT_TEXT_PLAIN="text/plain",*ID_NETWORK="network";
enum WebRequestMethod{HTTP_GET,HTTP_POST};
const char*FORM_PW_NOCHANGE="___NOCHANGE___";
struct WDevice{
    WDevice*next=nullptr;WPage*firstPage=nullptr;const char*id;const char*name;
    WDevice(const char*i,const char*n):id(i),name(n){}
    std::function<void(WCheckedPrint*)>info;
    std::function<void(AsyncWebServerRequest*,WCheckedPrint*)>config;
    bool isProvidingConfigPage(){return true;}bool hasInfoPage(){return static_cast<bool>(info);}
    const char*getId(){return id;}const char*getName(){return name;}
    void printInfoPage(WCheckedPrint*p){if(info)info(p);}
    void printConfigPage(AsyncWebServerRequest*r,WCheckedPrint*p){if(config)config(r,p);}
};
struct Net{
    Log logger;Log*wlog=&logger;WDevice*firstDevice=nullptr;
    String applicationName="WThermostatBeca",firmwareVersion=PREVIEW_VERSION,csrfToken="preview-token",address;
    bool debug=false,enabled=true,staticEnabled=false,bssidLocked=false;const char*restartFlag=nullptr;
    unsigned long apStartedAt=0;wnWifiMode wifiModeRunning=wnWifiMode::WIFIMODE_STATION;
    Log*log(){return &logger;}bool isWebServerRunning(){return true;}
    const char*getIdx(){return "Living-room";}String getFirmwareVersion(){return firmwareVersion;}
    bool isSupportingMqtt(){return enabled;}bool isSupportingMqttHASS(){return true;}
    bool isSupportingMqttSingleValues(){return false;}bool isSupportingApFallback(){return true;}
    bool isAuthenticationRequired(){return true;}
    bool isStaticIpEnabled(){return staticEnabled;}bool isSoftAP(){return false;}
    bool recoveryApActive=false;unsigned long recoveryApStartedAt=0;
    const char*getSsid(){return "Example Wi-Fi";}const char*getPassword(){return "fake-password";}
    String getBssid(){return bssidLocked ? "02:11:22:33:44:55" : "";}bool isWifiConnected(){return true;}
    const char*getStaticIp(){return address.c_str();}const char*getSubnetMask(){return "255.255.255.0";}
    const char*getGateway(){return "";}const char*getDns1(){return "";}const char*getDns2(){return "";}
    const char*getMqttServer(){return "mqtt.example.test";}const char*getMqttPort(){return "1883";}
    const char*getMqttUser(){return "thermostat";}const char*getMqttPassword(){return "fake-password";}
    const char*getMqttTopic(){return "thermostat/living-room";}Ip getDeviceIp(){return {};}
};
'''
    # Add the real header/footer and handlers to the mock network class.
    start = network.index("\ttemplate<class T, typename ... Args> WCheckedPrint * httpHeader")
    end = network.index("\n\tString getClientName", start)
    methods = method(NETWORK, "getCsrfToken") + method(NETWORK, "printHttpButton") + method(NETWORK, "printHttpCaption") + network[start:end]
    for name in ("handleHttpRootRequest", "handleHttpDeviceConfiguration", "handleHttpDevicePage", "handleHttpDevicePageSubmitted", "webReturnStatusPage", "ipToStr", "handleHttpNetworkConfiguration", "handleHttpFirmwareUpdate", "handleHttpInfo"):
        methods += method(NETWORK, name)
    source = source.removesuffix("};\n") + methods + "\n};\n"
    source += beca[beca.index("const static char HTTP_CONFIG_SCHTAB_HEAD"):beca.index("class WBecaDevice:")]
    source += '\nconst char HTTP_TEXT_CLOCK_HOWTO[]=' + json.dumps(raw_asset(clock, "HTTP_TEXT_CLOCK_HOWTO")) + ';\n'
    source += log.read_text()[log.read_text().index("const char* ID_LOGDEVICE"):log.read_text().index("AsyncWebSocket wslog")]
    source += r'''
enum{LOG_LEVEL_SILENT,LOG_LEVEL_FATAL,LOG_LEVEL_ERROR,LOG_LEVEL_WARNING,LOG_LEVEL_NOTICE,LOG_LEVEL_TRACE,LOG_LEVEL_VERBOSE};
struct Value{String text;Value(const char*s=""):text(s){}bool getBoolean(){return true;}byte getByte(){return 1;}double getDouble(){return 20;}int getInteger(){return 60;}const char*c_str(){return text.c_str();}};
struct Beca{
    Net*network;Value value;Value*floorSensor=&value,*switchBackToAuto=&value,*deadzoneTemp=&value;
    Value sensor{"Fake <MCU> & sensor"},modeValue{"heat"};Value*mcuId=&sensor,*mode=&modeValue,*schedulesMode=&modeValue,*holdState=&modeValue,*systemMode=&modeValue,*fanMode=&modeValue,*action=&modeValue,*state=&modeValue;
    Value*deviceOn=&value,*actualTemperature=&value,*actualFloorTemperature=&value,*targetTemperature=&value,*ecoMode=&value;
    unsigned long lastHeartBeat=0,lastTimeRequested=0,lastTimeSent=0;
    int model=0;float factor=2;Beca(Net*n):network(n){}const char*getId(){return "thermostat";}
    bool isMcuInitialized(){return true;}
    int getThermostatModel(){return model;}float getTemperatureFactor(){return factor;}
    bool isSupportingHeatingRelay(){return false;}bool isSupportingCoolingRelay(){return false;}
    byte getSchedulesDayOffset(){return 0;}String getSchedulesValue(const char*key){return key[2]=='h'?"06:00":"20.0";}
'''+method(BECA, "printConfigPage")+method(BECA, "printInfoPage")
    schedule = beca.split("schedulePage->setPrintPage(", 1)[1].split("schedulePage->setSubmittedPage(", 1)[0]
    schedule = schedule[schedule.index("{") + 1:schedule.rindex("});")]
    source += '\nvoid printSchedules(AsyncWebServerRequest*request,WCheckedPrint*page){WPage item("schedules","Schedules");WPage*schedulePage=&item;' + schedule + "}\n};\n"
    source += r'''
struct Clock{
    Net*network;Value server{"pool.ntp.org"},zone{"99"},dst{"0,3,0,2,120"},standard{"0,10,0,3,60"};
    Value*ntpServer=&server,*timeZoneConfig=&zone,*timeDST=&dst,*timeSTD=&standard;
    Value formatted{"2026-10-27 12:34:56"},offsetValue;Value*epochTimeLocalFormatted=&formatted,*offset=&offsetValue;
    unsigned long lastTry=0,lastNtpSync=0;int lastDiff=0;bool isValidTime(){return true;}
    Clock(Net*n):network(n){}const char*getId(){return "clock";}
'''+method(clock, "printConfigPage")+method(clock, "printInfoPage")+"\n};\n"
    source += r'''
struct Logging{
    Net*network;Logging(Net*n):network(n){}const char*getId(){return "logging";}
    int getlogLevelByte(){return 3;}int getlogLevelWebByte(){return 5;}
'''+method(log, "printConfigPage")+r'''
};
void emit(const char*name,AsyncWebServerRequest&r){printf("%s\n%s\x1e",name,r.body.c_str());}
int main(){
    Net net;Beca beca(&net);Clock clock(&net);Logging logging(&net);
    WDevice therm("thermostat","Thermostat"),time("clock","Clock"),logs("logging","Logging");
    WPage schedules("schedules","Configure schedules"),reinit("reinit","Reinitialize thermostat"),weblog("weblog","Live log");
    therm.info=[&](WCheckedPrint*p){beca.printInfoPage(p);};time.info=[&](WCheckedPrint*p){clock.printInfoPage(p);};
    therm.config=[&](AsyncWebServerRequest*r,WCheckedPrint*p){beca.printConfigPage(r,p);};
    time.config=[&](AsyncWebServerRequest*r,WCheckedPrint*p){clock.printConfigPage(r,p);};
    logs.config=[&](AsyncWebServerRequest*r,WCheckedPrint*p){logging.printConfigPage(r,p);};
    therm.next=&time;time.next=&logs;therm.firstPage=&schedules;schedules.next=&reinit;logs.firstPage=&weblog;net.firstDevice=&therm;
    schedules.setPrintPage([&](AsyncWebServerRequest*r,WCheckedPrint*p){beca.printSchedules(r,p);});
    unsigned submitted=0;
    schedules.setSubmittedPage([&](AsyncWebServerRequest*,WCheckedPrint*p){++submitted;p->print("Submitted preview");});
    {AsyncWebServerRequest r;net.handleHttpRootRequest(&r);emit("/config",r);}
    {AsyncWebServerRequest r;net.handleHttpNetworkConfiguration(&r);emit("/wifi",r);}
    {AsyncWebServerRequest r;net.enabled=false;net.handleHttpNetworkConfiguration(&r);emit("/wifi-off",r);net.enabled=true;}
    {AsyncWebServerRequest r;net.staticEnabled=true;net.handleHttpNetworkConfiguration(&r);emit("/wifi-static",r);net.staticEnabled=false;}
    {AsyncWebServerRequest r;net.address="<IP>'&";net.handleHttpNetworkConfiguration(&r);emit("/wifi-escaped",r);net.address="";}
    {AsyncWebServerRequest r;net.handleHttpDeviceConfiguration(&r,&therm);emit("/thermostat",r);}
    {AsyncWebServerRequest r;beca.model=1;net.handleHttpDeviceConfiguration(&r,&therm);emit("/thermostat-bac",r);beca.model=0;}
    {AsyncWebServerRequest r;beca.factor=10;net.handleHttpDeviceConfiguration(&r,&therm);emit("/thermostat-fine",r);beca.factor=2;}
    {AsyncWebServerRequest r;net.handleHttpDeviceConfiguration(&r,&time);emit("/clock",r);}
    {AsyncWebServerRequest r;net.handleHttpDeviceConfiguration(&r,&logs);emit("/logging",r);}
    {AsyncWebServerRequest r;net.handleHttpDevicePage(&r,&therm,&schedules);emit("/thermostat_schedules",r);}
    {AsyncWebServerRequest r;net.handleHttpDevicePageSubmitted(&r,&therm,&schedules);emit("/submitted-preview",r);}
    assert(submitted==(FAIL_RESPONSE || FAIL_HEADER_WRITE || MAX_BLOCK<1024U ? 0U : 1U));
    {AsyncWebServerRequest r;net.webReturnStatusPage(&r,F("Saved preview"),"");emit("/saved-preview",r);}
    {AsyncWebServerRequest r;net.restartFlag="Preview status";net.handleHttpRootRequest(&r);emit("/restart-status-preview",r);net.restartFlag=nullptr;}
    {AsyncWebServerRequest r;beca.factor=10;net.handleHttpDevicePage(&r,&therm,&schedules);emit("/schedules-fine",r);beca.factor=2;}
    {AsyncWebServerRequest r;beca.factor=1;net.handleHttpDevicePage(&r,&therm,&schedules);emit("/schedules-whole",r);beca.factor=2;}
    {AsyncWebServerRequest r;auto*p=net.httpHeader(&r,"Live log");if(p){net.printHttpCaption(p);p->format(HTTP_WEBLOG,net.getCsrfToken());p->print(FPSTR(HTTP_HOME_BUTTON));p->print(FPSTR(HTTP_WEBLOG_SCRIPT));net.httpFooter(p);net.sendHttpPage(&r,p);}emit("/logging_weblog",r);}
    {AsyncWebServerRequest r;net.handleHttpFirmwareUpdate(&r);emit("/firmware",r);}
    {AsyncWebServerRequest r;net.handleHttpInfo(&r);emit("/info",r);}
    {AsyncWebServerRequest r;beca.model=1;net.handleHttpInfo(&r);emit("/info-bac",r);}
}
'''
    source = '#include <new>\n#define MAX_BLOCK ' + str(int(largest_heap_block)) + 'U\n#define FAIL_RESPONSE ' + str(int(response_allocation_fails)) + '\n' + '#define FAIL_HEADER_WRITE ' + str(int(fail_header_write)) + '\n#define HEAP_BUDGET ' + str(int(response_heap_budget)) + 'U\n' + source
    config = configparser.ConfigParser(interpolation=None)
    config.read([ROOT / "platformio.ini", ROOT / "platformio_override.ini"])
    source = '#define PREVIEW_VERSION ' + json.dumps(config["common"]["appversion"]) + '\n' + source
    with tempfile.TemporaryDirectory(prefix="wthermostat-ui-native-") as directory:
        cpp = Path(directory) / "preview.cpp"
        binary = Path(directory) / "preview"
        cpp.write_text(source)
        subprocess.run([os.environ.get("CXX", "g++"), "-std=c++17", "-I", str(ROOT / "tests/native"),
                        "-I", str(ROOT), str(cpp), "-o", str(binary)], check=True)
        result = subprocess.check_output([str(binary)], text=True)
    pages = dict(record.split("\n", 1) for record in result.split("\x1e") if record)
    pages["/css"] = raw_asset(ROOT / "lib/WAdapter/WAdapter/WHtmlPages.h", "PAGE_CSS")
    pages["/js"] = raw_asset(ROOT / "lib/WAdapter/WAdapter/WHtmlPages.h", "PAGE_JS")
    return pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build_output/ui-preview")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    pages = render_pages()
    args.output.mkdir(parents=True, exist_ok=True)
    for route, content in pages.items():
        suffix = ".css" if route == "/css" else ".js" if route == "/js" else ".html"
        (args.output / (route[1:] + suffix)).write_text(content)
    print(json.dumps({"pages": len(pages) - 2, "css_bytes": len(pages["/css"].encode()),
                      "js_bytes": len(pages["/js"].encode()), "output": str(args.output)}), flush=True)
    if args.serve:
        class Preview(BaseHTTPRequestHandler):
            def do_GET(self):
                path = urlsplit(self.path).path
                if path == "/":
                    path = "/config"
                if path not in pages:
                    self.send_error(404)
                    return
                data = pages[path].encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/css" if path == "/css" else "text/javascript" if path == "/js" else "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                self.send_error(405, "Read-only preview: no device is connected")

        ThreadingHTTPServer(("127.0.0.1", args.port), Preview).serve_forever()


if __name__ == "__main__":
    main()
