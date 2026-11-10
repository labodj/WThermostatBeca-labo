"""Exercise production HTTP allocation decisions, including cold-cache assets."""

import unittest

import test_regressions as native
from render_ui import render_pages
from test_regressions import NETWORK, method


class WebMemoryTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_static_assets_borrow_flash_and_keep_cache_headers(self):
        text = NETWORK.read_text()
        methods = text[
            text.index("\tvoid replyStaticHeader(") : text.index(
                "\n\tvoid handleOnRoot("
            )
        ]
        source = (
            r"""
#include "Stream.h"
#include <map>
const char* HEADER_CT_ENCODING="Content-Encoding",*HEADER_CT_ENCODING_GZ="gzip",*HEADER_CACHECONTROL="Cache-Control",*HEADER_CACHECONTROL_900="max-age=900";
struct AsyncWebServerResponse{std::map<String,String>headers;const uint8_t*bytes=nullptr;size_t length=0;void addHeader(const char*n,const char*v){headers[n]=v;}};
struct AsyncWebServerRequest{
 AsyncWebServerResponse response;size_t copied=0;bool fail=false,sent=false;int status=0;
 AsyncWebServerResponse*beginResponse(int,const String&,const char* text){copied=strlen(text);return fail?nullptr:&response;}
 AsyncWebServerResponse*beginResponse(int,const String&,const uint8_t*bytes,size_t len){response.bytes=bytes;response.length=len;return fail?nullptr:&response;}
 void send(AsyncWebServerResponse*r){assert(r==&response);sent=true;status=200;}
 void send(int code){status=code;}
};
struct Probe{
"""
            + methods
            + r"""
};
int main(){
 Probe p;static const char asset[]="body{color:red}";AsyncWebServerRequest request;
 p.replyStatic(&request,"text/css",asset);assert(request.sent&&request.copied==0);
 assert(request.response.bytes==reinterpret_cast<const uint8_t*>(asset)&&request.response.length==strlen(asset));
 assert(request.response.headers["Cache-Control"]=="max-age=900");
 const uint8_t gzip[]={0x1f,0x8b,0,1};AsyncWebServerRequest icon;p.replyStatic(&icon,"image/x-icon",gzip,sizeof(gzip),true);
 assert(icon.sent&&icon.copied==0&&icon.response.length==sizeof(gzip)&&icon.response.headers["Content-Encoding"]=="gzip");
 AsyncWebServerRequest failure;failure.fail=true;p.replyStatic(&failure,"text/css",asset);assert(failure.status==503&&!failure.sent);
 puts("PASS static flash responses avoid body copies, preserve cache/gzip and handle failed factories");
}
"""
        )
        self.compile_run(source, "web_static_memory")

    def test_assets_use_a_smaller_reserve_without_weakening_page_guard(self):
        source = (
            r"""
#include "Arduino.h"
const char*URI_THINGS="/things",*URI_RESET="/reset",*URI_CSS="/css",*URI_JS="/js",*URI_FAVICON="/favicon.ico";
struct Chip{unsigned block=1536,free=20000;unsigned getFreeHeap(){return free;}unsigned getMaxFreeBlockSize(){return block;}}ESP;
struct AsyncWebServerRequest{String path;int code=0;String url(){return path;}const char*methodToString(){return "GET";}struct Client{struct Ip{String toString(){return "192.0.2.1";}};Ip remoteIP(){return {};}}client_;Client*client(){return &client_;}void send(int c){code=c;}};
struct Logger{template<class...T>void notice(T...) {}};
struct Probe{Logger log;Logger*wlog=&log;
"""
            + method(NETWORK, "checkAndLogWebAccess")
            + r"""
};
int main(){Probe p;
 for(const char*path:{"/css","/js","/favicon.ico"}){AsyncWebServerRequest r;r.path=path;assert(p.checkAndLogWebAccess(&r)&&!r.code);}
 for(const char*path:{"/things/thermostat"}){AsyncWebServerRequest r;r.path=path;assert(!p.checkAndLogWebAccess(&r)&&r.code==503);}
 for(const char*path:{"/config","/wifi","/thermostat_schedules"}){AsyncWebServerRequest r;r.path=path;assert(p.checkAndLogWebAccess(&r));}
 ESP.free=4000;AsyncWebServerRequest lowTotal;lowTotal.path="/wifi";assert(!p.checkAndLogWebAccess(&lowTotal));ESP.free=20000;
 ESP.block=512;AsyncWebServerRequest low;low.path="/js";assert(!p.checkAndLogWebAccess(&low)&&low.code==503);
 ESP.block=1024;AsyncWebServerRequest boundary;boundary.path="/js";assert(p.checkAndLogWebAccess(&boundary));
 ESP.block=10000;AsyncWebServerRequest page;page.path="/wifi";assert(p.checkAndLogWebAccess(&page));
 puts("PASS cold-cache assets have a bounded lower reserve; HTML/JSON and critically low memory remain protected");}
"""
        )
        self.compile_run(source, "web_heap_admission")

    def test_large_page_rejected_before_unsafe_constructor(self):
        # Small individual blocks and response objects still need a safe minimum.
        pages = render_pages(largest_heap_block=768)
        for route in ["/thermostat_schedules", "/schedules-fine", "/schedules-whole"]:
            self.assertEqual("", pages[route])
        self.assertEqual("", pages["/config"])

    def test_fragmented_heap_can_render_pages_larger_than_any_free_block(self):
        normal = render_pages()
        fragmented = render_pages(largest_heap_block=1536)
        for route, body in normal.items():
            if route.startswith("/info"):
                self.assertTrue(fragmented[route].rstrip().endswith("</html>"))
                self.assertIn("1536 Byte", fragmented[route])
            else:
                self.assertEqual(body, fragmented[route])

    def test_every_html_caller_handles_failed_response_allocation(self):
        pages = render_pages(response_allocation_fails=True)
        self.assertTrue(
            all(
                not body
                for route, body in pages.items()
                if route not in ["/css", "/js"]
            )
        )

    def test_html_and_two_cold_cache_assets_share_a_constrained_heap(self):
        import json

        from render_ui import raw_asset
        from test_regressions import ROOT

        text = NETWORK.read_text()
        static_methods = text[
            text.index("\tvoid replyStaticHeader(") : text.index(
                "\n\tvoid handleOnRoot("
            )
        ]
        source = (
            r"""
#include "Stream.h"
// Conservative model: three HTTP objects and the HTML transport window are already held.
// This exercises admission/copy interaction, not an ESP allocator or radio emulator.
struct Heap{size_t block=13088-6144-3*512-1072;size_t getFreeHeap(){return 20000;}size_t getMaxFreeBlockSize(){return block;}}ESP;
const char*URI_THINGS="/things",*URI_RESET="/reset",*URI_CSS="/css",*URI_JS="/js",*URI_FAVICON="/favicon.ico";
const char*HEADER_CT_ENCODING="Content-Encoding",*HEADER_CT_ENCODING_GZ="gzip",*HEADER_CACHECONTROL="Cache-Control",*HEADER_CACHECONTROL_900="max-age=900";
struct AsyncWebServerResponse{void addHeader(const char*,const char*){}};
struct AsyncWebServerRequest{
 String path;int status=0;size_t copies=0;AsyncWebServerResponse response;
 String url(){return path;}const char*methodToString(){return "GET";}
 struct Client{struct Ip{String toString(){return "192.0.2.1";}};Ip remoteIP(){return {};}}client_;
 Client*client(){return &client_;}
 AsyncWebServerResponse*beginResponse(int,const String&,const char*text){copies=strlen(text);assert(ESP.block>=copies);ESP.block-=copies;return &response;}
 AsyncWebServerResponse*beginResponse(int,const String&,const uint8_t*,size_t){return &response;}
 void send(int code){status=code;}
 void send(AsyncWebServerResponse*){status=200;assert(ESP.block>=1072);ESP.block-=1072;}
};
struct Log{template<class...T>void notice(T...){}};
struct Probe{Log logger;Log*wlog=&logger;
"""
            + static_methods
            + method(NETWORK, "checkAndLogWebAccess")
            + "\n};\n"
        )
        source += (
            "const char js[]="
            + json.dumps(
                raw_asset(ROOT / "lib/WAdapter/WAdapter/WHtmlPages.h", "PAGE_JS")
            )
            + ";\n"
        )
        source += (
            "const char css[]="
            + json.dumps(
                raw_asset(ROOT / "lib/WAdapter/WAdapter/WHtmlPages.h", "PAGE_CSS")
            )
            + ";\n"
        )
        source += r"""
int main(){Probe p;AsyncWebServerRequest script,style;script.path="/js";style.path="/css";
 assert(p.checkAndLogWebAccess(&script));p.replyStatic(&script,"text/javascript",js);assert(script.status==200&&script.copies==0);
 assert(p.checkAndLogWebAccess(&style));p.replyStatic(&style,"text/css",css);assert(style.status==200&&style.copies==0);
 assert(ESP.block>=2048);puts("PASS HTML plus two cold-cache flash assets fit the constrained heap without body copies");}
"""
        self.compile_run(source, "web_concurrent_asset_memory")
