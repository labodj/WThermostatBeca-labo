"""Exercise the emitted discovery messages, not a copy of their JSON templates."""
from functools import lru_cache
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_regressions as regressions
from test_regressions import BECA, NETWORK, ROOT, method


@lru_cache(maxsize=1)
def discovery_records():
    text = BECA.read_text()
    constants = text[text.index("const static char HTTP_CONFIG_SCHTAB_HEAD"):text.index("class WBecaDevice:")]
    source = r'''
#include "Arduino.h"
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WJson.h"
#include "lib/WAdapter/WAdapter/WStringStream.h"
#define SIZE_JSON_PACKET 3096
struct Log{template<class...T>void notice(T...){}};
struct Ip{String toString(){return "192.0.2.1";}};
struct Net{
    Log value;bool success=true;unsigned scenario=0;
    String id="room_A-1",topic="home/room_A-1",firmware="1.24-labo.1";
    Log*log(){return &value;}const char*getIdx(){return id.c_str();}
    String getMacAddress(){return "aa:bb:cc:dd:ee:ff";}
    String getApplicationName(){return "WThermostat";}String getFirmwareVersion(){return firmware;}
    Ip getDeviceIp(){return {};}const char*getMqttTopic(){return topic.c_str();}
    bool publishMqtt(const char*topic,const char*payload,bool retained){
        printf("%u\n%s\n%d\n%s\x1e",scenario,topic,retained,payload);return success;
    }
    bool publishMqtt(const char*topic,WStringStream*payload,bool retained){return publishMqtt(topic,payload->c_str(),retained);}
};
struct Value{double number=0.5;bool flag=true;double getDouble(){return number;}bool getBoolean(){return flag;}};
'''+constants+r'''
struct Probe{
    Net net;Net*network=&net;Value precision,floor;Value*temperaturePrecision=&precision,*floorSensor=&floor;
    int model=0;bool complete=true;
    bool hasDevicesWithHassAutodiscoverSupport(){return true;}int getThermostatModel(){return model;}
    bool isDeviceStateComplete(){return complete;}
'''
    if "String discoveryId(" in text:
        source += method(BECA, "discoveryId")
    source += method(BECA, "escapedForDiscovery") + method(BECA, "sendMqttHassAutodiscover")
    source += r'''
};
int main(){
    Probe p;
    for(int model=0;model<2;++model)for(double precision:{0.1,0.5,1.0})for(bool floor:{false,true})for(bool online:{false,true}){
        p.model=model;p.precision.number=precision;p.floor.flag=floor;p.complete=online;
        assert(p.sendMqttHassAutodiscover(false));++p.net.scenario;
    }
    for(const char* id:{"room_\"A","bad/name+#","","caff\xc3\xa8"}){
        p.net.id=id;assert(p.sendMqttHassAutodiscover(false));++p.net.scenario;
    }
    p.net.id=std::string(16,'"');p.net.topic=std::string(32,'"');p.net.firmware=std::string(60,'"');
    assert(p.sendMqttHassAutodiscover(false));++p.net.scenario;
    assert(p.sendMqttHassAutodiscover(true));++p.net.scenario;
    p.net.success=false;assert(!p.sendMqttHassAutodiscover(false));
}
'''
    with tempfile.TemporaryDirectory(prefix="wthermostat-discovery-") as directory:
        cpp = Path(directory) / "discovery.cpp"
        binary = Path(directory) / "discovery"
        cpp.write_text(source)
        subprocess.run([os.environ.get("CXX", "g++"), "-std=c++17", "-I", str(ROOT / "tests/native"),
                        "-I", str(ROOT), "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                        str(cpp), "-o", str(binary)], check=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True, check=True, timeout=30)
    return [(int(case), topic, retained == "1", payload)
            for case, topic, retained, payload in
            (record.split("\n", 3) for record in result.stdout.split("\x1e") if record)]


class HomeAssistantTests(unittest.TestCase):
    compile_run = regressions.NativeTests.compile_run

    def test_payload_contract_and_legacy_ids(self):
        records = discovery_records()
        for case, topic, retained, payload in records:
            with self.subTest(case=case, topic=topic):
                self.assertTrue(retained)
                if not topic.startswith("homeassistant/"):
                    self.assertTrue(topic.endswith("/tele/mcu"))
                    self.assertIn(payload, ("Online", "Offline"))
                    continue
                self.assertRegex(topic, r"^homeassistant/(climate|sensor)/[a-zA-Z0-9_-]+/config$")
                if case == 29 or (topic.endswith("_floorsensor/config") and
                                  (case >= 12 or not (case // 2) % 2)):
                    self.assertEqual("", payload)
                    continue
                value = json.loads(payload)
                self.assertEqual(topic.split("/")[2], value["unique_id"])
                self.assertEqual(["aa:bb:cc:dd:ee:ff"], value["dev"]["ids"])
                self.assertEqual("WThermostatBeca", value["o"]["name"])
                if case < 24:
                    self.assertTrue(value["unique_id"].startswith("room_A-1_"))
                else:
                    self.assertTrue(value["unique_id"].startswith("aabbccddeeff_"))
                if "/climate/" in topic:
                    self.assertIsNone(value["name"])
                    self.assertEqual("C", value["temperature_unit"])
                    self.assertIsInstance(value["temp_step"], (int, float))
                    self.assertEqual(value["temp_step"], value["precision"])
                    self.assertEqual("all", value["avty_mode"])
                    self.assertEqual(2, len(value["avty"]))
                    self.assertNotIn("none", value["pr_modes"])
                    if "fan_mode_cmd_t" in value:
                        self.assertEqual(["auto", "low", "medium", "high"], value["fan_modes"])
                elif value.get("device_class") in ("temperature", "signal_strength"):
                    self.assertEqual("measurement", value["state_class"])
                if topic.endswith(("_rssi/config", "_ip/config")):
                    self.assertEqual("diagnostic", value["entity_category"])
        for case in range(24):
            group = [r for r in records if r[0] == case]
            self.assertEqual(6, len(group))
            self.assertEqual("Online" if case % 2 else "Offline", group[0][3])

    def test_reconnect_birth_retry_and_deferred_state(self):
        source = r'''
#include "Arduino.h"
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WJson.h"
#include "lib/WAdapter/WAdapter/WStringStream.h"
#include "lib/WAdapter/WAdapter/WProperty.h"
const char*MQTT_CMND="cmnd",*MQTT_STAT="stat",*MQTT_TELE="tele";
struct WDevice{
    WDevice*next=nullptr;unsigned long lastStateNotify=123;
    WProperty property{"mode","Mode",STRING};
    const char*getId(){return "thermostat";}const char*getName(){return "Thermostat";}
    bool isMqttRetain(){return true;}
    WProperty*getPropertyById(const char*name){return !strcmp(name,"mode")?&property:nullptr;}
    void handleUnknownMqttCallback(const String&,const String&,const String&,unsigned){}
};
#include "lib/WAdapter/WAdapter/WJsonParser.h"
struct Log{template<class...T>void notice(T...){}template<class...T>void trace(T...){}template<class...T>void warning(T...){}};
struct Ip{String toString(){return "192.0.2.1";}};
struct Client{
    bool live=false,subscribeOk=true;unsigned connects=0;std::vector<std::string>subscriptions;
    bool connected(){return live;}void setServer(const char*,int){}
    template<class...T>bool connect(T...){++connects;live=true;return true;}
    bool subscribe(const char*topic){subscriptions.emplace_back(topic);return strcmp(topic,"homeassistant/status")||subscribeOk;}
    void unsubscribe(const char*){}void disconnect(){live=false;}int state(){return 0;}
    bool publish(const char*,const char*,bool=false){return true;}
};
struct Probe{
    Client client;Client*mqttClient=&client;Log log;Log*wlog=&log;WDevice one,two;WDevice*firstDevice=&one;
    WStringStream stream{3096};bool enabled=true,discoveryOk=true;
    unsigned long hassDiscoveryRequestedAt=0;bool hassDiscoveryPending=false,hassStatePending=false;
    unsigned discoveries=0,states=0;String base="home/room";
    Probe(){one.next=&two;}
    bool isSupportingMqtt(){return true;}bool isSupportingMqttHASS(){return enabled;}
    bool isMqttConnected(){return client.live;}bool isWifiConnected(){return true;}
    bool sendMqttHassAutodiscover(bool remove){assert(!remove);++discoveries;return discoveryOk;}
    const char*getMqttTopic(){return base.c_str();}const char*getMqttServer(){return "test";}
    const char*getMqttPort(){return "1883";}const char*getMqttUser(){return "";}const char*getMqttPassword(){return "";}
    String getClientName(bool){return "thermostat";}Ip getDeviceIp(){return {};}
    void logHeap(const char*){}void notify(bool){}
    WStringStream*getMQTTResponseStream(){stream.flush();return &stream;}
    WDevice*getDeviceById(const char*id){return !strcmp(id,"thermostat")?&one:nullptr;}
    bool publishMqtt(const char*,const char*,bool){return true;}
    void mqttSendDeviceState(const String&,WDevice*){++states;}
'''
        for name in ("requestHassDiscovery", "serviceHassDiscovery", "mqttCallback", "mqttReconnect"):
            source += method(NETWORK, name)
        source += r'''
};
int main(){
    Probe p;testMillis=100;
    assert(p.mqttReconnect()&&p.hassDiscoveryPending&&p.client.connects==1);
    assert(std::find(p.client.subscriptions.begin(),p.client.subscriptions.end(),"homeassistant/status")!=p.client.subscriptions.end());
    p.serviceHassDiscovery(1099);assert(p.discoveries==0);
    p.serviceHassDiscovery(1100);assert(p.discoveries==1&&p.hassStatePending&&!p.hassDiscoveryPending);
    p.serviceHassDiscovery(2099);assert(p.one.lastStateNotify==123);
    p.serviceHassDiscovery(2100);assert(!p.hassStatePending&&p.one.lastStateNotify==0&&p.two.lastStateNotify==0);
    p.serviceHassDiscovery(9000);assert(p.discoveries==1&&testMillis==100);
    p.client.live=false;testMillis=10000;assert(p.mqttReconnect());
    p.serviceHassDiscovery(11000);assert(p.discoveries==2);
    p.hassStatePending=false;char birth[]="homeassistant/status",online[]="online",offline[]="offline",wrong[]="other/status";
    p.mqttCallback(birth,offline,7);p.mqttCallback(wrong,online,6);assert(!p.hassDiscoveryPending);
    testMillis=20000;p.mqttCallback(birth,online,6);assert(p.hassDiscoveryPending&&p.states==0);
    p.discoveryOk=false;p.serviceHassDiscovery(21000);assert(p.hassDiscoveryPending&&!p.hassStatePending&&p.discoveries==3);
    p.serviceHassDiscovery(21500);assert(p.discoveries==3);
    p.discoveryOk=true;p.serviceHassDiscovery(22000);assert(p.hassStatePending&&p.discoveries==4);
    testMillis=23000;p.mqttCallback(birth,online,6);p.mqttCallback(birth,online,6);
    assert(p.hassDiscoveryPending&&!p.hassStatePending);p.serviceHassDiscovery(24000);assert(p.discoveries==5);
    p.hassDiscoveryPending=false;p.hassStatePending=false;
    char embedded[]={'o','n',0,'i','n','e',0};p.mqttCallback(birth,embedded,6);p.mqttCallback(birth,online,5);
    assert(!p.hassDiscoveryPending);
    p.enabled=false;p.mqttCallback(birth,online,6);assert(!p.hassDiscoveryPending);
    Probe disabled;disabled.enabled=false;assert(disabled.mqttReconnect());
    assert(!disabled.hassDiscoveryPending&&std::find(disabled.client.subscriptions.begin(),disabled.client.subscriptions.end(),"homeassistant/status")==disabled.client.subscriptions.end());
    Probe denied;denied.client.subscribeOk=false;assert(!denied.mqttReconnect()&&!denied.client.live);
    p.enabled=true;testMillis=ULONG_MAX-500;p.requestHassDiscovery();p.serviceHassDiscovery(498);assert(p.discoveries==5);
    p.serviceHassDiscovery(499);assert(p.discoveries==6);
    p.hassDiscoveryPending=false;p.hassStatePending=false;p.base="homeassistant";
    char command[]="homeassistant/cmnd/things/thermostat/properties/mode",heat[]="heat";
    p.mqttCallback(command,heat,4);assert(p.states==1&&p.one.property.equalsString("heat"));
    puts("PASS reconnect, HA Birth, debounce, retry, deferred replay, disabled discovery and millis wrap");
}
'''
        self.compile_run(source, "ha_lifecycle")


if __name__ == "__main__":
    unittest.main()
