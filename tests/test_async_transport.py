"""Exercise the installed server's transport code with bounded TCP space and retries."""
import os
import re
import unittest
from pathlib import Path
import native_support as native


SDK = native.ROOT / ".pio/libdeps/wthermostat/ESPAsyncWebServer/src/WebResponses.cpp"
TCP = native.tcp_source()


class AsyncTransportTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_queued_tail_and_retrying_sources_finish_only_after_delivery(self):
        path = Path(os.environ.get("ASYNC_RESPONSE_SOURCE", SDK))
        self.assertTrue(
            path.is_file(),
            "Run pio pkg install -e wthermostat before these integration tests",
        )
        body = native.method(path, "AsyncAbstractResponse::write_send_buffs").replace(
            "AsyncAbstractResponse::write_send_buffs", "write_send_buffs", 1
        )
        finished = native.method(path, "AsyncWebServerResponse::_finished").replace(
            "AsyncWebServerResponse::_finished", "_finished", 1
        )
        basic = native.method(path, "AsyncBasicResponse::write_send_buffs").replace(
            "AsyncBasicResponse::write_send_buffs", "write_basic", 1
        )
        tcp_path = Path(os.environ.get("ASYNC_TCP_SOURCE", TCP))
        send = native.method(tcp_path, "AsyncClient::send").replace("AsyncClient::send", "send", 1)
        can_send = native.method(tcp_path, "AsyncClient::canSend").replace("AsyncClient::canSend", "canSend", 1)
        buffer_policy = re.search(r"(?m)^#define ASYNC_RESPONCE_BUFF_SIZE .+$", SDK.with_name("WebResponseImpl.h").read_text()).group(0)
        poll = native.method(tcp_path, "AsyncClient::_poll").replace("AsyncClient::_poll", "poll", 1)
        write = re.search(r"(?ms)^size_t AsyncClient::write\(const char\* data, size_t size, uint8_t apiflags\).*?^}", tcp_path.read_text()).group().replace("AsyncClient::write", "write", 1)
        # Match the public TCP declaration, including its default write flag.
        write = write.replace("uint8_t apiflags)", "uint8_t apiflags=0)", 1)
        source = (
            r"""
#include "Arduino.h"
#include <array>
#include <memory>
#include <algorithm>
#include <limits>
#include <vector>
namespace asyncsrv { constexpr char T_hex_chars[] = "0123456789abcdef"; }
#include "lib/WAdapter/WAdapter/WPageResponse.h"
#define ASYNC_WRITE_FLAG_COPY 1
#define ASYNC_TCP_DEBUG(...) do{}while(0)
#define ASYNCWEBSERVER_USE_CHUNK_INFLIGHT 1
#define CONFIG_LWIP_TCP_MSS 536
#define CONFIG_LWIP_TCP_WND_DEFAULT 2144
#define ASYNC_RESPONCE_BUFF_SIZE 1072
constexpr size_t RESPONSE_TRY_AGAIN=std::numeric_limits<size_t>::max();
unsigned failedBufferAllocations=0;
void*operator new(std::size_t size,const std::nothrow_t&)noexcept{
 if(size==ASYNC_RESPONCE_BUFF_SIZE&&failedBufferAllocations){--failedBufferAllocations;return nullptr;}
 return ::operator new(size);
}
enum{RESPONSE_SETUP,RESPONSE_HEADERS,RESPONSE_CONTENT,RESPONSE_WAIT_ACK,RESPONSE_END,RESPONSE_FAILED};
using err_t=int;constexpr err_t ERR_OK=0,ERR_MEM=-1,ERR_RTE=-4;
unsigned outputFailures=0,outputAdvanceMs=0;err_t outputError=ERR_MEM;bool outputReady=false;
err_t tcp_output(void*){testMillis+=outputAdvanceMs;outputReady=!outputFailures;if(outputFailures){--outputFailures;return outputError;}return ERR_OK;}
struct tcp_pcb{};
struct ACErrorTracker{void setCloseError(err_t){}bool hasClient(){return true;}};
struct Client{
 tcp_pcb pcb;tcp_pcb*_pcb=&pcb;bool _pcb_busy=false,_tx_output_pending=false,_close_pcb=false;
 uint32_t _ack_timeout=5000,_rx_since_timeout=0,_rx_last_packet=0;
 std::function<void(void*,Client*,uint32_t)>_timeout_cb;void*_timeout_cb_arg=nullptr;
 std::function<void(void*,Client*)>_poll_cb;void*_poll_cb_arg=nullptr;
 uint16_t remotePort(){return 80;}
 void _close(){closed=true;}
 uint32_t _pcb_sent_at=0;size_t _tx_unacked_len=0;
 struct Pending{const char*data;size_t length;std::string copy;};
 std::vector<Pending>pending;
 std::string wire;size_t capacity=1072,window=1072,quota=1072;bool closed=false;
 size_t space(){return std::min(window,quota);}
 size_t add(const char*data,size_t n,uint8_t flags=0){size_t sent=std::min(n,std::min(window,quota));pending.push_back({data,sent,std::string(data,sent)});window-=sent;quota-=sent;_tx_unacked_len+=sent;return sent;}
 void transmit(){if(!outputReady)return;for(const auto&p:pending){const char*data=p.copy.empty()?p.data:p.copy.data();for(size_t i=0;i<p.length;++i)wire.push_back(data[i]);}pending.clear();}
 void close(){closed=true;}
 void next(size_t amount){assert(_tx_unacked_len<=capacity);window=capacity-_tx_unacked_len;quota=amount;}
"""
            + send
            + can_send
            + poll
            + write
            + r"""
};
struct AsyncWebServerRequest{Client tcp;Client*client(){return &tcp;}};
struct Probe{
 size_t _in_flight=0;unsigned _in_flight_credit=2;
 size_t _ackedLength=0,_writtenLength=0,_writtenHeadersLength=0,_sentLength=0,_contentLength=0;
 bool _chunked=false,_sendContentLength=true;int _state=RESPONSE_CONTENT;
 String _assembled_headers,_content;
 std::unique_ptr<std::array<uint8_t,ASYNC_RESPONCE_BUFF_SIZE>>_send_buffer;
 size_t _send_buffer_len=0,_send_buffer_offset=0;
 std::string payload;size_t cursor=0;unsigned emptyReads=0;
 WPageResponse*segmented=nullptr;
 explicit Probe(std::string body):_contentLength(body.size()),payload(std::move(body)){}
 bool _sourceValid(){return true;}
 size_t _fillBufferAndProcessTemplates(uint8_t*data,size_t length){
  if(emptyReads){--emptyReads;return RESPONSE_TRY_AGAIN;}
  if(segmented)return segmented->_fillBuffer(data,length);
  size_t n=std::min(length,payload.size()-cursor);memcpy(data,payload.data()+cursor,n);cursor+=n;return n;
 }
"""
            + body
            + basic
            + finished
            + r"""
};
void deliver(Probe&p,AsyncWebServerRequest&r,size_t quota,const std::string&expected,bool basic=false){
 size_t ack=0;auto tracker=std::make_shared<ACErrorTracker>();
 r.tcp._timeout_cb=[](void*,Client*c,uint32_t){c->close();};
 r.tcp._poll_cb=[&](void*,Client*c){if(c->canSend()&&!p._finished()){if(basic)p.write_basic(&r,0,0);else p.write_send_buffs(&r,0,0);}};
 for(unsigned tick=0;tick<expected.size()*4+10000&&(!p._finished()||r.tcp._tx_unacked_len);++tick){
  size_t previous=r.tcp.wire.size();
  if(ack){r.tcp._tx_unacked_len-=ack;if(!r.tcp._tx_unacked_len)r.tcp._pcb_busy=false;}
  r.tcp.next(quota);
  if(ack){if(!p._finished()){if(basic)p.write_basic(&r,ack,0);else p.write_send_buffs(&r,ack,0);}}
  else r.tcp.poll(tracker,&r.tcp.pcb);
  r.tcp.transmit();ack=r.tcp.wire.size()-previous;
  if(p._finished()&&!r.tcp._tx_unacked_len)assert(r.tcp.wire==expected);
 }
 assert(p._finished()&&!r.tcp.closed&&r.tcp.wire==expected);
}
int main(){
 {Probe p(std::string(4096,'t'));AsyncWebServerRequest r;outputFailures=2;outputAdvanceMs=1;deliver(p,r,1072,std::string(4096,'t'));outputAdvanceMs=0;testMillis=0;}
 {Client c;c.add("x",1,ASYNC_WRITE_FLAG_COPY);outputFailures=100;assert(c.send());c._timeout_cb=[](void*,Client*client,uint32_t){client->close();};testMillis=6000;auto tracker=std::make_shared<ACErrorTracker>();c.poll(tracker,&c.pcb);assert(c.closed);outputFailures=0;testMillis=0;}
 for(err_t error:{ERR_MEM,ERR_RTE}){
  std::string bytes(4096,'r');Probe p(bytes);AsyncWebServerRequest r;outputError=error;outputFailures=3;deliver(p,r,1072,bytes);assert(!outputFailures);
  Probe b(bytes);b._content=bytes.c_str();AsyncWebServerRequest br;outputFailures=3;deliver(b,br,1072,bytes,true);assert(!outputFailures);
 }
 {Probe p("body");p._state=RESPONSE_HEADERS;p._assembled_headers="HTTP/1.1 200 OK\r\n\r\n";AsyncWebServerRequest r;outputError=ERR_MEM;outputFailures=3;deliver(p,r,7,"HTTP/1.1 200 OK\r\n\r\nbody");}
 for(size_t quota:{1072U}){
  std::string bytes(8192,'p');WPageResponse page("text/html");assert(page.write(reinterpret_cast<const uint8_t*>(bytes.data()),bytes.size())==bytes.size());
  page.startForTest();Probe p(bytes);p.segmented=&page;AsyncWebServerRequest r;deliver(p,r,quota,bytes);
 }
 {Client tcp;for(unsigned n=0;n<10;++n){assert(tcp.send());assert(tcp.canSend());}}
 for(size_t size:{1U,939U,1072U,2011U,6144U}){
  std::string bytes;for(size_t i=0;i<size;++i)bytes+=char('a'+i%26);
  for(size_t quota:{1U,7U,536U,1072U})for(size_t capacity:{1072U,4096U}){
   if(size>CONFIG_LWIP_TCP_WND_DEFAULT&&quota<ASYNC_RESPONCE_BUFF_SIZE)continue;
   Probe p(bytes);AsyncWebServerRequest r;r.tcp.capacity=capacity;deliver(p,r,quota,bytes);
   Probe b(bytes);b._state=RESPONSE_HEADERS;b._assembled_headers="HTTP/1.1 200 OK\r\n\r\n";b._content=bytes.c_str();AsyncWebServerRequest br;br.tcp.capacity=capacity;deliver(b,br,quota,"HTTP/1.1 200 OK\r\n\r\n"+bytes,true);
  }
 }
 {Probe p("abc");p._chunked=true;p.emptyReads=2;AsyncWebServerRequest r;deliver(p,r,1072,"0003\r\nabc\r\n0000\r\n\r\n");}
 {Probe p("payload");p._state=RESPONSE_HEADERS;p._assembled_headers="HTTP/1.1 200 OK\r\n\r\n";AsyncWebServerRequest r;deliver(p,r,3,"HTTP/1.1 200 OK\r\n\r\npayload");}
 {Probe p("payload after memory pressure");p._state=RESPONSE_HEADERS;p._assembled_headers="HTTP/1.1 200 OK\r\n\r\n";AsyncWebServerRequest r;failedBufferAllocations=3;deliver(p,r,1072,"HTTP/1.1 200 OK\r\n\r\npayload after memory pressure");assert(failedBufferAllocations==0);}
 puts("PASS real SDK transport: complete tails, partial writes, retries, chunk termination and headers");
}
"""
        )
        source = source.replace("#define ASYNC_RESPONCE_BUFF_SIZE 1072", buffer_policy)
        self.compile_run(source, "async_transport_partial_writes")

    def test_global_weblog_handler_remains_user_owned_across_server_teardown(self):
        path = native.ROOT / "WThermostat/WLogDevice.h"
        source = (
            r"""
#include "Arduino.h"
struct AsyncWebServerRequest{};struct AsyncWebSocketClient{};using AwsEventType=int;
using ArMiddlewareNext=std::function<void()>;
struct AsyncWebSocket{
 bool destroyed=false;unsigned closes=0;
 template<class T>void addMiddleware(T){assert(!destroyed);}
 template<class T>void onEvent(T){assert(!destroyed);}
 void closeAll(){assert(!destroyed);++closes;}
}wslog;
struct AsyncWebServer{
 bool owns=false;AsyncWebSocket*handler=nullptr;
 void addHandler(AsyncWebSocket*p){owns=true;handler=p;}
 void addHandler(AsyncWebSocket&p){owns=false;handler=&p;}
 ~AsyncWebServer(){if(owns&&handler)handler->destroyed=true;}
};
struct Net{bool authorize(AsyncWebServerRequest*){return true;}};
struct Probe{Net net;Net*network=&net;
 void wsOnEvent(AsyncWebSocket*,AsyncWebSocketClient*,AwsEventType,void*,uint8_t*,size_t){}
"""
            + native.method(path, "webserverInitHook")
            + native.method(path, "webserverDeinitHook")
            + r"""
};
int main(){Probe p;
 for(unsigned n=0;n<2;++n){
  {AsyncWebServer server;p.webserverInitHook(&server);assert(server.handler==&wslog&&!server.owns);p.webserverDeinitHook(&server);}
  assert(!wslog.destroyed&&wslog.closes==n+1);
 }
 puts("PASS global WebLog handler is borrowed and survives server teardown/recreation");}
"""
        )
        self.compile_run(source, "web_log_handler_ownership")
