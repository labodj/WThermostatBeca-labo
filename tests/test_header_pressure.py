"""Exercise the installed parser's admission before its throwing list allocation."""

import unittest

import test_regressions as native


class HeaderPressureTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_header_memory_guard_precedes_allocation_and_never_dispatches(self):
        path = native.ROOT / ".pio/libdeps/wthermostat/ESPAsyncWebServer/src/WebRequest.cpp"
        method = native.method(path, "AsyncWebServerRequest::_parseReqHeader")
        prefix = method.split("  AsyncWebHeader header =", 1)[0]
        self.assertIn("freeHeap", prefix)
        parse_line = native.method(path, "AsyncWebServerRequest::_parseLine")
        raw_response = native.method(path, "AsyncWebServerRequest::sendRawResponse")
        self.compile_run(r'''
#include "Arduino.h"
#include <limits>
struct Chip {
    size_t heap=16000, block=16000;
    size_t getFreeHeap(){return heap;}
    size_t getMaxFreeBlockSize(){return block;}
} ESP;
namespace asyncsrv { const char T_HTTP_503_HEAD[]="HTTP/1.1 503 Service Unavailable\r\n\r\n";
const char T_HTTP_400_HEAD[]="HTTP/1.1 400 Bad Request\r\n\r\n"; }
const char *REQUEST_ENDED="";
const char T_HTTP_100_CONT[]="HTTP/1.1 100 Continue\r\n\r\n";
constexpr unsigned PARSE_REQ_START=0, PARSE_REQ_HEADERS=1, PARSE_REQ_BODY=2, PARSE_REQ_END=3, CHUNK_NONE=0;
struct AsyncWebServerRequest {
    struct Temp {size_t size=0;size_t length(){return size;}} _temp;
    struct Server {unsigned attached=0;void _rewriteRequest(AsyncWebServerRequest*){}
      bool _attachHandler(AsyncWebServerRequest*){++attached;return true;}} server;
    Server *_server=&server;
    struct Client {unsigned writes=0,closed=0;std::string wire;
      size_t write(const char*data,size_t length){++writes;wire.append(data,length);return length;}
      void close(){++closed;}} client;
    Client *_client=&client;
    unsigned _parseState=PARSE_REQ_HEADERS, allocated=0, _contentLength=0, _chunkedParseState=CHUNK_NONE;
    bool _sent=false, _paused=true, _expectingContinue=false;
    bool _parseReqHead(){return true;}
    const char *_parseReqHeader();
    const char *_parseLine();
    void sendRawResponse(const char*);
};
''' + prefix + r'''
    ++allocated; return nullptr;
}
''' + parse_line + raw_response + r'''
int main(){
    for(size_t heap:{0U,1024U,2047U,2048U,3000U,4095U,4096U,16000U}){
        ESP.heap=heap;ESP.block=heap;
        AsyncWebServerRequest r;r._temp.size=256;
        const char *response=r._parseLine();
        const bool accepted=response==nullptr;
        assert(accepted==(heap>=2048));
        assert(r.allocated==(accepted?1U:0U));
        assert(r.server.attached==0);
        if(!accepted){
            r.sendRawResponse(response);
            assert(r._parseState==PARSE_REQ_END && r._sent && !r._paused);
            assert(r.client.wire==asyncsrv::T_HTTP_503_HEAD && r.client.closed==1);
            r.sendRawResponse(response);assert(r.client.writes==1);
            r._temp.size=0;assert(!r._parseLine() && r.server.attached==0);
        }
    }
    ESP.heap=16000;ESP.block=256;
    AsyncWebServerRequest fragmented;assert(fragmented._parseReqHeader()==asyncsrv::T_HTTP_503_HEAD);
    assert(fragmented.allocated==0);
    ESP.block=16000;
    AsyncWebServerRequest longHeader;longHeader._temp.size=std::numeric_limits<size_t>::max();
    assert(longHeader._parseReqHeader()==asyncsrv::T_HTTP_503_HEAD && !longHeader.allocated);
    AsyncWebServerRequest next;assert(!next._parseReqHeader() && next.allocated==1);
    next._expectingContinue=true;assert(!next._parseLine());
    assert(next.client.wire==T_HTTP_100_CONT && next.server.attached==1);
}
''', "header_pressure")
