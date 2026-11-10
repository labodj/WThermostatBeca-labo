"""Production regressions for reentrant logging, command validation and timer edges."""

import unittest

import test_regressions as native
import test_temperature_commands as temperature
from test_regressions import BECA, NETWORK, ROOT, method


class AuditRegressionTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_mqtt_logging(self):
        source = (
            r"""
        #include "Arduino.h"
        #include "Stream.h"
        #include "lib/WAdapter/WAdapter/WProperty.h"
        #include "lib/WAdapter/WAdapter/WLog.h"
        #include "lib/WAdapter/WAdapter/WAdapterMqtt.h"
        struct WDevice{
         WProperty power{"deviceOn","Power",BOOLEAN};
         WDevice(){power.setBoolean(false);}
         WProperty*getPropertyById(const char*id){return !strcmp(id,"deviceOn")?&power:nullptr;}
         const char*getId(){return "thermostat";}const char*getName(){return "Thermostat";}
         bool isMqttRetain(){return true;}
         void handleUnknownMqttCallback(const String&,const String&,const String&,unsigned){}
        };
        #include "lib/WAdapter/WAdapter/WJsonParser.h"
        const char* MQTT_CMND="cmnd",*MQTT_STAT="stat";
        struct Probe{
         Print output;WLog logger;WLog*wlog=&logger;WAdapterMqtt*mqttClient;WDevice device;
         bool logging=false;
         Probe(WAdapterMqtt*m,int level):logger(0,level,&output),mqttClient(m){
          logger.setOnLogCommand([this](int,const char* message){
           if(logging)return;logging=true;
           const String line=String("notice: ")+message;
           publishMqtt("home/room/tele/log",line.c_str());logging=false;
          });
         }
         const char* getMqttTopic(){return "home/room";}const char*getMqttServer(){return "broker";}
         WDevice*getDeviceById(const char* id){return !strcmp(id,"thermostat")?&device:nullptr;}
         bool isMqttConnected(){return mqttClient->connected();}
         void disconnectMqtt(){mqttClient->disconnect();}
         void requestHassDiscovery(){}void mqttSendDeviceState(const String&,WDevice*){}
        """
            + method(NETWORK, "publishMqtt")
            + method(NETWORK, "mqttCallback")
            + r"""
        };
        int main(){
         for(bool single:{false,true})for(int level:{0,4,5,6}){
          Client client;client.data={0x20,2,0,0};WAdapterMqtt mqtt(false,client,3096);assert(mqtt.connect("probe"));
          Probe p(&mqtt,level);mqtt.setCallback([&](char*t,char*b,unsigned n){p.mqttCallback(t,b,n);});
          std::string topic="home/room/cmnd/things/thermostat/properties";if(single)topic+="/deviceOn";
          std::string body=single?"true":"{\"deviceOn\":true}";
          size_t n=topic.size()+2+body.size();assert(n<128);client.data.push_back(0x30);client.data.push_back(n);
          client.data.push_back(topic.size()>>8);client.data.push_back(topic.size()&255);
          client.data.insert(client.data.end(),topic.begin(),topic.end());client.data.insert(client.data.end(),body.begin(),body.end());
          assert(mqtt.loop());bool applied=p.device.power.getBoolean();
          printf("%s loglevel=%d applied=%d\n",single?"single":"JSON",level,applied);
          assert(applied);
         }
        }
        """
        )
        self.compile_run(source, "mqtt_logging")

    def test_state_batch(self):
        s = (
            temperature.TemperatureCommandTests()
            .source()
            .replace('eco{"eco",', 'eco{"ecoMode",')
            + r"""
        #include "lib/WAdapter/WAdapter/WJsonParser.h"
        int main(){
         Probe p;p.eco.parse("true");assert(p.eco.getBoolean()&&p.target.isReadOnly());
         WDevice dev;dev.properties={&p.eco,&p.target};WJsonParser parser;
         auto* result=parser.parse("{\"ecoMode\":false,\"targetTemperature\":999}",&dev);
         printf("Invalid batch: valid=%d eco_after=%d result=%p\n",parser.isValid(),p.eco.getBoolean(),static_cast<void*>(result));
         assert(!parser.isValid()&&p.eco.getBoolean());
        }
        """
        )
        self.compile_run(s, "state_batch")

    def test_clock_transition(self):
        clock = ROOT / "WThermostat/WClock.h"
        text = clock.read_text()
        s = '#include "properties.h"\n#define SECS_PER_DAY 86400UL\n#define SECS_PER_HOUR 3600UL\n#define SECS_PER_MIN 60UL\n'
        s += text[text.index("typedef struct {") : text.index("WiFiUDP ntpUDP")]
        s += r"""
        const int WL_CONNECTED=3;struct Wifi{int status(){return WL_CONNECTED;}}WiFi;
        struct Ntp{uint32_t epoch=0;bool update(){return false;}uint32_t getEpochTime(){return epoch;}}ntpClient;
        struct Log{template<class...T>void error(T...){}template<class...T>void trace(T...){}template<class...T>void notice(T...){}template<class...T>void warning(T...){} };
        struct Net{Log logger;Log*log(){return &logger;}void logHeap(const char*){}};
        struct Probe{
         Net net;Net*network=&net;unsigned long lastTry=1000,lastNtpSync=1000,ntpTime=0,lastRun=0;int64_t lastDiff=0;
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
         Probe p;ntpClient.epoch=1774745999UL;p.loop(10000);assert(p.Rtc.time_timezone==0);
         ntpClient.epoch=1774746001UL;p.loop(12000);
         printf("London spring transition: UTC=01:00:01 actual_offset=%d expected=3600\n",p.Rtc.time_timezone);
         assert(p.Rtc.time_timezone==3600);
         ntpClient.epoch=1774749600UL;p.loop(3611000);
         printf("Next local whole hour: offset=%d\n",p.Rtc.time_timezone);assert(p.Rtc.time_timezone==3600);
        }
        """
        self.compile_run(s, "clock_transition")

    def test_state_enum(self):
        text = BECA.read_text()
        const = text[
            text.index("#define COUNT_DEVICE_MODELS") : text.index("//typedef")
        ]
        start = text.index("\t\tthis->state = nullptr;")
        end = text.index("\n\t\tthis->addProperty(state);", start) + len(
            "\n\t\tthis->addProperty(state);"
        )
        s = (
            r"""
        #include "Arduino.h"
        #include "Stream.h"
        #include "lib/WAdapter/WAdapter/WProperty.h"
        #include "lib/WAdapter/WAdapter/WStringStream.h"
        """
            + const
            + r"""
        struct Probe{WProperty*state=nullptr;int model;int getThermostatModel(){return model;}
         void addProperty(WProperty*){}void updateModeAndAction(){}
         Probe(int model):model(model){
        """
            + text[start:end]
            + r"""
         }~Probe(){delete state;}
        };
        int main(){for(int model:{MODEL_BHT_002_GBLW,MODEL_BAC_002_ALW}){
         Probe p(model);WStringStream stream(1024);WJson json(&stream);p.state->toJsonStructure(&json,"state","/things/thermostat");
         bool coolingListed=strstr(stream.c_str(),"\"cooling\"");
         printf("%s schema lists cooling=%d\n",model==MODEL_BAC_002_ALW?"BAC":"BHT",coolingListed);
         assert(coolingListed==(model==MODEL_BAC_002_ALW));
         }}
        """
        )
        self.compile_run(s, "state_enum")

    def test_timer_rollover(self):
        text = method(NETWORK, "loop")
        start = text.index("if ((this->isMqttConnected())")
        end = text.index("{", start)
        condition = text[start + 3 : end].strip()
        s = (
            """#include <cstdio>\n#include <cassert>\n#include <cstdint>\nstruct Device{uint32_t lastStateNotify=0,stateNotifyInterval=60000;bool isDeviceStateComplete(){return true;}};\nstruct Probe{bool isMqttConnected(){return true;}bool isSupportingMqtt(){return true;}bool due(uint32_t now,Device*device){return """
            + condition
            + """;}};\nint main(){Probe p;Device d;d.lastStateNotify=UINT32_MAX-1000;uint32_t now=120000;assert(now-d.lastStateNotify>60000);printf("After millis rollover: elapsed=%u ms, periodic_publish_due=%d\\n",now-d.lastStateNotify,p.due(now,&d));assert(p.due(now,&d));d.lastStateNotify=0;assert(p.due(now,&d));}\n"""
        )
        self.compile_run(s, "timer_rollover")
