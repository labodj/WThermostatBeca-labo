"""MQTT commands, packet limits and state publication."""
import unittest
import native_support as native
from native_support import NETWORK, ROOT, method


MQTT = ROOT / "lib/WAdapter/WAdapter/WAdapterMqtt.h"


class MqttDeliveryTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_mqtt_logging(self):
        source = (
            r"""
        #include "Arduino.h"
        #include "Stream.h"
        #include "lib/WAdapter/WAdapter/WProperty.h"
        #include "lib/WAdapter/WAdapter/WLog.h"
        #include "lib/WAdapter/WAdapter/WAdapterMqtt.h"
        struct WDevice{
         WProperty power{"deviceOn","Power",BOOLEAN};
         WDevice(){power.setBoolean(false);}
         WProperty*getPropertyById(const char*id){return !strcmp(id,"deviceOn")?&power:nullptr;}
         const char*getId(){return "thermostat";}const char*getName(){return "Thermostat";}
         bool isMqttRetain(){return true;}
         void handleUnknownMqttCallback(const String&,const String&,const String&,unsigned){}
        };
        #include "lib/WAdapter/WAdapter/WJsonParser.h"
        const char* MQTT_CMND="cmnd",*MQTT_STAT="stat";
        struct Probe{
         Print output;WLog logger;WLog*wlog=&logger;WAdapterMqtt*mqttClient;WDevice device;
         bool logging=false;
         Probe(WAdapterMqtt*m,int level):logger(0,level,&output),mqttClient(m){
          logger.setOnLogCommand([this](int,const char* message){
           if(logging)return;logging=true;
           const String line=String("notice: ")+message;
           publishMqtt("home/room/tele/log",line.c_str());logging=false;
          });
         }
         const char* getMqttTopic(){return "home/room";}const char*getMqttServer(){return "broker";}
         WDevice*getDeviceById(const char* id){return !strcmp(id,"thermostat")?&device:nullptr;}
         bool isMqttConnected(){return mqttClient->connected();}
         void disconnectMqtt(){mqttClient->disconnect();}
         void requestHassDiscovery(){}void mqttSendDeviceState(const String&,WDevice*){}
        """
            + method(NETWORK, "publishMqtt")
            + method(NETWORK, "mqttCallback")
            + r"""
        };
        int main(){
         for(bool single:{false,true})for(int level:{0,4,5,6}){
          Client client;client.data={0x20,2,0,0};WAdapterMqtt mqtt(false,client,3096);assert(mqtt.connect("probe"));
          Probe p(&mqtt,level);mqtt.setCallback([&](char*t,char*b,unsigned n){p.mqttCallback(t,b,n);});
          std::string topic="home/room/cmnd/things/thermostat/properties";if(single)topic+="/deviceOn";
          std::string body=single?"true":"{\"deviceOn\":true}";
          size_t n=topic.size()+2+body.size();assert(n<128);client.data.push_back(0x30);client.data.push_back(n);
          client.data.push_back(topic.size()>>8);client.data.push_back(topic.size()&255);
          client.data.insert(client.data.end(),topic.begin(),topic.end());client.data.insert(client.data.end(),body.begin(),body.end());
          assert(mqtt.loop());bool applied=p.device.power.getBoolean();
          printf("%s loglevel=%d applied=%d\n",single?"single":"JSON",level,applied);
          assert(applied);
         }
        }
        """
        )
        self.compile_run(source, "mqtt_logging")

    def test_mqtt_eof_is_not_a_valid_ff_byte(self):
        source = r'''
#include "Arduino.h"
#include <functional>
const int MQTT_CONNECTION_TIMEOUT=-4,MQTT_CONNECTION_LOST=-3,MQTT_SOCKET_TIMEOUT=2;
struct Client{int value=-1;bool stopped=false;int available(){return 1;}int read(){return value;}void stop(){stopped=true;}};
struct Probe{Client client;Client*_client=&client;int _state=0;unsigned long packetStarted=0;std::function<void()>onIdle;
'''+native.method(MQTT, 'readByte')+r'''
};
int main(){
 for(int value:{-1,0,255}){Probe p;p.client.value=value;uint8_t byte=42;
  assert(p.readByte(&byte)==(value>=0));
  if(value<0){assert(p.client.stopped&&p._state==MQTT_CONNECTION_LOST&&byte==42);}
  else{assert(!p.client.stopped&&byte==value);}
 }
 puts("PASS MQTT distinguishes EOF, zero and 0xff");
}
'''
        self.compile_run(source, 'mqtt_eof')

    def test_streaming_mqtt_rejects_oversize_before_writing(self):
        source = r'''
#include "properties.h"
#include "lib/WAdapter/WAdapter/WStringStream.h"
#include "lib/WAdapter/WAdapter/WStringProperty.h"
#include "lib/WAdapter/WAdapter/WSettings.h"
#include "lib/WAdapter/WAdapter/WAdapterMqtt.h"
#include <type_traits>
static_assert(!std::is_copy_constructible<WProperty>::value&&!std::is_copy_assignable<WProperty>::value);
static_assert(!std::is_copy_constructible<WStringStream>::value&&!std::is_copy_assignable<WStringStream>::value);
static_assert(!std::is_copy_constructible<WSettings>::value&&!std::is_copy_assignable<WSettings>::value);
static_assert(!std::is_copy_constructible<WAdapterMqtt>::value&&!std::is_copy_assignable<WAdapterMqtt>::value);
int main(){
 Client client;client.data={0x20,2,0,0};WAdapterMqtt mqtt(false,client,64);assert(mqtt.connect("test"));client.sent.clear();
 for(const char*topic:{static_cast<const char*>(nullptr),std::string(58,'x').c_str()}){
  assert(!mqtt.beginPublish(topic,0,false));assert(client.sent.empty());
 }
 assert(!mqtt.beginPublish("x",UINT_MAX,false)&&client.sent.empty());
 assert(!mqtt.beginPublish("x",65533,false)&&client.sent.empty());
 assert(mqtt.beginPublish("x",65532,false));
 assert((client.sent==std::vector<uint8_t>{0x30,0xff,0xff,0x03,0,1,'x'}));
 client.sent.clear();assert(mqtt.beginPublish("x",1,true));assert(mqtt.write(uint8_t('a'))==1);
 assert((client.sent==std::vector<uint8_t>{0x31,4,0,1,'x','a'}));
 WSettingItem item;assert(item.value==nullptr&&item.address==0&&item.next==nullptr);
 puts("PASS ownership traits and streaming MQTT capacity/16-bit length limits");
}
'''
        # Keep the oversized topic alive for the entire loop.
        source = source.replace('for(const char*topic:', "const std::string longTopic(58,'x');for(const char*topic:").replace("std::string(58,'x').c_str()", 'longTopic.c_str()')
        self.compile_run(source, 'mqtt_streaming')

    def test_state_publish_failure_retains_retry_and_success_marks_delivery(self):
        source = r'''
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WProperty.h"
#include "lib/WAdapter/WAdapter/WStringStream.h"
const char*PROP_IDX="idx";
struct WDevice{unsigned long lastStateNotify=123;WProperty value{"v","V",BOOLEAN};WProperty*firstProperty=&value;
 WDevice(){value.setBoolean(true);value.setUnChanged();}
 bool isDeviceStateComplete(){return true;}bool isMainDevice(){return false;}
 void toJsonValues(WJson*j,int){j->propertyBoolean("v",true);}bool isMqttRetain(){return true;}
 bool isVisible(int){return true;}bool isMqttSendChangedValues(){return true;}};
struct Log{template<class...T>void notice(T...){}template<class...T>void verbose(T...){}template<class...T>void warning(T...){}};
struct Mqtt{bool succeeds=false;unsigned calls=0;bool publish(const char*,const char*,bool){++calls;return succeeds;}int state(){return 0;}};
struct Ip{String toString(){return "ip";}};
struct Probe{Log logger;Log*wlog=&logger;Mqtt mqtt;Mqtt*mqttClient=&mqtt;String firmwareVersion="test";WStringStream stream{100};bool connected=true;
 bool isMqttConnected(){return connected;}void disconnectMqtt(){connected=false;}
 bool isSupportingMqtt(){return true;}bool isSupportingMqttSingleValues(){return true;}
 const char*getMqttServer(){return "broker";}const char*getIdx(){return "idx";}Ip getDeviceIp(){return {};}
 WStringStream*getMQTTResponseStream(){stream.flush();return &stream;}
''' + method(NETWORK, 'publishMqtt') + method(NETWORK, 'mqttSendDeviceState') + r'''
};int main(){testMillis=1000;Probe p;WDevice d;p.mqttSendDeviceState("state",&d);
 assert(p.mqtt.calls==1&&d.lastStateNotify==0&&!p.connected&&!d.value.isChanged());
 p.mqttSendDeviceState("state",&d);assert(p.mqtt.calls==1);
 p.connected=true;p.mqtt.succeeds=true;testMillis=2000;p.mqttSendDeviceState("state",&d);
 assert(p.mqtt.calls==2&&d.lastStateNotify==2000&&d.value.isChanged());}
'''
        self.compile_run(source, 'state_publish_retry')

    def test_periodic_state_uses_time_after_device_loop_and_handles_wrap(self):
        loop = method(NETWORK, 'loop')
        start = loop.index('device->loop(millis());')
        end = loop.index('device = device->next;', start)
        body = loop[start:end]
        source = r'''
#include "Arduino.h"
#include <cstdint>
struct Device{uint32_t lastStateNotify=0,stateNotifyInterval=60000;bool isDeviceStateComplete(){return true;}void loop(unsigned long){}};
struct Log{template<class...T>void notice(T...){}};
struct Probe{Log logger;Log*wlog=&logger;unsigned sends=0;
 bool isMqttConnected(){return true;}bool isSupportingMqtt(){return true;}
 void handleDeviceStateChange(Device*){++sends;}
 void tick(uint32_t now,Device*device){
''' + body + r'''
}};int main(){Probe p;Device d;d.lastStateNotify=1001;testMillis=1001;p.tick(1000,&d);assert(!p.sends);
 d.lastStateNotify=0;p.tick(1000,&d);assert(p.sends==1);
 d.lastStateNotify=UINT32_MAX-1000;testMillis=120000;p.tick(119999,&d);assert(p.sends==2);
 d.lastStateNotify=120000;testMillis=120001;p.tick(119999,&d);assert(p.sends==2);}
'''
        self.compile_run(source, 'fresh_state_timer')
