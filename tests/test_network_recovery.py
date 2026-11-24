"""Recovery access stays local and Digest explicitly uses UTF-8."""
import unittest
import native_support as native
from native_support import NETWORK, method


class NetworkRecoveryTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_server_cleanup_with_and_without_an_active_listener(self):
        source = r'''
#include "Arduino.h"
struct Listener { int stops=0; void end(){++stops;} };
struct Log { void notice(const __FlashStringHelper*){} };
struct Probe {
 Listener* webServer=nullptr; Log log; Log* wlog=&log;
 int hooks=0, notices=0, dns=0, mqtt=0, finished=0;
 std::function<void()> onConfigurationFinished=[this]{++finished;};
 bool updateRunning=false;
 bool isWebServerRunning(){return webServer!=nullptr;}
 void initWebserverDeinitHooks(Listener* active){assert(active);++hooks;}
 void notify(bool){++notices;}
 void deleteDnsApServer(){++dns;}
 void disconnectMqtt(){++mqtt;}
''' + method(NETWORK, 'stopWebServer') + r'''
};
int main(){
 for(bool active:{false,true}){
  Probe p;Listener listener;if(active)p.webServer=&listener;
  p.updateRunning=true;p.stopWebServer();
  assert(!listener.stops && !p.hooks && !p.dns && !p.mqtt && !p.finished);
  p.updateRunning=false;p.stopWebServer();
  assert(listener.stops==active && p.hooks==active && p.notices==active);
  assert(p.dns==1 && p.mqtt==1 && p.finished==1);
 }
}
'''
        self.compile_run(source, 'server_cleanup')

    def test_digest_challenge_charset_and_failed_randomness(self):
        source = r'''
#include "Arduino.h"
#include "lib/WAdapter/WAdapter/WDigestAuth.h"
String randomHash="01234567890123456789012345678901";
String genRandomMD5(){return randomHash;}
struct AsyncWebServerResponse{String header;void addHeader(const char* name,const String& value){assert(!strcmp(name,"WWW-Authenticate"));header=value;}};
struct AsyncWebServerRequest{
 int status=0;bool allocationFails=false;AsyncWebServerResponse response;
 AsyncWebServerResponse*beginResponse(int code){status=code;return allocationFails?nullptr:&response;}
 void send(int code){status=code;}void send(AsyncWebServerResponse*r){assert(r==&response);}
};
struct Probe{
 WDigestAuth digestAuth;
''' + method(NETWORK, 'requestAdminLogin') + r'''
};
int main(){Probe p;AsyncWebServerRequest r;p.requestAdminLogin(&r);
 assert(r.status==401&&r.response.header.indexOf("charset=UTF-8")>=0&&r.response.header.indexOf("qop=\"auth\"")>=0);
 AsyncWebServerRequest allocation;allocation.allocationFails=true;p.requestAdminLogin(&allocation);assert(allocation.status==503);
 randomHash="";AsyncWebServerRequest failed;p.requestAdminLogin(&failed);assert(failed.status==503&&failed.response.header.empty());
 puts("PASS UTF-8 Digest challenge and failed-randomness error path");}
'''
        self.compile_run(source, 'recovery_digest_challenge')

    def test_only_physical_configuration_callback_opens_local_login_recovery(self):
        from native_support import ROOT
        main = (ROOT / 'WThermostat/WThermostat.cpp').read_text()
        self.assertIn('becaDevice->setOnConfigurationRequest([]() {\n        network->startLocalRecovery();', main)
        self.assertEqual(1, main.count('startLocalRecovery();'))
        self.assertNotIn('startLocalRecovery', method(NETWORK, 'updateWifiRecovery'))
        self.assertLess(main.index('network->migrateRecoverySettings();'), main.index('network->getSettings()->save()'))
