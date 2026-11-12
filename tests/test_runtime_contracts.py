"""Core stream, value, pin and object-lifetime contracts."""
import unittest
import native_support as native


class RuntimeContractsTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_publish_eeprom_stream_and_color(self):
        self.compile_run(None, "value_contracts")

    def test_callback_ownership_and_replacement_boundaries(self):
        self.compile_run(None, "lifetime_contracts")

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

    def test_led_initial_blink_and_virtual_device_destruction(self):
        source = r'''
#include "Arduino.h"
#include "Stream.h"
#include <type_traits>
#include "lib/WAdapter/WAdapter/WJson.h"
enum{INPUT,OUTPUT,INPUT_PULLUP,HIGH,LOW};int output=-1;
void pinMode(int,int){}void digitalWrite(int,int value){output=value;}
class AsyncWebServerRequest;class AsyncResponseStream;class AsyncWebServer;
#include "lib/WAdapter/WAdapter/WDevice.h"
static_assert(!std::is_copy_constructible<WDevice>::value&&!std::is_copy_assignable<WDevice>::value);
int main(){
 WProperty on("on","On",BOOLEAN);on.setBoolean(true);WLed led(4);led.setProperty(&on);
 assert(output==LOW);led.setOn(true,100);led.loop(1);assert(output==LOW);led.loop(102);assert(output==HIGH);
 bool destroyed=false;struct Device:WDevice{bool&flag;Device(bool&f):WDevice(nullptr,"id","name","root","type"),flag(f){}~Device()override{flag=true;}};
 WDevice*device=new Device(destroyed);assert(!strcmp(device->getFullName(),"root_name"));delete device;assert(destroyed);
 puts("PASS initialized LED, ownership traits and virtual device destruction");
}
'''
        self.compile_run(source, 'device_led_ownership')

    def test_relay_reads_configured_pin_and_disabled_pin_is_inactive(self):
        self.compile_run(r'''
#include "properties.h"
enum{INPUT,OUTPUT,INPUT_PULLUP,LOW,HIGH};
int readPin=-1,level=HIGH,reads=0;
void pinMode(int,int){}void digitalWrite(int,int){}
int digitalRead(int pin){readPin=pin;++reads;return level;}
#include "lib/WAdapter/WAdapter/WRelay.h"
int main(){for(bool highIsOn:{false,true}){WRelay relay(4,highIsOn);
 for(int value:{LOW,HIGH}){level=value;bool on=relay.isOn();assert(readPin==4&&on==(value==(highIsOn?HIGH:LOW)));}}
 int before=reads;WRelay disabled(-1,true);assert(!disabled.isOn()&&reads==before);}
''', 'relay_pin')
