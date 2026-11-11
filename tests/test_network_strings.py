"""Legacy network values survive migration without moving existing EEPROM fields."""
import unittest

import test_regressions as native
from test_regressions import BECA, NETWORK, method


class NetworkStringTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_extension_roundtrip_prefix_binding_validation_and_failure(self):
        source = r'''
#include "properties.h"
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WStringProperty.h"
#include "lib/WAdapter/WAdapter/WNetworkStrings.h"
int main(){
 EEPROM.bytes.fill(0xff);for(unsigned i=504;i<640;++i)EEPROM.bytes[i]=byte(i);
 const auto before=EEPROM.bytes;
 String values[]={String(std::string(32,'h')),String(std::string(32,'u')),String(std::string(64,'p')),String(std::string(64,'t'))};
 std::string prefixes[4];const char* legacy[4];
 for(unsigned i=0;i<4;++i){prefixes[i]=values[i].substr(0,WNetworkStrings::legacyLength(i));legacy[i]=prefixes[i].c_str();}
 WNetworkStrings first;assert(first.save(values));
 for(unsigned i=0;i<640;++i)assert(EEPROM.bytes[i]==before[i]);
 assert(EEPROM.bytes.back()==before.back());
 WNetworkStrings loaded;assert(loaded.loadAndMigrate(legacy,nullptr));
 for(unsigned i=0;i<4;++i)assert(!strcmp(loaded.get(i,legacy[i]),values[i].c_str()));
 unsigned commits=EEPROM.commits;assert(first.save(values)&&EEPROM.commits==commits);
 const auto saved=EEPROM.bytes;values[2]=String(std::string(65,'x'));assert(!first.save(values)&&EEPROM.bytes==saved);
 values[2]=String("ab\0cd",5);assert(!first.save(values)&&EEPROM.bytes==saved);
 legacy[3]="different";assert(loaded.loadAndMigrate(legacy,nullptr));
 assert(!strcmp(loaded.get(3,legacy[3]),"different")&&!strcmp(loaded.get(2,legacy[2]),std::string(64,'p').c_str()));
 EEPROM.bytes[660]^=1;assert(loaded.loadAndMigrate(legacy,nullptr));assert(!strcmp(loaded.get(2,legacy[2]),legacy[2]));
 EEPROM.bytes=saved;EEPROM.bytes[642]=2;assert(loaded.loadAndMigrate(legacy,nullptr));assert(!strcmp(loaded.get(0,legacy[0]),legacy[0]));
 EEPROM.bytes=saved;String shorter[]={"room","user","secret","room/topic"};assert(first.save(shorter));
 for(unsigned i=640;i<844;++i)assert(EEPROM.bytes[i]==0xff);
 for(unsigned i=0;i<640;++i)assert(EEPROM.bytes[i]==before[i]);
 puts("PASS full values, prefix binding, checksums, limits, erasure and legacy bytes");
}
'''
        self.compile_run(source, 'network_string_record')

    def test_real_network_loader_migrates_old_values_and_preserves_identity(self):
        text = NETWORK.read_text()
        constants = text[text.index('const byte NETBITS1_MQTT'):text.index('\n#ifdef DEBUG', text.index('const byte NETBITS1_MQTT'))]
        constants += '\n' + '\n'.join(line for line in text.splitlines() if line.startswith('const char* DEFAULT_TOPIC_'))
        source = r'''
#define MINIMAL
#include "properties.h"
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WStringProperty.h"
#include "lib/WAdapter/WAdapter/WNetworkStrings.h"
#include "lib/WAdapter/WAdapter/WWifiPassword.h"
''' + constants + r'''
struct Probe{
 Print output;WLog logger{0,0,&output};WLog*wlog=&logger;WSettings*settings=nullptr,*settingsOld=nullptr;
 WProperty*idx=nullptr,*ssid=nullptr,*netBits1=nullptr,*mqttBaseTopic=nullptr,*supportingMqtt=nullptr,*supportingMqttHASS=nullptr,
 *supportingApFallback=nullptr,*supportingMqttSingleValues=nullptr,*staticIpEnabled=nullptr,*staticIp=nullptr,*subnetMask=nullptr,*gateway=nullptr,*dns1=nullptr,*dns2=nullptr;
 WNetworkStrings networkStrings;String extendedWifiPassword;byte bssid[6]{};bool bssidLocked=false;
 Probe(bool expected=true){startAddressReadOffset=startAddressSaveOffset=2;settings=new WSettings(wlog,0xf1,false);
  if(settings->getNetworkSettingsVersion()!=NETWORKSETTINGS_CURRENT||settings->getApplicationSettingsVersion()!=0xf1)settingsOld=new WSettings(wlog,0xf1,true);
  assert(loadSettings()==expected);}
 ~Probe(){delete supportingMqtt;delete supportingMqttHASS;delete supportingApFallback;delete supportingMqttSingleValues;delete staticIpEnabled;delete settingsOld;delete settings;}
 String getClientName(bool){return "default-room";}String getMacAddress(){return "AA:BB:CC:DD:EE:FF";}
 bool isSupportingWebThing(){return true;}
 void deleteSettingsOld(){delete settingsOld;settingsOld=nullptr;}
'''
        for name in ['loadSettings', 'getIdx', 'getSsid', 'getPassword', 'getMqttUser', 'getMqttPassword', 'getMqttTopic', 'getMqttServer', 'getMqttPort', 'getStaticIp', 'getSubnetMask', 'getGateway', 'getDns1', 'getDns2', 'isSupportingMqtt', 'isStaticIpEnabled', 'loadBssid']:
            source += method(NETWORK, name) + '\n'
        source += '};\nstruct Beca{Probe*network;\n' + method(BECA, 'discoveryId') + r'''
};
const std::string name(32,'h'),user(32,'u'),password(64,'p'),topic(64,'t');
void legacy(){
 EEPROM.bytes.fill(0xff);EEPROM.commitOk=true;EEPROM.bytes[0]=0xf0;unsigned at=1;
 auto field=[&](const std::string& text,unsigned size){for(unsigned i=0;i<size;++i)EEPROM.bytes[at+i]=i<text.size()?byte(text[i]):0;at+=size;};
 field(name,32);field("room-wifi",32);field("wifi-password",32);EEPROM.bytes[at++]=3;
 field("broker.local",32);field("1883",4);field(user,32);field(password,64);field(topic,64);
 EEPROM.bytes[at]=0xa7;EEPROM.bytes[504]=0xb5;for(unsigned i=0;i<6;++i)EEPROM.bytes[505+i]=i+2;
}
int main(){
 EEPROM.bytes.fill(0xff);EEPROM.commitOk=true;
 {Probe p(false);assert(strlen(p.getSsid())==0&&strlen(p.getPassword())==0);}
 legacy();const auto original=EEPROM.bytes;
 {Probe p;assert(p.settings->writesEnabled);
  assert(p.getIdx()==name&&p.getMqttUser()==user&&p.getMqttPassword()==password&&p.getMqttTopic()==topic);
  Beca b{&p};assert(b.discoveryId("_climate")==String(name+"_climate"));
  for(unsigned i=0;i<640;++i)assert(EEPROM.bytes[i]==original[i]);
  p.settingsOld->setByte("app-marker",0);assert(p.settingsOld->getByte("app-marker")==0xa7);
  p.settings->setByte("app-marker",p.settingsOld->getByte("app-marker"));p.settings->save();
  assert(p.bssidLocked&&p.bssid[0]==2&&!strcmp(p.getPassword(),"wifi-password"));
 }
 {Probe p;assert(p.settingsOld==nullptr);p.settings->setByte("app-marker",0);
  assert(p.settings->getByte("app-marker")==0xa7&&p.getIdx()==name&&p.getMqttPassword()==password&&p.getMqttTopic()==topic);
  Beca b{&p};assert(b.discoveryId("_climate")==String(name+"_climate"));}
 legacy();const auto failed=EEPROM.bytes;EEPROM.commitOk=false;
 {Probe p;assert(!p.settings->writesEnabled&&p.getIdx()==name&&p.getMqttPassword()==password);
  p.settings->setByte(PROP_NETBITS1,0);p.settings->save();
  for(unsigned i=0;i<640;++i)assert(EEPROM.bytes[i]==failed[i]);}
 EEPROM.commitOk=true;{Probe p;assert(p.settings->writesEnabled&&p.getIdx()==name&&p.getMqttPassword()==password);}
 puts("PASS actual legacy loader, app offset, identity, full MQTT credentials, BSSID and failed-migration write guard");
}
'''
        self.compile_run(source, 'network_string_migration')
