"""Exercise the actual Wi-Fi handlers and EEPROM extension without a radio."""
import re
import unittest

import test_regressions as native
from test_regressions import ROOT, NETWORK, method


class BssidTests(unittest.TestCase):
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
    const char*getMqttPassword(){return settings->getString(PROP_MQTTPASSWORD);}
    bool isWebServerRunning(){return true;}
    void restart(AsyncWebServerRequest*,const __FlashStringHelper*){restarted=true;}
'''
        for name in ['getPassword', 'migrateRecoverySettings', 'getBssid', 'parseBssid', 'connectWifi', 'loadBssid', 'saveBssid', 'isAuthenticationRequired', 'validStaticNetwork', 'handleHttpSave']:
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
    puts("PASS BSSID parser, atomic HTTP validation, EEPROM preservation, minimal/normal and reconnect lock");
}
'''
        native.NativeTests().compile_run(source, 'wifi_bssid')

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


if __name__ == '__main__':
    unittest.main()
