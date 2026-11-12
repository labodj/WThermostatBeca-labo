"""End-to-end property callbacks must send mode and requested setpoint to the MCU."""
import unittest
import native_support as native
from native_support import BECA, method


class TemperatureCommandTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def source(self):
        text = BECA.read_text()
        constants = text[text.index('#define COUNT_DEVICE_MODELS'):text.index('//typedef')]
        source = r'''
#include "properties.h"
#include "lib/WAdapter/WAdapter/WTargetTemperatureProperty.h"
#include <algorithm>
struct Log{template<class...T>void trace(T...){}template<class...T>void notice(T...){}template<class...T>void warning(T...){}bool isEnabled(int){return false;}};
struct Net{Log logger;Log*log(){return &logger;}bool isDebug(){return false;}};
struct Clock{bool valid=true;byte day=1;unsigned minute=120;bool isValidTime(){return valid;}byte getWeekDay(){return day;}
 bool isTimeEarlierThan(byte h,byte m){return minute<h*60U+m;}bool isTimeLaterThan(byte h,byte m){return minute>=h*60U+m;}
 bool isTimeBetween(byte h,byte m,byte hh,byte mm){return isTimeLaterThan(h,m)&&isTimeEarlierThan(hh,mm);}};
const int LOG_LEVEL_TRACE=5;
''' + constants + r'''
struct Probe{
 Net net;Net*network=&net;Clock clock;Clock*wClock=&clock;
 bool receivingDataFromMcu=false,schedulesReceived=true,relayHardware=false,coolingHardware=false;int model=MODEL_BHT_002_GBLW;
 double targetTemperatureManualMode=18,factor=2;
 int currentSchedulePeriod=0;byte schedules[54]{};unsigned char receivedCommand[1024]{};
 WTargetTemperatureProperty target{"targetTemperature","Target",5,35};
 WProperty actual{"temperature","Actual",DOUBLE},deadzone{"deadzone","Deadzone",BYTE},power{"power","Power",BOOLEAN},eco{"eco","Eco",BOOLEAN},
 schedule{"schedulesMode","Schedules",STRING},hold{"holdState","Hold",STRING},overall{"mode","Mode",STRING},
 outputState{"state","State",STRING},outputAction{"action","Action",STRING},sys{"systemMode","System",STRING},fan{"fanMode","Fan",STRING},back{"back","Back",BOOLEAN};
 WProperty*targetTemperature=&target,*actualTemperature=&actual,*deadzoneTemp=&deadzone,*deviceOn=&power,*ecoMode=&eco,
 *schedulesMode=&schedule,*holdState=&hold,*mode=&overall,*state=&outputState,*action=&outputAction,*systemMode=&sys,*fanMode=&fan,*switchBackToAuto=&back;
 byte getThermostatModel(){return model;}double getTemperatureFactor(){return factor;}
 bool isSupportingHeatingRelay(){return relayHardware;}bool isSupportingCoolingRelay(){return coolingHardware;}
 byte getSchedulesDayOffset(){return 0;}bool receivedSchedules(){return schedulesReceived;}
 Probe(){
  target.setMultipleOf(0.5);target.setDouble(20);actual.setDouble(21);deadzone.setByte(1);power.setBoolean(true);eco.setBoolean(false);
  schedule.setString(SCHEDULES_MODE_AUTO);hold.setString(HOLD_STATE_SCHEDULER);overall.setString(MODE_AUTO);
  outputState.setString(STATE_OFF);outputAction.setString(ACTION_IDLE);sys.setString(SYSTEM_MODE_HEAT);fan.setString(FAN_MODE_AUTO);back.setBoolean(false);
  for(unsigned day=0;day<3;++day)for(unsigned period=0;period<6;++period){unsigned i=day*18+period*3;schedules[i]=0;schedules[i+1]=period*4;schedules[i+2]=40;}
  target.setOnChange([this](WProperty*p){onChangeTargetTemperature(p);});
  schedule.setOnChange([this](WProperty*p){schedulesModeToMcu(p);});
  overall.setOnChange([this](WProperty*p){modeToMcu(p);});
  overall.setOnValueRequest([this](WProperty*){updateModeAndAction();});
  outputState.setOnValueRequest([this](WProperty*){updateModeAndAction();});
  power.setOnChange([this](WProperty*p){deviceOnToMcu(p);});
  hold.setOnChange([this](WProperty*p){holdStateToScheduleMode(p);});
  hold.setOnValueRequest([this](WProperty*p){holdStateRequest(p);});
  eco.setOnChange([this](WProperty*p){ecoModeToMcu(p);});
  sys.setOnChange([this](WProperty*p){systemModeToMcu(p);});
  actual.setOnChange([this](WProperty*p){onChangeActualTemperature(p);});
 }
'''
        for name in ['onChangeTargetTemperature', 'targetTemperatureManualModeToMcu', 'schedulesModeToMcu', 'updateTargetTemperature', 'updateRelaySimulation', 'updateModeAndAction', 'modeToMcu', 'holdStateToScheduleMode', 'holdStateRequest', 'holdFromScheduler', 'ecoModeToMcu', 'deviceOnToMcu', 'updateCurrentSchedulePeriod', 'validSchedulesOrder', 'onChangeActualTemperature', 'getCommandAsString', 'commandCharsToSerial', 'getSystemModeAsByte', 'systemModeToMcu']:
            source += method(BECA, name) + '\n'
        source += r'''
};
std::vector<std::vector<byte>> frames(){
 std::vector<std::vector<byte>> result;
 for(size_t p=0;p<Serial.output.size();){
  assert(Serial.output[p]==0x55&&Serial.output[p+1]==0xaa);
  unsigned length=Serial.output[p+4]*256U+Serial.output[p+5]+7;
  assert(p+length<=Serial.output.size());byte checksum=0;
  for(unsigned i=0;i<length-1;++i)checksum+=Serial.output[p+i];
  assert(checksum==Serial.output[p+length-1]);
  result.emplace_back(Serial.output.begin()+p,Serial.output.begin()+p+length);p+=length;
 }
 return result;
}
void expectSetpoint(const std::vector<byte>& frame,unsigned value){
 assert(frame.size()==15&&frame[6]==2&&frame[7]==2);
 assert(frame[10]==byte(value>>24)&&frame[11]==byte(value>>16)&&frame[12]==byte(value>>8)&&frame[13]==byte(value));
}
'''
        return source

    def test_auto_to_manual_keeps_requested_temperature_and_sends_both_frames(self):
        source = self.source() + r'''
int main(){
 for(bool validClock:{false,true})for(bool switchBack:{false,true})for(double factor:{1.0,2.0,10.0})for(double previousManual:{18.0,24.0}){
  Probe p;p.clock.valid=validClock;p.back.setBoolean(switchBack);p.factor=factor;
  p.target.setMultipleOf(1.0/factor);p.targetTemperatureManualMode=previousManual;
  for(unsigned i=2;i<54;i+=3)p.schedules[i]=20*factor;
  Serial.output.clear();assert(p.target.parse("24"));auto sent=frames();
  // Changing a local property must produce the physical manual-mode command first.
  assert(sent.size()==2&&sent[0].size()==12);
  assert(sent[0][6]==4&&sent[0][7]==4&&sent[0][10]==1);
  expectSetpoint(sent[1],24*factor);
  assert(p.schedule.equalsString("off")&&p.overall.equalsString("heat"));
  assert(p.targetTemperatureManualMode==24&&p.target.getDouble()==24&&p.power.getBoolean());
  Serial.output.clear();assert(p.target.parse("24"));assert(Serial.output.empty());
  assert(p.target.parse("25"));sent=frames();assert(sent.size()==1);expectSetpoint(sent[0],25*factor);
  Serial.output.clear();assert(p.overall.parse("auto"));sent=frames();
  assert(sent.size()==1&&sent[0][6]==4&&sent[0][10]==0&&p.target.getDouble()==(validClock?20:25));
 }
 // Controller-originated updates must not echo commands back to the MCU.
 {Probe p;p.receivingDataFromMcu=true;Serial.output.clear();p.target.setDouble(24);assert(Serial.output.empty());}
 // A setpoint change must not turn on a thermostat that was explicitly powered off.
 {Probe p;p.power.setBoolean(false);Serial.output.clear();assert(p.target.parse("24"));
  assert(!p.power.getBoolean());for(const auto& f:frames())assert(f[6]!=1);}
 puts("PASS real temperature/mode callbacks, mode-before-setpoint UART frames, precision, reentrancy, clock/schedule options and MCU echo guard");
}
'''
        self.compile_run(source, 'temperature_mode_transition')

    def test_midnight_final_schedule_and_validation(self):
        source = self.source() + r'''
int group(byte day){return day==0?36:day==6?18:0;}
int main(){
 for(bool midnight:{false,true})for(byte day=0;day<7;++day){
  Probe p;p.clock.day=day;p.currentSchedulePeriod=-1;
  for(unsigned d=0;d<3;++d)for(unsigned k=0;k<6;++k){
   unsigned a=d*18+k*3;p.schedules[a]=0;p.schedules[a+1]=k==5?(midnight?0:23):(6+k*3);
   p.schedules[a+2]=byte(14+d*2+k*2);
  }
  assert(p.validSchedulesOrder());
  for(unsigned minute=0;minute<1440;++minute){
   p.clock.minute=minute;p.updateCurrentSchedulePeriod();
   const int dayStart=group(day), previous=group(byte((day+6)%7));
   int expected=previous+15;
   if(minute>=360){
    expected=dayStart+3*std::min(4U,(minute-360)/180);
    if(!midnight&&minute>=1380)expected=dayStart+15;
   }
   assert(p.currentSchedulePeriod==expected);
   assert(p.target.getDouble()==p.schedules[expected+2]/2.0);
  }
  // Only a terminal midnight may wrap; arbitrary reversed periods remain invalid.
  p.schedules[4]=5;assert(!p.validSchedulesOrder());p.schedules[4]=9;
  p.schedules[0]=60;assert(!p.validSchedulesOrder());p.schedules[0]=0;
  p.schedules[1]=24;assert(!p.validSchedulesOrder());p.schedules[1]=6;
  if(midnight){p.schedules[16]=1;assert(!p.validSchedulesOrder());}
 }
 {Probe p;for(unsigned day=0;day<3;++day)for(unsigned k=0;k<6;++k){
   p.schedules[day*18+k*3]=0;p.schedules[day*18+k*3+1]=k==5?0:k*4;}
  assert(p.validSchedulesOrder());p.clock.minute=60;p.currentSchedulePeriod=-1;p.updateCurrentSchedulePeriod();assert(p.currentSchedulePeriod==0);}
 // Duplicate midnight starts retain their existing last-period-wins meaning.
 {Probe p;for(unsigned i=0;i<54;i+=3){p.schedules[i]=0;p.schedules[i+1]=0;}
  assert(p.validSchedulesOrder());p.clock.minute=0;p.currentSchedulePeriod=-1;p.updateCurrentSchedulePeriod();assert(p.currentSchedulePeriod==15);}
 // Returning to auto occurs on an actual period boundary, including midnight.
 {Probe p;p.schedules[1]=6;p.schedules[4]=9;p.schedules[7]=12;p.schedules[10]=15;p.schedules[13]=18;p.schedules[16]=0;
  p.clock.minute=1439;p.currentSchedulePeriod=-1;p.updateCurrentSchedulePeriod();assert(p.currentSchedulePeriod==12);
  p.back.setBoolean(true);p.target.parse("24");p.clock.minute=0;p.clock.day=2;p.updateCurrentSchedulePeriod();
  assert(p.currentSchedulePeriod==15&&p.schedule.equalsString(SCHEDULES_MODE_AUTO));
  p.clock.valid=false;p.updateCurrentSchedulePeriod();assert(p.currentSchedulePeriod==-1);}
 puts("PASS full-week schedule boundaries, terminal midnight, validation and auto return");
}
'''
        self.compile_run(source, 'midnight_schedule')

    def test_power_state_and_unchanged_temperature_recovery(self):
        source = self.source() + r'''
int main(){
 for(bool fromMcu:{false,true})for(int model:{MODEL_BHT_002_GBLW,MODEL_BAC_002_ALW})for(bool cooling:{false,true}){
  Probe p;p.model=model;p.receivingDataFromMcu=fromMcu;
  p.schedule.setSuppressOnChange();p.schedule.setString(SCHEDULES_MODE_OFF);
  p.sys.setString(cooling?SYSTEM_MODE_COOL:SYSTEM_MODE_HEAT);
  p.targetTemperatureManualMode=cooling?18:24;p.target.setDouble(p.targetTemperatureManualMode);p.updateRelaySimulation();
  const char* active=cooling&&model==MODEL_BAC_002_ALW?STATE_COOLING:cooling?STATE_OFF:STATE_HEATING;
  assert(p.outputState.equalsString(active));
  Serial.output.clear();p.power.setBoolean(false);
  assert(p.outputState.equalsString(STATE_OFF));assert(p.outputAction.equalsString(ACTION_OFF));
  if(fromMcu)assert(Serial.output.empty());
  Serial.output.clear();p.power.setBoolean(true);
  assert(p.outputState.equalsString(active));
  if(fromMcu)assert(Serial.output.empty());
 }
 // Updating derived status must preserve auto mode and emit no additional commands.
 for(bool fromMcu:{false,true}){Probe p;p.receivingDataFromMcu=fromMcu;
  for(bool powered:{false,true}){
   Serial.output.clear();p.power.setBoolean(powered);p.updateModeAndAction();
   assert(p.schedule.equalsString(SCHEDULES_MODE_AUTO));
   assert(p.overall.equalsString(powered?MODE_AUTO:MODE_OFF));
   auto sent=frames();assert(sent.size()==(fromMcu?0U:1U));
   if(!fromMcu)assert(sent[0][6]==1&&sent[0][10]==byte(powered));
  }
 }
 // An unsupported reported mode must not suppress the next real user command.
 {Probe p;p.model=MODEL_BAC_002_ALW;p.sys.setString("unknown");unsigned calls=0;
  p.overall.setOnChange([&](WProperty*){++calls;});p.updateModeAndAction();p.overall.parse("cool");assert(calls==1);}
 // #106: manual high -> auto low -> off -> manual high, without a new room reading.
 {Probe p;p.power.setBoolean(false);assert(p.schedule.equalsString(SCHEDULES_MODE_AUTO));
  p.overall.parse("heat");assert(p.power.getBoolean()&&p.overall.equalsString(MODE_HEAT)&&p.schedule.equalsString(SCHEDULES_MODE_OFF));}
 {Probe p;p.targetTemperatureManualMode=24;p.overall.setString(MODE_HEAT);p.target.setDouble(24);
  assert(p.outputState.equalsString(STATE_HEATING));p.overall.setString(MODE_AUTO);
  assert(p.target.getDouble()==20&&p.outputState.equalsString(STATE_OFF));
  p.overall.setString(MODE_OFF);p.overall.setString(MODE_HEAT);
  assert(p.target.getDouble()==24&&p.outputState.equalsString(STATE_HEATING)&&p.outputAction.equalsString(ACTION_HEATING));}
 // Hysteresis must hold its state inside the band, even on repeated recalculation.
 {Probe p;p.target.setDouble(24);p.actual.setDouble(23.5);p.updateRelaySimulation();assert(p.outputState.equalsString(STATE_HEATING));
  p.actual.setDouble(24);p.actual.setDouble(23.5);p.updateRelaySimulation();assert(p.outputState.equalsString(STATE_OFF));
  p.actual.setDouble(23);assert(p.outputState.equalsString(STATE_HEATING));}
 {Probe p;p.model=MODEL_BAC_002_ALW;p.sys.setString(SYSTEM_MODE_COOL);p.target.setDouble(18);p.actual.setDouble(18.5);
  p.updateRelaySimulation();assert(p.outputState.equalsString(STATE_COOLING));p.actual.setDouble(18);p.actual.setDouble(18.5);
  p.updateRelaySimulation();assert(p.outputState.equalsString(STATE_OFF));p.actual.setDouble(19);assert(p.outputState.equalsString(STATE_COOLING));}
 // Feedback from a real GPIO must never be replaced by the simulated state.
 for(bool cooling:{false,true}){Probe p;p.model=MODEL_BAC_002_ALW;p.relayHardware=!cooling;p.coolingHardware=cooling;
  p.sys.setString(cooling?SYSTEM_MODE_COOL:SYSTEM_MODE_HEAT);p.outputState.setString(cooling?STATE_COOLING:STATE_HEATING);
  p.power.setBoolean(false);p.updateRelaySimulation();assert(p.outputState.equalsString(cooling?STATE_COOLING:STATE_HEATING));}
 puts("PASS power state, MCU echo guard, issue 106, hysteresis and GPIO feedback preservation");
}
'''
        self.compile_run(source, 'power_state')

    def test_internal_targets_do_not_change_auto_mode(self):
        source = self.source() + r'''
int main(){
 for(bool clock:{false,true})for(bool schedules:{false,true})for(bool incoming:{false,true}){
  Probe p;p.clock.valid=clock;p.schedulesReceived=schedules;p.receivingDataFromMcu=incoming;
  Serial.output.clear();p.updateCurrentSchedulePeriod();p.updateTargetTemperature();
  assert(p.schedule.equalsString(SCHEDULES_MODE_AUTO)&&p.overall.equalsString(MODE_AUTO));
  assert(p.target.getDouble()==(clock&&schedules?20:18)&&p.targetTemperatureManualMode==18&&Serial.output.empty());
  p.receivingDataFromMcu=false;p.target.parse("24");auto sent=frames();
  assert(sent.size()==2&&sent[0][6]==4&&sent[0][10]==1);expectSetpoint(sent[1],48);
 }
}
'''
        self.compile_run(source, 'internal_target_updates')

    def test_eco_and_system_mode_refresh_without_echo_or_manual_cache_changes(self):
        source = self.source() + r'''
int main(){
 for(int model:{MODEL_BHT_002_GBLW,MODEL_BAC_002_ALW})for(bool incoming:{false,true}){
  Probe p;p.model=model;p.overall.parse("heat");p.target.parse("24");p.receivingDataFromMcu=incoming;Serial.output.clear();
  p.eco.parse("true");assert(p.eco.getBoolean()&&p.target.getDouble()==ECOMODETEMP&&p.target.isReadOnly());
  assert(p.outputState.equalsString(STATE_OFF)&&p.targetTemperatureManualMode==24);
  auto sent=frames();assert(sent.size()==(incoming?0U:1U));if(!incoming)assert(sent[0][6]==5);
  Serial.output.clear();assert(!p.target.parse("26"));assert(p.target.getDouble()==ECOMODETEMP&&p.targetTemperatureManualMode==24&&Serial.output.empty());
  p.eco.parse("false");assert(!p.target.isReadOnly()&&p.target.getDouble()==24&&p.outputState.equalsString(STATE_HEATING));
 }
 for(bool incoming:{false,true}){
  Probe p;p.model=MODEL_BAC_002_ALW;p.overall.parse("heat");p.target.parse("24");p.receivingDataFromMcu=incoming;Serial.output.clear();
  p.sys.parse("cool");assert(p.outputState.equalsString(STATE_OFF)&&p.outputAction.equalsString(ACTION_IDLE));
  if(incoming)assert(Serial.output.empty());else {auto sent=frames();assert(sent.size()==1&&sent[0][6]==0x66&&sent[0][10]==0);}
  p.eco.parse("true");assert(p.target.getDouble()==ECOMODETEMP_COOL);
  p.sys.parse("heat");assert(p.target.getDouble()==ECOMODETEMP);
 }
 for(bool incoming:{false,true}){
  Probe p;p.model=MODEL_BAC_002_ALW;p.target.parse("24");p.actual.setDouble(24.5);
  p.receivingDataFromMcu=incoming;Serial.output.clear();p.sys.parse("cool");
  assert(p.overall.equalsString(MODE_COOL)&&p.outputState.equalsString(STATE_OFF)&&p.outputAction.equalsString(ACTION_IDLE));
  p.actual.setDouble(26);assert(p.outputState.equalsString(STATE_COOLING));
  p.actual.setDouble(24.5);p.sys.parse(SYSTEM_MODE_FAN);
  assert(p.overall.equalsString(MODE_FAN)&&p.outputState.equalsString(STATE_FAN)&&p.outputAction.equalsString(ACTION_FAN));
  p.actual.setDouble(26);assert(p.outputState.equalsString(STATE_FAN));
  p.actual.setDouble(24.5);p.sys.parse("cool");
  assert(p.overall.equalsString(MODE_COOL)&&p.outputState.equalsString(STATE_COOLING)&&p.outputAction.equalsString(ACTION_COOLING));
  if(incoming)assert(Serial.output.empty());
 }
}
'''
        self.compile_run(source, 'eco_system_mode')
