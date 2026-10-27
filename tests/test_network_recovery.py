"""Recovery access stays local and Digest explicitly uses UTF-8."""
import unittest

import test_regressions as native
from test_regressions import NETWORK, method


class NetworkRecoveryTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_digest_challenge_charset_and_failed_randomness(self):
        source = r'''
#include "Arduino.h"
String randomHash="01234567890123456789012345678901";
String genRandomMD5(){return randomHash;}
struct AsyncWebServerResponse{String header;void addHeader(const char* name,const String& value){assert(!strcmp(name,"WWW-Authenticate"));header=value;}};
struct AsyncWebServerRequest{
 int status=0;bool allocationFails=false;AsyncWebServerResponse response;
 AsyncWebServerResponse*beginResponse(int code){status=code;return allocationFails?nullptr:&response;}
 void send(int code){status=code;}void send(AsyncWebServerResponse*r){assert(r==&response);}
};
struct Probe{
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
        from test_regressions import ROOT
        main = (ROOT / 'WThermostat/WThermostat.cpp').read_text()
        self.assertIn('becaDevice->setOnConfigurationRequest([]() {\n        network->startLocalRecovery();', main)
        self.assertEqual(1, main.count('startLocalRecovery();'))
        self.assertNotIn('startLocalRecovery', method(NETWORK, 'updateWifiRecovery'))
        self.assertLess(main.index('network->migrateRecoverySettings();'), main.index('network->getSettings()->save();'))
