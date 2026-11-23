"""Power interruption and long-running network contracts."""
import unittest

from native_support import NativeTests, ROOT, method


class ResilienceTests(unittest.TestCase, NativeTests):
    def test_response_buffer_survives_allocation_failure_and_retries(self):
        self.compile_run(r'''
#include "lib/WAdapter/WAdapter/WStringStream.h"
#include <optional>
constexpr unsigned SIZE_MQTT_PACKET = 11;
struct Network {
    std::optional<WStringStream> responseStream;
''' + method(ROOT / 'lib/WAdapter/WAdapter/WNetwork.h', 'getMQTTResponseStream') + r'''
};
static bool failBuffer = true;
void* operator new[](size_t size, const std::nothrow_t&) noexcept {
    if (failBuffer && size == 12) return nullptr;
    return ::operator new[](size);
}
int main() {
    Network first, second;
    assert(!first.responseStream && !second.responseStream);
    WStringStream& stream = *first.getMQTTResponseStream();
    assert(stream.overflowed() && !*stream.c_str() && !stream.write('x'));
    assert(stream.printf("%s", "abc") == 0 && stream.charAt(0) == 0);
    stream.flush(); assert(stream.overflowed());
    failBuffer = false;
    assert(first.getMQTTResponseStream()==&stream);
    auto* separate = second.getMQTTResponseStream();
    assert(separate != &stream && separate->write('z') && stream.length() == 0);
    stream.flush(); assert(!stream.overflowed());
    assert(stream.printf(F("%s"), "recovered") == 9 && !strcmp(stream.c_str(), "recovered"));
    assert(stream.charAt(-1) == 0 && stream.charAt(9) == 0);
    WStringStream impossible(UINT_MAX);
    assert(impossible.overflowed() && !*impossible.c_str());
    std::string format(1080, 'a'); format += "%s";
    WStringStream large(1081);
    assert(large.printf(FPSTR(format.c_str()), "Z") == 1081 && !large.overflowed());
    assert(large.charAt(1080) == 'Z');
    assert(large.printf("x") == 0 && large.overflowed());
}
''', 'response_buffer_failure')

    def test_discovery_allocation_failure_preserves_identity(self):
        beca = ROOT / 'WThermostat/WBecaDevice.h'
        self.compile_run(r'''
#include "Arduino.h"
struct DeviceString : String {
    static bool failName;
    DeviceString() = default;
    DeviceString(const char* p): String(failName && !strcmp(p, "configured-room") ? "" : p) {}
};
bool DeviceString::failName = true;
struct Network {
    const char* id = "configured-room"; unsigned macReads = 0;
    const char* getIdx() { return id; }
    DeviceString getMacAddress() { ++macReads; return "aa:bb:cc:dd:ee:ff"; }
};
#define String DeviceString
struct Probe { Network net; Network* network = &net;
''' + method(beca, 'discoveryId') + r'''
};
#undef String
int main() {
    Probe p;
    assert(p.discoveryId("_sensor").empty() && p.net.macReads == 0);
    DeviceString::failName = false;
    assert(p.discoveryId("_sensor") == "configured-room_sensor" && p.net.macReads == 0);
    p.net.id = "bad/name";
    assert(p.discoveryId("_sensor") == "aabbccddeeff_sensor" && p.net.macReads == 1);
}
''', 'discovery_low_memory')

    def test_power_cuts_during_settings_replacement(self):
        self.compile_run(None, 'settings_flash')

    def test_mqtt_handshake_and_subscription_bounds(self):
        self.compile_run(r'''
#include "lib/WAdapter/WAdapter/WAdapterMqtt.h"
struct ShortWrite : Client {
    size_t write(const uint8_t*, size_t) override { return 1; }
};
int main() {
    for (const auto& reply : std::vector<std::vector<uint8_t>>{
            {0x40,2,0,0}, {0x21,2,0,0}, {0x20,2,1,0}, {0x20,2,2,0}, {0x20,2,0,6}}) {
        Client c; c.data=reply; WAdapterMqtt mqtt(false,c,64);
        assert(!mqtt.connect("room") && !c.live && mqtt.state()==MQTT_CONNECT_BAD_PROTOCOL);
    }
    Client c; c.data={0x20,2,0,4}; WAdapterMqtt mqtt(false,c,64);
    assert(!mqtt.connect("room") && mqtt.state()==MQTT_CONNECT_BAD_CREDENTIALS);
    c.data={0x20,2,0,0}; c.pos=0;
    assert(mqtt.connect("room"));
    c.sent.clear();
    std::string exact(54,'a'), large(55,'a');
    assert(!mqtt.subscribe(large.c_str()) && c.sent.empty());
    assert(mqtt.subscribe(exact.c_str()));
    ShortWrite shortClient; shortClient.data={0x20,2,0,0};
    WAdapterMqtt shortMqtt(false,shortClient,64);
    assert(!shortMqtt.connect("room") && !shortClient.live);
}
''', 'mqtt_handshake')

    def test_uptime_reports_ten_years_without_wrapping(self):
        self.compile_run(r'''
#include <cassert>
#include <cstdint>
uint64_t uptime;
uint64_t micros64() { return uptime; }
struct Clock {
''' + method(ROOT / 'WThermostat/WClock.h', 'getUptime') + r'''
};
int main() {
    Clock clock;
    uptime = (uint64_t(UINT32_MAX)+1)*1000;
    assert(clock.getUptime()==4294967);
    uptime = 3652ULL*86400*1000000;
    assert(clock.getUptime()==315532800);
}
''', 'uptime')

    def test_wifi_and_broker_retry_intervals(self):
        network = ROOT / 'lib/WAdapter/WAdapter/WNetwork.h'
        self.compile_run(r'''
#include "lib/WAdapter/WAdapter/WAdapterMqtt.h"
struct Mqtt {
    int reason=0;
    unsigned loops=0;
    int state(){return reason;}
    void loop(){++loops;}
};
struct Probe {
    Mqtt mqtt; Mqtt* mqttClient=&mqtt;
    bool wifi=false, online=false;
    unsigned attempts=0;
    unsigned long lastMqttConnect=0, mqttRetryInterval=0;
    bool isWifiConnected(){return wifi;}
    bool isMqttConnected(){return online;}
    bool mqttReconnect(){++attempts;return online=mqtt.reason==0;}
    void serviceHassDiscovery(unsigned long){}
''' + method(network, 'serviceMqtt') + r'''
    void tick(unsigned long t){testMillis=t;serviceMqtt(t);}
};
int main(){
    Probe p; p.tick(0);assert(!p.attempts);
    p.wifi=true;p.mqtt.reason=MQTT_CONNECT_BAD_CREDENTIALS;
    p.tick(0);p.tick(299999);assert(p.attempts==1);
    p.mqtt.reason=MQTT_CONNECT_FAILED;
    p.tick(300000);p.tick(329999);assert(p.attempts==2 && !p.online);
    p.mqtt.reason=0;p.tick(330000);assert(p.online && p.mqtt.loops==1);
    p.wifi=false;p.tick(330001);assert(p.mqtt.loops==1);
    Probe wrap;wrap.wifi=true;wrap.mqtt.reason=MQTT_CONNECT_FAILED;
    wrap.tick(ULONG_MAX-999);wrap.tick(28999);assert(wrap.attempts==1);
    wrap.tick(29000);assert(wrap.attempts==2);
}
''', 'mqtt_backoff')

    def test_transport_close_leaves_offline_will_to_broker(self):
        network = ROOT / 'lib/WAdapter/WAdapter/WNetwork.h'
        self.compile_run(r'''
#include "lib/WAdapter/WAdapter/WAdapterMqtt.h"
struct Probe {WAdapterMqtt* mqttClient;
''' + method(network, 'disconnectMqtt') + r'''
};
int main(){
    Client c;c.data={0x20,2,0,0};WAdapterMqtt mqtt(false,c,64);
    assert(mqtt.connect("room",nullptr,nullptr,"room/LWT",1,true,"Offline",true));
    c.sent.clear();Probe p{&mqtt};p.disconnectMqtt();
    assert(!c.live && c.sent.empty());
}
''', 'mqtt_will')

    def test_partial_mqtt_frames_require_a_new_connection(self):
        self.compile_run(r'''
#include "lib/WAdapter/WAdapter/WAdapterMqtt.h"
struct Socket : Client {
    bool shortWrite = false;
    size_t write(const uint8_t* data, size_t size) override {
        return Client::write(data, shortWrite ? size - 1 : size);
    }
};
int main() {
    for (unsigned which = 0; which < 4; ++which) {
        Socket c; c.data = {0x20, 2, 0, 0};
        WAdapterMqtt mqtt(false, c, 64);
        assert(mqtt.connect("room"));
        mqtt.setCallback([](char*, char*, unsigned){});
        c.shortWrite = true;
        if (which == 0) assert(!mqtt.publish("room", "value"));
        if (which == 1) { testMillis += 60000; assert(!mqtt.loop()); }
        if (which == 2) { c.data = {0xc0, 0}; c.pos = 0; assert(!mqtt.loop()); }
        if (which == 3) {
            c.data = {0x32, 6, 0, 1, 't', 0, 7, 'x'}; c.pos = 0;
            assert(!mqtt.loop());
        }
        assert(!c.live && !mqtt.connected());
        c.shortWrite = false; c.data = {0x20, 2, 0, 0}; c.pos = 0;
        assert(mqtt.connect("room") && mqtt.publish("room", "back"));
    }
    Socket c; c.data = {0x20, 2, 0, 0}; WAdapterMqtt mqtt(false, c, 64);
    assert(mqtt.connect("room"));
    c.data = {0x30}; c.pos = 0;
    unsigned idle = 0;
    mqtt.setIdleCallback([&](){ ++idle; c.stop(); });
    assert(!mqtt.loop() && idle == 1 && mqtt.state() == MQTT_CONNECTION_LOST);
}
''', 'mqtt_partial_frames')
