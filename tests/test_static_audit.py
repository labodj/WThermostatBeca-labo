"""Behavioral regressions for the cross-analyzer audit."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_analysis_tool
import test_regressions as native

ROOT = native.ROOT
MQTT = ROOT / 'lib/WAdapter/WAdapter/WAdapterMqtt.h'
spec = importlib.util.spec_from_file_location('cross_analysis', ROOT / 'pio/analyze.py')
analysis = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'check': test_analysis_tool.checker}):
    spec.loader.exec_module(analysis)


class StaticAuditTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_model_and_macro_arguments_preserve_values(self):
        self.assertEqual(['-UFOO', '-DFOO=1', '-UF', '-DF(x)=x + 1', '-UEMPTY', '-DEMPTY='],
                         analysis.builtin_flags('#define FOO 1\n#define F(x) x + 1\n#define EMPTY\n'))
        self.assertIn('-mlong-double-64', analysis.MODEL)
        self.assertIn('-malign-double', analysis.MODEL)
        for failure in ['syntaxError', 'unknownMacro', 'missingIncludeSystem', 'internalError']:
            self.assertFalse(analysis.cppcheck_complete(f'<results><errors><error id="{failure}"/></errors></results>'))
        # Findings stay in the raw report; completion and findings are separate.
        self.assertTrue(analysis.cppcheck_complete('<results><errors><error id="uninitvar"/></errors></results>'))

    def test_override_extraction_preserves_body(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'method.h'
            path.write_text('virtual const char* value() override { return "override"; }')
            self.assertEqual('virtual const char* value()  { return "override"; }', native.method(path, 'value'))

    def test_mqtt_eof_is_not_a_valid_ff_byte(self):
        source = r'''
#include "Arduino.h"
#include <functional>
const int MQTT_CONNECTION_TIMEOUT=-4,MQTT_CONNECTION_LOST=-3,MQTT_SOCKET_TIMEOUT=2;
struct Client{int value=-1;bool stopped=false;int available(){return 1;}int read(){return value;}void stop(){stopped=true;}};
struct Probe{Client client;Client*_client=&client;int _state=0;unsigned long packetStarted=0;std::function<void()>onIdle;
'''+native.method(MQTT, 'readByte')+r'''
};
int main(){
 for(int value:{-1,0,255}){Probe p;p.client.value=value;uint8_t byte=42;
  assert(p.readByte(&byte)==(value>=0));
  if(value<0){assert(p.client.stopped&&p._state==MQTT_CONNECTION_LOST&&byte==42);}
  else{assert(!p.client.stopped&&byte==value);}
 }
 puts("PASS MQTT distinguishes EOF, zero and 0xff");
}
'''
        self.compile_run(source, 'mqtt_eof')

    def test_streaming_mqtt_rejects_oversize_before_writing(self):
        source = r'''
#include "properties.h"
#include "lib/WAdapter/WAdapter/WStringStream.h"
#include "lib/WAdapter/WAdapter/WStringProperty.h"
#include "lib/WAdapter/WAdapter/WSettings.h"
#include "lib/WAdapter/WAdapter/WAdapterMqtt.h"
#include <type_traits>
static_assert(!std::is_copy_constructible<WProperty>::value&&!std::is_copy_assignable<WProperty>::value);
static_assert(!std::is_copy_constructible<WStringStream>::value&&!std::is_copy_assignable<WStringStream>::value);
static_assert(!std::is_copy_constructible<WSettings>::value&&!std::is_copy_assignable<WSettings>::value);
static_assert(!std::is_copy_constructible<WAdapterMqtt>::value&&!std::is_copy_assignable<WAdapterMqtt>::value);
int main(){
 Client client;client.data={0x20,2,0,0};WAdapterMqtt mqtt(false,client,64);assert(mqtt.connect("test"));client.sent.clear();
 for(const char*topic:{static_cast<const char*>(nullptr),std::string(58,'x').c_str()}){
  assert(!mqtt.beginPublish(topic,0,false));assert(client.sent.empty());
 }
 assert(!mqtt.beginPublish("x",UINT_MAX,false)&&client.sent.empty());
 assert(!mqtt.beginPublish("x",65533,false)&&client.sent.empty());
 assert(mqtt.beginPublish("x",65532,false));
 assert((client.sent==std::vector<uint8_t>{0x30,0xff,0xff,0x03,0,1,'x'}));
 client.sent.clear();assert(mqtt.beginPublish("x",1,true));assert(mqtt.write(uint8_t('a'))==1);
 assert((client.sent==std::vector<uint8_t>{0x31,4,0,1,'x','a'}));
 WSettingItem item;assert(item.value==nullptr&&item.address==0&&item.next==nullptr);
 puts("PASS ownership traits and streaming MQTT capacity/16-bit length limits");
}
'''
        # Keep the oversized topic alive for the entire loop.
        source = source.replace('for(const char*topic:', "const std::string longTopic(58,'x');for(const char*topic:").replace("std::string(58,'x').c_str()", 'longTopic.c_str()')
        self.compile_run(source, 'mqtt_streaming')

    def test_cpp_flags_do_not_change_c_flags(self):
        import runpy
        class Environment(dict):
            def AppendUnique(self, **items):
                for key, values in items.items():
                    self.setdefault(key, []).extend(v for v in values if v not in self.get(key, []))
            def Replace(self, **items):
                self.update(items)
        env = Environment(CCFLAGS=['-Os'], CXXFLAGS=['-fno-rtti'], LINKFLAGS=['-u', '_printf_float', '-Os'])
        runpy.run_path(str(ROOT / 'pio/strip-floats.py'), init_globals={'env': env, 'Import': lambda *_: None})
        self.assertEqual(['-Os'], env['CCFLAGS'])
        self.assertEqual(['-fno-rtti', '-fno-threadsafe-statics', '-fno-use-cxa-atexit'], env['CXXFLAGS'])
        self.assertEqual(['-Os'], env['LINKFLAGS'])

    def test_http_headers_remain_with_their_request_on_reentry(self):
        text = native.NETWORK.read_text()
        start = text.index('\ttemplate<class T, typename ... Args> AsyncResponseStream * httpHeader')
        end = text.index('\n\ttemplate<class T, typename ... Args> AsyncResponseStream * httpHeader', start + 1)
        source = r'''
#include "Arduino.h"
#include "Stream.h"
const char* CT_TEXT_HTML="text/html",*HTTP_HEAD_BEGIN="%s:%s;",*HTTP_HEAD_SCRIPT="script:%s;",*HTTP_HEAD_STYLE="style:%s;",*HTTP_HEAD_END="end;";
String htmlEscapedString(const char* value){return value;}
struct AsyncResponseStream:Print{
 std::string body;std::function<void()>hook;
 size_t write(uint8_t c)override{body+=static_cast<char>(c);if(hook){auto next=std::move(hook);hook=nullptr;next();}return 1;}
 void addHeader(const char*,const char*){}
};
struct AsyncWebServerRequest{AsyncResponseStream response;
 AsyncResponseStream*beginResponseStream(const char*,unsigned){return &response;}};
struct Probe{String csrfToken="token";AsyncResponseStream*page=nullptr;
 bool isWebServerRunning(){return true;}const char*getIdx(){return "room";}String getFirmwareVersion(){return "test";}
'''+text[start:end]+r'''
};
int main(){Probe p;AsyncWebServerRequest first,second;
 first.response.hook=[&](){assert(p.httpHeader(&second,"second",nullptr)==&second.response);};
 assert(p.httpHeader(&first,"first",nullptr)==&first.response);
 assert(first.response.body.find("<h1>first</h1>")!=std::string::npos);
 assert(first.response.body.find("second")==std::string::npos);
 assert(second.response.body.find("<h1>second</h1>")!=std::string::npos);
 assert(second.response.body.find("first")==std::string::npos);
 puts("PASS response headers remain request-local under reentry");}
'''
        self.compile_run(source, 'http_header_reentry')

    def test_led_initial_blink_and_virtual_device_destruction(self):
        source = r'''
#include "Arduino.h"
#include "Stream.h"
#include <type_traits>
#include "lib/WAdapter/WAdapter/WJson.h"
enum{INPUT,OUTPUT,INPUT_PULLUP,HIGH,LOW};int output=-1;
void pinMode(int,int){}void digitalWrite(int,int value){output=value;}
class AsyncWebServerRequest;class AsyncResponseStream;class AsyncWebServer;
#include "lib/WAdapter/WAdapter/WDevice.h"
static_assert(!std::is_copy_constructible<WDevice>::value&&!std::is_copy_assignable<WDevice>::value);
int main(){
 WProperty on("on","On",BOOLEAN);on.setBoolean(true);WLed led(4);led.setProperty(&on);
 assert(output==LOW);led.setOn(true,100);led.loop(1);assert(output==LOW);led.loop(102);assert(output==HIGH);
 bool destroyed=false;struct Device:WDevice{bool&flag;Device(bool&f):WDevice(nullptr,"id","name","root","type"),flag(f){}~Device()override{flag=true;}};
 WDevice*device=new Device(destroyed);assert(!strcmp(device->getFullName(),"root_name"));delete device;assert(destroyed);
 puts("PASS initialized LED, ownership traits and virtual device destruction");
}
'''
        self.compile_run(source, 'device_led_ownership')

    def test_http_dispatch_always_finishes_unsupported_methods(self):
        source = r'''
#include "Arduino.h"
const int HTTP_GET=1,HTTP_POST=2;
const char*URI_SAVE="/save_",*URI_RESET="/reset",*URI_THINGS="/things",*URI_CONFIG="/config",*URI_WIFI="/wifi",
 *URI_INFO="/info",*URI_FIRMWARE="/firmware",*URI_CSS="/css",*URI_JS="/js",*URI_FAVICON="/favicon",*ID_NETWORK="network";
const char*CT_TEXT_CSS="text/css",*CT_TEXT_JS="text/js",*CT_IMAGE_ICON="image/x-icon",*PAGE_CSS="",*PAGE_JS="",*favicon_ico_gz="";
const int favicon_ico_gz_len=0;
struct AsyncWebServerRequest{String path;int verb=HTTP_GET,status=0;bool authenticated=true;
 String url(){return path;}int method(){return verb;}void send(int code){assert(status==0);status=code;}
 void redirect(const char*){send(302);}};
struct WPage{WPage*next=nullptr;const char*getId(){return "page";}};
struct WDevice{WDevice*next=nullptr;WPage*firstPage=nullptr;const char*getId(){return "device";}};
struct Probe{WDevice*firstDevice=nullptr;bool mutation=false;
 bool authorize(AsyncWebServerRequest*r,bool value){mutation=value;if(!r->authenticated){r->send(401);return false;}return true;}
 bool checkAndLogWebAccess(AsyncWebServerRequest*){return true;}
 void handleUnknown(AsyncWebServerRequest*r){r->send(404);}
'''
        for name in ['handleHttpRootRequest', 'handleHttpNetworkConfiguration', 'handleHttpSave',
                     'handleHttpInfo', 'handleHttpReset', 'handleHttpFirmwareUpdate', 'replyStatic',
                     'handleOnThings', 'handleHttpDeviceConfiguration', 'handleHttpSaveDeviceConfiguration',
                     'handleHttpDevicePage', 'handleHttpDevicePageSubmitted']:
            source += f'template<class...T>void {name}(AsyncWebServerRequest*r,T...){{r->send(200);}}\n'
        source += native.method(native.NETWORK, 'handleOnRoot')+r'''
};
int main(){
 for(int verb:{4,8,16,32,64}){Probe p;AsyncWebServerRequest r;r.path="/info";r.verb=verb;p.handleOnRoot(&r);assert(r.status==404);}
 for(int verb:{HTTP_GET,4,8,16,32,64}){Probe p;AsyncWebServerRequest r;r.path="/save_network";r.verb=verb;p.handleOnRoot(&r);assert(r.status==405);}
 for(int verb:{HTTP_GET,HTTP_POST}){Probe p;AsyncWebServerRequest r;r.path="/info";r.verb=verb;p.handleOnRoot(&r);assert(r.status==200);}
 Probe p;AsyncWebServerRequest r;r.path="/save_network";r.verb=HTTP_POST;p.handleOnRoot(&r);assert(r.status==200&&p.mutation);
 AsyncWebServerRequest denied;denied.path="/info";denied.authenticated=false;p.handleOnRoot(&denied);assert(denied.status==401);
 puts("PASS root dispatcher completes all tested methods and preserves POST/auth guards");}
'''
        self.compile_run(source, 'http_dispatch')

    def test_json_keeps_signed_longs_and_full_unsigned_range(self):
        source = r'''
#include "Arduino.h"
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WJson.h"
#include "lib/WAdapter/WAdapter/WStringStream.h"
int main(){
 WStringStream stream(512);
 for(long value:{LONG_MIN,-2147483647L-1,-1L,0L,2147483647L,LONG_MAX}){
  stream.flush();WJson json(&stream);json.beginObject();json.propertyLong("value",value);json.endObject();
  assert(String(stream.c_str())==String("{\"value\":")+String(value)+"}");
 }
 for(unsigned long value:{0UL,2147483648UL,4294967295UL,ULONG_MAX}){
  stream.flush();WJson json(&stream);json.beginObject();json.propertyUnsignedLong("value",value);json.endObject();
  assert(String(stream.c_str())==String("{\"value\":")+String(value)+"}");
 }
 puts("PASS JSON signed LONG_MIN/-1/LONG_MAX and unsigned full range");}
'''
        self.compile_run(source, 'json_signed_long')
