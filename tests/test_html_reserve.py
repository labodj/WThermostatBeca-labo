"""Leave transport/header capacity while constructing the next large page."""

import unittest

import test_regressions as native


class HtmlReserveTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_page_rejected_before_allocating_into_transport_reserve(self):
        text = native.NETWORK.read_text()
        start = text.index('\ttemplate<class T, typename ... Args> WCheckedPrint * httpHeader')
        end = text.index('\n\ttemplate<class T, typename ... Args> WCheckedPrint * httpHeader', start + 1)
        self.compile_run(r'''
#include "Arduino.h"
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WCheckedPrint.h"
#include "lib/WAdapter/WAdapter/WPageResponse.h"
const char* CT_TEXT_HTML="text/html",*HTTP_HEAD_BEGIN="%s:%s;",*HTTP_HEAD_SCRIPT="script:%s;",*HTTP_HEAD_STYLE="style:%s;",*HTTP_HEAD_END="end;";
String htmlEscapedString(const char* value){return value;}
struct Chip {unsigned heap=12000;unsigned getFreeHeap(){return heap;}unsigned getMaxFreeBlockSize(){return heap;}} ESP;
struct AsyncWebServerRequest {unsigned status=0;bool headersReleased=false;void removeHeaders(){headersReleased=true;}void send(unsigned code){status=code;}};
struct Probe {
    String csrfToken="token";
    bool isWebServerRunning(){return true;}
    const char* getIdx(){return "room";}
    String getFirmwareVersion(){return "test";}
    static void sendHttpPage(AsyncWebServerRequest*,WCheckedPrint*){assert(false);}
''' + text[start:end] + r'''
};
int main(){
    Probe p;AsyncWebServerRequest busy,next;
    assert(p.httpHeader(&busy,"large page",nullptr,6144)==nullptr && busy.status==503);
    assert(busy.headersReleased);
    ESP.heap=16384;
    auto* page=p.httpHeader(&next,"large page",nullptr,6144);assert(page && next.status==0);
    assert(next.headersReleased);
    auto* response=static_cast<WPageResponse*>(page->getTarget());delete page;delete response;
    ESP.heap=0;AsyncWebServerRequest empty;
    assert(p.httpHeader(&empty,"page",nullptr)==nullptr && empty.status==503);
}
''', "html_transport_reserve")
