"""HTTP authentication, upload ownership and request isolation."""
import unittest
import native_support as native
from native_support import NETWORK, method


class HttpRequestsTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_http_authorization_and_request_isolation(self):
        source = r'''
#include "Arduino.h"
#include <map>
const int HTTP_GET=1,HTTP_POST=2,HTTP_PUT=4;
const char* CT_TEXT_PLAIN="text/plain",*URI_FIRMWARE="/firmware";
const size_t SIZE_JSON_PACKET=3096;
enum class wnWifiMode{WIFIMODE_AP,WIFIMODE_FALLBACK,WIFIMODE_STATION};
struct Parameter{String text;String value(){return text;}};
struct AsyncWebServerRequest{
    void*_tempObject=nullptr;bool sent=false,authenticated=true;int status=0,verb=HTTP_PUT;
    String path="/things/thermostat/properties",hostname="thermostat";
    std::map<std::string,Parameter>headers,params;
    ~AsyncWebServerRequest(){free(_tempObject);}
    bool isSent(){return sent;}void send(int s,const char* =nullptr,const char* =nullptr){sent=true;status=s;}
    bool hasHeader(const char*s){return headers.count(s);}Parameter*getHeader(const char*s){return &headers.at(s);}
    bool hasParam(const char*s,bool){return params.count(s);}Parameter*getParam(const char*s,bool){return &params.at(s);}
    String host(){return hostname;}String url(){return path;}int method(){return verb;}
    bool authenticate(const char*,const char*){return authenticated;}
    struct Client{int ip=1;int localIP(){return ip;}} connection;
    Client*client(){return &connection;}
    void requestAuthentication(const char*){send(401);}
};
struct Wifi{int softAPIP(){return 1;}} WiFi;
struct Probe{
    struct Auth { bool authenticate(AsyncWebServerRequest* r,const char*) {return r->authenticated;} } digestAuth;
    bool updating=false;AsyncWebServerRequest*updateRequest=nullptr;
    bool isUpdateRunning(){return updating;}
    bool localRecoveryActive=false;unsigned long localRecoveryStartedAt=0;
    void requestAdminLogin(AsyncWebServerRequest* r){r->requestAuthentication("WThermostat");}
    struct HttpBody{size_t capacity,received;char data[1];};
    String csrfToken="token",ssid="wifi",password="test-pass";bool ap=false,authRequired=true;
    bool isAuthenticationRequired(){return authRequired;}
    wnWifiMode wifiModeRunning=wnWifiMode::WIFIMODE_STATION;
    bool isSoftAP(){return ap;}const char*getSsid(){return ssid.c_str();}const char*getPassword(){return password.c_str();}
'''
        for name in ["isLocalRecoveryRequest", "authorize", "handlePutBody", "handlePutBodyDone"]:
            source += method(NETWORK, name) + "\n"
        source += r'''
};
int main(){
    Probe network;uint8_t small[4]={'1','2','3','4'},large[24]{};
    AsyncWebServerRequest a,b;
    network.handlePutBody(&a,small,2,0,4);network.handlePutBody(&b,large,24,0,24);
    network.handlePutBody(&a,small+2,2,2,4);
    auto*one=static_cast<Probe::HttpBody*>(a._tempObject);auto*two=static_cast<Probe::HttpBody*>(b._tempObject);
    assert(one!=two&&one->received==4&&two->received==24&&!strcmp(one->data,"1234"));
    network.handlePutBodyDone(&a);assert(a._tempObject==nullptr);
    AsyncWebServerRequest denied;denied.authenticated=false;network.handlePutBody(&denied,small,4,0,4);assert(denied.status==401&&!denied._tempObject);
    AsyncWebServerRequest huge;network.handlePutBody(&huge,small,4,0,3097);assert(huge.status==413&&!huge._tempObject);
    AsyncWebServerRequest order;network.handlePutBody(&order,small,2,0,4);network.handlePutBody(&order,small,2,1,4);assert(order.status==400);
    AsyncWebServerRequest evil;evil.headers["Origin"]={"http://evil.example"};assert(!network.authorize(&evil,true)&&evil.status==403);
    AsyncWebServerRequest form;form.verb=HTTP_POST;form.path="/save_network";assert(!network.authorize(&form,true)&&form.status==403);
    form.sent=false;form.params["csrf"]={"token"};assert(network.authorize(&form,true));
    AsyncWebServerRequest setup;setup.authenticated=false;network.ap=true;network.ssid="";assert(network.authorize(&setup));
    network.ssid="wifi";network.wifiModeRunning=wnWifiMode::WIFIMODE_FALLBACK;assert(!network.authorize(&setup)&&setup.status==401);
    setup.sent=false;setup.authenticated=true;assert(network.authorize(&setup));
    network.localRecoveryActive=true;network.localRecoveryStartedAt=100;testMillis=100;
    setup.sent=false;setup.authenticated=false;network.wifiModeRunning=wnWifiMode::WIFIMODE_AP;
    assert(network.authorize(&setup));
    setup.connection.ip=2;assert(!network.authorize(&setup)&&setup.status==401);
    setup.sent=false;setup.connection.ip=1;testMillis=300100;assert(!network.authorize(&setup)&&setup.status==401);
    network.updating=true;network.updateRequest=&setup;setup.sent=false;assert(network.authorize(&setup));
    AsyncWebServerRequest newcomer;newcomer.authenticated=false;assert(!network.authorize(&newcomer)&&newcomer.status==401);
    network.updating=false;network.updateRequest=nullptr;
    testMillis=100;setup.sent=false;setup.verb=HTTP_POST;assert(!network.authorize(&setup,true)&&setup.status==403);
    setup.sent=false;setup.params["csrf"]={"token"};assert(network.authorize(&setup,true));
    network.localRecoveryActive=false;
    network.authRequired=false;network.ap=false;network.password="";
    AsyncWebServerRequest open;open.authenticated=false;assert(network.authorize(&open));
    open.verb=HTTP_POST;assert(!network.authorize(&open,true)&&open.status==403);
    open.sent=false;open.params["csrf"]={"token"};assert(network.authorize(&open,true));
    AsyncWebServerRequest cross;cross.authenticated=false;cross.headers["Origin"]={"http://evil.example"};
    assert(!network.authorize(&cross,true)&&cross.status==403);
    puts("PASS authentication, CSRF, body size/order, concurrent requests and provisioning");
}
'''
        self.compile_run(source, "http")

    def test_ota_ownership_authorization_and_disconnect(self):
        source = r"""
#include "Arduino.h"
const char* CT_TEXT_PLAIN="text/plain";
struct AsyncWebServerRequest {
    int status=0;bool sent=false,allowed=true;std::function<void()>disconnect;
    bool isSent(){return sent;}void send(int s,const char* =nullptr,const char* =nullptr){sent=true;status=s;}
    void onDisconnect(std::function<void()>f){disconnect=f;}
};
struct ESPType{uint32_t getFreeSketchSpace(){return 500000;}}ESP;
struct Updater{
    bool running=false,error=false;unsigned written=0,ends=0;
    void runAsync(bool){}bool begin(unsigned){running=true;error=false;written=0;return true;}
    size_t write(uint8_t*,size_t n){written+=n;return n;}bool hasError(){return error;}
    bool isRunning(){return running;}bool end(bool final){++ends;running=false;return final&&!error;}
}Update;
struct Probe{
    bool updateRunning=false,updateSucceeded=false,restarted=false;const __FlashStringHelper*firmwareUpdateError=nullptr;
    AsyncWebServerRequest*updateRequest=nullptr;
    bool authorize(AsyncWebServerRequest*r,bool){if(!r->allowed){r->send(401);return false;}return true;}
    void disconnectMqtt(){}void setFirmwareUpdateError(const char*){Update.error=true;}
    void restart(AsyncWebServerRequest*r,const __FlashStringHelper*){restarted=true;r->send(200);}
"""
        for name in ["handleHttpFirmwareUpdateProgress", "handleHttpFirmwareUpdateFinished"]:
            source += method(NETWORK, name) + "\n"
        source += r"""
};
int main(){
    uint8_t bytes[8]{};Probe network;
    AsyncWebServerRequest denied;denied.allowed=false;
    network.handleHttpFirmwareUpdateProgress(&denied,"x",0,bytes,8,true);
    assert(denied.status==401&&Update.written==0&&!network.updateRunning);
    AsyncWebServerRequest a,b;network.handleHttpFirmwareUpdateProgress(&a,"x",0,bytes,4,false);
    assert(network.updateRunning&&Update.written==4);
    network.handleHttpFirmwareUpdateProgress(&b,"x",0,bytes,8,true);
    assert(b.status==409&&Update.written==4);
    network.handleHttpFirmwareUpdateFinished(&b);assert(!network.restarted);
    a.disconnect();assert(!network.updateRunning&&!Update.running);
    AsyncWebServerRequest c;network.handleHttpFirmwareUpdateProgress(&c,"x",0,bytes,8,true);
    network.handleHttpFirmwareUpdateFinished(&c);assert(c.status==200&&network.restarted);
    network.restarted=false;
    AsyncWebServerRequest d;network.handleHttpFirmwareUpdateProgress(&d,"x",0,bytes,8,false);
    Update.error=true;network.handleHttpFirmwareUpdateFinished(&d);
    assert(d.status==400&&!network.restarted&&!Update.running);
    puts("PASS OTA rejects unauthorized/concurrent requests and handles interruption/failure");
}
"""
        self.compile_run(source, "ota")

    def test_http_headers_remain_with_their_request_on_reentry(self):
        text = native.NETWORK.read_text()
        start = text.index('\ttemplate<class T, typename ... Args> WCheckedPrint * httpHeader')
        end = text.index('\n\ttemplate<class T, typename ... Args> WCheckedPrint * httpHeader', start + 1)
        source = r'''
#include "Arduino.h"
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WCheckedPrint.h"
const char* CT_TEXT_HTML="text/html",*HTTP_HEAD_BEGIN="%s:%s;",*HTTP_HEAD_SCRIPT="script:%s;",*HTTP_HEAD_STYLE="style:%s;",*HTTP_HEAD_END="end;";
String htmlEscapedString(const char* value){return value;}
#include "lib/WAdapter/WAdapter/WPageResponse.h"
std::function<void()> allocationHook;
void*operator new(size_t size,const std::nothrow_t&)noexcept{
 if(allocationHook){auto hook=std::move(allocationHook);allocationHook=nullptr;hook();}
 return ::operator new(size);
}
struct AsyncWebServerRequest{void removeHeaders(){}void send(int){assert(false);}};
struct Chip{unsigned getMaxFreeBlockSize(){return 24000;}unsigned getFreeHeap(){return 24000;}}ESP;
struct Probe{String csrfToken="token";
 static void sendHttpPage(AsyncWebServerRequest*,WCheckedPrint*){assert(false);}
 bool isWebServerRunning(){return true;}const char*getIdx(){return "room";}String getFirmwareVersion(){return "test";}
'''+text[start:end]+r'''
};
std::string drain(WCheckedPrint*page){auto*r=static_cast<WPageResponse*>(page->getTarget());delete page;uint8_t data[256];std::string out;
 while(size_t size=r->_fillBuffer(data,sizeof(data)))out.append(reinterpret_cast<char*>(data),size);delete r;return out;}
int main(){Probe p;AsyncWebServerRequest first,second;WCheckedPrint*inner=nullptr;
 allocationHook=[&](){inner=p.httpHeader(&second,"second",nullptr);};
 auto*outer=p.httpHeader(&first,"first",nullptr);assert(outer&&inner&&outer->getTarget()!=inner->getTarget());
 const auto firstBody=drain(outer),secondBody=drain(inner);
 assert(firstBody.find("<h1>first</h1>")!=std::string::npos&&firstBody.find("second")==std::string::npos);
 assert(secondBody.find("<h1>second</h1>")!=std::string::npos&&secondBody.find("first")==std::string::npos);
 puts("PASS response headers remain request-local under reentry");}
'''
        self.compile_run(source, 'http_header_reentry')

    def test_http_dispatch_always_finishes_unsupported_methods(self):
        source = r'''
#include "Arduino.h"
const int HTTP_GET=1,HTTP_POST=2;
const char*URI_SAVE="/save_",*URI_RESET="/reset",*URI_THINGS="/things",*URI_CONFIG="/config",*URI_WIFI="/wifi",
 *URI_INFO="/info",*URI_FIRMWARE="/firmware",*URI_CSS="/css",*URI_JS="/js",*URI_FAVICON="/favicon",*ID_NETWORK="network";
const char*CT_TEXT_CSS="text/css",*CT_TEXT_JS="text/js",*CT_IMAGE_ICON="image/x-icon",*PAGE_CSS="",*PAGE_JS="",*favicon_ico_gz="";
const int favicon_ico_gz_len=0;
struct AsyncWebServerRequest{String path;int verb=HTTP_GET,status=0;bool authenticated=true,csrf=true;
 String url(){return path;}int method(){return verb;}void send(int code){assert(status==0);status=code;}
 void redirect(const char*){send(302);}};
struct WPage{WPage*next=nullptr;const char*id="page";const char*getId(){return id;}};
struct WDevice{WDevice*next=nullptr;WPage*firstPage=nullptr;const char*id="device";const char*getId(){return id;}};
struct Probe{WDevice*firstDevice=nullptr;bool mutation=false;unsigned submitted=0;
 bool authorize(AsyncWebServerRequest*r,bool value){mutation=value;if(!r->authenticated){r->send(401);return false;}if(value&&!r->csrf){r->send(403);return false;}return true;}
 void handleHttpDevicePageSubmitted(AsyncWebServerRequest*r,WDevice*,WPage*){++submitted;r->send(200);}
 bool checkAndLogWebAccess(AsyncWebServerRequest*){return true;}
 void handleUnknown(AsyncWebServerRequest*r){r->send(404);}
'''
        for name in ['handleHttpRootRequest', 'handleHttpNetworkConfiguration', 'handleHttpSave',
                     'handleHttpInfo', 'handleHttpReset', 'handleHttpFirmwareUpdate', 'replyStatic',
                     'handleOnThings', 'handleHttpDeviceConfiguration', 'handleHttpSaveDeviceConfiguration',
                     'handleHttpDevicePage']:
            source += f'template<class...T>void {name}(AsyncWebServerRequest*r,T...){{r->send(200);}}\n'
        source += native.method(native.NETWORK, 'handleOnRoot')+r'''
};
int main(){
 for(int verb:{4,8,16,32,64}){Probe p;AsyncWebServerRequest r;r.path="/info";r.verb=verb;p.handleOnRoot(&r);assert(r.status==404);}
 for(int verb:{HTTP_GET,4,8,16,32,64}){Probe p;AsyncWebServerRequest r;r.path="/save_network";r.verb=verb;p.handleOnRoot(&r);assert(r.status==405);}
 for(int verb:{HTTP_GET,HTTP_POST}){Probe p;AsyncWebServerRequest r;r.path="/info";r.verb=verb;p.handleOnRoot(&r);assert(r.status==200);}
 Probe p;AsyncWebServerRequest r;r.path="/save_network";r.verb=HTTP_POST;p.handleOnRoot(&r);assert(r.status==200&&p.mutation);
 AsyncWebServerRequest denied;denied.path="/info";denied.authenticated=false;p.handleOnRoot(&denied);assert(denied.status==401);
 for(int verb:{HTTP_GET,HTTP_POST}){
  Probe p;WDevice device;WPage page;device.id="thermostat";page.id="reinit";
  device.firstPage=&page;p.firstDevice=&device;
  AsyncWebServerRequest preview;preview.path="/thermostat_reinit";preview.verb=verb;
  p.handleOnRoot(&preview);assert(preview.status==200&&!p.mutation&&!p.submitted);
 }
 for(int scenario=0;scenario<4;++scenario){
  Probe p;WDevice device;WPage page;device.id="thermostat";page.id="reinit";
  device.firstPage=&page;p.firstDevice=&device;
  AsyncWebServerRequest r;r.path="/save_thermostat_reinit";r.verb=scenario==0?HTTP_GET:HTTP_POST;
  r.authenticated=scenario!=1;r.csrf=scenario!=2;p.handleOnRoot(&r);
  assert(r.status==(scenario==0?405:scenario==1?401:scenario==2?403:200));
  assert(p.submitted==(scenario==3?1U:0U));
  if(scenario==3)assert(p.mutation);
 }
 puts("PASS root dispatcher completes all tested methods and preserves POST/auth guards");}
'''
        self.compile_run(source, 'http_dispatch')
