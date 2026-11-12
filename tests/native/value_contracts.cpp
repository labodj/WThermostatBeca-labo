#include "properties.h"
#include "lib/WAdapter/WAdapter/WStringStream.h"
#include "lib/WAdapter/WAdapter/WColorProperty.h"
#include "lib/WAdapter/WAdapter/WStringProperty.h"
#include "lib/WAdapter/WAdapter/WSettings.h"
#include "lib/WAdapter/WAdapter/WAdapterMqtt.h"

int main(int argc,char**argv){
    const std::string only=argc>1?argv[1]:"all";
    if(only=="all"||only=="mqtt"){
        Client client;client.data={0x20,2,0,0};WAdapterMqtt mqtt(false,client,64);
        assert(mqtt.connect("test"));const size_t sent=client.sent.size();
        assert(!mqtt.publish("x","a",UINT_MAX-7,false));assert(client.sent.size()==sent);
        const std::string payload(56,'a');assert(mqtt.publish("x",payload.c_str(),56,false));
        assert(!mqtt.publish("x",payload.c_str(),57,false));
    }
    if(only=="all"||only=="eeprom"){
        Print output;WLog log(0,0,&output);
        for(uint32_t bits:{0U,0x7fffffffU,0x80000000U,0xffffffffU,0x89abcdefU}){
            EEPROM.bytes.fill(0);EEPROM.bytes[0]=0x66;EEPROM.bytes[1]=0xf1;
            for(unsigned i=0;i<4;++i){EEPROM.bytes[2+i]=(bits>>(i*8))&255;EEPROM.bytes[6+i]=EEPROM.bytes[2+i];}
            const auto original=EEPROM.bytes;
            WSettings settings(&log,0xf1,false);
            const int64_t signedValue=bits<=INT32_MAX?int64_t(bits):int64_t(bits)-0x100000000LL;
            assert(settings.setLong("signed",0)->getLong()==signedValue);
            assert(settings.setUnsignedLong("unsigned",0)->getUnsignedLong()==bits);
            settings.save();assert(EEPROM.bytes==original);
        }
    }
    if(only=="all"||only=="stream"){
        WStringStream stream(8);assert(stream.available()==0);
        stream.write(0xff);stream.write(0x80);assert(stream.available()==2);
        assert(stream.peek()==255&&stream.read()==255);assert(stream.available()==1);
        assert(stream.peek()==128&&stream.read()==128);assert(stream.available()==0);
        assert(stream.peek()==-1&&stream.read()==-1);
    }
    if(only=="all"||only=="color"){
        WColorProperty color("color","Color",255,16,0);
        assert(!strcmp(color.c_str(),"#ff1000"));assert(color.getRed()==255&&color.getGreen()==16&&color.getBlue()==0);
        color.setRGB(0,0,0);assert(!strcmp(color.c_str(),"#000000"));
        WColorProperty black("black","Black",0,0,0);assert(!strcmp(black.c_str(),"#000000"));
        assert(color.parse("rgb(255,16,0)"));assert(!strcmp(color.c_str(),"#ff1000"));
        assert(color.parse("#80A0ff"));assert(color.getRed()==128&&color.getGreen()==160&&color.getBlue()==255);
        for(const char* bad:{"#gggggg","#123","rgb(256,0,0)","rgb(-1,0,0)","rgb(1,2)","rgb(1,2,3,4)","rgb(1,2,3)junk","rgb(999999999999999999999,0,0)"}){
            assert(!color.parse(bad));assert(!strcmp(color.c_str(),"#80A0ff"));
        }
        color.setReadOnly(true);assert(!color.parse("#000000"));color.setReadOnly(false);color.setRGB(0,0,0);
        const char* text=color.createRGBString();assert(!strcmp(text,"#000000"));delete[] text;
    }
    puts("PASS MQTT publish bounds, signed EEPROM, stream bytes and color lifetime");
}
