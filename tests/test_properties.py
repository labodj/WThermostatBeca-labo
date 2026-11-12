"""Property validation, read callbacks and aliased string updates."""
import unittest
import native_support as native


class PropertiesTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_level_bounds_through_base_class_and_updated_limits(self):
        self.compile_run(r'''
#include "properties.h"
#include "lib/WAdapter/WAdapter/WLevelProperty.h"
#include "lib/WAdapter/WAdapter/WLevelIntProperty.h"
int main(){WLevelProperty d("d","D",-10,20);WLevelIntProperty i("i","I",-10,20);
 for(WProperty*p:{static_cast<WProperty*>(&d),static_cast<WProperty*>(&i)}){
  assert(p->parse("-10")&&p->parse("20"));assert(!p->parse("-11")&&!p->parse("21"));
  assert(!p->parse("nan")&&!p->parse("inf")&&!p->parse("junk"));
  p->setReadOnly(true);assert(p->isValidValue("10")&&!p->parse("10"));p->setReadOnly(false);
 }
 assert(d.parse("1.5")&&!i.parse("1.5"));d.setMultipleOf(0.5);assert(!d.parse("1.1"));
 d.setMinimum(0);d.setMaximum(10);i.setMinimum(0);i.setMaximum(10);
 assert(!d.parse("-1")&&!d.parse("11")&&!i.parse("-1")&&!i.parse("11"));
 assert(d.parse("0")&&d.parse("10")&&i.parse("0")&&i.parse("10"));}
''', 'level_bounds')

    def test_serialization_requests_each_value_once(self):
        self.compile_run(r'''
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WProperty.h"
#include "lib/WAdapter/WAdapter/WStringStream.h"
int main(){for(auto type:{BOOLEAN,DOUBLE,INTEGER,LONG,UNSIGNED_LONG,BYTE,STRING}){
 WProperty p("p","P",type);unsigned calls=0;
 p.setOnValueRequest([&](WProperty*v){++calls;switch(type){
 case BOOLEAN:v->setBoolean(true);break;case DOUBLE:v->setDouble(1.5);break;
 case INTEGER:v->setInteger(2);break;case LONG:v->setLong(-3);break;
 case UNSIGNED_LONG:v->setUnsignedLong(4);break;case BYTE:v->setByte(5);break;
 case STRING:v->setString("value");break;}});
 WStringStream out(128);WJson json(&out);json.beginObject();p.toJsonValue(&json);json.endObject();assert(calls==1);
 const char*expected[]={"{\"p\":true}","{\"p\":1.500000}","{\"p\":2}","{\"p\":-3}","{\"p\":4}","{\"p\":5}","{\"p\":\"value\"}"};
 if(type!=DOUBLE)assert(!strcmp(out.c_str(),expected[type]));
}}
''', 'single_value_request')

    def test_recursive_and_mutual_reads_are_bounded_and_rearm(self):
        self.compile_run(r'''
#include "properties.h"
int main(){WProperty a("a","A",INTEGER),b("b","B",INTEGER);a.setInteger(1);b.setInteger(2);
 unsigned first=0,second=0;
 a.setOnValueRequest([&](WProperty*p){assert(++first<=2);assert(p->getInteger()==1);b.getInteger();});
 b.setOnValueRequest([&](WProperty*p){assert(++second<=2);assert(p->getInteger()==2);a.getInteger();});
 assert(a.getInteger()==1&&first==1&&second==1);assert(a.getInteger()==1&&first==2&&second==2);
}
''', 'recursive_value_requests')

    def test_string_setter_accepts_overlapping_input(self):
        self.compile_run(r'''
#include "properties.h"
int main(){WProperty p("p","P",STRING,6);unsigned changes=0;p.setOnChange([&](WProperty*){++changes;});
 p.setString("abcdef");p.setString(p.c_str()+1);assert(!strcmp(p.c_str(),"bcdef")&&changes==2);
 p.setString(p.c_str());assert(changes==2);p.setString(p.c_str()+5);assert(!strcmp(p.c_str(),"")&&changes==3);
 p.setString(nullptr);assert(p.isNull());p.setString("123456789");assert(!strcmp(p.c_str(),"123456"));}
''', 'overlapping_property_string')
