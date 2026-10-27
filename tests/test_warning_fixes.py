"""Regression cases found while reviewing all 142 clang-tidy diagnostics."""
from pathlib import Path
import re
import unittest
import test_regressions as regressions

ROOT = Path(__file__).resolve().parents[1]


class WarningTests(unittest.TestCase):
    compile_run = regressions.NativeTests.compile_run

    def test_publish_eeprom_stream_and_color(self):
        self.compile_run(None, "warning_fixes")

    def test_ntp_server_lifetime_and_client_name_limit(self):
        # Use the actual constructor assignment: NTPClient retains this pointer.
        assignment = re.search(r"ntpClient = NTPClient\([^;]+;", (ROOT / "WThermostat/WClock.h").read_text()).group()
        source = r'''
#include "properties.h"
struct NTPClient {
    const char* server=nullptr;
    NTPClient()=default;
    NTPClient(int&,const char* name):server(name){}
};
String htmlEscapedString(const char* text){return String(text);}
struct Probe {
    WProperty server{"server","Server",STRING};WProperty*ntpServer=&server;
    NTPClient ntpClient;int ntpUDP=0;
    void init(){
'''+assignment+r'''
    }
};
struct Esp {unsigned getChipId(){return 123456;}} ESP;
struct NameProbe {
    String applicationName;
'''+regressions.method(ROOT / "lib/WAdapter/WAdapter/WNetwork.h", "getClientName")+r'''
};
int main(){
    Probe p;p.server.setString("a-long-custom-ntp.example.org");p.init();
    assert(p.ntpClient.server==p.ntpServer->c_str());
    assert(!strcmp(p.ntpClient.server,"a-long-custom-ntp.example.org"));
    NameProbe name;name.applicationName="WThermostat";
    assert(name.getClientName(false)=="WThermostat-123456");
    assert(name.getClientName(true)=="wthermostat-123456");
    name.applicationName="";assert(name.getClientName(false)=="ESP-123456");
    name.applicationName=String(std::string(80,'A'));
    const String client=name.getClientName(true);
    assert(client.length()==32&&client.endsWith("-123456"));
    puts("PASS retained NTP name lifetime and bounded stable client names");
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

    def test_callback_ownership_and_replacement_boundaries(self):
        self.compile_run(None, "maintenance")

    def test_serial_index_bounds_and_temperature_precision(self):
        source = r'''
#include "properties.h"
const unsigned char COMMAND_START[]={0x55,0xaa};
struct Probe {
    unsigned char receivedCommand[1024]{};
    int receiveIndex=-1,commandLength=-1,handled=0;
    unsigned long lastSerialByte=0,lastMcuReceived=0;
    WProperty precision{"precision","Precision",DOUBLE};WProperty*temperaturePrecision=&precision;
    void processSerialCommand(unsigned long){++handled;}
'''
        for name in ["resetAll", "serviceSerial", "getTemperatureFactor", "getTemperaturePrecision", "decodeMcuValue"]:
            source += regressions.method(ROOT / "WThermostat/WBecaDevice.h", name) + "\n"
        source += r'''
};
int main(){
    for(int index:{INT_MIN,-2,-1,0,1022,1023,INT_MAX}){
        Probe p;p.receiveIndex=index;p.lastSerialByte=1;
        Serial.position=0;Serial.input={0x55,0x55,0xaa,0,0,0,0,0xff};p.serviceSerial(1);
        assert(p.handled==1&&p.receiveIndex==-1);
    }
    Probe p;
    for(double step:{0.1,0.5,1.0}){
        p.precision.setDouble(step);assert(p.getTemperaturePrecision()==step);
        assert(fabs(1.0/p.getTemperatureFactor()-step)<1e-14);
        const byte bytes[]={0x7f,0xff,0xff,0xff};
        assert(fabs(p.decodeMcuValue(bytes)/p.getTemperatureFactor()-double(INT32_MAX)*step)<1e-7);
    }
    puts("PASS serial index guard, resync and double temperature precision");
}
'''
        self.compile_run(source, "maintenance_serial")

    def test_logging_levels_and_defaults_remain_compatible(self):
        log_device = ROOT / "WThermostat/WLogDevice.h"
        text = log_device.read_text()
        levels = "\n".join(line for line in (ROOT / "lib/WAdapter/WAdapter/WLog.h").read_text().splitlines()
                           if line.startswith("#define LOG_LEVEL_"))
        modes = text[text.index("const char* LOG_MODE_SILENT"):text.index("const char* URI_WSLOG")]
        source = '#include "properties.h"\n' + levels + "\n" + modes + r'''
struct Log{int level=0;void setLevelNetwork(int value){level=value;}};
struct Net{Log output;Log*log(){return &output;}};
struct Probe{
    int mqtt=0,web=0;Net net;Net*network=&net;
    void setlogLevelByte(byte value){mqtt=value;}
    void setlogLevelWebByte(byte value){web=value;}
    byte getlogLevelByte(){return mqtt;}
    byte getlogLevelWebByte(){return web;}
'''
        for name in ["setMinLogLevel", "onlogLevelMqttChange", "onlogLevelWebChange", "logLevelByteToString"]:
            source += regressions.method(log_device, name) + "\n"
        source += r'''
};
int main(){
    Probe p;WProperty mode("mode","Mode",STRING);
    const char* modes[]={"silent","fatal","error","warning","notice","trace","verbose"};
    for(unsigned i=0;i<7;++i){
        mode.setString(modes[i]);p.onlogLevelMqttChange(&mode);p.onlogLevelWebChange(&mode);
        assert(p.mqtt==int(i)&&p.web==int(i)&&!strcmp(p.logLevelByteToString(i),modes[i]));
    }
    mode.setString("invalid");p.onlogLevelMqttChange(&mode);p.onlogLevelWebChange(&mode);
    assert(p.mqtt==0&&p.web==0&&!strcmp(p.logLevelByteToString(255),"silent"));
    p.mqtt=2;p.web=6;p.setMinLogLevel();assert(p.net.output.level==6);
    p.mqtt=5;p.web=1;p.setMinLogLevel();assert(p.net.output.level==5);
    puts("PASS all log levels, channel routing and silent defaults");
}
'''
        self.compile_run(source, "maintenance_logging")
