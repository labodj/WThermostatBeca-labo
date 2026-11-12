"""Schedule validation, day groups and period selection."""
import unittest
from native_support import BECA, method
import native_support as native


class SchedulesTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_schedules_serial_and_persistence(self):
        source = r'''
#include "properties.h"
const char SCHEDULES_PERIODS[]="123456", SCHEDULES_DAYS[]="wau";
const char* SCHEDULES_MODE_OFF="off",*SCHEDULES_MODE_AUTO="auto";
const int MODEL_BAC_002_ALW=1;
const byte BECABITS1_SWITCHBACKOFF=16;
const unsigned char COMMAND_START[]={0x55,0xaa};
struct Clock {
    byte day=0; unsigned minute=0;
    byte getWeekDay(){return day;} bool isValidTime(){return true;}
    bool isTimeEarlierThan(byte h,byte m){return minute<h*60U+m;}
    bool isTimeLaterThan(byte h,byte m){return minute>=h*60U+m;}
    bool isTimeBetween(byte h,byte m,byte hh,byte mm){return isTimeLaterThan(h,m)&&isTimeEarlierThan(hh,mm);}
};
struct Log{template<class...T>void notice(T...){}};
struct Net{Log value;Log*log(){return &value;}};
struct Probe {
    byte schedules[54]{};
    bool schedulesChanged=false;
    byte offset=0,model=0;
    float factor=2;
    int currentSchedulePeriod=-1,receiveIndex=-1,commandLength=-1,frames=0;
    unsigned char receivedCommand[1024];
    unsigned long lastSerialByte=0,lastMcuReceived=0;
    Clock clock;Clock*wClock=&clock;Net net;Net*network=&net;
    WProperty autoBack{"auto","Auto",BOOLEAN},mode{"mode","Mode",STRING},bits{"bits","Bits",BYTE};
    WProperty*switchBackToAuto=&autoBack,*schedulesMode=&mode,*becaBits1=&bits;
    bool receivedSchedules(){return true;}
    byte getSchedulesDayOffset(){return offset;}
    byte getThermostatModel(){return model;}
    float getTemperatureFactor(){return factor;}
    void updateTargetTemperature(){}
    void resetAll(){receiveIndex=-1;commandLength=-1;}
    void processSerialCommand(unsigned long){++frames;}
'''
        for name in ["getSchedulesPeriod", "getSchedulesStartAddress", "getSchedulesValue",
                     "validSchedulesKeyValue", "validSchedulesOrder", "processSchedulesKeyValue",
                     "updateCurrentSchedulePeriod", "saveSettings", "serviceSerial"]:
            source += method(BECA, name) + "\n"
        source += r'''
};
int main(){
    Probe p; p.mode.setString("auto"); p.autoBack.setBoolean(false);
    for(unsigned d=0;d<3;++d)for(unsigned n=0;n<6;++n){p.schedules[d*18+n*3+1]=n+1;p.schedules[d*18+n*3+2]=40;}
    for(unsigned day=0;day<7;++day)for(unsigned offset=0;offset<7;++offset){
        p.clock.day=day;p.offset=offset;p.clock.minute=0;p.updateCurrentSchedulePeriod();
        unsigned previous=(day+offset+6)%7;
        assert(p.currentSchedulePeriod==(previous==0?36:previous==6?18:0)+15);
    }
    const auto before=p.schedules[2];
    for(const char* key:{"w7t","x1t","w1x","","w1","w11t"})assert(!p.processSchedulesKeyValue(key,"20"));
    assert(p.schedules[2]==before);
    assert(!p.processSchedulesKeyValue("w1h","99:99"));assert(!p.processSchedulesKeyValue("w1h","-1:00"));
    assert(!p.processSchedulesKeyValue("w1h","aa:bb"));assert(!p.processSchedulesKeyValue("w1t","garbage"));
    assert(!p.processSchedulesKeyValue("w1t","nan"));assert(!p.processSchedulesKeyValue("w1t","999"));
    assert(p.processSchedulesKeyValue("w1h","0:30"));assert(p.processSchedulesKeyValue("w1t","20.5"));
    assert(p.schedules[0]==30&&p.schedules[1]==0&&p.schedules[2]==41);
    assert(p.validSchedulesOrder());assert(!p.processSchedulesKeyValue("w1t","20.1"));
    p.factor=1;p.schedules[2]=21;assert(p.getSchedulesValue("w1t").toDouble()==21);
    unsigned saves=0;p.bits.setByte(0xa5);p.bits.setSettingsNotification([&](WProperty*){++saves;});
    p.autoBack.setBoolean(false);p.saveSettings(nullptr);assert(p.bits.getByte()==0xb5);
    p.autoBack.setBoolean(true);p.saveSettings(nullptr);assert(p.bits.getByte()==0xa5&&saves==2);
    // Oversize, bad checksum, partial frame timeout, resynchronization and bursts.
    Serial.input={0x55,0xaa,0,7,0xff,0xff};Serial.input.resize(1100,0);Serial.position=0;p.serviceSerial(1);assert(p.frames==0);
    Serial.input={0x55,0xaa,0,3,0,0,2};Serial.position=0;p.serviceSerial(2);assert(p.frames==1);
    Serial.input={0x55,0xaa,0,3,0,0,99};Serial.position=0;p.serviceSerial(3);assert(p.frames==1);
    Serial.input={0x55,0xaa,0,3,0};Serial.position=0;p.serviceSerial(4);
    Serial.input={0x55,0x55,0xaa,0,3,0,0,2};Serial.position=0;p.serviceSerial(2000);assert(p.frames==2);
    Serial.input={0x55,0xaa,0,3,0,0,2,0x55,0xaa,0,3,0,0,2};Serial.position=0;p.serviceSerial(2001);assert(p.frames==4);
    puts("PASS schedule matrix, input validation, precision, persistence and UART recovery");
}
'''
        self.compile_run(source, "schedules")

    def test_schedule_groups_preserve_default_for_all_byte_values(self):
        source = r'''
#include "Arduino.h"
#include <map>
struct WJson{std::map<std::string,String>strings;std::map<std::string,double>numbers;
 void propertyString(const char*k,const char*v){strings[k]=v;}void propertyDouble(const char*k,double v){numbers[k]=v;}};
const char SCHEDULES_DAYS[]="wau",SCHEDULES_PERIODS[]="123456";
struct Probe{byte schedules[54]{};double getTemperatureFactor(){return 2;}
'''+method(BECA, 'toJsonSchedules')+r'''
};
int main(){
    Probe p;
    for(unsigned day=0;day<3;++day)for(unsigned n=0;n<6;++n){unsigned i=day*18+n*3;p.schedules[i]=n*10;p.schedules[i+1]=day*6+n;p.schedules[i+2]=40+day+n;}
    for(unsigned group=0;group<256;++group){
        WJson json;p.toJsonSchedules(&json,group);assert(json.strings.size()==6&&json.numbers.size()==6);
        const unsigned day=group==1?1:group==2?2:0;
        for(unsigned n=0;n<6;++n){
            char key[]={SCHEDULES_DAYS[day],static_cast<char>('1'+n),'h','\0'},time[6];
            snprintf(time,sizeof(time),"%02u:%02u",day*6+n,n*10);
            assert(json.strings.at(key)==time);key[2]='t';assert(json.numbers.at(key)==(40+day+n)/2.0);
        }
    }
    puts("PASS all 256 schedule groups retain their legacy field names and values");
}
'''
        self.compile_run(source, 'medium_schedule_groups')
