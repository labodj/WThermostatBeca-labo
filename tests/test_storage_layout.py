"""EEPROM layout, version flags and stored value compatibility."""
import unittest
from native_support import BECA, NETWORK, enum_definition
import native_support as native


class StorageLayoutTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_eeprom_layout_and_roundtrip(self):
        self.compile_run(None, "settings")

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
