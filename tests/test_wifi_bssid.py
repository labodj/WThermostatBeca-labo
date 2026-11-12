"""Exercise the actual Wi-Fi handlers and EEPROM extension without a radio."""
import re
import unittest
import native_support as native
from native_support import NETWORK, ROOT, method


class BssidTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_lock_validation_reconnect_and_existing_eeprom(self):
        text = NETWORK.read_text()
        constants = text[text.index('const byte NETBITS1_MQTT'):text.index('\n#ifdef DEBUG', text.index('const byte NETBITS1_MQTT'))]
        # Derive every stored field/size from the production registration calls.
        layout = []
        sources = [(method(NETWORK, 'loadSettings'), r'(?<!\w)settings->'),
                   ((ROOT / 'WThermostat/WClock.h').read_text().split('parseTimeZone(this->timeZoneConfig')[0], r'network->getSettings\(\)->'),
                   ((ROOT / 'WThermostat/WBecaDevice.h').read_text().split('this->mcuId =')[0], r'network->getSettings\(\)->')]
        for source, receiver in sources:
            for kind, key, length in re.findall(receiver + r'set(String|Byte)\((PROP_\w+)(?:,\s*(\d+),)?', source):
                name = key if receiver.startswith('(?') else '"' + key + '"'
                value = '' if receiver.startswith('(?') else f'v{len(layout)}'
                byte_value = 0 if receiver.startswith('(?') else len(layout) + 1
                layout.append(f'settings->setString({name},{length},"{value}");' if kind == 'String' else f'settings->setByte({name},{byte_value});')
        network_fields = len(re.findall(r'(?<!\w)settings->set(?:String|Byte)\(PROP_', sources[0][0]))
        self.assertEqual(14, network_fields)
        source = r'''
#define MINIMAL
#include "properties.h"
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WStringProperty.h"
#include "lib/WAdapter/WAdapter/WNetworkStrings.h"
#include "lib/WAdapter/WAdapter/WSettings.h"
#include "lib/WAdapter/WAdapter/WWifiPassword.h"
#include <map>
const char* CT_TEXT_PLAIN="text/plain",*FORM_PW_NOCHANGE="___NOCHANGE___";
struct AsyncWebServerRequest{
    std::map<std::string,String> fields;int status=0;
    bool hasParam(const char* name,bool){return fields.count(name);}
    void send(int code,const char*,const char*){status=code;}
};
String getValueOrEmpty(AsyncWebServerRequest* request,const char* name){auto it=request->fields.find(name);return it==request->fields.end()?String(""):it->second;}
struct IPAddress{byte octets[4]{};byte operator[](unsigned i){return octets[i];}
 bool fromString(const String& value){unsigned a,b,c,d;char tail;
 if(sscanf(value.c_str(),"%u.%u.%u.%u%c",&a,&b,&c,&d,&tail)!=4||a>255||b>255||c>255||d>255)return false;
 octets[0]=a;octets[1]=b;octets[2]=c;octets[3]=d;return true;}};
struct Wifi{
    void setAutoReconnect(bool enabled){assert(enabled);}
    String lastPassword;bool locked=false;uint8_t selected[6]{};unsigned begins=0;int channel=-1;
    void begin(const char* ssid,const char* password,int ch,const uint8_t* address){
        assert(!strcmp(ssid,"room-wifi"));lastPassword=password;
        locked=address;channel=ch;++begins;if(address)memcpy(selected,address,6);
    }
}WiFi;
'''
        source += constants + r'''
struct Probe{
    Print output;WLog log{0,0,&output};WLog*wlog=&log;
    WSettings storage{&log,0xf1,false};WSettings*settings=&storage;
    WProperty*idx=nullptr,*ssid=nullptr,*mqttBaseTopic=nullptr;
    WProperty apFallback{"ap","AP",BOOLEAN};WProperty*supportingApFallback=&apFallback;
    String extendedWifiPassword;
    WNetworkStrings networkStrings;
    String removedIdx,removedTopic;unsigned removals=0;
    bool sendMqttHassAutodiscover(bool remove){assert(remove);++removals;removedIdx=getIdx();removedTopic=getMqttTopic();return true;}
    uint8_t bssid[6]{};bool bssidLocked=false,restarted=false;
    Probe(bool minimal=false){settings->reallyReadSettings=false;
'''
        source += '\n'.join(layout[:network_fields])
        source += 'if(!minimal){' + '\n'.join(layout[network_fields:]) + '}'
        source += r'''
        assert(settings->getCurrentAddress()+2<=LEGACY_EEPROM_SIZE-8);
        idx=settings->getSetting(PROP_IDX);ssid=settings->getSetting(PROP_SSID);mqttBaseTopic=settings->getSetting(PROP_MQTTTOPIC);
        settings->setString(PROP_SSID,"room-wifi");settings->setString(PROP_PASSWORD,"password");
        settings->setString(PROP_MQTTPORT,"1883");settings->setByte(PROP_NETBITS1,NETBITS1_MQTT|NETBITS1_HASS|NETBITS1_RECOVERY_MIGRATED);
    }
    const char*getSsid(){return ssid->c_str();}
    bool isWebServerRunning(){return true;}
    void restart(AsyncWebServerRequest*,const __FlashStringHelper*){restarted=true;}
'''
        for name in ['getIdx', 'getMqttUser', 'getMqttPassword', 'getMqttTopic', 'getPassword', 'migrateRecoverySettings', 'getBssid', 'parseBssid', 'connectWifi', 'loadBssid', 'saveBssid', 'isAuthenticationRequired', 'validStaticNetwork', 'handleHttpSave']:
            source += method(NETWORK, name) + '\n'
        source += r'''
};
AsyncWebServerRequest request(){
    AsyncWebServerRequest r;
    for(const char* key:{"i","s","p","ms","mo","mu","mp","mt","staticip","subnet","gateway","dns1","dns2"})r.fields[key]="";
    r.fields["s"]="room-wifi";r.fields["p"]="password";r.fields["mo"]="1883";r.fields["mq"]="true";r.fields["mqhass"]="true";
    return r;
}
int main(){
    EEPROM.bytes.fill(0xff);Probe p;p.settings->save();const auto original=EEPROM.bytes;
    p.loadBssid();assert(!p.bssidLocked&&p.getBssid()=="");p.connectWifi();assert(!WiFi.locked&&WiFi.channel==0);
    uint8_t address[6]{};
    for(const char* good:{"02:11:22:33:44:55","aa:bb:cc:dd:ee:ff","00:00:00:00:00:01"})assert(Probe::parseBssid(good,address));
    memset(address,0xa5,6);
    for(const char* bad:{"","00:00:00:00:00:00","FF:FF:FF:FF:FF:FF","01:11:22:33:44:55","02-11-22-33-44-55",
        "02:11:22:33:44:5","02:11:22:33:44:555","02:11:22:33:44:5G"," 02:11:22:33:44:55","02:11:22:33:44:55 ","02:11:22:33:44:é"}){
        assert(!Probe::parseBssid(bad,address));for(byte value:address)assert(value==0xa5);
    }
    assert(Probe::parseBssid("02:11:22:33:44:55",address));assert(p.saveBssid(address,true));
    for(unsigned i=0;i<LEGACY_EEPROM_SIZE-8;++i)assert(EEPROM.bytes[i]==original[i]);assert(EEPROM.bytes.back()==original.back());
    const auto locked=EEPROM.bytes;p.loadBssid();assert(p.bssidLocked&&p.getBssid()=="02:11:22:33:44:55");
    for(unsigned retry=0;retry<5;++retry){WiFi.locked=false;p.connectWifi();assert(WiFi.locked&&WiFi.channel==0&&!memcmp(WiFi.selected,address,6));}
    for(int i=0;i<6;++i)EEPROM.bytes[LEGACY_EEPROM_SIZE-7+i]=0xff;
    p.loadBssid();unsigned begins=WiFi.begins;p.connectWifi();assert(p.bssidLocked&&WiFi.begins==begins);
    assert(p.saveBssid(address,true));p.loadBssid();
    p.settings->save();assert(EEPROM.bytes==locked);
    {Probe minimal(true);minimal.settings->save();assert(EEPROM.bytes==locked);minimal.loadBssid();minimal.connectWifi();assert(WiFi.locked);}
    auto bad=request();bad.fields["bssid"]="FF:FF:FF:FF:FF:FF";unsigned commits=EEPROM.commits;
    p.handleHttpSave(&bad);assert(bad.status==400&&!p.restarted&&EEPROM.bytes==locked&&EEPROM.commits==commits);
    bad=request();bad.fields["bssid"]="02:AA:BB:CC:DD:EE";bad.fields["mo"]="99999";
    p.handleHttpSave(&bad);assert(bad.status==400&&EEPROM.bytes==locked&&EEPROM.commits==commits);
    auto missing=request();p.handleHttpSave(&missing);p.loadBssid();assert(p.getBssid()=="02:11:22:33:44:55");
    auto changed=request();changed.fields["bssid"]="02:aa:bb:cc:dd:ee";p.handleHttpSave(&changed);assert(p.restarted);
    p.loadBssid();assert(p.getBssid()=="02:AA:BB:CC:DD:EE");p.connectWifi();assert(WiFi.locked&&WiFi.selected[1]==0xaa);
    auto clear=request();clear.fields["bssid"]="";p.handleHttpSave(&clear);p.loadBssid();assert(!p.bssidLocked);p.connectWifi();assert(!WiFi.locked);
    for(unsigned i=0;i<LEGACY_EEPROM_SIZE-8;++i)assert(EEPROM.bytes[i]==original[i]);
    auto disable=request();disable.fields["authModePresent"]="1";p.handleHttpSave(&disable);
    assert(!p.isAuthenticationRequired()&&(p.settings->getByte(PROP_NETBITS1)&NETBITS1_AUTH_DISABLED));
    auto legacy=request();p.handleHttpSave(&legacy);assert(!p.isAuthenticationRequired());
    auto enable=request();enable.fields["authModePresent"]="1";enable.fields["authRequired"]="true";p.handleHttpSave(&enable);
    assert(p.isAuthenticationRequired());
    const auto protectedBytes=EEPROM.bytes;
    auto passwordless=request();passwordless.fields["p"]="";p.handleHttpSave(&passwordless);
    assert(passwordless.status==400&&EEPROM.bytes==protectedBytes);
    passwordless=request();passwordless.fields["p"]="";passwordless.fields["authModePresent"]="1";p.handleHttpSave(&passwordless);
    assert(!p.isAuthenticationRequired()&&p.getPassword()[0]==0);
    // Every migrated bit pattern enables fallback exactly once and preserves all other bytes.
    for(unsigned flags=0;flags<64;++flags){
        p.settings->setString(PROP_PASSWORD,"password");p.settings->setByte(PROP_NETBITS1,flags);
        const auto before=EEPROM.bytes;p.migrateRecoverySettings();
        assert(p.settings->getByte(PROP_NETBITS1)==(flags|NETBITS1_APFALLBACK|NETBITS1_RECOVERY_MIGRATED));
        for(unsigned i=0;i<EEPROM.bytes.size();++i)if(i!=82)assert(EEPROM.bytes[i]==before[i]);
        p.settings->setByte(PROP_NETBITS1,(flags|NETBITS1_RECOVERY_MIGRATED)&~NETBITS1_APFALLBACK);
        const auto chosen=EEPROM.bytes;p.migrateRecoverySettings();assert(EEPROM.bytes==chosen);
    }
    p.settings->setString(PROP_PASSWORD,"");p.settings->setByte(PROP_NETBITS1,0);p.migrateRecoverySettings();
    assert(!p.isAuthenticationRequired()&&(p.settings->getByte(PROP_NETBITS1)&NETBITS1_AUTH_DISABLED));
    const String punctuation=" !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~ ";
    for(const String& secret:{String(std::string(8,'a')),String(std::string(32,'b')),String(std::string(33,'c')),String(std::string(63,'d')),String(std::string(64,'A')),
        String("___NOCHANGE___"),punctuation,String("èéàü☃-long-password-012345678901234567890")}){
        auto save=request();save.fields["wifiPasswordMode"]="1";save.fields["p"]=secret;
        p.handleHttpSave(&save);assert(!save.status&&!strcmp(p.getPassword(),secret.c_str()));
        const auto saved=EEPROM.bytes;
        p.extendedWifiPassword=WWifiPassword::load(p.getSsid(),p.settings->getString(PROP_PASSWORD));
        assert(!strcmp(p.getPassword(),secret.c_str()));p.connectWifi();assert(WiFi.lastPassword==secret);
        p.settings->save();assert(EEPROM.bytes==saved);
        auto keep=request();keep.fields["wifiPasswordMode"]="1";keep.fields["keepWifiPassword"]="true";keep.fields["p"]="";
        p.handleHttpSave(&keep);assert(!keep.status&&!strcmp(p.getPassword(),secret.c_str()));
    }
    for(const String& secret:{String(std::string(7,'a')),String(std::string(65,'a')),String(std::string(64,'z')),String("ab\0cd12345",10)}){
        const auto before=EEPROM.bytes;auto invalid=request();invalid.fields["wifiPasswordMode"]="1";invalid.fields["p"]=secret;
        p.handleHttpSave(&invalid);assert(invalid.status==400&&EEPROM.bytes==before);
    }
    assert(WWifiPassword::load("different-ssid",p.settings->getString(PROP_PASSWORD))=="");
    EEPROM.bytes[530]^=1;assert(WWifiPassword::load(p.getSsid(),p.settings->getString(PROP_PASSWORD))=="");
    // Reject routing mistakes before any EEPROM write.
    auto ip=request();ip.fields["staticIpEnabled"]="true";ip.fields["staticip"]="192.168.1.20";
    ip.fields["subnet"]="255.255.255.0";ip.fields["gateway"]="192.168.2.1";
    auto before=EEPROM.bytes;p.handleHttpSave(&ip);assert(ip.status==400&&EEPROM.bytes==before);
    ip.fields["gateway"]="192.168.1.1";ip.status=0;p.handleHttpSave(&ip);assert(!ip.status);
    for(const char* mask:{"0.0.0.0","255.255.0.255","255.255.255.255","255.255.255.254"}){
      ip.status=0;ip.fields["subnet"]=mask;before=EEPROM.bytes;p.handleHttpSave(&ip);assert(ip.status==400&&EEPROM.bytes==before);}
    assert(!Probe::validStaticNetwork("192.168.1.0","255.255.255.0","192.168.1.1"));
    assert(!Probe::validStaticNetwork("192.168.1.255","255.255.255.0","192.168.1.1"));
    assert(!Probe::validStaticNetwork("192.168.1.1","255.255.255.0","192.168.1.1"));
    // New forms express keep/change separately, so every literal password is usable.
    for(const String& secret:{String("___NOCHANGE___"),String(std::string(64,'q')),String(" \"'&<password>\\")}){
      auto save=request();save.fields["mqttPasswordMode"]="1";save.fields["mp"]=secret;
      save.fields["i"]=String(std::string(32,'h'));save.fields["mu"]=String(std::string(32,'u'));save.fields["mt"]=String(std::string(64,'t'));
      p.handleHttpSave(&save);assert(!save.status&&String(p.getMqttPassword())==secret);
      assert(strlen(p.getIdx())==32&&strlen(p.getMqttUser())==32&&strlen(p.getMqttTopic())==64);
      const char* fields[]={p.idx->c_str(),p.settings->getString(PROP_MQTTUSER),p.settings->getString(PROP_MQTTPASSWORD),p.mqttBaseTopic->c_str()};
      assert(p.networkStrings.loadAndMigrate(fields,nullptr));assert(String(p.getMqttPassword())==secret);
      save.fields["keepMqttPassword"]="true";save.fields["mp"]="";p.handleHttpSave(&save);assert(String(p.getMqttPassword())==secret);
    }
    auto tooLong=request();tooLong.fields["mp"]=String(std::string(65,'p'));before=EEPROM.bytes;
    p.handleHttpSave(&tooLong);assert(tooLong.status==400&&EEPROM.bytes==before);
    auto fail=request();fail.fields["mqttPasswordMode"]="1";fail.fields["mp"]=String(std::string(64,'z'));
    const String oldPassword=p.getMqttPassword();before=EEPROM.bytes;EEPROM.commitOk=false;
    p.handleHttpSave(&fail);assert(fail.status==500&&String(p.getMqttPassword())==oldPassword);
    for(unsigned i=0;i<640;++i)assert(EEPROM.bytes[i]==before[i]);EEPROM.commitOk=true;

    // Raw fields and all extension records share one commit, even when many values change.
    auto whole=request();whole.fields["i"]="new-host";whole.fields["bssid"]="02:55:44:33:22:11";
    whole.fields["p"]=String(std::string(63,'w'));whole.fields["mp"]=String(std::string(64,'m'));
    whole.fields["mu"]=String(std::string(32,'u'));whole.fields["mt"]=String(std::string(64,'t'));
    whole.fields["staticip"]="192.168.1.9";whole.fields["subnet"]="255.255.255.0";whole.fields["gateway"]="192.168.1.1";
    whole.fields["apfb"]="true";whole.fields["authModePresent"]="1";
    const String previousIdx=p.getIdx(),previousTopic=p.getMqttTopic();
    commits=EEPROM.commits;p.handleHttpSave(&whole);assert(!whole.status&&EEPROM.commits==commits+1);
#ifndef MINIMAL
    assert(p.removedIdx==previousIdx&&p.removedTopic==previousTopic);
#endif
    const auto coherent=EEPROM.bytes;const String wifi=p.getPassword(),mqttSecret=p.getMqttPassword(),identity=p.getIdx();
    auto failure=whole;failure.status=0;failure.fields["i"]="failed-host";failure.fields["p"]=String(std::string(63,'x'));
    failure.fields["mp"]=String(std::string(64,'y'));failure.fields["bssid"]="";
    const unsigned removals=p.removals;
    commits=EEPROM.commits;EEPROM.failCommits=1;p.restarted=false;p.handleHttpSave(&failure);
    assert(p.removals==removals);
    assert(failure.status==500&&!p.restarted&&EEPROM.bytes==coherent&&EEPROM.commits==commits+1);
    assert(String(p.getPassword())==wifi&&String(p.getMqttPassword())==mqttSecret&&String(p.getIdx())==identity);
    p.loadBssid();assert(p.getBssid()=="02:55:44:33:22:11");
    assert(WWifiPassword::load(p.getSsid(),p.settings->getString(PROP_PASSWORD))==wifi);
    const char* restored[]={p.idx->c_str(),p.settings->getString(PROP_MQTTUSER),p.settings->getString(PROP_MQTTPASSWORD),p.mqttBaseTopic->c_str()};
    assert(p.networkStrings.loadAndMigrate(restored,nullptr)&&String(p.getMqttPassword())==mqttSecret);
    puts("PASS BSSID parser, one-commit saves, failed-commit rollback, EEPROM preservation, minimal/normal and reconnect lock");
}
'''
        native.NativeTests().compile_run(source, 'wifi_bssid_minimal')
        native.NativeTests().compile_run(source.replace('#define MINIMAL', ''), 'wifi_bssid_normal')

    def test_production_retry_uses_locked_connection(self):
        text = NETWORK.read_text()
        self.assertEqual(1, text.count('WiFi.begin('))
        self.assertIn('connectWifi();', text[:text.index('void connectWifi()')])
        self.assertIn('WiFi.setAutoReconnect(true)', text)
        self.assertIn('loadBssid();', method(NETWORK, 'loadSettings'))

    def test_legacy_layouts_do_not_reach_bssid_extension(self):
        old = method(NETWORK, 'loadSettings').split('Starting to fill new settings')[0]
        for branch in old.split('} else'):
            sizes = re.findall(r'settingsOld->set(String|Byte)\(PROP_\w+(?:,\s*(\d+),)?', branch)
            size = sum(int(length) if kind == 'String' else 1 for kind, length in sizes)
            # Upper bound: the four clock fields and all 13 current thermostat bytes.
            self.assertLessEqual(size + 66 + 13 + 2, 504)

    def test_optional_field_and_connected_ap_are_visible(self):
        from render_ui import render_pages
        from test_ui_rendering import Document
        pages = render_pages()
        fields = {attrs.get('name'): attrs for _, attrs, _ in Document(pages['/wifi']).fields}
        self.assertEqual('17', fields['bssid']['maxlength'])
        self.assertEqual('', fields['bssid']['value'])
        self.assertNotIn('required', fields['bssid'])
        self.assertIn('Connected AP BSSID:', pages['/info'])
        self.assertIn('02:11:22:33:44:55', pages['/info'])

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
 void setAutoReconnect(bool enabled){assert(enabled);}
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
