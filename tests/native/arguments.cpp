#include "Arduino.h"
#include "Stream.h"
#include <type_traits>
#include "lib/WAdapter/WAdapter/WArguments.h"
#include "lib/WAdapter/WAdapter/WStringStream.h"
#include "lib/WAdapter/WAdapter/WJson.h"
#include "lib/WAdapter/WAdapter/WProperty.h"
#include "lib/WAdapter/WAdapter/WLevelProperty.h"
#include "lib/WAdapter/WAdapter/WLevelIntProperty.h"
#include "lib/WAdapter/WAdapter/WTargetTemperatureProperty.h"
#include "lib/WAdapter/WAdapter/WAdapterMqtt.h"
#include "lib/WAdapter/WAdapter/WLog.h"
class AsyncWebServerRequest;class AsyncResponseStream;
#include "lib/WAdapter/WAdapter/WPage.h"

static_assert(sizeof(WMqttTopic)==sizeof(const char*));
static_assert(sizeof(WMinimum<double>)==sizeof(double));
static_assert(std::is_trivially_copyable<WMqttTopic>::value);
static_assert(std::is_standard_layout<WMqttTopic>::value);
static_assert(!std::is_convertible<const char*,WMqttTopic>::value);
static_assert(!std::is_constructible<WMqttTopic,WJsonName>::value);
static_assert(!std::is_constructible<WTextTitle,WDeviceType>::value);
static_assert(!std::is_constructible<WStatusLedPin,WConsoleLogLevel>::value);
static_assert(!std::is_constructible<WMinimum<double>,WTolerance>::value);
static_assert(!std::is_constructible<WHoursOutput,WEepromAddress>::value);

int main(){
    WLevelProperty oldLevel("level","Level",-10,20),typedLevel("level","Level",WMinimum<double>(-10),20);
    WLevelIntProperty oldInt("int","Int",-10,20),typedInt("int","Int",WMinimum<int>(-10),20);
    assert(oldLevel.getMinimum()==typedLevel.getMinimum()&&oldLevel.getMaximum()==typedLevel.getMaximum());
    assert(oldInt.getMinimum()==typedInt.getMinimum()&&oldInt.getMaximum()==typedInt.getMaximum());
    WTargetTemperatureProperty oldDefault("temperature","Temperature"),oldTarget("temperature","Temperature",10,35),typedTarget("temperature","Temperature",WMinimum<float>(10),35);
    assert(oldDefault.canParse("5"));assert(!oldTarget.canParse("5"));
    for(const char* value:{"5","10","23.5","35","36"})assert(oldTarget.canParse(value)==typedTarget.canParse(value));
    auto compare=&WProperty::isEqual;
    assert(compare(2,2.125,0.25)&&!compare(2,2.25,0.25));
    assert(compare(2,2.125,0.25)==WProperty::isEqualWithin(2,2.125,WTolerance(0.25)));
    WPage oldPage("id","Title"),typedPage("id",WTextTitle("Title"));
    assert(!strcmp(oldPage.getId(),typedPage.getId())&&!strcmp(oldPage.getTitle(),typedPage.getTitle()));

    WStringStream oldLog(128),typedLog(128);WLog oldLogger(4,1,&oldLog),typedLogger(WConsoleLogLevel(4),1,&typedLog);
    unsigned oldCalls=0,typedCalls=0;oldLogger.setOnLogCommand([&](int,const char*){++oldCalls;});typedLogger.setOnLogCommand([&](int,const char*){++typedCalls;});
    oldLogger.notice("normal");typedLogger.notice("normal");assert(!oldCalls&&!typedCalls);
    oldLogger.fatal("fatal");typedLogger.fatal("fatal");assert(oldCalls==1&&typedCalls==1&&!strcmp(oldLog.c_str(),typedLog.c_str()));

    Client client;client.data={0x20,2,0,0};WAdapterMqtt mqtt(false,client,64);assert(mqtt.connect("test"));
    using LegacyPublish=bool(WAdapterMqtt::*)(const char*,const char*,unsigned int,bool);
    auto publish=static_cast<LegacyPublish>(&WAdapterMqtt::publish);
    client.sent.clear();assert((mqtt.*publish)("topic","value",5,true));const auto bytes=client.sent;
    client.sent.clear();assert(mqtt.publish(WMqttTopic("topic"),"value",5,true));assert(bytes==client.sent);
    WStringStream output(1024);WJson json(&output);json.beginObject();
    json.propertyString("key","a","b","c","d","e","f","g","h","i","j");json.endObject();
    assert(!strcmp(output.c_str(),"{\"key\":\"abcdefghij\"}"));
    output.flush();WJson typedJson(&output);typedJson.beginObject();typedJson.propertyString(WJsonName("key"),"a","b","c","d","e","f","g","h","i","j");typedJson.endObject();
    assert(!strcmp(output.c_str(),"{\"key\":\"abcdefghij\"}"));
    auto schema=&WProperty::toJsonStructure;output.flush();WJson schemaJson(&output);oldTarget.toJsonStructure(&schemaJson,"temperature","/things/t");
    assert(strstr(output.c_str(),"\"title\":\"Temperature\"")&&strstr(output.c_str(),"/things/t/properties/temperature"));
    struct Derived:WProperty{bool called=false;Derived():WProperty("id","Title",INTEGER){}void toJsonStructure(WJson*,const char*,const char*)override{called=true;}} derived;
    WProperty* base=&derived;(base->*schema)(&json,"id","/things/t");assert(derived.called);
    puts("PASS explicit argument roles, legacy constructors/function pointers, virtual dispatch and wire output");
}
