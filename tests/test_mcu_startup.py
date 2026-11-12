"""Controller-dependent data stays unavailable until its first valid report."""
import re
import unittest
import native_support as native
from native_support import BECA, NETWORK, method


class McuStartupTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_optional_fan_and_schedule_storage_start_initialized(self):
        text = BECA.read_text()
        fields = '\n'.join(re.search(pattern, text, re.M).group() for pattern in
                           (r'^\s*WProperty\* fanMode[^\n]*', r'^\s*byte schedules\[54\][^\n]*'))
        source = r'''
#include "properties.h"
#include <new>
const char* FAN_MODE_AUTO="auto",*FAN_MODE_HIGH="high",*FAN_MODE_MEDIUM="medium",*FAN_MODE_LOW="low";
struct Probe{
''' + fields + method(BECA, 'getFanModeAsByte') + r'''
};
// Default initialization must initialize every field, even on recycled storage.
constexpr Probe initialized;
static_assert(initialized.fanMode==nullptr&&initialized.schedules[0]==0);
int main(){alignas(Probe) unsigned char storage[sizeof(Probe)];memset(storage,0xa5,sizeof(storage));
 Probe*p=new(storage) Probe;
 assert(p->fanMode==nullptr&&p->getFanModeAsByte()==0xff);
 for(byte value:p->schedules)assert(value==0);p->~Probe();}
'''
        self.compile_run(source, 'mcu_initial_storage')

    def test_schedule_responses_wait_for_controller(self):
        source = r'''
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WJson.h"
#include "lib/WAdapter/WAdapter/WStringStream.h"
const char* APPLICATION_JSON="application/json",*MQTT_STAT="stat";
const String SCHEDULES="schedules";const char SCHEDULES_DAYS[]="wau",SCHEDULES_PERIODS[]="123456";
struct Request{int status=0;String body;void send(int code,const char*,const char*value){status=code;body=value;}};
using AsyncWebServerRequest=Request;
struct Net{unsigned publishes=0;WStringStream stream{3096};
 WStringStream*getMQTTResponseStream(){stream.flush();return &stream;}
 const char*getMqttTopic(){return "room";}
 void publishMqtt(const char*,WStringStream*){++publishes;}
};
struct Probe{Net net;Net*network=&net;bool ready=false;byte schedules[54]{};
 bool receivedSchedules(){return ready;}double getTemperatureFactor(){return 2;}
 const char*getId(){return "thermostat";}
''' + ''.join(method(BECA, name) for name in ('toJsonSchedules', 'sendSchedules', 'sendSchedulesToMqtt')) + r'''
};
int main(){Probe p;Request unavailable;p.sendSchedules(&unavailable);
 assert(unavailable.status==503&&unavailable.body.indexOf("not available")>=0);
 p.sendSchedulesToMqtt();assert(p.net.publishes==0);
 p.ready=true;Request available;p.sendSchedules(&available);assert(available.status==200);
 assert(available.body.indexOf("w1h")>=0&&available.body.indexOf("u6t")>=0);
 p.sendSchedulesToMqtt();assert(p.net.publishes==1);}
'''
        self.compile_run(source, 'schedule_readiness')

    def test_schedule_page_does_not_offer_empty_programs_before_first_report(self):
        from render_ui import render_pages
        pages = render_pages(schedules_ready=False)
        for route in ('/thermostat_schedules', '/schedules-fine', '/schedules-whole'):
            self.assertIn('Schedules are not available yet', pages[route])
            self.assertNotIn('name="w1h"', pages[route])
            self.assertNotIn('/save_thermostat_schedules', pages[route])

    def test_schedule_writes_wait_for_controller_on_http_and_mqtt(self):
        text = BECA.read_text()
        start = text.index('schedulePage->setSubmittedPage(')
        callback = text[start:text.index('this->addPage(schedulePage);', start)]
        source = r'''
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WProperty.h"
struct WDevice{WProperty*getPropertyById(const char*){return nullptr;}};
#include "lib/WAdapter/WAdapter/WJsonParser.h"
struct AsyncWebServerRequest;
#include "lib/WAdapter/WAdapter/WPage.h"
const char SCHEDULES_DAYS[]="wau",SCHEDULES_PERIODS[]="123456";
const String SCHEDULES="schedules",MCUCOMMAND="mcucommand";const int MODEL_BAC_002_ALW=1;
struct AsyncWebServerRequest{};
String getValueOrEmpty(AsyncWebServerRequest*,const char*key){return key[2]=='h'?"06:00":"20";}
struct Log{template<class...T>void notice(T...){}template<class...T>void warning(T...){}};
struct Net{Log logger;Log*log(){return &logger;}void setDesiredModeAp(){}void setDesiredModeFallback(){}void setDesiredModeStation(){}};
struct Probe{Net net;Net*network=&net;bool ready=false,schedulesChanged=false;byte schedules[54]{};
 unsigned writes=0,replies=0;WPage page{"schedules","Schedules"};
 bool receivedSchedules(){return ready;}int getThermostatModel(){return 0;}double getTemperatureFactor(){return 2;}
 void schedulesToMcu(){++writes;}void sendSchedulesToMqtt(){++replies;}void commandHexStrToSerial(String){assert(false);}
 void install(){WPage*schedulePage=&page;
''' + callback + '\n}\n' + ''.join(method(BECA, name) for name in (
            'getSchedulesPeriod', 'getSchedulesStartAddress', 'validSchedulesKeyValue',
            'validSchedulesOrder', 'processSchedulesKeyValue', 'handleUnknownMqttCallback')) + r'''
};
int main(){Probe p;p.install();AsyncWebServerRequest request;Print sink;WCheckedPrint output(&sink);
 p.page.submittedPage(&request,&output);
 p.handleUnknownMqttCallback("reply","schedules/","{\"w1t\":21}",10);
 assert(p.writes==0&&p.replies==0);for(byte value:p.schedules)assert(value==0);
 p.ready=true;p.page.submittedPage(&request,&output);assert(p.writes==1&&p.schedules[2]==40);
 p.handleUnknownMqttCallback("reply","schedules/","{\"w1t\":21}",10);
 assert(p.writes==2&&p.replies==1&&p.schedules[2]==42);}
'''
        self.compile_run(source, 'schedule_write_readiness')

    def test_server_initialization_registers_the_schedule_get_route(self):
        source = r'''
#include "Arduino.h"
const int HTTP_GET=1;const String SCHEDULES="schedules";
struct AsyncWebServerRequest{};
struct AsyncWebServer{String path;int verb=0;std::function<void(AsyncWebServerRequest*)>handler;
 void on(const char*route,int method,std::function<void(AsyncWebServerRequest*)>callback){path=route;verb=method;handler=callback;}};
struct WDevice{WDevice*next=nullptr;unsigned reads=0,hooks=0;const char*getId(){return "thermostat";}
 void sendSchedules(AsyncWebServerRequest*){++reads;}
 void webserverInitHook(AsyncWebServer*){++hooks;}
''' + method(BECA, 'bindWebServerCalls') + r'''
};
struct Probe{WDevice*firstDevice;
''' + method(NETWORK, 'initWebserverInitHooks') + r'''
};
int main(){WDevice device;Probe p{&device};AsyncWebServer server;p.initWebserverInitHooks(&server);
 assert(server.path=="/things/thermostat/schedules"&&server.verb==HTTP_GET&&server.handler&&device.hooks==1);
 AsyncWebServerRequest request;server.handler(&request);assert(device.reads==1);}
'''
        self.compile_run(source, 'registered_schedule_route')
