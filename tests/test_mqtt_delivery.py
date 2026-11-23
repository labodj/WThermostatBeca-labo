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
struct Client{int value=-1;bool stopped=false;bool connected(){return !stopped;}int available(){return 1;}int read(){return value;}void stop(){stopped=true;}};
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
 bool oversized=false;
 void toJsonValues(WJson*j,int){if(oversized)j->propertyString("data",std::string(180,'x').c_str());else j->propertyBoolean("v",true);}bool isMqttRetain(){return true;}
 bool isVisible(int){return true;}bool isMqttSendChangedValues(){return true;}};
struct Log{template<class...T>void notice(T...){}template<class...T>void verbose(T...){}template<class...T>void warning(T...){}};
struct Mqtt{bool succeeds=false;unsigned calls=0;bool isReadingPacket(){return false;}bool publish(const char*,const char*,bool){++calls;return succeeds;}int state(){return 0;}};
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
 assert(p.mqtt.calls==2&&d.lastStateNotify==2000&&d.value.isChanged());
 d.oversized=true;p.mqttSendDeviceState("state",&d);
 assert(p.mqtt.calls==2&&d.lastStateNotify==0&&p.connected);
 d.oversized=false;p.mqttSendDeviceState("state",&d);assert(p.mqtt.calls==3&&d.lastStateNotify==2000);}
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

    def test_single_property_failure_keeps_pending_update(self):
        source = r'''
        #include "Arduino.h"
        #include "Stream.h"
        #include "lib/WAdapter/WAdapter/WProperty.h"
        const char* MQTT_STAT="stat";
        struct WDevice{WDevice*next=nullptr;WProperty*firstProperty=nullptr;bool visible=true,single=true,retain=true;
         bool isVisible(int){return visible;}bool isMqttSendChangedValues(){return single;}bool isMqttRetain(){return retain;}const char*getId(){return "thermostat";}};
        struct Probe{WDevice*firstDevice=nullptr;bool connected=true,support=true;unsigned sends=0;bool succeed=false;
         bool isMqttConnected(){return connected;}bool isSupportingMqttSingleValues(){return support;}
         const char*getMqttTopic(){return "home/room";}
         bool publishMqtt(const char*,const char*,bool){++sends;if(!succeed)connected=false;return succeed;}
        '''+method(NETWORK,'handleDevicesChangedPropertiesMQTT')+r'''
        };
        int main(){Probe p;WDevice d;WProperty value("deviceOn","Power",BOOLEAN);value.setBoolean(true);value.setVisibility(MQTT);value.setChanged();d.firstProperty=&value;p.firstDevice=&d;
         p.handleDevicesChangedPropertiesMQTT();printf("after_failed_send calls=%u changed=%d connected=%d\n",p.sends,value.isChanged(),p.connected);
         assert(p.sends==1&&value.isChanged()&&!p.connected);
         p.connected=true;p.succeed=true;p.handleDevicesChangedPropertiesMQTT();printf("after_reconnect calls=%u changed=%d\n",p.sends,value.isChanged());assert(p.sends==2&&!value.isChanged());
        }
        '''
        self.compile_run(source, "single_property_retry")

    def test_fragmented_command_survives_log_during_receive(self):
        source = r'''
#include "Arduino.h"
#include "lib/WAdapter/WAdapter/WAdapterMqtt.h"
struct Log{template<class...T>void verbose(T...){}template<class...T>void notice(T...){}template<class...T>void warning(T...){};};
struct Probe{Log logger;Log*wlog=&logger;WAdapterMqtt*mqttClient;
 bool isMqttConnected(){return mqttClient->connected();}
 const char*getMqttServer(){return "broker";}
 void disconnectMqtt(){mqttClient->disconnect();}
''' + method(NETWORK, 'publishMqtt') + r'''
};
int main(){
 Client client;client.data={0x20,2,0,0};WAdapterMqtt mqtt(false,client,512);assert(mqtt.connect("probe"));
 Probe probe{{},nullptr,&mqtt};probe.wlog=&probe.logger;
 const std::string topic="home/room/cmnd/things/thermostat/properties/deviceOn",body="true";
 std::vector<uint8_t> packet={0x30,static_cast<uint8_t>(2+topic.size()+body.size()),0,static_cast<uint8_t>(topic.size())};
 packet.insert(packet.end(),topic.begin(),topic.end());packet.insert(packet.end(),body.begin(),body.end());
 client.data.insert(client.data.end(),packet.begin(),packet.begin()+15);
 unsigned callbacks=0;std::string actualTopic,actualBody;
 mqtt.setCallback([&](char*t,char*p,unsigned n){++callbacks;actualTopic=t;actualBody.assign(p,n);});
 bool deferred=false;
 mqtt.setIdleCallback([&](){assert(!deferred);deferred=true;
  assert(!probe.publishMqtt("home/room/tele/log","MCU state"));
  client.data.insert(client.data.end(),packet.begin()+15,packet.end());
 });
 assert(mqtt.loop()&&mqtt.connected()&&deferred&&callbacks==1);
 assert(actualTopic==topic&&actualBody==body);
}
'''
        self.compile_run(source, "mqtt_fragmented_log")

    def test_suback_acceptance_and_refusal(self):
        source = r'''
#include "Arduino.h"
#include "lib/WAdapter/WAdapter/WAdapterMqtt.h"
int main(){
 for(uint8_t result:{uint8_t(0),uint8_t(1),uint8_t(0x80)}){
  Client client;client.data={0x20,2,0,0,0x90,3,0,2,0,0xb0,2,0,3,0x90,3,0,4,result};
  WAdapterMqtt mqtt(false,client,512);assert(mqtt.connect("probe"));
  assert(mqtt.subscribe("devices/#"));assert(mqtt.unsubscribe("devices/#"));
  const bool accepted=mqtt.subscribeConfirmed("home/room/cmnd/#");
  assert(accepted==(result!=0x80));
  if(!accepted){mqtt.abort();assert(!mqtt.connected());}
 }
}
'''
        self.compile_run(source, "mqtt_suback")
