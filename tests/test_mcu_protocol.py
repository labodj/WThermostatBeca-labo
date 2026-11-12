"""MCU handshake, UART frames and model-specific status handling."""
import unittest
import native_support as regressions
from native_support import BECA, ROOT, method
import native_support as native


class McuProtocolTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_mcu_handshake_readiness_and_numeric_protocol(self):
        source = r"""
#include "properties.h"
#define STATE_COMPLETE 6
#define SECONDS_DIVIDER 1
struct Clock {
    bool valid=false;bool isValidTime(){return valid;}
    unsigned long getEpochTime(){return 1704067200;}unsigned long getEpochTimeLocal(){return getEpochTime();}
    byte getYear(unsigned long){return 24;}byte getMonth(unsigned long){return 1;}byte getDay(unsigned long){return 1;}
    byte getHours(unsigned long){return 12;}byte getMinutes(unsigned long){return 10;}byte getSeconds(unsigned long){return 30;}
};
struct Log{template<class...T>void notice(T...){}template<class...T>void warning(T...){}template<class...T>void trace(T...){}bool isEnabled(int){return false;}};
struct Net{Log value;Log*log(){return &value;}bool isDebug(){return false;}};
const int LOG_LEVEL_TRACE=5;
struct Probe{
    Net net;Net*network=&net;Clock clock;Clock*wClock=&clock;
    bool mcuInitialized=false,receivingDataFromMcu=false,receivedStates[STATE_COMPLETE]{};
    int mcuInitializeState=0;unsigned long lastMcuAttempt=0,lastMcuReceived=0,lastTimeSent=0;
    unsigned mcuRetryCount=0;
    bool timeIsRequested=false,timeIsRequestedLocaltime=false,timeIsRequestedSendZeroSecs=false;
    unsigned char receivedCommand[1024];double targetTemperatureManualMode=35;float factor=10;
    float getTemperatureFactor(){return factor;}byte getSchedulesDayOffset(){return 0;}byte getDayOfWeek(){return 1;}
    void updateTargetTemperature(){}void updateModeAndAction(){}
"""
        for name in ["getCommandAsString", "commandCharsToSerial", "queryAllDPs", "startMcuInitialize",
                     "mcuInitialize", "isDeviceStateComplete", "decodeMcuValue", "targetTemperatureManualModeToMcu",
                     "sendActualTimeToBecaRequested", "sendActualTimeToBeca"]:
            source += method(BECA, name) + "\n"
        source += r"""
};
int main(){
    Probe p;testMillis=1;p.startMcuInitialize();p.mcuInitialize();
    assert(p.mcuInitializeState==2&&Serial.output.size()==7);
    testMillis=2000;p.mcuInitialize();assert(Serial.output.size()==7);
    testMillis=4001;p.mcuInitialize();assert(Serial.output.size()==14);
    p.mcuInitializeState=5;p.mcuInitialize();assert(p.mcuInitializeState==6&&Serial.output.size()==21);
    p.mcuInitialized=true;p.lastMcuReceived=millis();assert(!p.isDeviceStateComplete());
    for(bool& state:p.receivedStates)state=true;
    assert(p.isDeviceStateComplete());testMillis+=60001;assert(!p.isDeviceStateComplete());
    p.startMcuInitialize();for(bool state:p.receivedStates)assert(!state);
    byte positive[]={0,0,0,128},negative[]={255,255,255,246},large[]={0,0,1,94};
    assert(p.decodeMcuValue(positive)==128);assert(p.decodeMcuValue(negative)==-10);assert(p.decodeMcuValue(large)==350);
    Serial.output.clear();p.targetTemperatureManualModeToMcu();assert(Serial.output.size()==15);
    assert(Serial.output[10]==0&&Serial.output[11]==0&&Serial.output[12]==1&&Serial.output[13]==94);
    byte checksum=0;for(unsigned i=0;i<14;++i)checksum+=Serial.output[i];assert(checksum==Serial.output[14]);
    Serial.output.clear();p.sendActualTimeToBeca(true);assert(Serial.output.empty()&&p.timeIsRequested);
    p.clock.valid=true;p.sendActualTimeToBeca(true);assert(Serial.output.size()==15&&Serial.output[3]==0x1c&&Serial.output[6]==1&&Serial.output[7]==24);
    assert(Serial.output[12]==30/SECONDS_DIVIDER);
    Serial.output.clear();p.sendActualTimeToBeca(false);assert(Serial.output[3]==0x0c&&Serial.output[12]==30);
    p.timeIsRequestedSendZeroSecs=true;Serial.output.clear();p.sendActualTimeToBeca(true);assert(Serial.output[12]==0);
    puts("PASS MCU retry/readiness, full-width signed values, setpoint encoding, checksum and deferred time");
}
"""
        self.compile_run(source, "mcu")
        self.compile_run(source.replace("#define SECONDS_DIVIDER 1", "#define SECONDS_DIVIDER 4"), "mcu_divisor4")

    def test_mcu_idle_and_unknown_initialization_states(self):
        source = r'''
#include "Arduino.h"
struct Log{template<class...T>void notice(T...){};};struct Net{Log value;Log*log(){return &value;}};
struct Probe{Net net;Net*network=&net;bool mcuInitialized=false,receivingDataFromMcu=false;
 unsigned mcuInitializeState=0,mcuRetryCount=0,commands=0,updates=0;unsigned long lastMcuAttempt=0;
 void commandCharsToSerial(int,const unsigned char*){++commands;}void queryAllDPs(){++commands;}
 void updateTargetTemperature(){++updates;}void updateModeAndAction(){++updates;}
'''+method(BECA, 'mcuInitialize')+r'''
};
int main(){
    for(unsigned state=0;state<256;++state){
        Probe p;p.mcuInitializeState=state;testMillis=0;p.mcuInitialize();
        assert(p.commands==((state==1||state==3||state==5)?1U:0U));
        const unsigned expected=state==1?2:state==3?5:state==5?6:state==7?0:state;
        assert(p.mcuInitializeState==expected&&p.mcuInitialized==(state==7)&&p.updates==(state==7?2U:0U));
    }
    puts("PASS idle, waiting, known and all unsupported MCU initialization states");
}
'''
        self.compile_run(source, 'medium_mcu_init')

    def test_unknown_mcu_values_preserve_protocol_behavior(self):
        source = r"""
#include "properties.h"
const int MODEL_BHT_002_GBLW=0,MODEL_BAC_002_ALW=1,STATE_COMPLETE=6;
const int LOG_LEVEL_NOTICE=1,LOG_LEVEL_TRACE=2,LOG_LEVEL_VERBOSE=3,LOG_LEVEL_WARNING=4;
const char* SYSTEM_MODE_COOL="cool",*SYSTEM_MODE_HEAT="heat",*SYSTEM_MODE_FAN="fan";
const char* FAN_MODE_AUTO="auto",*FAN_MODE_HIGH="high",*FAN_MODE_MEDIUM="medium",*FAN_MODE_LOW="low";
const char* SCHEDULES_MODE_OFF="off",*SCHEDULES_MODE_AUTO="auto";
struct Log{template<class...T>void trace(T...){}template<class...T>void notice(T...){}};
struct Net{Log logger;Log*log(){return &logger;}};
struct Probe{
 Net net;Net*network=&net;int commandLength=0,mcuInitializeState=0;
 bool mcuInitialized=false,receivingDataFromMcu=false,receivedStates[6]{};
 byte receivedCommand[1024]{},schedules[54]{},schedulesDataPoint=0;
 double targetTemperatureManualMode=21.5;unsigned long lastTimeRequested=0;
 unsigned unknown=0,notifications=0,commands=0;std::function<bool()>onConfigurationRequest,onPowerButtonOn;
 WProperty on{"on","",BOOLEAN},eco{"eco","",BOOLEAN},lock{"lock","",BOOLEAN},temp{"temp","",DOUBLE},floor{"floor","",DOUBLE},
   sys{"sys","",STRING},fan{"fan","",STRING},mode{"mode","",STRING},model{"model","",BYTE},id{"id","",STRING};
 WProperty*deviceOn=&on,*ecoMode=&eco,*locked=&lock,*actualTemperature=&temp,*actualFloorTemperature=&floor,
   *systemMode=&sys,*fanMode=&fan,*schedulesMode=&mode,*thermostatModel=&model,*mcuId=&id;
 Probe(){model.setByte(MODEL_BAC_002_ALW);sys.setString("heat");fan.setString("low");mode.setString("off");}
 void logIncomingCommand(const char*text,int){if(!strcmp(text,"unknown"))++unknown;}
 void notifyState(){++notifications;}void notifySchedules(){++notifications;}
 void updateTargetTemperature(){}void updateModeAndAction(){}void updateCurrentSchedulePeriod(){}void holdFromScheduler(){}
 void startMcuInitialize(){mcuInitialized=false;}void sendActualTimeToBecaRequested(bool){}
 void commandCharsToSerial(int,const unsigned char*){++commands;}
 double getTemperatureFactor(){return 2;}byte getThermostatModel(){return model.getByte();}
 void frame(byte type,byte dp,byte value){
  commandLength=type==7?5:1;receivedCommand[0]=0x55;receivedCommand[1]=0xaa;receivedCommand[2]=1;
  receivedCommand[3]=type;receivedCommand[4]=0;receivedCommand[5]=commandLength;receivedCommand[6]=dp;
  receivedCommand[8]=0;receivedCommand[9]=1;receivedCommand[10]=value;processSerialCommand(1000);
 }
"""
        for name in ['getSystemModeAsByte','getFanModeAsByte','decodeMcuValue','processSerialCommand']:
            source += method(BECA,name)+'\n'
        source += r"""
};
int main(){
 for(unsigned value=0;value<256;++value){
  Probe heartbeat;heartbeat.frame(0,value,0);assert(heartbeat.unknown==(value>1?1U:0U)&&!heartbeat.receivingDataFromMcu&&heartbeat.commands==0);
  Probe sys;sys.frame(7,0x66,value);const char*expected=value==0?"cool":value==1?"heat":value==2?"fan":"heat";
  assert(sys.sys.equalsString(expected)&&sys.unknown==0);
  Probe fan;fan.frame(7,0x67,value);expected=value==0?"auto":value==1?"high":value==2?"medium":"low";
  assert(fan.fan.equalsString(expected)&&fan.unknown==0);
  if((value>=1&&value<=6)||value==0x65||value==0x66||value==0x67||value==0x68)continue;
  Probe dp;dp.frame(7,value,1);assert(dp.unknown==1&&dp.notifications==0&&dp.commands==0);
  assert(dp.sys.equalsString("heat")&&dp.fan.equalsString("low")&&dp.targetTemperatureManualMode==21.5);
  for(bool received:dp.receivedStates)assert(!received);
 }
 puts("PASS all byte values for heartbeat, data points, system mode and fan mode preserve legacy behavior");
}
"""
        self.compile_run(source,'medium_mcu_protocol')

    def test_serial_index_bounds_and_temperature_precision(self):
        source = r'''
#include "properties.h"
const unsigned char COMMAND_START[]={0x55,0xaa};
struct Probe {
    unsigned char receivedCommand[1024]{};
    int receiveIndex=-1,commandLength=-1,handled=0;
    unsigned long lastSerialByte=0,lastMcuReceived=0;
    WProperty precision{"precision","Precision",DOUBLE};WProperty*temperaturePrecision=&precision;
    void processSerialCommand(unsigned long){++handled;}
'''
        for name in ["resetAll", "serviceSerial", "getTemperatureFactor", "getTemperaturePrecision", "decodeMcuValue"]:
            source += regressions.method(ROOT / "WThermostat/WBecaDevice.h", name) + "\n"
        source += r'''
};
int main(){
    for(int index:{INT_MIN,-2,-1,0,1022,1023,INT_MAX}){
        Probe p;p.receiveIndex=index;p.lastSerialByte=1;
        Serial.position=0;Serial.input={0x55,0x55,0xaa,0,0,0,0,0xff};p.serviceSerial(1);
        assert(p.handled==1&&p.receiveIndex==-1);
    }
    Probe p;
    for(double step:{0.1,0.5,1.0}){
        p.precision.setDouble(step);assert(p.getTemperaturePrecision()==step);
        assert(fabs(1.0/p.getTemperatureFactor()-step)<1e-14);
        const byte bytes[]={0x7f,0xff,0xff,0xff};
        assert(fabs(p.decodeMcuValue(bytes)/p.getTemperatureFactor()-double(INT32_MAX)*step)<1e-7);
    }
    puts("PASS serial index guard, resync and double temperature precision");
}
'''
        self.compile_run(source, "maintenance_serial")

    def test_state_enum(self):
        text = BECA.read_text()
        const = text[
            text.index("#define COUNT_DEVICE_MODELS") : text.index("//typedef")
        ]
        start = text.index("\t\tthis->state = nullptr;")
        end = text.index("\n\t\tthis->addProperty(state);", start) + len(
            "\n\t\tthis->addProperty(state);"
        )
        s = (
            r"""
        #include "Arduino.h"
        #include "Stream.h"
        #include "lib/WAdapter/WAdapter/WProperty.h"
        #include "lib/WAdapter/WAdapter/WStringStream.h"
        """
            + const
            + r"""
        struct Probe{WProperty*state=nullptr;int model;int getThermostatModel(){return model;}
         void addProperty(WProperty*){}void updateModeAndAction(){}
         Probe(int model):model(model){
        """
            + text[start:end]
            + r"""
         }~Probe(){delete state;}
        };
        int main(){for(int model:{MODEL_BHT_002_GBLW,MODEL_BAC_002_ALW}){
         Probe p(model);WStringStream stream(1024);WJson json(&stream);p.state->toJsonStructure(&json,"state","/things/thermostat");
         bool coolingListed=strstr(stream.c_str(),"\"cooling\"");
         printf("%s schema lists cooling=%d\n",model==MODEL_BAC_002_ALW?"BAC":"BHT",coolingListed);
         assert(coolingListed==(model==MODEL_BAC_002_ALW));
         }}
        """
        )
        self.compile_run(s, "state_enum")
