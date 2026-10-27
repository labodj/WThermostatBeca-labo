"""Contracts for clang-tidy 19 fixes and BSSID recovery, using production code."""
import unittest

import test_regressions as native
from test_regressions import BECA, NETWORK, method


def enum_definition(path, name):
    text = path.read_text()
    start = text.index('enum ' + name)
    return text[start:text.index('}', start) + 1] + ';\n'


class MediumReviewTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_string_stream_initializes_inherited_timeout_state(self):
        source = r'''
#include "Stream.h"
struct PoisonedStream:Stream{PoisonedStream(){_startMillis=0xdeadbeefUL;}};
#define Stream PoisonedStream
#include "lib/WAdapter/WAdapter/WStringStream.h"
#undef Stream
struct Probe:WStringStream{Probe():WStringStream(8){}unsigned long start()const{return _startMillis;}};
int main(){Probe p;assert(p.start()==0);p.print("test");assert(p.start()==0&&p.available()==4);
 puts("PASS production WStringStream initializes inherited timeout state even with a poisoned base field");}
'''
        self.compile_run(source, 'medium_stream_constructor')

    def test_enum_values_and_all_eeprom_version_flags(self):
        source = r'''
#include "properties.h"
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WStringProperty.h"
#include "lib/WAdapter/WAdapter/WSettings.h"
'''
        source += enum_definition(NETWORK, 'wnWifiMode') + enum_definition(BECA, 'mcuNetworkMode')
        source += r'''
static_assert(sizeof(WPropertyType)==1&&sizeof(WPropertyVisibility)==1&&sizeof(wnWifiMode)==1&&sizeof(mcuNetworkMode)==1);
static_assert(BOOLEAN==0&&DOUBLE==1&&INTEGER==2&&LONG==3&&UNSIGNED_LONG==4&&BYTE==5&&STRING==6);
static_assert(ALL==0&&NONE==1&&MQTT==2&&WEBTHING==3);
static_assert(WIFIMODE_UNSET==0&&WIFIMODE_STATION==1&&WIFIMODE_AP==2&&WIFIMODE_FALLBACK==3);
static_assert(MCU_NETWORKMODE_SMARTCONFIG==0&&MCU_NETWORKMODE_APCONFIG==1&&MCU_NETWORKMODE_NOTCONNECTED==2&&
    MCU_NETWORKMODE_CONNECTED==3&&MCU_NETWORKMODE_CONNECTEDCLOUD==4&&MCU_NETWORKMODE_POWERSAVE==5);
int main(){
    Print output;WLog log(0,0,&output);
    for(unsigned flag=0;flag<256;++flag){
        EEPROM.bytes.fill(0xa5);EEPROM.bytes[0]=flag;EEPROM.bytes[1]=0xf1;const auto before=EEPROM.bytes;
        WSettings settings(&log,0xf1,false);
        const bool known=flag>=FLAG_OPTIONS_NETWORK_V1&&flag<=FLAG_OPTIONS_NETWORK_V3;
        assert(settings.existsSettingsNetwork()==known&&settings.getSettingsApplicationIsCurrent()==known);
        const unsigned expected=flag==FLAG_OPTIONS_NETWORK_V1?NETWORKSETTINGS_PRE_FAS123:
            flag==FLAG_OPTIONS_NETWORK_V2?NETWORKSETTINGS_PR2:flag==FLAG_OPTIONS_NETWORK_V3?NETWORKSETTINGS_CURRENT:NETWORKSETTINGS_UNKNOWN;
        assert(settings.getNetworkSettingsVersion()==expected);
        assert(settings.getSettingsNetworkIsCurrent()==(flag==FLAG_OPTIONS_NETWORK_V3));
        assert(EEPROM.bytes==before);
    }
    puts("PASS compact enum values and all 256 EEPROM version flags, without writes");
}
'''
        self.compile_run(source, 'medium_enums_settings')

    def test_schedule_groups_preserve_default_for_all_byte_values(self):
        source = r'''
#include "Arduino.h"
#include <map>
struct WJson{std::map<std::string,String>strings;std::map<std::string,double>numbers;
 void propertyString(const char*k,const char*v){strings[k]=v;}void propertyDouble(const char*k,double v){numbers[k]=v;}};
const char SCHEDULES_DAYS[]="wau",SCHEDULES_PERIODS[]="123456";
struct Probe{byte schedules[54]{};double getTemperatureFactor(){return 2;}
'''+method(BECA, 'toJsonSchedules')+r'''
};
int main(){
    Probe p;
    for(unsigned day=0;day<3;++day)for(unsigned n=0;n<6;++n){unsigned i=day*18+n*3;p.schedules[i]=n*10;p.schedules[i+1]=day*6+n;p.schedules[i+2]=40+day+n;}
    for(unsigned group=0;group<256;++group){
        WJson json;p.toJsonSchedules(&json,group);assert(json.strings.size()==6&&json.numbers.size()==6);
        const unsigned day=group==1?1:group==2?2:0;
        for(unsigned n=0;n<6;++n){
            char key[]={SCHEDULES_DAYS[day],static_cast<char>('1'+n),'h','\0'},time[6];
            snprintf(time,sizeof(time),"%02u:%02u",day*6+n,n*10);
            assert(json.strings.at(key)==time);key[2]='t';assert(json.numbers.at(key)==(40+day+n)/2.0);
        }
    }
    puts("PASS all 256 schedule groups retain their legacy field names and values");
}
'''
        self.compile_run(source, 'medium_schedule_groups')

    def test_mcu_idle_and_unknown_initialization_states(self):
        source = r'''
#include "Arduino.h"
struct Log{template<class...T>void notice(T...){};};struct Net{Log value;Log*log(){return &value;}};
struct Probe{Net net;Net*network=&net;bool mcuInitialized=false,receivingDataFromMcu=false;
 unsigned mcuInitializeState=0,mcuRetryCount=0,commands=0,updates=0;unsigned long lastMcuAttempt=0;
 void commandCharsToSerial(int,const unsigned char*){++commands;}void queryAllDPs(){++commands;}
 void updateTargetTemperature(){++updates;}void updateModeAndAction(){++updates;}
'''+method(BECA, 'mcuInitialize')+r'''
};
int main(){
    for(unsigned state=0;state<256;++state){
        Probe p;p.mcuInitializeState=state;testMillis=0;p.mcuInitialize();
        assert(p.commands==((state==1||state==3||state==5)?1U:0U));
        const unsigned expected=state==1?2:state==3?5:state==5?6:state==7?0:state;
        assert(p.mcuInitializeState==expected&&p.mcuInitialized==(state==7)&&p.updates==(state==7?2U:0U));
    }
    puts("PASS idle, waiting, known and all unsupported MCU initialization states");
}
'''
        self.compile_run(source, 'medium_mcu_init')

    def test_unknown_mcu_values_preserve_protocol_behavior(self):
        source = r"""
#include "properties.h"
const int MODEL_BHT_002_GBLW=0,MODEL_BAC_002_ALW=1,STATE_COMPLETE=6;
const int LOG_LEVEL_NOTICE=1,LOG_LEVEL_TRACE=2,LOG_LEVEL_VERBOSE=3,LOG_LEVEL_WARNING=4;
const char* SYSTEM_MODE_COOL="cool",*SYSTEM_MODE_HEAT="heat",*SYSTEM_MODE_FAN="fan";
const char* FAN_MODE_AUTO="auto",*FAN_MODE_HIGH="high",*FAN_MODE_MEDIUM="medium",*FAN_MODE_LOW="low";
const char* SCHEDULES_MODE_OFF="off",*SCHEDULES_MODE_AUTO="auto";
struct Log{template<class...T>void trace(T...){}template<class...T>void notice(T...){}};
struct Net{Log logger;Log*log(){return &logger;}};
struct Probe{
 Net net;Net*network=&net;int commandLength=0,mcuInitializeState=0;
 bool mcuInitialized=false,receivingDataFromMcu=false,receivedStates[6]{};
 byte receivedCommand[1024]{},schedules[54]{},schedulesDataPoint=0;
 double targetTemperatureManualMode=21.5;unsigned long lastTimeRequested=0;
 unsigned unknown=0,notifications=0,commands=0;std::function<bool()>onConfigurationRequest,onPowerButtonOn;
 WProperty on{"on","",BOOLEAN},eco{"eco","",BOOLEAN},lock{"lock","",BOOLEAN},temp{"temp","",DOUBLE},floor{"floor","",DOUBLE},
   sys{"sys","",STRING},fan{"fan","",STRING},mode{"mode","",STRING},model{"model","",BYTE},id{"id","",STRING};
 WProperty*deviceOn=&on,*ecoMode=&eco,*locked=&lock,*actualTemperature=&temp,*actualFloorTemperature=&floor,
   *systemMode=&sys,*fanMode=&fan,*schedulesMode=&mode,*thermostatModel=&model,*mcuId=&id;
 Probe(){model.setByte(MODEL_BAC_002_ALW);sys.setString("heat");fan.setString("low");mode.setString("off");}
 void logIncomingCommand(const char*text,int){if(!strcmp(text,"unknown"))++unknown;}
 void notifyState(){++notifications;}void notifySchedules(){++notifications;}
 void updateTargetTemperature(){}void updateModeAndAction(){}void updateCurrentSchedulePeriod(){}void holdFromScheduler(){}
 void startMcuInitialize(){mcuInitialized=false;}void sendActualTimeToBecaRequested(bool){}
 void commandCharsToSerial(int,const unsigned char*){++commands;}
 double getTemperatureFactor(){return 2;}byte getThermostatModel(){return model.getByte();}
 void frame(byte type,byte dp,byte value){
  commandLength=type==7?5:1;receivedCommand[0]=0x55;receivedCommand[1]=0xaa;receivedCommand[2]=1;
  receivedCommand[3]=type;receivedCommand[4]=0;receivedCommand[5]=commandLength;receivedCommand[6]=dp;
  receivedCommand[8]=0;receivedCommand[9]=1;receivedCommand[10]=value;processSerialCommand(1000);
 }
"""
        for name in ['getSystemModeAsByte','getFanModeAsByte','decodeMcuValue','processSerialCommand']:
            source += method(BECA,name)+'\n'
        source += r"""
};
int main(){
 for(unsigned value=0;value<256;++value){
  Probe heartbeat;heartbeat.frame(0,value,0);assert(heartbeat.unknown==(value>1?1U:0U)&&!heartbeat.receivingDataFromMcu&&heartbeat.commands==0);
  Probe sys;sys.frame(7,0x66,value);const char*expected=value==0?"cool":value==1?"heat":value==2?"fan":"heat";
  assert(sys.sys.equalsString(expected)&&sys.unknown==0);
  Probe fan;fan.frame(7,0x67,value);expected=value==0?"auto":value==1?"high":value==2?"medium":"low";
  assert(fan.fan.equalsString(expected)&&fan.unknown==0);
  if((value>=1&&value<=6)||value==0x65||value==0x66||value==0x67||value==0x68)continue;
  Probe dp;dp.frame(7,value,1);assert(dp.unknown==1&&dp.notifications==0&&dp.commands==0);
  assert(dp.sys.equalsString("heat")&&dp.fan.equalsString("low")&&dp.targetTemperatureManualMode==21.5);
  for(bool received:dp.receivedStates)assert(!received);
 }
 puts("PASS all byte values for heartbeat, data points, system mode and fan mode preserve legacy behavior");
}
"""
        self.compile_run(source,'medium_mcu_protocol')

    def test_bssid_recovery_ap_transition_and_retry(self):
        text = NETWORK.read_text()
        start = text.index('#ifdef DEBUG\nconst int maxApRunTimeMinutes')
        constants = text[start:text.index('WiFiEventHandler', start)]
        loop = method(NETWORK, 'loop')
        self.assertIn('updateWifiRecovery(now);', loop)
        self.assertIn('WiFi.mode(recoveryApActive ? WIFI_AP_STA : WIFI_STA)', loop)
        transition = loop[loop.index('if (wifiModeDesired!=wifiModeRunning)'):loop.index('if (wifiModeRunning == wnWifiMode::WIFIMODE_STATION &&')]
        source = r'''
#include "Arduino.h"
const int WL_CONNECTED=3,WIFI_AP=2,WIFI_AP_STA=3;
const char*CONFIG_PASSWORD="fixture-ap-key";
struct IPAddress{uint32_t value;IPAddress(uint32_t v=0):value(v){}IPAddress(byte a,byte b,byte c,byte d):value(a|(b<<8)|(c<<16)|(uint32_t(d)<<24)){}
 byte operator[](unsigned i)const{return value>>(i*8);}operator uint32_t()const{return value;}
 bool fromString(const char* s){unsigned a,b,c,d;if(sscanf(s,"%u.%u.%u.%u",&a,&b,&c,&d)!=4)return false;*this=IPAddress(a,b,c,d);return true;}};
struct Wifi{int connected=0,modeValue=0;unsigned aps=0,disconnects=0;bool selectedLock=false,apOk=true;byte selected[6]{};
 IPAddress ip{192,168,1,20},apIp{192,168,4,1};
 int status(){return connected;}void disconnect(){++disconnects;}void softAPdisconnect(bool=false){}bool mode(int m){modeValue=m;return true;}
 bool softAP(const char*,const char*){++aps;return apOk;}IPAddress softAPIP(){return apIp;}IPAddress localIP(){return ip;}IPAddress subnetMask(){return IPAddress(255,255,255,0);}
 bool softAPConfig(IPAddress ip,IPAddress,IPAddress){apIp=ip;return true;}
 void begin(const char*,const char*,int channel,const uint8_t* bssid){assert(channel==0);selectedLock=bssid;if(bssid)memcpy(selected,bssid,6);}
}WiFi;
struct ip4_addr_t{uint32_t addr;};struct eth_addr{};
struct netif{netif*next=nullptr;ip4_addr_t ip{WiFi.ip},gateway{IPAddress(192,168,1,1)};};
netif station;netif*netif_list=&station;bool cachedGateway=true;unsigned arpRequests=0;
uint32_t ip4_addr_get_u32(const ip4_addr_t*p){return p->addr;}bool ip4_addr_isany_val(ip4_addr_t ip){return !ip.addr;}
const ip4_addr_t*netif_ip4_addr(netif*p){return &p->ip;}const ip4_addr_t*netif_ip4_gw(netif*p){return &p->gateway;}
int etharp_find_addr(netif*,const ip4_addr_t*,eth_addr**,const ip4_addr_t**){return cachedGateway?0:-1;}
void etharp_request(netif*,const ip4_addr_t*){++arpRequests;}
enum class DNSReplyCode{NoError};
struct DNSServer{void setErrorReplyCode(DNSReplyCode){}void start(int,const char*,IPAddress){}};
struct Log{template<class...T>void warning(T...){}template<class...T>void notice(T...){}template<class...T>void trace(T...){}};
'''+constants+r'''
struct Probe{
 Log logger;Log*wlog=&logger;bool bssidLocked=true,fallback=false,updating=false,settingsFound=true,staticIp=false;
 wnWifiMode wifiModeRunning=WIFIMODE_STATION,wifiModeDesired=WIFIMODE_STATION;
 unsigned long wifiOfflineSince=0,apStartedAt=0,lastWifiConnect=0,lastMqttConnect=0;int connectFailCounter=0;
 unsigned long gatewayLastCheck=0,gatewayLastSeen=0,recoveryApStartedAt=0,localRecoveryStartedAt=0;
 bool recoveryApActive=false,localRecoveryActive=false;
 DNSServer*dnsApServer=nullptr;uint8_t bssid[6]={2,0x11,0x22,0x33,0x44,0x55};
 ~Probe(){deleteDnsApServer();}void deleteDnsApServer(){delete dnsApServer;dnsApServer=nullptr;}
 bool isSupportingApFallback(){return fallback;}bool isUpdateRunning(){return updating;}bool isStaticIpEnabled(){return staticIp;}const char*getStaticIp(){return "192.168.4.20";}const char*getSubnetMask(){return "255.255.0.0";}
 void disconnectMqtt(){}void logHeap(const char*){}String getClientName(bool){return "fixture";}
 const char*getSsid(){return "fixture-ssid";}const char*getPassword(){return "fixture-password";}
'''
        for name in ['updateWifiRecovery', 'gatewayReachable', 'startRecoveryAp', 'stopRecoveryAp', 'startLocalRecovery', 'getBssid', 'parseBssid', 'connectWifi']:
            source += method(NETWORK, name) + '\n'
        source += 'void transition(unsigned long now){' + transition + '}\n};\n'
        source += r'''
int main(){
    Probe p;p.wifiOfflineSince=5000;
    p.updateWifiRecovery(124999);assert(!p.recoveryApActive);
    p.updating=true;p.updateWifiRecovery(125000);assert(!p.recoveryApActive);
    p.updating=false;p.updateWifiRecovery(125000);
    assert(p.recoveryApActive&&p.wifiModeDesired==WIFIMODE_STATION&&WiFi.modeValue==WIFI_AP_STA&&WiFi.disconnects==0&&p.dnsApServer);
    for(int i=0;i<5;++i){p.connectWifi();assert(WiFi.selectedLock&&!memcmp(WiFi.selected,p.bssid,6));}
    const unsigned long end=125000+maxApRunTimeMinutes*60000UL;
    p.updating=true;p.updateWifiRecovery(end+1);assert(p.recoveryApActive);
    p.updating=false;p.updateWifiRecovery(end+1);assert(!p.recoveryApActive&&!p.dnsApServer);
    p.updateWifiRecovery(end+120000);assert(!p.recoveryApActive);
    p.updateWifiRecovery(end+120001);assert(p.recoveryApActive);
    p.wifiModeDesired=WIFIMODE_AP;p.transition(end+120001);
    assert(!p.recoveryApActive&&p.wifiModeRunning==WIFIMODE_AP&&WiFi.modeValue==WIFI_AP);
    p.wifiModeDesired=WIFIMODE_STATION;p.transition(end+120002);
    assert(!p.dnsApServer&&p.wifiOfflineSince==end+120002);
    {Probe healthy;healthy.bssidLocked=false;healthy.fallback=true;WiFi.connected=WL_CONNECTED;
     healthy.updateWifiRecovery(1000000);assert(!healthy.recoveryApActive);
     healthy.staticIp=true;healthy.gatewayLastSeen=1000000;cachedGateway=true;
     healthy.updateWifiRecovery(1500000);assert(!healthy.recoveryApActive&&arpRequests);
     cachedGateway=false;healthy.updateWifiRecovery(1619999);assert(!healthy.recoveryApActive);
     healthy.updateWifiRecovery(1625000);assert(healthy.recoveryApActive);
     // Returning to the LAN does not cut off a user who is editing recovery settings.
     cachedGateway=true;healthy.updateWifiRecovery(1630000);assert(healthy.recoveryApActive);}
    WiFi.connected=0;
    {Probe wrap;wrap.wifiOfflineSince=ULONG_MAX-60000UL;
     wrap.updateWifiRecovery(wrap.wifiOfflineSince+119999UL);assert(!wrap.recoveryApActive);
     wrap.updateWifiRecovery(wrap.wifiOfflineSince+120000UL);assert(wrap.recoveryApActive);}
    {Probe disabled;disabled.bssidLocked=false;disabled.fallback=false;disabled.updateWifiRecovery(3000000);
#ifdef MINIMAL
     assert(disabled.recoveryApActive);
#else
     assert(!disabled.recoveryApActive);
#endif
    }
    {Probe local;testMillis=100;local.startLocalRecovery();local.transition(100);
     assert(local.localRecoveryActive&&local.wifiModeRunning==WIFIMODE_AP);
     local.updateWifiRecovery(300099);assert(local.localRecoveryActive);
     local.updateWifiRecovery(300100);assert(!local.localRecoveryActive&&local.wifiModeDesired==WIFIMODE_STATION);}
    {Probe collision;collision.staticIp=true;WiFi.ip=IPAddress(0U);collision.startRecoveryAp(0);assert(WiFi.apIp==IPAddress(172,31,255,1));}
    {Probe failed;WiFi.apOk=false;failed.startRecoveryAp(0);assert(!failed.recoveryApActive&&!failed.dnsApServer);WiFi.apOk=true;}
    puts("PASS fault-only AP+STA, gateway ARP, offline timeout, physical recovery expiry, BSSID retries, OTA deferral and clock wrap");
}
'''
        for define, suffix in [('', 'normal'), ('#define MINIMAL\n', 'minimal'), ('#define DEBUG\n', 'debug')]:
            self.compile_run(define+source, 'medium_recovery_'+suffix)


if __name__ == '__main__':
    unittest.main()
