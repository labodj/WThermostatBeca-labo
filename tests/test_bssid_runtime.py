"""Reject an SDK association that does not match the saved AP lock."""
import unittest
import native_support as native


class BssidRuntimeTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_connected_station_is_checked_without_interrupting_ota(self):
        self.compile_run(r'''
#include "Arduino.h"
constexpr int WL_CONNECTED=3;
struct Wifi {
    int state=WL_CONNECTED;unsigned disconnects=0;
    uint8_t address[6]={2,1,2,3,4,5};bool missing=false;
    int status(){return state;}
    const uint8_t* BSSID(){return missing?nullptr:address;}
    void disconnect(){++disconnects;state=0;}
} WiFi;
struct Probe {
    bool bssidLocked=true,updating=false;
    uint8_t bssid[6]={2,1,2,3,4,5};
    bool isUpdateRunning(){return updating;}
''' + native.method(native.NETWORK, "enforceBssidLock") + r'''
};
int main(){
    Probe p;p.enforceBssidLock();assert(!WiFi.disconnects);
    for(unsigned byte=0;byte<6;++byte){
        WiFi.state=WL_CONNECTED;WiFi.address[byte]^=1;
        const auto before=WiFi.disconnects;p.enforceBssidLock();
        assert(WiFi.disconnects==before+1 && WiFi.state==0);
        p.enforceBssidLock();assert(WiFi.disconnects==before+1);
        WiFi.address[byte]^=1;
    }
    WiFi.state=WL_CONNECTED;WiFi.address[5]^=1;p.bssidLocked=false;
    const auto before=WiFi.disconnects;p.enforceBssidLock();assert(WiFi.disconnects==before);
    p.bssidLocked=true;p.updating=true;p.enforceBssidLock();assert(WiFi.disconnects==before);
    p.updating=false;p.enforceBssidLock();assert(WiFi.disconnects==before+1);
    WiFi.state=WL_CONNECTED;WiFi.missing=true;p.enforceBssidLock();assert(WiFi.disconnects==before+2);
}
''', "bssid_runtime")

    def test_sdk_autoconnect_stays_disabled_until_selected_begin(self):
        text = native.NETWORK.read_text()
        constructor = text[text.index("    WNetwork(bool debug"):text.index("\t//returns true")]
        activation = constructor.index("WiFi.mode(")
        for call in ("WiFi.persistent(false)", "WiFi.setAutoConnect(false)", "WiFi.setAutoReconnect(false)"):
            self.assertLess(constructor.index(call), activation)
        connect = native.method(native.NETWORK, "connectWifi")
        self.assertLess(connect.index("WiFi.begin("), connect.index("WiFi.setAutoReconnect(true)"))
        loop = native.method(native.NETWORK, "loop")
        self.assertLess(loop.index("enforceBssidLock();"), loop.index("updateWifiRecovery(now);"))
