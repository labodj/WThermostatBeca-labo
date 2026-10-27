#include "properties.h"
#include "lib/WAdapter/WAdapter/WTargetTemperatureProperty.h"
#include "lib/WAdapter/WAdapter/WJsonParser.h"
#include "lib/WAdapter/WAdapter/WStringStream.h"
#include "lib/WAdapter/WAdapter/WAdapterMqtt.h"

int main(){
    WProperty power("deviceOn","Power",BOOLEAN);
    WTargetTemperatureProperty temperature("targetTemperature","Temperature");
    WProperty mode("mode","Mode",STRING);
    mode.addEnumString("heat"); mode.addEnumString("off");
    temperature.setMultipleOf(0.5);
    WDevice device; device.properties={&power,&temperature,&mode};
    WJsonParser parser;
    assert(parser.parse("{\"deviceOn\":true,\"targetTemperature\":23.5}",&device));
    assert(power.getBoolean() && temperature.getDouble()==23.5);
    assert(!parser.parse("{\"deviceOn\":false,\"targetTemperature\":",&device));
    assert(power.getBoolean());
    assert(!parser.parse("{\"deviceOn\":false,\"targetTemperature\":999}",&device));
    assert(power.getBoolean());
    for(const char* input:{"[]","[[[[[[[[[[[[[[[[[[[[[","{\"x\":{}}","{\"deviceOn\":true,}","{}junk","{\"x\":01}","{\"x\":1.}","{\"x\":1e}","{\"x\":\"\\uD800\"}"}) {
        assert(!parser.parse(input,&device)); assert(!parser.isValid());
    }
    assert(!temperature.parse("garbage")); assert(!temperature.parse("nan"));
    assert(!temperature.parse("23.1"));assert(temperature.parse("24.5"));
    assert(!mode.parse("invalid"));assert(mode.parse("heat"));
    assert(!power.parse("garbage"));assert(power.parse("false"));assert(!power.getBoolean());
    WProperty number("n","N",INTEGER);assert(!number.parse("12oops"));assert(!number.parse("40000"));assert(number.parse("-12"));
    int emitted=0;std::string text;
    assert(parser.parse("{\"s\":\"caf\\u00e9\"}",[&](const char*,const char* value){++emitted;text=value;}));
    assert(text=="caf\xc3\xa9" && emitted==1);
    assert(parser.parse("{\"s\":\"null\"}",[&](const char*,const char* value){text=value;}));
    assert(text=="null");
    const std::string longValue = "{\"s\":\""+std::string(128,'a')+"\"}";
    assert(!parser.parse(longValue.c_str(),[](const char*,const char*){}));
    // The callback overload must validate every field before applying any.
    assert(!parser.parse("{\"a\":1,\"b\":2}",[&](const char*,const char*){++emitted;},[](const char* key,const char*){return strcmp(key,"b")!=0;}));
    assert(emitted==1);
    // On i386 va_list is char*: avoid GCC's legacy string-literal conversion.
    const char* longText="12345678901234567890";
    WStringStream stream(8);assert(stream.printf("%s",longText)==8);
    assert(stream.length()==8);assert(!strcmp(stream.c_str(),"12345678"));assert(stream.printf("more")==0);
    assert(stream.overflowed());stream.flush();assert(!stream.overflowed());assert(stream.printf("abc")==3);assert(stream.printf("defghij")==5);
    Client client; client.data={0x20,2,0,0,0x30,0x95,0x18,0,1,'x'};client.data.resize(3100,'a');
    WAdapterMqtt mqtt(false,client,3096);unsigned calls=0;
    mqtt.setCallback([&](char* topic,char* payload,unsigned int length){assert(!strcmp(topic,"x"));assert(length==3090);assert(strlen(payload)==length);++calls;});
    assert(mqtt.connect("test"));assert(mqtt.loop());assert(calls==1);
    for(auto bytes:std::vector<std::vector<uint8_t>>{{0x30,3,0,100,'x'},{0x30,0},{0x30,0xff,0xff,0xff,0x7f}}){
        Client bad;bad.data={0x20,2,0,0};bad.data.insert(bad.data.end(),bytes.begin(),bytes.end());WAdapterMqtt receiver(false,bad,64);assert(receiver.connect("test"));receiver.setCallback([&](char*,char*,unsigned){assert(false);});receiver.loop();assert(!bad.live);
    }
    Client slow;slow.live=false;WAdapterMqtt reconnect(false,slow,64);unsigned idle=0;
    reconnect.setServer("test",1883);reconnect.setIdleCallback([&](){++idle;assert(!reconnect.connected());});
    const auto start=millis();assert(!reconnect.connect("test"));assert(idle>0);assert(millis()-start<=2100);
    puts("PASS properties, atomic JSON, stream bounds, MQTT bounds and timeout");
}
