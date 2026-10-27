#include "properties.h"
#include "Stream.h"
#include "lib/WAdapter/WAdapter/WStringProperty.h"
#include "lib/WAdapter/WAdapter/WSettings.h"
int main(){
    EEPROM.bytes.fill(0xff);EEPROM.bytes[0]=0x66;EEPROM.bytes[1]=0xf1;
    memcpy(EEPROM.bytes.data()+2,"existing-room",14);
    EEPROM.bytes[18]=0xa5;EEPROM.bytes[19]=0xf4;EEPROM.bytes[20]=0xff;
    const auto original=EEPROM.bytes;
    Print output;WLog log(0,0,&output);
    {
        WSettings settings(&log,0xf1,false);
        settings.setString("name",16,"");auto*bits=settings.setByte("bits",0);
        settings.setInteger("integer",0);
        assert(!strcmp(settings.getString("name"),"existing-room"));
        assert(bits->getByte()==0xa5&&settings.getInteger("integer")==-12);
        assert(EEPROM.bytes==original);
        bits->setByte(0xb5);
        for(size_t i=0;i<EEPROM.bytes.size();++i)assert(EEPROM.bytes[i]==(i==18?0xb5:original[i]));
    }
    {
        WSettings loaded(&log,0xf1,false);
        loaded.setString("name",16,"");loaded.setByte("bits",0);loaded.setInteger("integer",0);
        assert(!strcmp(loaded.getString("name"),"existing-room"));
        assert(loaded.getByte("bits")==0xb5&&loaded.getInteger("integer")==-12);
        loaded.save();
        for(size_t i=0;i<EEPROM.bytes.size();++i)assert(EEPROM.bytes[i]==(i==18?0xb5:original[i]));
    }
    puts("PASS EEPROM layout/read/write/reload and settings cleanup");
}
