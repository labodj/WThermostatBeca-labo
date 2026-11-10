"""Regressions for low-memory HTML and a concurrent live WebLog client."""

import unittest

import test_regressions as native
from render_ui import render_pages


class WebConcurrencyTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_wifi_never_needs_copy_before_free_growth(self):
        normal = render_pages()
        constrained = render_pages(response_heap_budget=6500)
        for route in ("/wifi", "/wifi-static", "/wifi-off"):
            with self.subTest(route=route):
                self.assertEqual(normal[route], constrained[route])
                self.assertTrue(constrained[route].rstrip().endswith("</html>"))

    def test_web_logging_yields_to_http_and_full_queues_without_losing_mqtt(self):
        source = (
            r"""
#include "Arduino.h"
const char*MQTT_TELE="tele";
struct Chip{unsigned block=7000;unsigned getMaxFreeBlockSize(){return block;}}ESP;
struct Socket{bool writable=true;unsigned clients=1,sent=0;bool availableForWriteAll(){return writable;}unsigned count(){return clients;}
 template<class...T>void printfAll(T...){++sent;}}wslog;
struct Network{unsigned mqtt=0;const char*getMqttTopic(){return "room";}bool isMqttConnected(){return true;}void publishMqtt(const char*,const char*){++mqtt;}};
struct Probe{Network*network;unsigned getlogLevelWebByte(){return 6;}unsigned getlogLevelByte(){return 6;}const char*logLevelByteToString(int){return "Notice";}
"""
            + native.method(
                native.ROOT / "WThermostat/WLogDevice.h", "sendLog"
            ).replace(" override", "")
            + r"""
};
int main(){Network net;Probe p{&net};
 p.sendLog(4,"HTTP is using memory");assert(wslog.sent==0&&net.mqtt==1);
 ESP.block=16000;wslog.writable=false;p.sendLog(4,"Slow browser");assert(wslog.sent==0&&net.mqtt==2);
 wslog.writable=true;wslog.clients=0;p.sendLog(4,"No clients");assert(wslog.sent==0&&net.mqtt==3);
 wslog.clients=1;p.sendLog(4,"Available");assert(wslog.sent==1&&net.mqtt==4);
 puts("PASS WebLog drops transient messages under pressure; MQTT logging is independent");}
"""
        )
        self.compile_run(source, "web_log_backpressure")

    def test_short_html_is_discarded_and_response_ownership_is_transferred_once(self):
        source = (
            r"""
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WCheckedPrint.h"
const char*CT_TEXT_PLAIN="text/plain";
struct WPageResponse:Print{
 static unsigned destroyed;std::string body;size_t limit=100;
 ~WPageResponse(){++destroyed;}
 size_t write(uint8_t c)override{return write(&c,1);}
 size_t write(const uint8_t*d,size_t n)override{size_t actual=std::min(n,limit-body.size());body.append(reinterpret_cast<const char*>(d),actual);return actual;}
};unsigned WPageResponse::destroyed=0;
struct AsyncWebServerRequest{int code=0;std::string body;
 void send(WPageResponse*r){code=200;body=r->body;delete r;}
 void send(int c,const char*,const char*message){code=c;body=message;}
};
struct Probe{
"""
            + native.method(native.NETWORK, "sendHttpPage")
            + r"""
};
int main(){
 auto*r=new WPageResponse;r->limit=7;auto*p=new WCheckedPrint(r);
 assert(p->print("partial page")==7);assert(!p->ok());assert(!p->print("</html>"));
 AsyncWebServerRequest failed;Probe::sendHttpPage(&failed,p);
 assert(failed.code==503&&failed.body.find("partial page")==std::string::npos&&WPageResponse::destroyed==1);
 r=new WPageResponse;p=new WCheckedPrint(r);assert(p->format("<html>%d</html>",23)==15);
 AsyncWebServerRequest good;Probe::sendHttpPage(&good,p);
 assert(good.code==200&&good.body=="<html>23</html>"&&WPageResponse::destroyed==2);
 puts("PASS short HTML is never sent as success and both ownership paths destroy exactly once");}
"""
        )
        self.compile_run(source, "web_checked_html_send")

    def test_format_allocation_failure_is_sticky_and_bounded(self):
        source = r"""
#include "Stream.h"
#include <new>
#include <cstdlib>
bool failArrayAllocation=false;
void* operator new[](size_t size,const std::nothrow_t&)noexcept{
 if(failArrayAllocation)return nullptr;
 return std::malloc(size);
}
void operator delete[](void*p)noexcept{std::free(p);}
#include "lib/WAdapter/WAdapter/WCheckedPrint.h"
struct Sink:Print{std::string body;
 size_t write(uint8_t c)override{return write(&c,1);}
 size_t write(const uint8_t*d,size_t n)override{body.append(reinterpret_cast<const char*>(d),n);return n;}};
int main(){
 Sink sink;WCheckedPrint good(&sink);std::string large(512,'x');
 assert(good.format("[%s]",large.c_str())==514&&good.ok());assert(sink.body=="["+large+"]");
 Sink other;WCheckedPrint failed(&other);failArrayAllocation=true;
 assert(!failed.format("%s",large.c_str())&&!failed.ok()&&other.body.empty());
 failArrayAllocation=false;assert(!failed.print("after failure")&&other.body.empty());
 WCheckedPrint bounded(&other);std::string huge(8193,'y');
 assert(!bounded.format("%s",huge.c_str())&&!bounded.ok()&&other.body.empty());
 puts("PASS formatting allocation failures and size bounds invalidate the whole response");}
"""
        self.compile_run(source, "web_checked_format_allocation")

    def test_failed_headers_do_not_run_submitted_callbacks(self):
        # The renderer also asserts that the submitted callback was not invoked.
        pages = render_pages(fail_header_write=True)
        self.assertTrue(
            all(
                not body
                for route, body in pages.items()
                if route not in ("/css", "/js")
            )
        )
