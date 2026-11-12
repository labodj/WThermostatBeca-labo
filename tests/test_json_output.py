"""JSON formatting and container boundaries."""
import unittest
import native_support as native


class JsonOutputTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_empty_and_nested_json_containers_keep_separators(self):
        self.compile_run(r'''
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WJson.h"
struct Sink:Print{std::string text;size_t write(uint8_t c)override{text+=char(c);return 1;}};
int main(){
 {Sink s;WJson j(&s);j.beginObject();j.beginArray("items");j.endArray();j.propertyInteger("count",0);j.endObject();assert(s.text=="{\"items\":[],\"count\":0}");}
 {Sink s;WJson j(&s);j.beginArray();j.beginArray();j.endArray();j.beginObject();j.endObject();j.numberInteger(1);j.endArray();assert(s.text=="[[],{},1]");}
 {Sink s;WJson j(&s);j.beginObject();j.beginArray("items");j.beginArray();j.endArray();j.endArray();j.beginObject("next");j.endObject();j.propertyBoolean("ok",true);j.endObject();assert(s.text=="{\"items\":[[]],\"next\":{},\"ok\":true}");}
 {Sink s;WJson j(&s);j.beginArray();j.endArray();assert(s.text=="[]");}
}
''', 'empty_json_containers')

    def test_json_keeps_signed_longs_and_full_unsigned_range(self):
        source = r'''
#include "Arduino.h"
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WJson.h"
#include "lib/WAdapter/WAdapter/WStringStream.h"
int main(){
 WStringStream stream(512);
 for(long value:{LONG_MIN,-2147483647L-1,-1L,0L,2147483647L,LONG_MAX}){
  stream.flush();WJson json(&stream);json.beginObject();json.propertyLong("value",value);json.endObject();
  assert(String(stream.c_str())==String("{\"value\":")+String(value)+"}");
 }
 for(unsigned long value:{0UL,2147483648UL,4294967295UL,ULONG_MAX}){
  stream.flush();WJson json(&stream);json.beginObject();json.propertyUnsignedLong("value",value);json.endObject();
  assert(String(stream.c_str())==String("{\"value\":")+String(value)+"}");
 }
 puts("PASS JSON signed LONG_MIN/-1/LONG_MAX and unsigned full range");}
'''
        self.compile_run(source, 'json_signed_long')
