"""The optional admin gate preserves legacy defaults and EEPROM layout."""
import unittest

import test_regressions as native
from test_regressions import NETWORK, method


class OptionalAuthTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_legacy_flags_default_to_auth_and_opt_out_survives_reload(self):
        source = r'''
#include "properties.h"
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WStringProperty.h"
#include "lib/WAdapter/WAdapter/WSettings.h"
'''
        text = NETWORK.read_text()
        source += text[text.index('const byte NETBITS1_MQTT'):text.index('\n#ifdef DEBUG', text.index('const byte NETBITS1_MQTT'))]
        source += 'struct Probe{WSettings*settings;const char*getPassword(){return "test-pass";}\n'+method(NETWORK, 'isAuthenticationRequired')+'\n};\n'
        source += r'''
int main(){
 Print output;WLog log(0,0,&output);
 for(unsigned flags=0;flags<32;++flags){
  EEPROM.bytes.fill(0xa5);EEPROM.bytes[0]=FLAG_OPTIONS_NETWORK_V3;EEPROM.bytes[1]=0xf1;EEPROM.bytes[2]=flags;
  const auto before=EEPROM.bytes;
  {WSettings settings(&log,0xf1,false);settings.setByte(PROP_NETBITS1,0);Probe p{&settings};assert(p.isAuthenticationRequired());
   assert(EEPROM.bytes==before);settings.setByte(PROP_NETBITS1,flags|NETBITS1_AUTH_DISABLED);settings.save();
   assert(!p.isAuthenticationRequired());
   for(unsigned i=0;i<EEPROM.bytes.size();++i)assert(EEPROM.bytes[i]==(i==2?(flags|NETBITS1_AUTH_DISABLED):before[i]));}
  {WSettings loaded(&log,0xf1,false);loaded.setByte(PROP_NETBITS1,0);Probe p{&loaded};assert(!p.isAuthenticationRequired());
   assert(loaded.getByte(PROP_NETBITS1)==(flags|NETBITS1_AUTH_DISABLED));loaded.setByte(PROP_NETBITS1,flags);loaded.save();assert(p.isAuthenticationRequired());}
  assert(EEPROM.bytes==before);
 }
 puts("PASS all legacy network flag combinations, opt-out persistence and unchanged surrounding EEPROM");
}
'''
        self.compile_run(source, 'optional_auth_storage')

    def test_login_checkbox_defaults_checked_and_explains_effect(self):
        from render_ui import render_pages
        from test_ui_rendering import Document
        page = render_pages()['/wifi']
        fields = {attrs.get('name'): attrs for _, attrs, _ in Document(page).fields}
        self.assertEqual('checkbox', fields['authRequired']['type'])
        self.assertIn('checked', fields['authRequired'])
        self.assertEqual('1', fields['authModePresent']['value'])
        self.assertIn('anyone who can reach this device', page)
        self.assertIn('upload firmware', page)
