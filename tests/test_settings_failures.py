"""Actual settings and HTTP save handlers must report failed writes accurately."""
import unittest
import native_support as native
from native_support import NETWORK, method, ROOT
import native_support as regressions


class SettingsFailureTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_batch_rollback_and_http_failure_without_reboot(self):
        source = (
            r"""
#include "Arduino.h"
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WProperty.h"
#include "lib/WAdapter/WAdapter/WStringProperty.h"
#include "lib/WAdapter/WAdapter/WSettings.h"
const char* CT_TEXT_PLAIN="text/plain";
struct AsyncWebServerRequest{int status=0;bool isSent(){return status!=0;}void send(int code,const char*=nullptr,const char*=nullptr){status=code;}};
struct WDevice{
 WSettings* settings;bool reject=false,reboot=true;
 const char*getId(){return "probe";}
 bool isConfigNeedsReboot(){return reboot;}
 bool isMainDevice(){return false;}
 void saveConfigPage(AsyncWebServerRequest* r){settings->setByte("byte",10);settings->setString("text","changed");if(reject)r->send(400);}
};
struct Probe{
 Print output;WLog log{0,0,&output};WLog*wlog=&log;WSettings store{&log,0xf1,false};WSettings*settings=&store;
 bool restarted=false;bool isWebServerRunning(){return true;}
 void sendMqttHassAutodiscover(bool){}
 void restart(AsyncWebServerRequest*,const __FlashStringHelper*){restarted=true;}
 void webReturnStatusPage(AsyncWebServerRequest*r,const __FlashStringHelper*,const char*){r->send(200);}
 Probe(){store.reallyReadSettings=false;store.setByte("byte",7);store.setString("text","original");assert(store.save());}
""".replace("const char*=", "const char* =")
            + method(NETWORK, "handleHttpSaveDeviceConfiguration")
            + r"""
};
int main(){
 EEPROM.bytes.fill(0xff);Probe p;WDevice device{p.settings};const auto before=EEPROM.bytes;unsigned commits=EEPROM.commits;
 EEPROM.failCommits=1;AsyncWebServerRequest failed;p.handleHttpSaveDeviceConfiguration(&failed,&device);
 assert(failed.status==500&&!p.restarted&&EEPROM.bytes==before&&EEPROM.commits==commits+1);
 assert(p.store.getByte("byte")==7&&!strcmp(p.store.getString("text"),"original"));
 assert(!p.store.writesEnabled&&!p.store.beginUpdate());
 p.store.writesEnabled=true; // Explicitly rearm the next independent fault scenario.
 device.reject=true;AsyncWebServerRequest invalid;p.handleHttpSaveDeviceConfiguration(&invalid,&device);
 assert(invalid.status==400&&!p.restarted&&EEPROM.bytes==before&&EEPROM.commits==commits+1);
 assert(p.store.getByte("byte")==7&&!strcmp(p.store.getString("text"),"original"));
 device.reject=false;AsyncWebServerRequest good;p.handleHttpSaveDeviceConfiguration(&good,&device);
 assert(!good.status&&p.restarted&&p.store.getByte("byte")==10&&EEPROM.commits==commits+2);
 p.store.writesEnabled=false;AsyncWebServerRequest disabled;p.restarted=false;p.handleHttpSaveDeviceConfiguration(&disabled,&device);
 assert(disabled.status==503&&!p.restarted);
 p.store.writesEnabled=true;
 assert(p.store.beginUpdate());p.store.setString("text","cancelled");assert(!p.store.endUpdate(false));
 assert(!strcmp(p.store.getString("text"),"changed"));
 EEPROM.failCommits=1;p.store.reallyReadSettings=false;p.store.setByte("new",42);assert(!p.store.save());
 assert(!p.store.writesEnabled&&!p.store.save());
 assert(p.store.beginUpdate(true)&&p.store.endUpdate()&&p.store.writesEnabled);
 puts("PASS one-commit application saves, rollback, validation errors, migration guard, explicit save failures and no hidden retry");
}
"""
        )
        self.compile_run(source, "settings_failures")

    def test_legacy_autosave_waits_for_complete_layout(self):
        source = r"""
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WStringProperty.h"
#include "lib/WAdapter/WAdapter/WSettings.h"
int main(){
 EEPROM.bytes.fill(0xa5);EEPROM.bytes[0]=STORED_FLAG_OLD;const auto legacy=EEPROM.bytes;
 Print output;WLog log(0,0,&output);WSettings store(&log,0xf1,true);store.reallyReadSettings=false;
 store.setString("name",16,"room");store.setByte("flags",3);store.setByte("flags",7);
 assert(EEPROM.bytes==legacy);assert(store.save());const auto migrated=EEPROM.bytes;
 store.setByte("flags",11);assert(EEPROM.bytes[18]==11);
 for(unsigned i=0;i<EEPROM.bytes.size();++i)if(i!=18)assert(EEPROM.bytes[i]==migrated[i]);
 puts("PASS legacy autosaves deferred until canonical layout is saved, then normal autosaves resume");
}
"""
        self.compile_run(source, "migration_autosave")

    def test_logging_filters_follow_rolled_back_storage(self):
        from native_support import ROOT

        device = ROOT / "WThermostat/WLogDevice.h"
        text = device.read_text()
        modes = text[
            text.index("const char* LOG_MODE_SILENT") : text.index(
                "const char* URI_WSLOG"
            )
        ]
        callbacks = text[
            text.index("        // Follow stored bytes too") : text.index(
                "\n\t\t// Pages"
            )
        ]
        source = (
            r"""
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WStringProperty.h"
#include "lib/WAdapter/WAdapter/WSettings.h"
"""
            + modes
            + r"""
struct Net{Print output;WLog logger{0,0,&output};WLog*log(){return &logger;}};
struct Probe{
 Net net;Net*network=&net;WSettings settings{net.log(),0xf1,false};
 WProperty*logLevelByte,*logLevelWebByte;
 WProperty mqtt{"mqtt","MQTT",STRING,8},web{"web","Web",STRING,8};
 WProperty*logLevel=&mqtt,*logLevelWeb=&web;
 Probe(){settings.reallyReadSettings=false;logLevelByte=settings.setByte("mqtt",0);logLevelWebByte=settings.setByte("web",0);assert(settings.save());
  mqtt.setString("silent");web.setString("silent");
  mqtt.setOnChange([this](WProperty*p){onlogLevelMqttChange(p);});web.setOnChange([this](WProperty*p){onlogLevelWebChange(p);});
"""
            + callbacks
            + "\n}\n"
        )
        for name in [
            "getlogLevelByte",
            "getlogLevelWebByte",
            "setlogLevelByte",
            "setlogLevelWebByte",
            "setMinLogLevel",
            "onlogLevelMqttChange",
            "onlogLevelWebChange",
            "setlogLevelMqtt",
            "setlogLevelWeb",
            "logLevelByteToString",
        ]:
            source += method(device, name) + "\n"
        source += r"""
};
int main(){
 EEPROM.bytes.fill(0xff);Probe p;const auto saved=EEPROM.bytes;
 for(byte mqtt=1;mqtt<=6;++mqtt)for(byte web=0;web<=6;++web){
  assert(p.settings.beginUpdate(true));p.setlogLevelByte(mqtt);p.setlogLevelWebByte(web);
  assert(p.getlogLevelByte()==mqtt&&p.getlogLevelWebByte()==web&&p.net.logger.isEnabled(std::max(mqtt,web)));
  EEPROM.failCommits=1;assert(!p.settings.endUpdate());assert(EEPROM.bytes==saved);
  assert(p.getlogLevelByte()==0&&p.getlogLevelWebByte()==0&&p.mqtt.equalsString("silent")&&p.web.equalsString("silent"));
  assert(!p.net.logger.isEnabled(1));
 }
 puts("PASS failed logging saves restore stored levels, public properties and active filters without recursion");
}
"""
        self.compile_run(source, "logging_rollback")

    def test_transaction_registration_is_rejected_without_changing_storage(self):
        self.compile_run(r'''
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WStringProperty.h"
#include "lib/WAdapter/WAdapter/WSettings.h"
int main(){
 EEPROM.bytes.fill(0xff);Print output;WLog log(0,0,&output);WSettings store(&log,0xf1,false);
 store.reallyReadSettings=false;store.setByte("existing",1);assert(store.save());const auto before=EEPROM.bytes;
 for(bool commit:{false,true}){
  assert(store.beginUpdate());assert(store.setByte("existing",2));
  assert(!store.setBoolean("boolean",true));assert(!store.setByte("byte",2));
  assert(!store.setInteger("integer",3));assert(!store.setLong("long",4));
  assert(!store.setUnsignedLong("unsigned",5));assert(!store.setDouble("double",6));
  assert(!store.setString("string","text"));assert(!store.setString("sized",8,"text"));
  WProperty external("external","External",BYTE);store.add(&external);assert(!store.existsSetting("external"));
  assert(store.endUpdate(commit)==commit);assert(store.getByte("existing")==byte(commit?2:1));
  if(!commit)assert(EEPROM.bytes==before);
 }
 assert(store.setByte("new",3));assert(store.save());
}
''', 'fixed_transaction_layout')

    def test_logging_levels_and_defaults_remain_compatible(self):
        log_device = ROOT / "WThermostat/WLogDevice.h"
        text = log_device.read_text()
        levels = "\n".join(line for line in (ROOT / "lib/WAdapter/WAdapter/WLog.h").read_text().splitlines()
                           if line.startswith("#define LOG_LEVEL_"))
        modes = text[text.index("const char* LOG_MODE_SILENT"):text.index("const char* URI_WSLOG")]
        source = '#include "properties.h"\n' + levels + "\n" + modes + r'''
struct Log{int level=0;void setLevelNetwork(int value){level=value;}};
struct Net{Log output;Log*log(){return &output;}};
struct Probe{
    int mqtt=0,web=0;Net net;Net*network=&net;
    void setlogLevelByte(byte value){mqtt=value;}
    void setlogLevelWebByte(byte value){web=value;}
    byte getlogLevelByte(){return mqtt;}
    byte getlogLevelWebByte(){return web;}
'''
        for name in ["setMinLogLevel", "onlogLevelMqttChange", "onlogLevelWebChange", "logLevelByteToString"]:
            source += regressions.method(log_device, name) + "\n"
        source += r'''
};
int main(){
    Probe p;WProperty mode("mode","Mode",STRING);
    const char* modes[]={"silent","fatal","error","warning","notice","trace","verbose"};
    for(unsigned i=0;i<7;++i){
        mode.setString(modes[i]);p.onlogLevelMqttChange(&mode);p.onlogLevelWebChange(&mode);
        assert(p.mqtt==int(i)&&p.web==int(i)&&!strcmp(p.logLevelByteToString(i),modes[i]));
    }
    mode.setString("invalid");p.onlogLevelMqttChange(&mode);p.onlogLevelWebChange(&mode);
    assert(p.mqtt==0&&p.web==0&&!strcmp(p.logLevelByteToString(255),"silent"));
    p.mqtt=2;p.web=6;p.setMinLogLevel();assert(p.net.output.level==6);
    p.mqtt=5;p.web=1;p.setMinLogLevel();assert(p.net.output.level==5);
    puts("PASS all log levels, channel routing and silent defaults");
}
'''
        self.compile_run(source, "maintenance_logging")
