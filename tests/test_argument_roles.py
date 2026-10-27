"""Legacy calls and typed roles must coexist without changing the wire protocols."""
from pathlib import Path
import tempfile
import unittest
import test_regressions as regressions

ROOT = Path(__file__).resolve().parents[1]


class ArgumentRoleTests(unittest.TestCase):
    compile_run = regressions.NativeTests.compile_run

    def test_legacy_signatures_and_role_safety(self):
        self.compile_run(None, "arguments")

    def test_device_constructors_mqtt_forwarding_and_virtual_callbacks(self):
        device = (ROOT / "lib/WAdapter/WAdapter/WDevice.h").read_text()
        constructors = device[device.index("\tWDevice(WNetwork*"):device.index("\n\tvirtual ~WDevice()")]
        network = (ROOT / "lib/WAdapter/WAdapter/WNetwork.h").read_text()
        start = network.index("\tbool publishMqtt(const char* topic, const char* key,")
        publishing = network[start:network.index("\n#endif", start)]
        source = r'''
#include "Arduino.h"
#include "Stream.h"
#include <type_traits>
#include "lib/WAdapter/WAdapter/WArguments.h"
#include "lib/WAdapter/WAdapter/WStringStream.h"
#include "lib/WAdapter/WAdapter/WJson.h"
struct WNetwork;
enum {ALL};
struct WDevice {
    WNetwork*network;const char*id,*name,*type;char*fullname;int visibility;
    bool providingConfigPage,configNeedsReboot,mainDevice,mqttRetain,mqttSendChangedValues;
    unsigned long lastStateNotify,stateNotifyInterval;
'''+constructors+r'''
'''+regressions.method(ROOT / "lib/WAdapter/WAdapter/WDevice.h", "~WDevice")+regressions.method(ROOT / "lib/WAdapter/WAdapter/WDevice.h", "handleUnknownMqttCallback")+r'''
};
struct WNetwork {
    WStringStream stream{128};String sentTopic,sentJson;bool retained=false;
    bool isSupportingMqtt(){return true;}
    WStringStream*getMQTTResponseStream(){stream.flush();return &stream;}
    bool publishMqtt(const char* topic,WStringStream*data,bool retain){sentTopic=topic;sentJson=data->c_str();retained=retain;return true;}
'''+publishing+r'''
};
struct NetworkDevice:WDevice {
    using WDevice::WDevice;
'''+regressions.method(ROOT / "lib/WAdapter/WAdapter/WNetworkDevice.h", "handleUnknownMqttCallback")+r'''
};
struct LogDevice:WDevice {
    using WDevice::WDevice;
'''+regressions.method(ROOT / "WThermostat/WLogDevice.h", "handleUnknownMqttCallback")+r'''
};
struct Custom:WDevice {
    bool called=false;using WDevice::WDevice;
    void handleUnknownMqttCallback(const String& complete,const String& partial,const String& payload,unsigned length)override{
        called=complete=="full"&&partial=="partial"&&payload=="value"&&length==5;
    }
};
int main(){
    WDevice oldDevice(nullptr,"id","Title","root","type"),typedDevice(nullptr,"id",WTextTitle("Title"),"root",WDeviceType("type"));
    assert(!strcmp(oldDevice.id,typedDevice.id)&&!strcmp(oldDevice.name,typedDevice.name)&&!strcmp(oldDevice.type,typedDevice.type));
    assert(!strcmp(oldDevice.fullname,"root_Title")&&!strcmp(oldDevice.fullname,typedDevice.fullname));
    Custom custom(nullptr,"id","Title","root","type");WDevice*base=&custom;
    auto callback=&WDevice::handleUnknownMqttCallback;(base->*callback)("full","partial","value",5);assert(custom.called);
    using Callback=void(NetworkDevice::*)(const String&,const String&,const String&,unsigned);
    Callback noOp=&NetworkDevice::handleUnknownMqttCallback;
    NetworkDevice net(nullptr,"id","Title","root","type");(net.*noOp)("full","partial","value",5);
    WNetwork network;
    using Publish=bool(WNetwork::*)(const char*,const char*,const char*,const char*,const char*,bool);
    auto publish=static_cast<Publish>(&WNetwork::publishMqtt);
    assert((network.*publish)("topic","first","value","second","two",true));
    assert(network.sentTopic=="topic"&&network.sentJson=="{\"first\":\"value\",\"second\":\"two\"}"&&network.retained);
    assert(network.publishMqtt(WMqttTopic("topic"),"first","value",WJsonName("second"),"two",true));
    assert(network.sentJson=="{\"first\":\"value\",\"second\":\"two\"}");
    assert(network.publishMqtt("topic","first","value"));assert(network.sentJson=="{\"first\":\"value\"}"&&!network.retained);
    puts("PASS legacy device metadata, callbacks and MQTT JSON forwarding");
}
'''
        self.compile_run(source, "arguments_devices")

    def test_source_extraction_ignores_a_forwarding_return(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "forward.h"
            path.write_text("bool original() {\n    return implementation();\n}\nbool implementation() { return true; }\n")
            self.assertEqual("bool implementation() { return true; }", regressions.method(path, "implementation"))
