"""WebLog connection status reflects the actual saved logging level."""
import unittest

import test_regressions as native


class WebLogStatusTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_silent_and_enabled_levels_report_their_actual_status(self):
        handler = native.method(native.ROOT / "WThermostat/WLogDevice.h", "wsOnEvent")
        self.compile_run(r'''
#include "Arduino.h"
#include <cstdarg>
#include <cstdio>
constexpr unsigned LOG_LEVEL_SILENT=0;
constexpr int WS_CONNECTED=1;
enum AwsEventType {WS_EVT_CONNECT,WS_EVT_DATA,WS_EVT_DISCONNECT};
struct AsyncWebSocket {};
struct AsyncWebSocketClient {
    int state=WS_CONNECTED;bool writable=true;unsigned pings=0;std::string wire;
    int status(){return state;} bool canSend(){return writable;} unsigned id(){return 7;}
    void printf(const char*format,...){
        char text[256];va_list args;va_start(args,format);
        int count=std::vsnprintf(text,sizeof(text),format,args);va_end(args);
        assert(count>=0&&static_cast<size_t>(count)<sizeof(text));wire+=text;
    }
    void ping(){++pings;}
};
struct Property {const char*value;const char*c_str(){return value;}};
struct Log {
    unsigned level=0;Property property{"silent"};Property*logLevelWeb=&property;
    unsigned getlogLevelWebByte(){return level;}
''' + handler + r'''
};
int main(){
    const char*levels[]={"silent","fatal","error","warning","notice","trace","verbose"};
    for(unsigned level=0;level<7;++level){
        Log log;log.level=level;log.property.value=levels[level];AsyncWebSocketClient client;
        log.wsOnEvent(nullptr,&client,WS_EVT_CONNECT,nullptr,nullptr,0);
        assert(client.wire.find("Hello WebSocket Client #7")!=std::string::npos);
        if(level==0){
            assert(client.wire.find("Web logging is disabled.")!=std::string::npos);
            assert(client.wire.find("Showing")==std::string::npos);
        }else{
            assert(client.wire.find(std::string("Showing ")+levels[level]+" logs and more severe messages.")!=std::string::npos);
            assert(client.wire.find("disabled")==std::string::npos);
        }
        assert(client.pings==1);auto greeting=client.wire;
        log.wsOnEvent(nullptr,&client,WS_EVT_DATA,nullptr,nullptr,0);
        assert(client.pings==2&&client.wire==greeting);
        log.wsOnEvent(nullptr,nullptr,WS_EVT_CONNECT,nullptr,nullptr,0);
        client.state=0;log.wsOnEvent(nullptr,&client,WS_EVT_CONNECT,nullptr,nullptr,0);
        assert(client.pings==2&&client.wire==greeting);
        client.state=WS_CONNECTED;client.writable=false;
        log.wsOnEvent(nullptr,&client,WS_EVT_CONNECT,nullptr,nullptr,0);
        assert(client.pings==2&&client.wire==greeting);
    }
}
''', "weblog_status")
