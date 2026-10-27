#ifndef BECAMCU_H
#define	BECAMCU_H 

#include <utility>
#include "Arduino.h"
#include <ESP8266WiFi.h>
#include <EEPROM.h>
#include "../lib/WAdapter/WAdapter/WDevice.h"
#include "../lib/WAdapter/WAdapter/WPage.h"
#include "WClock.h"

const static char HTTP_CONFIG_SCHTAB_HEAD[]         PROGMEM = R"=====(
	<div class="schedules">
)=====";
const static char HTTP_CONFIG_SCHTAB_TD[]         PROGMEM = R"=====(
	<label>Time<input type="time" name="%c%ch" value="%s" required></label>
	<label>Temperature (&deg;C)<input type="number" name="%c%ct" min="5" max="%s" step="%s" value="%s" required></label>
)=====";
const static char HTTP_CONFIG_SCHTAB_FOOT[]         PROGMEM = R"=====(
	</div>
)=====";

// see https://www.home-assistant.io/docs/mqtt/discovery/ 
// and https://www.home-assistant.io/integrations/climate.mqtt/
// LWT = Last Will & Testament
const static char MQTT_HASS_AUTODISCOVERY_CLIMATE[]         PROGMEM = R"=====(
{
"name":null,
"unique_id": "%s",
"o":{"name":"WThermostatBeca","sw":"%s","url":"https://github.com/labodj/WThermostatBeca-labo"},
"dev":{"ids":["%s"],"name":"%s","mdl":"%s","sw":"%s","mf":"WThermostatBeca","cu":"http://%s/config/"},
"~": "%s",
"avty_mode":"all",
"avty":[{"topic":"~/tele/LWT","payload_available":"Online","payload_not_available":"Offline"},
        {"topic":"~/tele/mcu","payload_available":"Online","payload_not_available":"Offline"}],
"act_t":"~/stat/things/thermostat/properties",
"act_tpl":"{{value_json.action}}",
"mode_cmd_t":"~/cmnd/things/thermostat/properties/mode",
"mode_stat_t":"~/stat/things/thermostat/properties",
"mode_stat_tpl":"{{value_json.mode}}",
"temp_cmd_t":"~/cmnd/things/thermostat/properties/targetTemperature",
"temp_stat_t":"~/stat/things/thermostat/properties",
"temp_stat_tpl":"{{value_json.targetTemperature}}",
"curr_temp_t":"~/stat/things/thermostat/properties",
"curr_temp_tpl":"{{value_json.temperature}}",
"pr_mode_cmd_t":"~/cmnd/things/thermostat/properties/preset",
"pr_mode_stat_t":"~/stat/things/thermostat/properties",
"pr_mode_val_tpl":"{{value_json.preset}}",
"pr_modes":["away"],
"min_temp":5,
"max_temp":35,
"temperature_unit":"C",
"precision":%s,
"temp_step":%s,
"modes":["heat","auto","off"]
}
)=====";
const static char MQTT_HASS_AUTODISCOVERY_AIRCO[]         PROGMEM = R"=====(
{
"name":null,
"unique_id": "%s",
"o":{"name":"WThermostatBeca","sw":"%s","url":"https://github.com/labodj/WThermostatBeca-labo"},
"dev":{"ids":["%s"],"name":"%s","mdl":"%s","sw":"%s","mf":"WThermostatBeca","cu":"http://%s/config/"},
"~": "%s",
"avty_mode":"all",
"avty":[{"topic":"~/tele/LWT","payload_available":"Online","payload_not_available":"Offline"},
        {"topic":"~/tele/mcu","payload_available":"Online","payload_not_available":"Offline"}],
"act_t":"~/stat/things/thermostat/properties",
"act_tpl":"{{value_json.action}}",
"mode_cmd_t":"~/cmnd/things/thermostat/properties/mode",
"mode_stat_t":"~/stat/things/thermostat/properties",
"mode_stat_tpl":"{{value_json.mode}}",
"temp_cmd_t":"~/cmnd/things/thermostat/properties/targetTemperature",
"temp_stat_t":"~/stat/things/thermostat/properties",
"temp_stat_tpl":"{{value_json.targetTemperature}}",
"curr_temp_t":"~/stat/things/thermostat/properties",
"curr_temp_tpl":"{{value_json.temperature}}",
"fan_mode_cmd_t":"~/cmnd/things/thermostat/properties/fanMode",
"fan_mode_stat_t":"~/stat/things/thermostat/properties",
"fan_mode_stat_tpl":"{{value_json.fanMode}}",
"fan_modes":["auto","low","medium","high"],
"pr_mode_cmd_t":"~/cmnd/things/thermostat/properties/preset",
"pr_mode_stat_t":"~/stat/things/thermostat/properties",
"pr_mode_val_tpl":"{{value_json.preset}}",
"pr_modes":["away", "scheduler"],
"min_temp":10,
"max_temp":35,
"temperature_unit":"C",
"precision":%s,
"temp_step":%s,
"modes":["heat","cool","fan_only","off"]
}
)=====";
const static char MQTT_HASS_AUTODISCOVERY_SENSOR[]         PROGMEM = R"=====(
{
"name":"Temperature",
"unique_id":"%s",
"o":{"name":"WThermostatBeca","sw":"%s","url":"https://github.com/labodj/WThermostatBeca-labo"},
"device_class":"temperature",
"state_class":"measurement",
"dev":{"ids":["%s"]},
"~":"%s",
"avty_mode":"all",
"avty":[{"topic":"~/tele/LWT","payload_available":"Online","payload_not_available":"Offline"},
        {"topic":"~/tele/mcu","payload_available":"Online","payload_not_available":"Offline"}],
"stat_t":"~/stat/things/thermostat/properties",
"val_tpl":"{{value_json.temperature}}",
"unit_of_measurement":"°C"
}
)=====";
const static char MQTT_HASS_AUTODISCOVERY_SENSORFLOOR[]         PROGMEM = R"=====(
{
"name":"Temperature Floor",
"unique_id":"%s",
"o":{"name":"WThermostatBeca","sw":"%s","url":"https://github.com/labodj/WThermostatBeca-labo"},
"device_class":"temperature",
"state_class":"measurement",
"dev":{"ids":["%s"]},
"~":"%s",
"avty_mode":"all",
"avty":[{"topic":"~/tele/LWT","payload_available":"Online","payload_not_available":"Offline"},
        {"topic":"~/tele/mcu","payload_available":"Online","payload_not_available":"Offline"}],
"stat_t":"~/stat/things/thermostat/properties",
"val_tpl":"{{value_json.floorTemperature}}",
"unit_of_measurement":"°C"
}
)=====";
const static char MQTT_HASS_AUTODISCOVERY_SENSORRSSI[]         PROGMEM = R"=====(
{
"name":"WiFi RSSI",
"unique_id":"%s",
"o":{"name":"WThermostatBeca","sw":"%s","url":"https://github.com/labodj/WThermostatBeca-labo"},
"device_class":"signal_strength",
"state_class":"measurement",
"entity_category":"diagnostic",
"dev":{"ids":["%s"]},
"~":"%s",
"avty_t":"~/tele/LWT","pl_avail":"Online","pl_not_avail":"Offline",
"stat_t":"~/stat/things/network/properties",
"val_tpl":"{{value_json.rssi}}",
"unit_of_measurement":"dBm"
}
)=====";
const static char MQTT_HASS_AUTODISCOVERY_SENSORIP[]         PROGMEM = R"=====(
{
"name":"IP",
"unique_id":"%s",
"o":{"name":"WThermostatBeca","sw":"%s","url":"https://github.com/labodj/WThermostatBeca-labo"},
"entity_category":"diagnostic",
"dev":{"ids":["%s"]},
"~":"%s",
"avty_t":"~/tele/LWT","pl_avail":"Online","pl_not_avail":"Offline",
"stat_t":"~/stat/things/thermostat/properties",
"val_tpl":"{{value_json.ip}}",
"icon":"mdi:ip-network"
}
)=====";

#define COUNT_DEVICE_MODELS 2
#define MODEL_BHT_002_GBLW 0
#define MODEL_BAC_002_ALW 1
#define HEARTBEAT_INTERVAL 10000
#define MINIMUM_INTERVAL 2000
#define STATE_COMPLETE 6
#define PIN_STATE_HEATING_RELAY 5
#define PIN_STATE_COOLING_RELAY 4
#define ECOMODETEMP 20.0
#define ECOMODETEMP_COOL 26.0
// tuya doc says local time seconds is from 0 to 15 but this seems to be not right
// for beca
#define SECONDS_DIVIDER 1

const unsigned char COMMAND_START[] = {0x55, 0xAA};
const String SCHEDULES = "schedules";
const String MCUCOMMAND = "mcucommand";
const char* SCHEDULES_MODE_OFF PROGMEM = "off";
const char* SCHEDULES_MODE_AUTO PROGMEM = "auto";
// HOLD_MODE is an alias for SCHEDULE_MODE - Just Different Names/attributes
// special for HASS
const char* HOLD_STATE_MANUAL PROGMEM = "manual";
const char* HOLD_STATE_SCHEDULER PROGMEM = "scheduler";
const char* HOLD_STATE_ECO PROGMEM = "eco";
const char* HOLD_STATE_OFF PROGMEM = "off";
const char* SYSTEM_MODE_NONE PROGMEM = "none";
const char* SYSTEM_MODE_COOL PROGMEM = "cool";
const char* SYSTEM_MODE_HEAT PROGMEM = "heat";
const char* SYSTEM_MODE_FAN PROGMEM = "fan_only";
const char* STATE_OFF PROGMEM = "off";
const char* STATE_HEATING PROGMEM = "heating";
const char* STATE_COOLING PROGMEM = "cooling";
const char* STATE_FAN PROGMEM = "fan";
const char* FAN_MODE_NONE PROGMEM = "none";
const char* FAN_MODE_AUTO PROGMEM = "auto";
const char* FAN_MODE_LOW  PROGMEM = "low";
const char* FAN_MODE_MEDIUM  PROGMEM = "medium";
const char* FAN_MODE_HIGH PROGMEM = "high";
const char* MODE_OFF  PROGMEM = "off";
const char* MODE_AUTO PROGMEM = "auto";
const char* MODE_HEAT PROGMEM = "heat";
const char* MODE_COOL PROGMEM = "cool";
const char* MODE_FAN  PROGMEM = "fan_only";
const char* PRESET_NONE PROGMEM = "none";
const char* PRESET_AWAY PROGMEM = "away";
const char* PRESET_SCHEDULER PROGMEM = "scheduler";
const char* ACTION_OFF  PROGMEM = "off";
const char* ACTION_COOLING  PROGMEM = "cooling";
const char* ACTION_HEATING  PROGMEM = "heating";
const char* ACTION_IDLE  PROGMEM = "idle";
const char* ACTION_FAN PROGMEM = "fan";

const char* ID_THERMOSTAT PROGMEM = "thermostat";
const char* NAME_THERMOSTAT PROGMEM = "Thermostat";

const char* PROP_BECABITS1 PROGMEM = "becabits1";
const char* PROP_BECABITS2 PROGMEM = "becabits2";
const char* PROP_THERMOSTATMODEL PROGMEM = "thermostatModel";
const char* PROP_SCHEDULESDAYOFFSET PROGMEM = "schedulesDayOffset";
const char* PROP_SUPPORTHEATINGRELAY PROGMEM = "supportingHeatingRelay";
const char* PROP_SUPPORTCOOLINGRELAY PROGMEM = "supportingCoolingRelay";
const char* PROP_DEADZONETEMP PROGMEM = "deadzoneTemp";
const char* PROP_BECARES1 PROGMEM = "becares1";
const char* PROP_BECARES2 PROGMEM = "becares2";
const char* PROP_BECARES3 PROGMEM = "becares3";
const char* PROP_BECARES4 PROGMEM = "becares4";
const char* PROP_BECARES5 PROGMEM = "becares5";
const char* PROP_BECARES6 PROGMEM = "becares6";
const char* PROP_BECARES7 PROGMEM = "becares7";
const char* PROP_BECARES8 PROGMEM = "becares8";
const char* PROP_SWITCHBACKTOAUTO PROGMEM = "switchBackToAuto";
const char* TITL_SWITCHBACKTOAUTO PROGMEM = "switch Back from Manual to Auto at next Schedule";
const char* PROP_FLOORSENSOR PROGMEM = "floorSensor";
const char* PROP_PRECISION PROGMEM = "precision";
const char* PROP_ACTUALTEMPERATURE PROGMEM = "temperature";
const char* TITL_ACTUALTEMPERATURE PROGMEM = "Actual";
const char* PROP_TARGETTEMPERATURE PROGMEM = "targetTemperature";
const char* TITL_TARGETTEMPERATURE PROGMEM = "Target";
const char* PROP_DEVICEON PROGMEM = "deviceOn";
const char* TITL_DEVICEON PROGMEM = "Power";
const char* PROP_SCHEDULESMODE PROGMEM = "schedulesMode";
const char* TITL_SCHEDULESMODE PROGMEM = "Schedules";
const char* PROP_HOLDSTATE PROGMEM = "holdState";
const char* PROP_ECOMODE PROGMEM = "ecoMode";
const char* TITL_ECOMODE PROGMEM = "Eco";
const char* PROP_LOCK PROGMEM = "locked";
const char* TITL_LOCK PROGMEM = "Lock";
const char* PROP_FLOORTEMPERATUR PROGMEM = "floorTemperature";
const char* TITL_FLOORTEMPERATUR PROGMEM = "Floor";
const char* PROP_SYSTEMMODE PROGMEM = "systemMode";
const char* TITL_SYSTEMMODE PROGMEM = "System Mode";
const char* PROP_FANMODE PROGMEM = "fanMode";
const char* TITL_FANMODE PROGMEM = "Fan";
const char* PROP_MODE PROGMEM = "mode";
const char* TITL_MODE PROGMEM = "Mode";
const char* PROP_PRESET PROGMEM = "preset";
const char* TITL_PRESET PROGMEM = "Preset";
const char* PROP_ACTION PROGMEM = "action";
const char* TITL_ACTION PROGMEM = "Action";
const char* PROP_STATE PROGMEM = "state";
const char* TITL_STATE PROGMEM = "State";
const char* PROP_MCUID PROGMEM = "mcuId";

const char* ATTYPE_SCHEDULESMODE PROGMEM = "ThermostatSchedulesModeProperty";
const char* ATTYPE_HOLDSTATE PROGMEM = "ThermostatHoldStateProperty";
const char* ATTYPE_MODE PROGMEM = "ThermostatModeProperty";
const char* ATTYPE_PRESET PROGMEM = "ThermostatPresetProperty";
const char* ATTYPE_FANMODE PROGMEM = "FanModeProperty";
const char* ATTYPE_ACTION PROGMEM = "ThermostatActionProperty";
const char* ATTYPE_HEATINGCOOLING PROGMEM = "HeatingCoolingProperty";


const char* ID_PAGE_SCHEDULE PROGMEM = "schedules";
const char* TITLE_PAGE_SCHEDULE PROGMEM = "Configure Schedules";
const char* ID_PAGE_REINIT PROGMEM = "reinit";
const char* TITLE_PAGE_REINIT PROGMEM = "Reinit Thermostat";

const byte STORED_FLAG_BECA = 0x36;
const char SCHEDULES_PERIODS[] = "123456";
const char SCHEDULES_DAYS[] = "wau";

const byte BECABITS1_RELAY_HEAT    =   1;
const byte BECABITS1_RELAY_COOL    =   2;
const byte BECABITS1_TEMP_01        =   4;
const byte BECABITS1_TEMP_10        =   8;
const byte BECABITS1_SWITCHBACKOFF  =  16;
const byte BECABITS1_FLOORSENSOR    =  32;

const byte devicesWithHassAutodiscoverSupport[] = {
	MODEL_BHT_002_GBLW,
	MODEL_BAC_002_ALW
	};

//typedef 
typedef enum mcuNetworkMode : uint8_t
{
	MCU_NETWORKMODE_SMARTCONFIG = 0x00,
	MCU_NETWORKMODE_APCONFIG = 0x01,
	MCU_NETWORKMODE_NOTCONNECTED = 0x02,
	MCU_NETWORKMODE_CONNECTED = 0x03,
	MCU_NETWORKMODE_CONNECTEDCLOUD = 0x04,
	MCU_NETWORKMODE_POWERSAVE = 0x05
} mcuNetworkMode_t;

class WBecaDevice: public WDevice {
public:
    typedef std::function<bool()> THandlerFunction;
    typedef std::function<bool(const char*)> TCommandHandlerFunction;

    WBecaDevice(WNetwork* network, WClock* wClock)
    	: WDevice(network, ID_THERMOSTAT, NAME_THERMOSTAT, network->getIdx(), DEVICE_TYPE_THERMOSTAT) {
		
    	this->receivingDataFromMcu = false;
    	this->schedulesChanged = false;
		this->providingConfigPage = true;
		this->currentSchedulePeriod = -1;
		this->targetTemperatureManualMode = 0.0;
    	this->wClock = wClock;
    	this->systemMode = nullptr;
		this->setMqttRetain(true);
		this->stateNotifyInterval=60000;
		this->onConfigurationRequest=nullptr;
		this->onPowerButtonOn=nullptr;
		oldActualTemperature = oldTargetTemperature = 0;
		network->log()->trace(F("Beca start (%d)"), ESP.getMaxFreeBlockSize());
		startMcuInitialize();
		/* properties */

		if (network->getSettingsOld()){
			if (network->getSettingsOld()->getNetworkSettingsVersion()==NETWORKSETTINGS_PRE_FAS114){
				network->log()->notice(F("Reading BecaDeviceSettings PRE_FAS114"));
				network->getSettingsOld()->setByte(PROP_BECABITS1, 0x00);
				network->getSettingsOld()->setByte(PROP_BECABITS2, 0x00);
				network->getSettingsOld()->setByte(PROP_THERMOSTATMODEL, MODEL_BHT_002_GBLW);
				network->getSettingsOld()->setByte(PROP_SCHEDULESDAYOFFSET, 0);
			} else if (network->getSettingsOld()->getApplicationSettingsVersion()==network->getSettingsOld()->getApplicationSettingsCurrent()-1){
				network->log()->notice(F("Reading BecaDeviceSettings FLAG_OPTIONS_APPLICATION -1"));
				network->getSettingsOld()->setByte(PROP_BECABITS1, 0x00);
				network->getSettingsOld()->setByte(PROP_BECABITS2, 0x00);
				network->getSettingsOld()->setByte(PROP_THERMOSTATMODEL, MODEL_BHT_002_GBLW);
				network->getSettingsOld()->setByte(PROP_SCHEDULESDAYOFFSET, 0);
			}
		}

		network->log()->trace(F("Beca settings (%d)"), ESP.getMaxFreeBlockSize());
		// read beca bits 
		this->becaBits1 = network->getSettings()->setByte(PROP_BECABITS1,
			(network->getSettingsOld() && network->getSettingsOld()->existsSetting(PROP_BECABITS1) ? network->getSettingsOld()->getByte(PROP_BECABITS1) : 0x00));
		this->becaBits2 = network->getSettings()->setByte(PROP_BECABITS2,
			(network->getSettingsOld() && network->getSettingsOld()->existsSetting(PROP_BECABITS2) ? network->getSettingsOld()->getByte(PROP_BECABITS2) : 0x00));
		// Split mqtt setting into bits - so we keep settings storage compatibility
		if (this->becaBits1->getByte() == 0xFF) this->becaBits1->setByte(BECABITS1_RELAY_HEAT); // compatibility

		// Heating Relay and State property
		this->supportingHeatingRelay = new WProperty(PROP_SUPPORTHEATINGRELAY, nullptr, BOOLEAN);
		this->supportingHeatingRelay->setBoolean(this->becaBits1->getByte() & BECABITS1_RELAY_HEAT);
		this->supportingCoolingRelay = new WProperty(PROP_SUPPORTCOOLINGRELAY, nullptr, BOOLEAN);
		this->supportingCoolingRelay->setBoolean(this->becaBits1->getByte() & BECABITS1_RELAY_COOL);

		if (this->supportingHeatingRelay->getBoolean() && this->supportingCoolingRelay->getBoolean()) {
			this->supportingCoolingRelay->setBoolean(false);
		}

		this->deadzoneTemp = network->getSettings()->setByte(PROP_DEADZONETEMP, 1);
		this->deadzoneTemp->setByte(constrain(this->deadzoneTemp->getByte(), 1, 5));


		// some reserved Bytes
		network->getSettings()->setByte(PROP_BECARES1, 255);
		network->getSettings()->setByte(PROP_BECARES2, 255);
		network->getSettings()->setByte(PROP_BECARES3, 255);
		network->getSettings()->setByte(PROP_BECARES4, 255);
		network->getSettings()->setByte(PROP_BECARES5, 255);
		network->getSettings()->setByte(PROP_BECARES6, 255);
		network->getSettings()->setByte(PROP_BECARES7, 255);
		network->getSettings()->setByte(PROP_BECARES8, 255);
		

		network->log()->trace(F("Beca settings switchBackToAuto (%d)"), ESP.getMaxFreeBlockSize());
		// switch back property
		this->switchBackToAuto = new WProperty(PROP_SWITCHBACKTOAUTO, TITL_SWITCHBACKTOAUTO, BOOLEAN);
		this->switchBackToAuto->setBoolean(!(this->becaBits1->getByte() & BECABITS1_SWITCHBACKOFF));
		this->switchBackToAuto->setVisibility(ALL);
		this->switchBackToAuto->setReadOnly(false);
		this->switchBackToAuto->setMqttSendChangedValues(true);
		this->switchBackToAuto->setOnChange(std::bind(&WBecaDevice::saveSettings, this, std::placeholders::_1));
		this->addProperty(switchBackToAuto);
		network->log()->trace(F("Beca settings switchBackToAuto done (%d)"), ESP.getMaxFreeBlockSize());

		// Floor Sensor 
		this->floorSensor = new WProperty(PROP_FLOORSENSOR, nullptr, BOOLEAN);
		this->floorSensor->setBoolean(this->becaBits1->getByte() & BECABITS1_FLOORSENSOR);

		// precicion (must be initialized before Temperature Values)
		this->temperaturePrecision = new WProperty(PROP_PRECISION, nullptr, DOUBLE);
		if (this->becaBits1->getByte() & BECABITS1_TEMP_01){
			this->temperaturePrecision->setDouble(0.1f);
		} else if (this->becaBits1->getByte() & BECABITS1_TEMP_10){
			this->temperaturePrecision->setDouble(1.0f);
		} else {
			this->temperaturePrecision->setDouble(0.5f);
		}
		this->temperaturePrecision->setReadOnly(true);


    	this->actualTemperature = new WTemperatureProperty(PROP_ACTUALTEMPERATURE, TITL_ACTUALTEMPERATURE);
    	this->actualTemperature->setReadOnly(true);
		this->actualTemperature->setOnChange(std::bind(&WBecaDevice::onChangeActualTemperature, this, std::placeholders::_1));
		this->actualTemperature->setMqttSendChangedValues(true);
    	this->addProperty(actualTemperature);
		network->log()->trace(F("Beca settings actualTemperature done (%d)"), ESP.getMaxFreeBlockSize());

	this->thermostatModel = network->getSettings()->setByte(PROP_THERMOSTATMODEL,
			(network->getSettingsOld() && network->getSettingsOld()->existsSetting(PROP_THERMOSTATMODEL) ? network->getSettingsOld()->getByte(PROP_THERMOSTATMODEL) : MODEL_BHT_002_GBLW));
	this->targetTemperature = new WTargetTemperatureProperty(PROP_TARGETTEMPERATURE, TITL_TARGETTEMPERATURE,
            getThermostatModel() == MODEL_BAC_002_ALW ? 10 : 5, 35);//, 12.0, 28.0);
    	this->targetTemperature->setMultipleOf(getTemperaturePrecision());
    	this->targetTemperature->setOnChange(std::bind(&WBecaDevice::onChangeTargetTemperature, this, std::placeholders::_1));
    	//this->targetTemperature->setOnValueRequest([this](WProperty* p) {updateTargetTemperature();});
		this->targetTemperature->setMqttSendChangedValues(true);
    	this->addProperty(targetTemperature);
		network->log()->trace(F("Beca settings targetTemperature done (%d)"), ESP.getMaxFreeBlockSize());


    	this->deviceOn = new WOnOffProperty(PROP_DEVICEON, TITL_DEVICEON);
    	this->deviceOn->setOnChange(std::bind(&WBecaDevice::deviceOnToMcu, this, std::placeholders::_1));
		this->deviceOn->setMqttSendChangedValues(true);
    	this->addProperty(deviceOn);
		network->log()->trace(F("Beca settings deviceOn done (%d)"), ESP.getMaxFreeBlockSize());
		
		this->schedulesMode = new WProperty(PROP_SCHEDULESMODE, TITL_SCHEDULESMODE, STRING);
		this->schedulesMode->setAtType(ATTYPE_SCHEDULESMODE);
		this->schedulesMode->addEnumString(SCHEDULES_MODE_OFF);
		this->schedulesMode->addEnumString(SCHEDULES_MODE_AUTO);
		this->schedulesMode->setOnChange(std::bind(&WBecaDevice::schedulesModeToMcu, this, std::placeholders::_1));
		this->schedulesMode->setMqttSendChangedValues(true);
		this->addProperty(schedulesMode);
		network->log()->trace(F("Beca settings schedulesMode done (%d)"), ESP.getMaxFreeBlockSize());

		this->holdState = new WProperty(PROP_HOLDSTATE, nullptr, STRING);
		this->holdState->setAtType(ATTYPE_HOLDSTATE);
		this->holdState->addEnumString(HOLD_STATE_MANUAL);
		this->holdState->addEnumString(HOLD_STATE_SCHEDULER);
		this->holdState->addEnumString(HOLD_STATE_ECO);
		this->holdState->addEnumString(HOLD_STATE_OFF);
		this->holdState->setOnChange(std::bind(&WBecaDevice::holdStateToScheduleMode, this, std::placeholders::_1));
		this->holdState->setOnValueRequest(std::bind(&WBecaDevice::holdStateRequest, this, std::placeholders::_1));
		this->holdState->setMqttSendChangedValues(true);
		this->holdState->setVisibility(MQTT);
		this->addProperty(holdState);
		network->log()->trace(F("Beca settings holdState done (%d)"), ESP.getMaxFreeBlockSize());

    	this->ecoMode = new WOnOffProperty(PROP_ECOMODE, TITL_ECOMODE);
    	this->ecoMode->setOnChange(std::bind(&WBecaDevice::ecoModeToMcu, this, std::placeholders::_1));
    	this->ecoMode->setVisibility(ALL);
		this->ecoMode->setMqttSendChangedValues(true);
    	this->addProperty(ecoMode);
		network->log()->trace(F("Beca settings ecoMode done (%d)"), ESP.getMaxFreeBlockSize());

    	this->locked = new WOnOffProperty(PROP_LOCK, TITL_LOCK);
    	this->locked->setOnChange(std::bind(&WBecaDevice::lockedToMcu, this, std::placeholders::_1));
    	this->locked->setVisibility(ALL);
		this->locked->setMqttSendChangedValues(true);
    	this->addProperty(locked);
		network->log()->trace(F("Beca settings locked done (%d)"), ESP.getMaxFreeBlockSize());


		network->log()->trace(F("Beca settings model (%d)"), ESP.getMaxFreeBlockSize());
    	//Model
    	this->actualFloorTemperature = nullptr;

    	if (getThermostatModel() == MODEL_BHT_002_GBLW) {
			if (this->floorSensor->getBoolean()){
				this->actualFloorTemperature = new WTemperatureProperty(PROP_FLOORTEMPERATUR, TITL_FLOORTEMPERATUR);
				this->actualFloorTemperature->setReadOnly(true);
				this->actualFloorTemperature->setVisibility(ALL);
				this->actualFloorTemperature->setMqttSendChangedValues(true);
				this->addProperty(actualFloorTemperature);
			}
    	} else if (getThermostatModel() == MODEL_BAC_002_ALW) {
    		this->systemMode = new WProperty(PROP_SYSTEMMODE, TITL_SYSTEMMODE, STRING);
        	this->systemMode->setAtType(ATTYPE_MODE);
			this->systemMode->addEnumString(SYSTEM_MODE_COOL);
        	this->systemMode->addEnumString(SYSTEM_MODE_HEAT);
        	this->systemMode->addEnumString(SYSTEM_MODE_FAN);
			this->systemMode->setOnChange(std::bind(&WBecaDevice::systemModeToMcu, this, std::placeholders::_1));
			this->systemMode->setMqttSendChangedValues(true);
        	this->addProperty(systemMode);
    		this->fanMode = new WProperty(PROP_FANMODE, TITL_FANMODE, STRING);
        	this->fanMode->setAtType(ATTYPE_FANMODE);
        	this->fanMode->addEnumString(FAN_MODE_NONE);
        	this->fanMode->addEnumString(FAN_MODE_LOW);
        	this->fanMode->addEnumString(FAN_MODE_MEDIUM);
			this->fanMode->addEnumString(FAN_MODE_HIGH);
			this->fanMode->addEnumString(FAN_MODE_AUTO);
			this->fanMode->setOnChange(std::bind(&WBecaDevice::fanModeToMcu, this, std::placeholders::_1));
			this->fanMode->setMqttSendChangedValues(true);
        	this->addProperty(fanMode);
    	}
		network->log()->trace(F("Beca settings model done (%d)"), ESP.getMaxFreeBlockSize());
		/* 
		* New OverAllMode for easier integration
		* https://iot.mozilla.org/schemas/#ThermostatModeProperty
		* https://www.home-assistant.io/integrations/climate.mqtt/
		*/

    	this->mode = new WProperty(PROP_MODE, TITL_MODE, STRING);
		this->mode->setVisibility(ALL);
    	this->mode->setAtType(ATTYPE_MODE); 
    	this->mode->addEnumString(MODE_OFF);
		if (getThermostatModel() == MODEL_BHT_002_GBLW) {
			this->mode->addEnumString(MODE_AUTO);
		}
		this->mode->addEnumString(MODE_HEAT);
		if (getThermostatModel() == MODEL_BAC_002_ALW) {
			this->mode->addEnumString(MODE_COOL);
    		this->mode->addEnumString(MODE_FAN);
		}
    	this->mode->setOnChange(std::bind(&WBecaDevice::modeToMcu, this, std::placeholders::_1));
		this->mode->setOnValueRequest([this](WProperty* p) {updateModeAndAction();});
		this->mode->setMqttSendChangedValues(true);
    	this->addProperty(mode);

		this->preset = new WProperty(PROP_PRESET, TITL_PRESET, STRING);
		this->preset->setVisibility(ALL);
		this->preset->setAtType(ATTYPE_PRESET); 
		this->preset->addEnumString(PRESET_NONE);
		this->preset->addEnumString(PRESET_AWAY);
		if (getThermostatModel() == MODEL_BAC_002_ALW) {
			this->preset->addEnumString(PRESET_SCHEDULER);
		}
		this->preset->setOnChange(std::bind(&WBecaDevice::presetToMcu, this, std::placeholders::_1));
		this->preset->setOnValueRequest([this](WProperty* p) {updatePreset();});
		this->preset->setMqttSendChangedValues(true);
		this->addProperty(preset);

		this->action = new WProperty(PROP_ACTION, TITL_ACTION, STRING);
		this->action->setAtType(ATTYPE_ACTION); 
		this->action->addEnumString(ACTION_OFF);
		this->action->addEnumString(ACTION_HEATING);
		this->action->addEnumString(ACTION_IDLE);
		if (getThermostatModel() == MODEL_BHT_002_GBLW) {
		} else if (getThermostatModel() == MODEL_BAC_002_ALW) {
			this->action->addEnumString(ACTION_COOLING);
			this->action->addEnumString(ACTION_FAN);
		}
		this->action->setMqttSendChangedValues(true);
		this->action->setReadOnly(true);
		this->addProperty(action);


		if (getThermostatModel() == MODEL_BHT_002_GBLW) {
			//disable Cooling Relay if enabled on heating-thermostat
			this->supportingCoolingRelay->setBoolean(false);
		}
		if (isSupportingHeatingRelay()) pinMode(PIN_STATE_HEATING_RELAY, INPUT);
    	else if (isSupportingCoolingRelay()) pinMode(PIN_STATE_COOLING_RELAY, INPUT);
		this->state = nullptr;
		this->state = new WProperty(PROP_STATE, TITL_STATE, STRING);
		this->state->setAtType(ATTYPE_HEATINGCOOLING);
		this->state->setReadOnly(true);
		this->state->addEnumString(STATE_OFF);
		this->state->addEnumString(STATE_HEATING);
		if (getThermostatModel() == MODEL_BHT_002_GBLW){
			this->state->addEnumString(STATE_COOLING);
			this->state->addEnumString(STATE_FAN);
		}
		this->state->setMqttSendChangedValues(true);
		this->state->setOnValueRequest([this](WProperty* p) {updateModeAndAction();});
		this->addProperty(state);

    	//schedulesDayOffset
    	this->schedulesDayOffset = network->getSettings()->setByte(PROP_SCHEDULESDAYOFFSET,
			(network->getSettingsOld() && network->getSettingsOld()->existsSetting(PROP_SCHEDULESDAYOFFSET) ? network->getSettingsOld()->getByte(PROP_SCHEDULESDAYOFFSET) : 0));


		this->mcuId = new WProperty(PROP_MCUID, nullptr, STRING);
		this->mcuId->setVisibility(ALL);
		this->mcuId->setReadOnly(true);
		this->addProperty(mcuId);

		network->log()->trace(F("Beca settings page schedule (%d)"), ESP.getMaxFreeBlockSize());
		// Pages
		WPage * schedulePage=new WPage(ID_PAGE_SCHEDULE, TITLE_PAGE_SCHEDULE);
		schedulePage->setPrintPage([this,schedulePage](AsyncWebServerRequest* request, AsyncResponseStream* page) {
			this->network->log()->notice(PSTR("Schedules"));
			page->printf_P(HTTP_CONFIG_PAGE_BEGIN, ((String)getId()+"_"+schedulePage->getId()).c_str());
			page->print(FPSTR(HTTP_CONFIG_SCHTAB_HEAD));
            char step[6], maximum[6];
            dtostrf(1.0 / getTemperatureFactor(), 0, 1, step);
            dtostrf(getTemperatureFactor() > 255.0 / 35.0 ? 255.0 / getTemperatureFactor() : 35.0, 0, 1, maximum);
            const char* dayTitles[] = {"Workdays (days 1-5)", "Day 6", "Day 7"};
            for (const char* day = SCHEDULES_DAYS; *day; ++day) {
                page->printf_P("<fieldset><legend>%s</legend>", dayTitles[day - SCHEDULES_DAYS]);
                for (const char* period = SCHEDULES_PERIODS; *period; ++period) {
					page->printf_P("<fieldset class='schedule-period'><legend>Period %c</legend>", *period);
					char keyH[4];
					char keyT[4];
					snprintf(keyH, 4, "%c%ch", *day, *period);
					snprintf(keyT, 4, "%c%ct", *day, *period);
					//this->network->log()->verbose(PSTR("Period %s / %s"), keyH, keyT);
					page->printf(HTTP_CONFIG_SCHTAB_TD,
					*day, *period, this->getSchedulesValue(keyH).c_str(),
						*day, *period, maximum, step, this->getSchedulesValue(keyT).c_str());
					page->print(F("</fieldset>"));
				}
				page->print(F("</fieldset>"));
			}
			page->printf_P(HTTP_CONFIG_SCHTAB_FOOT);
			page->printf_P(HTTP_CONFIG_SAVE_BUTTON);
			page->printf_P(HTTP_HOME_BUTTON);

		});
		schedulePage->setSubmittedPage([this,schedulePage](AsyncWebServerRequest* request, AsyncResponseStream* page) {
			this->network->log()->notice(PSTR("submitted"));
            byte previous[sizeof(schedules)];
            memcpy(previous, schedules, sizeof(schedules));
            bool valid = true;
			schedulesChanged = false;
			for (char *period=const_cast<char*>(SCHEDULES_PERIODS); *period > 0; period++){
				for (char *day=const_cast<char*>(SCHEDULES_DAYS); *day > 0; day++){
					char keyH[4];
					char keyT[4];
					snprintf(keyH, 4, "%c%ch", *day, *period);
					snprintf(keyT, 4, "%c%ct", *day, *period);
					String valueH = getValueOrEmpty(request, keyH);
					String valueT = getValueOrEmpty(request, keyT);
                    valid &= processSchedulesKeyValue(keyH, valueH.c_str());
                    valid &= processSchedulesKeyValue(keyT, valueT.c_str());
				}
			}
            if (!valid || !validSchedulesOrder()) {
                memcpy(schedules, previous, sizeof(schedules));
                schedulesChanged = false;
                page->print(F("Invalid schedules; no changes saved"));
                return;
            }
			if (schedulesChanged) {
				this->network->log()->notice(PSTR("Some schedules changed. Write to MCU..."));
				this->schedulesToMcu();
				page->print(F("Schedules have been saved"));
			} else {
				page->print(F("Nothing has been changed"));
			}
		});
		this->addPage(schedulePage);
		network->log()->trace(F("Beca settings page schedule done (%d)"), ESP.getMaxFreeBlockSize());

		// Pages reinit		
		WPage * reinitPage=new WPage(ID_PAGE_REINIT, TITLE_PAGE_REINIT);
		reinitPage->setPrintPage([this,reinitPage](AsyncWebServerRequest *request, AsyncResponseStream* page) {
			this->network->log()->notice(PSTR("Reinit"));
			page->print(F("Reinitialized"));
			page->print(FPSTR(HTTP_HOME_BUTTON));
			startMcuInitialize();
		});
		reinitPage->setSubmittedPage([this,reinitPage](AsyncWebServerRequest *request, AsyncResponseStream* page) {
			page->print(F("VOID"));			
		});
		this->addPage(reinitPage);
		

		lastHeartBeat = lastNotify = lastScheduleNotify  = lastLongLoop = lastTimeRequested = lastTimeSent = 0;
		timeIsRequested = timeIsRequestedLocaltime = timeIsRequestedSendZeroSecs = false;
		resetAll();
		for (int i = 0; i < STATE_COMPLETE; i++) {
			receivedStates[i] = false;
		}
		this->schedulesDataPoint = 0x00;

		network->log()->trace(F("Beca all done (%d)"), ESP.getMaxFreeBlockSize());
	}

    virtual void printConfigPage(AsyncWebServerRequest *request, AsyncResponseStream* page) override {
    	network->log()->notice(PSTR("Beca thermostat config page"));
    	page->printf_P(HTTP_CONFIG_PAGE_BEGIN, getId());

    	//ComboBox with model selection
        page->printf_P(HTTP_COMBOBOX_BEGIN, PSTR("Thermostat model:"), "tm");
        page->printf_P(HTTP_COMBOBOX_ITEM, "0", (getThermostatModel() == 0 ? HTTP_SELECTED : ""), PSTR("Floor heating (BHT-002-GxLW)"));
        page->printf_P(HTTP_COMBOBOX_ITEM, "1", (getThermostatModel() == 1 ? HTTP_SELECTED : ""), PSTR("Heating, Cooling, Ventilation (BAC-002-ALW)"));
    	page->printf_P(HTTP_COMBOBOX_END);

		// Temp precision
		page->printf_P(HTTP_COMBOBOX_BEGIN, PSTR("Temperature Precision (must match your hardware):"), "tp");
		page->printf_P(HTTP_COMBOBOX_ITEM, "05", (getTemperatureFactor() ==  2.0f ? HTTP_SELECTED : ""), PSTR("0.5 (default for most Devices)"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "10", (getTemperatureFactor() ==  1.0f ? HTTP_SELECTED : ""), PSTR("1.0 (untested)"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "01", (getTemperatureFactor() == 10.0f ? HTTP_SELECTED : ""), PSTR("0.1 (only if supported by hardware)"));
		page->printf_P(HTTP_COMBOBOX_END);

		//Checkbox with support for relay
		int rsMode=(this->isSupportingHeatingRelay() ? 1 :  (this->isSupportingCoolingRelay() ? 2 : 0));
		page->printf_P(HTTP_COMBOBOX_BEGIN, PSTR("Relay connected to GPIO Inputs:"), "rs");
		page->printf_P(HTTP_COMBOBOX_ITEM, "_", (rsMode == 0 ? HTTP_SELECTED : ""), PSTR("No Hardware Hack"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "h", (rsMode == 1 ? HTTP_SELECTED : ""), PSTR("Heating-Relay at GPIO 5"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "c", (rsMode == 2 ? HTTP_SELECTED : ""), PSTR("Cooling-Relay at GPIO 4"));
		page->printf_P(HTTP_COMBOBOX_END);

		// Calculated Heating 
		page->printf_P(HTTP_TEXT_FIELD_INTEGER, PSTR("Relay State Calculation: Deadzone/Deadband-Temperature (set here the same value as configured at Thermostat-Setup)"), "dz", 1, deadzoneTemp->getByte());

		// FloorSensor 
		page->printf_P(HTTP_CHECKBOX_OPTION, PSTR("Floor Sensor enabled"),
		"fs", "fs", (this->floorSensor->getBoolean() ? HTTP_CHECKED : ""), "", PSTR("Enabled"));

		// Switch back from manual temo
		page->printf_P(HTTP_CHECKBOX_OPTION, PSTR("Switch back to Auto mode from manual at next schedule period change"),
		"sb", "sb", (this->switchBackToAuto->getBoolean() ? HTTP_CHECKED : ""), "", PSTR("Enabled"));

		//ComboBox with weekday
    	byte dayOffset = getSchedulesDayOffset();
		page->printf_P(HTTP_COMBOBOX_BEGIN, "Workday schedules:", "ws");
        page->printf_P(HTTP_COMBOBOX_ITEM, "0", (dayOffset == 0 ? HTTP_SELECTED : ""), PSTR("Workday (1-5): Mon-Fri; Weekend (6 - 7): Sat-Sun"));
        page->printf_P(HTTP_COMBOBOX_ITEM, "1", (dayOffset == 1 ? HTTP_SELECTED : ""), PSTR("Workday (1-5): Sun-Thu; Weekend (6 - 7): Fri-Sat"));
        page->printf_P(HTTP_COMBOBOX_ITEM, "2", (dayOffset == 2 ? HTTP_SELECTED : ""), PSTR("Workday (1-5): Sat-Wed; Weekend (6 - 7): Thu-Fri"));
        page->printf_P(HTTP_COMBOBOX_ITEM, "3", (dayOffset == 3 ? HTTP_SELECTED : ""), PSTR("Workday (1-5): Fri-Tue; Weekend (6 - 7): Wed-Thu"));
        page->printf_P(HTTP_COMBOBOX_ITEM, "4", (dayOffset == 4 ? HTTP_SELECTED : ""), PSTR("Workday (1-5): Thu-Mon; Weekend (6 - 7): Tue-Wed"));
        page->printf_P(HTTP_COMBOBOX_ITEM, "5", (dayOffset == 5 ? HTTP_SELECTED : ""), PSTR("Workday (1-5): Wed-Sun; Weekend (6 - 7): Mon-Tue"));
        page->printf_P(HTTP_COMBOBOX_ITEM, "6", (dayOffset == 6 ? HTTP_SELECTED : ""), PSTR("Workday (1-5): Tue-Sat; Weekend (6 - 7): Sun-Mon"));
    	page->printf_P(HTTP_COMBOBOX_END);

		page->printf_P(HTTP_THERM_INFO);
		page->printf_P(HTTP_CONFIG_SAVEANDREBOOT_BUTTON);

		page->printf_P(HTTP_HOME_BUTTON);
		network->log()->notice(PSTR("Beca thermostat config page DONE"));
		return;
    }

    void saveConfigPage(AsyncWebServerRequest *request) override {
        const String model = getValueOrEmpty(request, "tm"), offset = getValueOrEmpty(request, "ws");
        if ((model != "0" && model != "1") || offset.length() != 1 || offset[0] < '0' || offset[0] > '6') {
            network->log()->warning(F("Invalid thermostat configuration ignored"));
            request->send(400, "text/plain", "Invalid thermostat model or day offset");
            return;
        }
        const String precision = getValueOrEmpty(request, "tp"), relay = getValueOrEmpty(request, "rs"), deadzone = getValueOrEmpty(request, "dz");
        if ((precision != "05" && precision != "10" && precision != "01") ||
            (relay != "_" && relay != "h" && relay != "c") ||
            deadzone.length() != 1 || deadzone[0] < '1' || deadzone[0] > '5') {
            request->send(400, "text/plain", "Invalid thermostat configuration");
            return;
        }
        network->sendMqttHassAutodiscover(true);
        network->log()->notice(PSTR("Save Beca config page"));
        this->thermostatModel->setByte(getValueOrEmpty(request, "tm").toInt());
        this->schedulesDayOffset->setByte(getValueOrEmpty(request, "ws").toInt());
		byte bb1 = 0;
		byte bb2 = 0;
		if (getValueOrEmpty(request, "rs") == "h"){
			bb1 |= BECABITS1_RELAY_HEAT;
		} else if (getValueOrEmpty(request, "rs") == "c"){
			bb1 |= BECABITS1_RELAY_COOL;
		} else {
			// default no relaus
		}
		if (getValueOrEmpty(request, "tp") == "10"){
			bb1 |= BECABITS1_TEMP_10;
		} else if (getValueOrEmpty(request, "tp") == "01"){
			bb1 |= BECABITS1_TEMP_01;
		} else {
			// default 0.5
		}
		bb1 |= ((getValueOrEmpty(request, "sb") == HTTP_TRUE) ? 0 : BECABITS1_SWITCHBACKOFF); //logic reversed!
		bb1 |= ((getValueOrEmpty(request, "fs") == HTTP_TRUE) ? BECABITS1_FLOORSENSOR : 0);
		this->becaBits1->setByte(bb1);
		this->becaBits2->setByte(bb2); // meets r2d2

		this->deadzoneTemp->setByte(constrain(getValueOrEmpty(request, "dz").toInt(), 1, 5));
    }

    void loop(unsigned long now) override {
    	if (state != nullptr) {
    		bool heating = false;
    		bool cooling = false;
    		if ((isSupportingHeatingRelay()) && (state != nullptr)) {
    			heating = digitalRead(PIN_STATE_HEATING_RELAY);
				this->state->setString(heating ? STATE_HEATING : STATE_OFF);
    		} else if ((isSupportingCoolingRelay()) && (state != nullptr)) {
    			cooling = digitalRead(PIN_STATE_COOLING_RELAY);
				this->state->setString(cooling ? STATE_COOLING : STATE_OFF);
    		}
    	}
        serviceSerial(now);

		// to tasks only every second
		if (now - lastLongLoop >= 1000){
			updateCurrentSchedulePeriod();
			lastLongLoop=now;
		}

    	//Heartbeat
    	//long now = millis();
    	if ((HEARTBEAT_INTERVAL > 0)
    			&& ((lastHeartBeat == 0)
    					|| (now - lastHeartBeat > HEARTBEAT_INTERVAL))) {
    		unsigned char heartBeatCommand[] =
    				{ 0x55, 0xAA, 0x00, 0x00, 0x00, 0x00 };
			network->log()->trace(F("sending heartBeatCommand"));
			network->logHeap(PSTR("HeartBeat"));
    		commandCharsToSerial(6, heartBeatCommand);
    		//commandHexStrToSerial("55 aa 00 00 00 00");
    		lastHeartBeat = now;
    	}
    	if (receivedSchedules()) {
    		//Notify schedules
    		if ((lastScheduleNotify == 0) && (now - lastScheduleNotify > MINIMUM_INTERVAL)) {
    			sendSchedulesToMqtt();
    			lastScheduleNotify = now;
    		}
    	}
        if (network->isMqttConnected()) {
            const bool online = isDeviceStateComplete();
            if (lastMcuAvailability != static_cast<int>(online) &&
                network->publishMqtt((String(network->getMqttTopic()) + "/tele/mcu").c_str(), online ? "Online" : "Offline", true))
                lastMcuAvailability = online;
        } else lastMcuAvailability = -1;
        if (mcuInitialized && now - lastMcuReceived > 60000UL) startMcuInitialize();
		if (!isMcuInitialized()) mcuInitialize();
		
		if (timeIsRequested && isMcuInitialized() &&  wClock->isValidTime()){
			if (lastTimeSent>0){
				// update time only if seconds == 30
				if (wClock->getSeconds()==30){
					timeIsRequestedSendZeroSecs=false;
					sendActualTimeToBeca(timeIsRequestedLocaltime);
					timeIsRequested=false;
				} else if (timeIsRequestedSendZeroSecs && wClock->getSeconds()%10==0 && now - lastTimeSent > 2000){
					sendActualTimeToBeca(timeIsRequestedLocaltime);
				}
			}  else {
				// send time immediately if it was never set, but do again at next full minute
				timeIsRequestedSendZeroSecs=true;
				sendActualTimeToBeca(timeIsRequestedLocaltime);
			}
		}
    }

    void serviceSerial(unsigned long now) {
        if (receiveIndex >= 0 && now - lastSerialByte > 1000UL) resetAll();
        while (Serial.available() > 0) {
            const unsigned char inChar = Serial.read();
            lastSerialByte = now;
            if (receiveIndex < -1 || receiveIndex >= static_cast<int>(sizeof(receivedCommand)) - 1) resetAll();
            receivedCommand[++receiveIndex] = inChar;
            if (receiveIndex < 2 && COMMAND_START[receiveIndex] != inChar) {
                resetAll();
                if (inChar == COMMAND_START[0]) receivedCommand[++receiveIndex] = inChar;
            } else if (receiveIndex == 5) {
                commandLength = receivedCommand[4] * 256 + receivedCommand[5];
                if (commandLength > static_cast<int>(sizeof(receivedCommand)) - 7) resetAll();
            } else if (commandLength >= 0 && receiveIndex == 6 + commandLength) {
                byte checksum = 0;
                for (int i = 0; i < receiveIndex; ++i) checksum += receivedCommand[i];
                if (checksum == inChar) {
                    lastMcuReceived = now;
                    processSerialCommand(now);
                }
                resetAll();
            }
        }
    }

    unsigned char* getCommand() {
    	return receivedCommand;
    }

    int getCommandLength() {
    	return commandLength;
    }

    String getCommandAsString(size_t length, unsigned char* command) {
        String result;
        if (length == 0 || length > sizeof(receivedCommand)) return result;
        result.reserve(length * 3);
        const char digits[] = "0123456789abcdef";
        for (size_t i = 0; i < length; ++i) {
            if (i) result += ' ';
            result += digits[command[i] >> 4];
            result += digits[command[i] & 15];
        }
        return result;
    }

	 String getIncomingCommandAsString() {
    	return getCommandAsString(commandLength + 6, receivedCommand);
    }

    void commandHexStrToSerial(String command) {
        command.trim();
        command.replace(" ", "");
        command.toLowerCase();
        const unsigned length = command.length() / 2;
        if (length < 6 || length > 128 || command.length() % 2) return;
        unsigned char cmd[128];
        for (unsigned i = 0; i < length; ++i) {
            const int high = getIndex(command.charAt(i * 2));
            const int low = getIndex(command.charAt(i * 2 + 1));
            if (high < 0 || low < 0) return;
            cmd[i] = high * 16 + low;
        }
        if (cmd[0] != 0x55 || cmd[1] != 0xaa || cmd[4] * 256U + cmd[5] != length - 6) return;
        commandCharsToSerial(length, cmd);
    }

    void commandCharsToSerial(unsigned int length, unsigned char* command) {
        if (!command || length < 6 || length > sizeof(receivedCommand) - 1) return;
        byte checksum = 0;
        for (unsigned i = 0; i < length; ++i) checksum += command[i];
        Serial.write(command, length);
        Serial.write(checksum);
        if (network->log()->isEnabled(LOG_LEVEL_TRACE))
            network->log()->trace(F("commandCharsToSerial: %s, ChckSum 0x%02x"),
                getCommandAsString(length, command).c_str(), checksum);
    }

    void queryAllDPs() {
    	//55 AA 00 08 00 00
    	unsigned char queryStateCommand[] = { 0x55, 0xAA, 0x00, 0x08, 0x00, 0x00 };
    	commandCharsToSerial(6, queryStateCommand);
    }

    void cancelConfiguration() {
    	reportNetworkToMcu(mcuNetworkMode::MCU_NETWORKMODE_NOTCONNECTED);
    }
	void reportNetworkToMcu(mcuNetworkMode state) {
		network->logHeap("sending networkMode to MCU");
		network->log()->trace(F("sending networkMode to Mcu: %d"), state);
		unsigned char mcuCommand[] = { 0x55, 0xaa, 0x00, 0x03, 0x00, 0x01,
				static_cast<unsigned char>(state) };
		commandCharsToSerial(7, mcuCommand);
		//  unsigned char configCommand[] = { 0x55, 0xAA, 0x00, 0x03, 0x00,
		//		0x01, 0x00 };
	}

	void sendActualTimeToBecaRequested(bool localtime) {
		timeIsRequested=true;
		timeIsRequestedLocaltime=localtime;
	}

    void sendActualTimeToBeca(bool localtime) {
        if (!wClock->isValidTime()) { sendActualTimeToBecaRequested(localtime); return; }
    	//Command: Set date and time
    	//                       OK YY MM DD HH MM SS Weekday
    	//DEC:                   01 19 02 15 16 04 18 05
    	//HEX: 55 AA 00 1C 00 08 01 13 02 0F 10 04 12 05
    	//DEC:                   01 19 02 20 17 51 44 03
    	//HEX: 55 AA 00 1C 00 08 01 13 02 14 11 33 2C 03
    	unsigned long epochTime = (localtime ? wClock->getEpochTimeLocal() : wClock->getEpochTime());
	epochTime = epochTime + (getSchedulesDayOffset() * 86400UL);
    	byte year = wClock->getYear(epochTime) % 100;
    	byte month = wClock->getMonth(epochTime);
    	byte dayOfMonth = wClock->getDay(epochTime);
    	byte hours = wClock->getHours(epochTime) ;
    	byte minutes = wClock->getMinutes(epochTime);
		// Tuya doc says: if localtime is requested: data[6] represents second, from 0 to 15. whaaa? divide by 4?
		// My BAC-002 and BHT-002 have another behaviour:
		// if secs is <30 it gets ceiled to 30
		// everything >59 gets floored to 59
		// so we set the clock after first ntp-sync to 0 seconds (gets rounded to 30), just to have a valid time immediately
		// then we renew seconds=0 every 10 seconds
		// finally we set at second 30 to real seconds (30, not 30/4)
		// and all further timesettings are executed at second 30
		// then we have a swiss clock in each room :)
	byte secondsDivider = 1;
        if (localtime) secondsDivider = SECONDS_DIVIDER;
        byte secondsDivided = wClock->getSeconds(epochTime) / secondsDivider;
    	byte dayOfWeek = getDayOfWeek();

		if (timeIsRequestedSendZeroSecs) secondsDivided=0;

		network->log()->trace(F("sendActual%sTimeToBeca %d + %d days: %02d.%02d.%02d %02d:%02d:%02d (/%d=%d) (dow: %d)" ),
		(localtime ? "Local" : "GMT"), epochTime, getSchedulesDayOffset(), year, month, dayOfMonth, hours, minutes,
			wClock->getSeconds(epochTime), secondsDivider, secondsDivided, dayOfWeek );
	unsigned char sendTimeCommand[] = { 0x55, 0xaa, 0x00, static_cast<byte>(localtime ? 0x1c : 0x0c), 0x00, 0x08,
    											0x01, year, month, dayOfMonth,
    											hours, minutes, secondsDivided, dayOfWeek};
    	commandCharsToSerial(14, sendTimeCommand);
		lastTimeSent=millis();
    }

    void bindWebServerCalls(AsyncWebServer* webServer) override {
    	String deviceBase("/things/");
    	deviceBase.concat(getId());
    	deviceBase.concat("/");
    	deviceBase.concat(SCHEDULES);
    	webServer->on(deviceBase.c_str(), HTTP_GET, [this](AsyncWebServerRequest *request){
			 sendSchedules(request);
		});
    }

    void handleUnknownMqttCallback(const String& stat_topic, const String& partialTopic, const String& payload, unsigned int length) override {
		network->log()->notice(F("handleUnknownMqttCallback %s|%s|%s" ), stat_topic.c_str(), partialTopic.c_str(), payload.c_str());
		// {"log":"handleUnknownMqttCallback home/test/stat/things/thermostat/properties / schedules / "}
    	if (partialTopic.startsWith(SCHEDULES)) {
		const String scheduleTopic = partialTopic.substring(SCHEDULES.length() + 1);
		if (scheduleTopic.equals("")) {
				if (length == 0) {
					//Send actual schedules
					network->log()->notice(PSTR("Empty payload for schedules -> send schedules..."));
				} else {
					//Set schedules
					network->log()->notice(PSTR("Payload for schedules -> set and send schedules..."));
                    WJsonParser parser;
                    byte previous[sizeof(schedules)];
                    memcpy(previous, schedules, sizeof(schedules));
                    schedulesChanged = false;
                    const bool valid = parser.parse(payload.c_str(),
                        [this](const char* key, const char* value) { processSchedulesKeyValue(key, value); },
                        [this](const char* key, const char* value) { return validSchedulesKeyValue(key, value); });
                    if (!valid || !validSchedulesOrder()) {
                        memcpy(schedules, previous, sizeof(schedules));
                        schedulesChanged = false;
                        network->log()->warning(F("Invalid schedule command ignored"));
                        return;
                    }
					if (schedulesChanged) {
						network->log()->notice(PSTR("Some schedules changed. Write to MCU..."));
						this->schedulesToMcu();
					} else {
						network->log()->notice(PSTR("No schedules changed."));
					}
				}
				sendSchedulesToMqtt();
    		} else {
    			//There are still some more topics after properties
    			network->log()->warning(PSTR("Longer topic for schedules -> not supported yet..."));

    		}
    	} else if (partialTopic.equals(MCUCOMMAND)) {
			//send to MCU
			network->log()->notice(PSTR("Received %s: %s"), MCUCOMMAND.c_str(), payload.c_str());
			commandHexStrToSerial(payload);
		} else if (partialTopic.equals("wifiap")) {
			network->log()->notice(PSTR("setDesiredModeAp"));
			network->setDesiredModeAp();
		} else if (partialTopic.equals("wififallback")) {
			network->log()->notice(PSTR("setDesiredModeAp"));
			network->setDesiredModeFallback();
		} else if (partialTopic.equals("wfistation")) {
			network->log()->notice(PSTR("setDesiredModeStation"));
			network->setDesiredModeStation();
		}
    }

	void sendSchedulesToMqtt(){
		WStringStream* response = network->getMQTTResponseStream();
		WJson json(response);
		json.beginObject();
		this->toJsonSchedules(&json, 0);// SCHEDULE_WORKDAY);
		this->toJsonSchedules(&json, 1);// SCHEDULE_SATURDAY);
		this->toJsonSchedules(&json, 2);// SCHEDULE_SUNDAY);
		json.endObject();
		String stat_topic = network->getMqttTopic() + (String)"/" + String(MQTT_STAT) + (String)"/things/" + String(getId()) + (String)"/";
		network->publishMqtt((stat_topic+SCHEDULES).c_str(), response);
	}


	int getSchedulesPeriod(const char* key) {
		if (strlen(key) == 3) {
			for (int i = 0; i < 6; i++) {
				if (SCHEDULES_PERIODS[i] == key[1]) {
					return i;
					break;
				}
			}
		}
		return -1;
	}

	int getSchedulesStartAddress(const char* key, byte period) {
		if (strlen(key) == 3) {
			if (key[0] == SCHEDULES_DAYS[0]) {
				return 0;
			} else if (key[0] == SCHEDULES_DAYS[1]) {
				return 18;
			} else if (key[0] == SCHEDULES_DAYS[2]) {
				return 36;
			}
		}
		return -1;
	}

	String getSchedulesValue(const char* key) {
		char buf[8];
		size_t size = sizeof buf;
		buf[0]=0;
		const int period = getSchedulesPeriod(key);
		if (period < 0) return String(buf);
		const int startAddr = getSchedulesStartAddress(key, period);
		if (startAddr < 0) return String(buf);
		if (key[2] == 'h') {
			snprintf(buf, size, "%02u:%02u", static_cast<unsigned>(schedules[startAddr + period * 3 + 1]), static_cast<unsigned>(schedules[startAddr + period * 3 + 0]));
		} else if (key[2] == 't') {
			//temperature
			char str_temp[6];
			double val = (double)(schedules[startAddr + period * 3 + 2]) / getTemperatureFactor();
			dtostrf(val, 4, 1, str_temp);
			 snprintf(buf, size, "%s", str_temp );
		}
		//network->log()->verbose(PSTR("getSch %s->%s"), key, buf);
		return String(buf);
	}
    bool validSchedulesKeyValue(const char* key, const char* value) {
        if (!key || !value || getSchedulesPeriod(key) < 0 || getSchedulesStartAddress(key, 0) < 0) return false;
        if (key[2] == 'h') {
            const size_t length = strlen(value);
            const size_t colon = length == 4 ? 1 : 2;
            if ((length != 4 && length != 5) || value[colon] != ':') return false;
            for (size_t i = 0; i < length; ++i)
                if (i != colon && (value[i] < '0' || value[i] > '9')) return false;
            return atoi(value) < 24 && atoi(value + colon + 1) < 60;
        }
        if (key[2] != 't' || !*value) return false;
        char* end;
        const double temperature = strtod(value, &end);
        const double encoded = temperature * getTemperatureFactor();
        const double minimum = getThermostatModel() == MODEL_BAC_002_ALW ? 10.0 : 5.0;
        return end != value && !*end && std::isfinite(temperature) && temperature >= minimum && temperature <= 35 &&
            encoded <= 255 && fabs(encoded - round(encoded)) < 0.001;
    }

    bool validSchedulesOrder() {
        for (unsigned day = 0; day < 3; ++day) {
            int previous = -1;
            for (unsigned period = 0; period < 6; ++period) {
                const unsigned index = day * 18 + period * 3;
                if (schedules[index] > 59 || schedules[index + 1] > 23) return false;
                const int minute = schedules[index + 1] * 60 + schedules[index];
                if (minute < previous) return false;
                previous = minute;
            }
        }
        return true;
    }

    bool processSchedulesKeyValue(const char* key, const char* value) {
        if (!validSchedulesKeyValue(key, value)) return false;
        const int period = getSchedulesPeriod(key);
        const int start = getSchedulesStartAddress(key, period) + period * 3;
        if (key[2] == 'h') {
            const char* colon = strchr(value, ':');
            const byte hour = atoi(value), minute = atoi(colon + 1);
            schedulesChanged |= schedules[start] != minute || schedules[start + 1] != hour;
            schedules[start] = minute;
            schedules[start + 1] = hour;
        } else {
            const byte temperature = static_cast<byte>(round(strtod(value, nullptr) * getTemperatureFactor()));
            schedulesChanged |= schedules[start + 2] != temperature;
            schedules[start + 2] = temperature;
        }
        return true;
    }

    void sendSchedules(AsyncWebServerRequest* request) {
    	WStringStream* response = network->getMQTTResponseStream();
    	WJson json(response);
    	json.beginObject();
    	this->toJsonSchedules(&json, 0);// SCHEDULE_WORKDAY);
    	this->toJsonSchedules(&json, 1);// SCHEDULE_SATURDAY);
    	this->toJsonSchedules(&json, 2);// SCHEDULE_SUNDAY);
    	json.endObject();
		request->send(200, APPLICATION_JSON, response->c_str());
    }

    virtual void toJsonSchedules(WJson* json, byte schedulesDay) {
    	byte startAddr = 0;
		char dayChar = SCHEDULES_DAYS[0];
		switch (schedulesDay) {
		case 1 :
			startAddr = 18;
			dayChar = SCHEDULES_DAYS[1];
			break;
		case 2 :
			startAddr = 36;
			dayChar = SCHEDULES_DAYS[2];
			break;
		default:
            // Day group 0 and unsupported groups retain the workday defaults.
            break;
		}
            char timeStr[8];
        char buffer[4];
    	buffer[0] = dayChar;
    	buffer[3] = '\0';
    	for (int i = 0; i < 6; i++) {
    		buffer[1] = SCHEDULES_PERIODS[i];
		snprintf(timeStr, sizeof(timeStr), "%02d:%02d", schedules[startAddr + i * 3 + 1], schedules[startAddr + i * 3 + 0]);
    		buffer[2] = 'h';
    		json->propertyString(buffer, timeStr);
    		buffer[2] = 't';
    		json->propertyDouble(buffer, (double) schedules[startAddr + i * 3 + 2]	/ getTemperatureFactor());
    	}
    }

	void setOnConfigurationRequest(THandlerFunction onConfigurationRequest) {
		this->onConfigurationRequest = std::move(onConfigurationRequest);
	}
	
	void setOnPowerButtonOn(THandlerFunction onPowerButtonOn) {
		this->onPowerButtonOn = std::move(onPowerButtonOn);
	}

    void schedulesToMcu() {
    	if (receivedSchedules()) {
    		//Changed schedules from MQTT server, send to mcu
    		//send the changed array to MCU
    		//per unit |MM HH TT|
    		//55 AA 00 06 00 3A 65 00 00 36|
    		//00 06 28|00 08 1E|1E 0B 1E|1E 0D 1E|00 11 2C|00 16 1E|
    		//00 06 28|00 08 28|1E 0B 28|1E 0D 28|00 11 28|00 16 1E|
    		//00 06 28|00 08 28|1E 0B 28|1E 0D 28|00 11 28|00 16 1E|
    		unsigned char scheduleCommand[64];
    		scheduleCommand[0] = 0x55;
    		scheduleCommand[1] = 0xaa;
    		scheduleCommand[2] = 0x00;
    		scheduleCommand[3] = 0x06;
    		scheduleCommand[4] = 0x00;
    		scheduleCommand[5] = 0x3a;
    		scheduleCommand[6] = schedulesDataPoint;
    		scheduleCommand[7] = 0x00;
    		scheduleCommand[8] = 0x00;
    		scheduleCommand[9] = 0x36;
    		for (int i = 0; i < 54; i++) {
    			scheduleCommand[i + 10] = schedules[i];
    		}
    		commandCharsToSerial(64, scheduleCommand);
    		//notify change
    		this->notifySchedules();
			updateCurrentSchedulePeriod();
			updateTargetTemperature();
			updateModeAndAction();
    	}
    }

    String getFanMode() {
        return (fanMode != nullptr ? fanMode->c_str() : FAN_MODE_NONE);
    }

    byte getFanModeAsByte() {
    	if (fanMode != nullptr) {
    	   	if (fanMode->equalsString(FAN_MODE_AUTO)) {
    	   		return 0x00;
    	   	} else if (fanMode->equalsString(FAN_MODE_HIGH)) {
    	   		return 0x01;
    	   	} else if (fanMode->equalsString(FAN_MODE_MEDIUM)) {
    	   		return 0x02;
    	   	} else if (fanMode->equalsString(FAN_MODE_LOW)) {
    	   		return 0x03;
    	   	} else {
    	   		return 0xFF;
    	   	}
    	} else {
    		return 0xFF;
    	}
    }

    void fanModeToMcu(WProperty* property) {
    	if ((fanMode != nullptr) && (!this->receivingDataFromMcu)) {
			network->log()->notice(F("fanModeToMcu"));
    		byte dt = this->getFanModeAsByte();
    		if (dt != 0xFF) {
    			//send to device
    		    //auto:   55 aa 00 06 00 05 67 04 00 01 00
    			//low:    55 aa 00 06 00 05 67 04 00 01 03
    			//medium: 55 aa 00 06 00 05 67 04 00 01 02
    			//high:   55 aa 00 06 00 05 67 04 00 01 01
    			unsigned char deviceOnCommand[] = { 0x55, 0xAA, 0x00, 0x06, 0x00, 0x05,
    			                                    0x67, 0x04, 0x00, 0x01, dt};
    			commandCharsToSerial(11, deviceOnCommand);
    		}
    	}
    }

    String getSystemMode() {
    	return (systemMode != nullptr ? systemMode->c_str() : SYSTEM_MODE_NONE);
    }

    byte getSystemModeAsByte() {
    	if (systemMode != nullptr) {
    		if (systemMode->equalsString(SYSTEM_MODE_COOL)) {
    			return 0x00;
    		} else if (systemMode->equalsString(SYSTEM_MODE_HEAT)) {
    			return 0x01;
    		} else if (systemMode->equalsString(SYSTEM_MODE_FAN)) {
    			return 0x02;
    		} else {
    			return 0xFF;
    		}
    	} else {
    		return 0xFF;
    	}
    }

    void systemModeToMcu(WProperty* property) {
    	if ((systemMode != nullptr) && (!this->receivingDataFromMcu)) {
			network->log()->notice(F("systemModeToMcu"));
    		byte dt = this->getSystemModeAsByte();
    		if (dt != 0xFF) {
    			//send to device
    			//cooling:     55 AA 00 06 00 05 66 04 00 01 00
    			//heating:     55 AA 00 06 00 05 66 04 00 01 01
    			//ventilation: 55 AA 00 06 00 05 66 04 00 01 02
    			unsigned char deviceOnCommand[] = { 0x55, 0xAA, 0x00, 0x06, 0x00, 0x05,
    												0x66, 0x04, 0x00, 0x01, dt};
    			commandCharsToSerial(11, deviceOnCommand);
				updateCurrentSchedulePeriod();
				updateTargetTemperature();
    		}
    	}
    }

	bool isMcuInitialized(){
		return this->mcuInitialized;
	}


	void startMcuInitialize(){
        for (unsigned i = 0; i < STATE_COMPLETE; ++i) receivedStates[i] = false;
        lastMcuAttempt = 0;
        mcuRetryCount = 0;
		network->log()->warning(F("startMcuInitialize"));
		this->mcuInitialized=false;
		this->mcuInitializeState=1;
	}

	void mcuInitialize(){
        const unsigned long now = millis();
        if (mcuInitializeState == 2 || mcuInitializeState == 6) {
            const unsigned long timeout = mcuRetryCount >= 3 ? 30000UL : 3000UL;
            if (now - lastMcuAttempt < timeout) return;
            if (++mcuRetryCount > 3) mcuRetryCount = 0;
            mcuInitializeState = mcuInitializeState == 2 ? 1 : 5;
        }
		if (!this->receivingDataFromMcu) {
            lastMcuAttempt = now;
			switch (mcuInitializeState){
			case 1:
				network->log()->notice(F("Query Product Information"));
				//send to device 
				//Query Product Information:   55 aa 00 01 00 00
				{
					unsigned char mcuCommand[] = { 0x55, 0xAA, 0x00, 0x01, 0x00, 0x00 };
					commandCharsToSerial(6, mcuCommand);
				}
				mcuInitializeState++;
				break;
			case 2:
				/* wait for answer of 1 */
				break;
			case 3:
				network->log()->notice(F("Query the MCU working mode."));
				//send to device 
				//Query Product Information:   55 aa 00 02 00 00
				{
					unsigned char mcuCommand[] = { 0x55, 0xAA, 0x00, 0x02, 0x00, 0x00 };
					commandCharsToSerial(6, mcuCommand);
				}
				mcuInitializeState++;
				mcuInitializeState=5; // FIXME HY08WE: no answer from MCU on Working Mode Query 
				break;
			case 4:
				/* wait for answer of 3 */
				break;
			case 5:
				network->log()->notice(F("Query all DPs."));
				//send to device 
				//Query Product Information:   55 aa 00 08 00 00
				queryAllDPs();
				mcuInitializeState++;
				break;
			case 6:
				/* wait for answer of 5 */
				break;

			case 7:
				/* all done */
				mcuInitialized=true;
				this->mcuInitializeState=0;
				network->log()->notice(F("mcuInitialized"));
				updateTargetTemperature();
				updateModeAndAction();
				break;
			default:
                // Idle and unsupported states send no initialization commands.
                break;
			}
		}

	}

    bool isDeviceStateComplete() override {
    	if (network->isDebug()) {
    		return true;
    	}
        if (!mcuInitialized || millis() - lastMcuReceived > 60000UL) return false;
    	for (int i = 0; i < STATE_COMPLETE; i++) {
    		if (receivedStates[i] == false) {
    			return false;
    		}
    	}
    	return true;
    }

    byte getSchedulesDayOffset() {
    	return schedulesDayOffset->getByte();
    }

    String escapedForDiscovery(const char* value) {
        WStringStream escaped(strlen(value) * 6);
        WJson json(&escaped);
        json.streamPrintQuoted(&escaped, value);
        return String(escaped.c_str());
    }

    String discoveryId(const char* suffix) {
        String id = network->getIdx();
        bool valid = id.length() > 0;
        for (unsigned int i = 0; i < id.length(); ++i) {
            const char c = id.charAt(i);
            if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                  (c >= '0' && c <= '9') || c == '_' || c == '-')) valid = false;
        }
        // Keep legacy IDs; invalid discovery topic names were never supported by HA.
        if (!valid) {
            id = network->getMacAddress();
            id.replace(":", "");
        }
        id.concat(suffix);
        return id;
    }

	bool sendMqttHassAutodiscover(bool removeDiscovery){
		if (!hasDevicesWithHassAutodiscoverSupport()) return true;
        bool sent = true;
		if (!removeDiscovery)
            sent = network->publishMqtt((String(network->getMqttTopic()) + "/tele/mcu").c_str(),
                                       isDeviceStateComplete() ? "Online" : "Offline", true);
		network->log()->notice(F("sendMqttHassAutodiscover-%s"), (removeDiscovery ? "remove" : "add"));
		// https://www.home-assistant.io/docs/mqtt/discovery/
		String topic=F("homeassistant/climate/");
		String unique_id = discoveryId("_climate");
		topic.concat(unique_id);
		topic.concat(F("/config"));
		WStringStream buffer(SIZE_JSON_PACKET - 128);
        WStringStream* response = &buffer;
		response->flush();
		char str_temp[6];
		dtostrf(this->temperaturePrecision->getDouble(), 3, 1, str_temp);
		if (!removeDiscovery){
			if (getThermostatModel() == MODEL_BHT_002_GBLW ){
				response->printf_P(MQTT_HASS_AUTODISCOVERY_CLIMATE,
					escapedForDiscovery(unique_id.c_str()).c_str(),
					escapedForDiscovery(network->getFirmwareVersion().c_str()).c_str(),
					escapedForDiscovery(network->getMacAddress().c_str()).c_str(),
					escapedForDiscovery(network->getIdx()).c_str(),
					escapedForDiscovery(network->getApplicationName().c_str()).c_str(),
					escapedForDiscovery(network->getFirmwareVersion().c_str()).c_str(),
					escapedForDiscovery(network->getDeviceIp().toString().c_str()).c_str(),
					escapedForDiscovery(network->getMqttTopic()).c_str(),
					str_temp, str_temp
				);
			} else if (getThermostatModel() == MODEL_BAC_002_ALW ){
				response->printf_P(MQTT_HASS_AUTODISCOVERY_AIRCO,
					escapedForDiscovery(unique_id.c_str()).c_str(),
					escapedForDiscovery(network->getFirmwareVersion().c_str()).c_str(),
					escapedForDiscovery(network->getMacAddress().c_str()).c_str(),
					escapedForDiscovery(network->getIdx()).c_str(),
					escapedForDiscovery(network->getApplicationName().c_str()).c_str(),
					escapedForDiscovery(network->getFirmwareVersion().c_str()).c_str(),
					escapedForDiscovery(network->getDeviceIp().toString().c_str()).c_str(),
					escapedForDiscovery(network->getMqttTopic()).c_str(),
					str_temp, str_temp
				);
			}
		}
		sent = !response->overflowed() && network->publishMqtt(topic.c_str(), response, true) && sent;
		response->flush();

		unique_id = discoveryId("_sensor");
		topic=F("homeassistant/sensor/"); 
		topic.concat(unique_id);
		topic.concat(F("/config"));
		if (!removeDiscovery){
				response->printf_P(MQTT_HASS_AUTODISCOVERY_SENSOR,
				escapedForDiscovery(unique_id.c_str()).c_str(),
				escapedForDiscovery(network->getFirmwareVersion().c_str()).c_str(),
				escapedForDiscovery(network->getMacAddress().c_str()).c_str(),
				escapedForDiscovery(network->getMqttTopic()).c_str()
			);
		}
		sent = !response->overflowed() && network->publishMqtt(topic.c_str(), response, true) && sent;
		response->flush();

        {
			unique_id = discoveryId("_floorsensor");
			topic=F("homeassistant/sensor/"); 
			topic.concat(unique_id);
			topic.concat(F("/config"));
			if (!removeDiscovery && getThermostatModel() == MODEL_BHT_002_GBLW && this->floorSensor->getBoolean()){
				response->printf_P(MQTT_HASS_AUTODISCOVERY_SENSORFLOOR,
					escapedForDiscovery(unique_id.c_str()).c_str(),
					escapedForDiscovery(network->getFirmwareVersion().c_str()).c_str(),
					escapedForDiscovery(network->getMacAddress().c_str()).c_str(),
					escapedForDiscovery(network->getMqttTopic()).c_str()
				);
			}
			sent = !response->overflowed() && network->publishMqtt(topic.c_str(), response, true) && sent;
			response->flush();
		}

		unique_id = discoveryId("_rssi");
		topic=F("homeassistant/sensor/"); 
		topic.concat(unique_id);
		topic.concat(F("/config"));
		if (!removeDiscovery){
			response->printf_P(MQTT_HASS_AUTODISCOVERY_SENSORRSSI,
				escapedForDiscovery(unique_id.c_str()).c_str(),
				escapedForDiscovery(network->getFirmwareVersion().c_str()).c_str(),
				escapedForDiscovery(network->getMacAddress().c_str()).c_str(),
				escapedForDiscovery(network->getMqttTopic()).c_str()
			);
		}
		sent = !response->overflowed() && network->publishMqtt(topic.c_str(), response, true) && sent;
		response->flush();
		
		unique_id = discoveryId("_ip");
		topic=F("homeassistant/sensor/"); 
		topic.concat(unique_id);
		topic.concat(F("/config"));
		if (!removeDiscovery){
			response->printf_P(MQTT_HASS_AUTODISCOVERY_SENSORIP,
				escapedForDiscovery(unique_id.c_str()).c_str(),
				escapedForDiscovery(network->getFirmwareVersion().c_str()).c_str(),
				escapedForDiscovery(network->getMacAddress().c_str()).c_str(),
				escapedForDiscovery(network->getMqttTopic()).c_str()
			);
		}
		sent = !response->overflowed() && network->publishMqtt(topic.c_str(), response, true) && sent;
		response->flush();
		return sent;
	}

protected:

    byte getThermostatModel() {
    	return this->thermostatModel->getByte();
    }

    bool isSupportingHeatingRelay() {
        return this->supportingHeatingRelay->getBoolean();
    }

    bool isSupportingCoolingRelay() {
        return this->supportingCoolingRelay->getBoolean();
    }

	double getTemperaturePrecision() {
		return this->temperaturePrecision->getDouble();
	}
	double getTemperatureFactor() {
		return 1 / this->temperaturePrecision->getDouble();
	}

private:
    WClock *wClock;
    int receiveIndex;
    int commandLength;
	unsigned long lastHeartBeat;
	unsigned long lastTimeRequested;
	unsigned long lastTimeSent;
    unsigned char receivedCommand[1024];
    boolean receivingDataFromMcu;
    double targetTemperatureManualMode;
    WProperty* deviceOn;
    WProperty* state;
    WProperty* targetTemperature;
    WProperty* actualTemperature;
    WProperty* actualFloorTemperature;
	WProperty* mode;
	WProperty* preset;
	WProperty* action;
	WProperty* schedulesMode;
	WProperty* holdState;
    WProperty* systemMode;
    WProperty* fanMode;
    WProperty* ecoMode;
    WProperty* locked;
	WProperty *becaBits1;
	WProperty *becaBits2;
    byte schedules[54];
    boolean receivedStates[STATE_COMPLETE];
    byte schedulesDataPoint;
    WProperty* thermostatModel;
    WProperty *supportingHeatingRelay;
	WProperty *supportingCoolingRelay;
	WProperty *deadzoneTemp;
	WProperty *temperaturePrecision;
	WProperty *switchBackToAuto;
	WProperty *floorSensor;
    WProperty* ntpServer;
    WProperty* schedulesDayOffset;
	WProperty *mcuId;
    THandlerFunction onConfigurationRequest;
	THandlerFunction onPowerButtonOn;
    unsigned long lastNotify, lastScheduleNotify, lastLongLoop;
    bool schedulesChanged;
	int currentSchedulePeriod;
	bool timeIsRequested, timeIsRequestedLocaltime, timeIsRequestedSendZeroSecs;

    bool mcuInitialized;
    int mcuInitializeState;
    unsigned long lastSerialByte = 0;
    unsigned long lastMcuReceived = 0;
    unsigned long lastMcuAttempt = 0;
    unsigned mcuRetryCount = 0;
    int lastMcuAvailability = -1;


	double oldActualTemperature, oldTargetTemperature;

    int getIndex(unsigned char c) {
	const unsigned char HEX_DIGITS[] = { '0', '1', '2', '3', '4', '5', '6', '7', '8',
    			'9', 'a', 'b', 'c', 'd', 'e', 'f' };
    	int result = -1;
    	for (int i = 0; i < 16; i++) {
    		if (c == HEX_DIGITS[i]) {
    			result = i;
    			break;
    		}
    	}
    	return result;
    }

    byte getDayOfWeek() {
    	unsigned long epochTime = wClock->getEpochTimeLocal();
	epochTime = epochTime + (getSchedulesDayOffset() * 86400UL);
    	byte dayOfWeek = wClock->getWeekDay(epochTime);
    	//make sunday a seven
    	dayOfWeek = (dayOfWeek ==0 ? 7 : dayOfWeek);
    	return dayOfWeek;
    }

    bool isWeekend() {
    	byte dayOfWeek = getDayOfWeek();
    	return ((dayOfWeek == 6) || (dayOfWeek == 7));
    }

	void logIncomingCommand(const char * message, int logLevel=LOG_LEVEL_TRACE){
		network->log()->printLevel(logLevel, F("MCU: %s;%s"), message,
		this->getIncomingCommandAsString().c_str());
	}

    static int32_t decodeMcuValue(const unsigned char* bytes) {
        const uint32_t value = (static_cast<uint32_t>(bytes[0]) << 24) |
            (static_cast<uint32_t>(bytes[1]) << 16) | (static_cast<uint32_t>(bytes[2]) << 8) | bytes[3];
        return value <= INT32_MAX ? static_cast<int32_t>(value) : -1 - static_cast<int32_t>(~value);
    }

    void processSerialCommand(unsigned long now) {
        if (commandLength < 0 || commandLength > static_cast<int>(sizeof(receivedCommand)) - 7) return;
        if ((receivedCommand[3] == 0 || receivedCommand[3] == 5) && commandLength < 1) return;
        if (receivedCommand[3] == 7) {
            if (commandLength < 4 || receivedCommand[4] != 0 ||
                receivedCommand[8] * 256 + receivedCommand[9] != commandLength - 4) return;
        }
    	if (commandLength > -1) {
			bool knownCommand = false;
    		//unknown
    		//55 aa 00 00 00 00
    		this->receivingDataFromMcu = true;
			// header 
			if (receivedCommand[0] == 0x55 && receivedCommand[1] == 0xaa) {
				//version
				if (receivedCommand[2] == 0x00 || receivedCommand[2] == 0x01 || receivedCommand[2] == 0x03 ){
					if (receivedCommand[3] == 0x00) {
						switch (receivedCommand[6]) {
						case 0x00:
						case 0x01:
							knownCommand = true;
							//ignore, heartbeat MCU
							//55 aa 01 00 00 01 01
							//55 aa 01 00 00 01 00
							if (receivedCommand[6] == 0x00){
                                if (mcuInitialized) startMcuInitialize();
								network->log()->notice(F("MCU sent first heart beat") );
							}
							break;
						default:
                            // Keep unrecognized heartbeat values on the unknown-command path.
                            break;
						}
					} else if (receivedCommand[3] == 0x02) {
						//ignore, MCU response to working mode
						//55 aa 01 02 00 00
						network->log()->trace(F("MCU working mode %d %d"), receivedCommand[4] , receivedCommand[5] );
						if (mcuInitializeState==4) mcuInitializeState++;
						knownCommand = true;
					} else if (receivedCommand[3] == 0x03) {
						//ignore, MCU response to wifi state
						//55 aa 01 03 00 00
						network->log()->trace(F("MCU wifi state response"));
						knownCommand = true;
					} else if (receivedCommand[3] == 0x04) {
						//Setup initialization request
						// long press DOWN-button during state off
						// long press DOWN+POWER-buttons during state on
						// in second mode no WifiModeCommands (reportNetworkToMcu) are accepted
						//received: 55 aa 01 04 00 00
						
						knownCommand = true;
						network->log()->trace(F("MCU sent wifi reset"));
						if (onConfigurationRequest) {
							//send answer: 55 aa 00 04 00 01 00
							unsigned char configCommand[] = { 0x55, 0xAA, 0x00, 0x04, 0x00,
									0x00 };
							commandCharsToSerial(6, configCommand);
							onConfigurationRequest();
						}
					} else if (receivedCommand[3] == 0x05) {
						// select AP mode
						//received: 55 aa 01 05 00 01 XX   ( 00 = smartconfig, 01 = AP mode)
						// not currently sent my MCU
						knownCommand = true;
						network->log()->trace(F("MCU requests wifi mode %d"), receivedCommand[6] );
						if (onConfigurationRequest) {
							//send answer: 55 aa 00 04 00 01 00
							unsigned char configCommand[] = { 0x55, 0xAA, 0x00, 0x05, 0x00,
									0x00, 0x04 };
							commandCharsToSerial(6, configCommand);
							onConfigurationRequest();
						}
					} else if (receivedCommand[3] == 0x07) {
						bool changed = false;
						bool newChanged = false;
						bool schedulesChanged = false;
						bool newB;
						double newValue;
						byte newByte;
						byte commandLength = receivedCommand[5];
						//Status report from MCU
						switch (receivedCommand[6]) {
						case 0x01:
							if (commandLength == 0x05) {
								//device On/Off
								//55 aa 00 06 00 05 01 01 00 01 00|01
								newB = (receivedCommand[10] == 0x01);
								changed = ((changed) || (newChanged=(newB != deviceOn->getBoolean())));
								deviceOn->setBoolean(newB);
								receivedStates[0] = true;
								logIncomingCommand("deviceOn_x01", (newChanged ? LOG_LEVEL_TRACE : LOG_LEVEL_VERBOSE));
								knownCommand = true;
								if (newChanged && newB && onPowerButtonOn) onPowerButtonOn();
							}
							break;
						case 0x02:
							if (commandLength == 0x08) {
								//target Temperature for manual mode
								//e.g. 24.5C: 55 aa 01 07 00 08 02 02 00 04 00 00 00 31
								//                                    LENGT xx xx xx xx (longer values? (for 0.1?)) 
								newValue = decodeMcuValue(receivedCommand + 10) / getTemperatureFactor();
								changed = ((changed) || (newChanged=!WProperty::isEqual(targetTemperatureManualMode, newValue, 0.01)));
								targetTemperatureManualMode = newValue;
								if (changed) updateTargetTemperature();
								receivedStates[1] = true;
								logIncomingCommand(((String)"targetTemperature_x02:"+(String)targetTemperatureManualMode+"/"+(String)newValue).c_str(), (newChanged ? LOG_LEVEL_TRACE : LOG_LEVEL_VERBOSE));
								knownCommand = true;
							}
							break;

						case 0x03:
							if (commandLength == 0x08) {
								//actual Temperature
								//e.g. 23C: 55 aa 01 07 00 08 03 02 00 04 00 00 00 2e
								newValue = decodeMcuValue(receivedCommand + 10) / getTemperatureFactor();
								changed = ((changed) || (newChanged=!actualTemperature->equalsDouble(newValue)));
								actualTemperature->setDouble(newValue);
                                receivedStates[5] = true;
								logIncomingCommand("actualTemperature_x03", (newChanged ? LOG_LEVEL_TRACE : LOG_LEVEL_VERBOSE));
								knownCommand = true;
							}
							break;
						case 0x04:
							if (commandLength == 0x05) {
								//manualMode?
								newB = (receivedCommand[10] == 0x01);
								changed = (changed || (newChanged=((!newB && schedulesMode->equalsString(SCHEDULES_MODE_OFF)) || (newB && schedulesMode->equalsString(SCHEDULES_MODE_AUTO)))));
								schedulesMode->setString(newB ? SCHEDULES_MODE_OFF : SCHEDULES_MODE_AUTO);
								if (newChanged){
									network->log()->trace("Manual Mode newChanged to %s", (newB ? "on" : "off"));
									holdFromScheduler();
									updateCurrentSchedulePeriod();
									updateTargetTemperature();
									updateModeAndAction();
								}
								receivedStates[2] = true;
								logIncomingCommand("manualMode_x04", (newChanged ? LOG_LEVEL_TRACE : LOG_LEVEL_VERBOSE));
								knownCommand = true;
							}
							break;
						case 0x05:
							if (commandLength == 0x05) {
								//ecoMode
								newB = (receivedCommand[10] == 0x01);
								changed = ((changed) || (newChanged=(newB != ecoMode->getBoolean())));
								ecoMode->setBoolean(newB);
								receivedStates[3] = true;
								logIncomingCommand("ecoMode_x05", (newChanged ? LOG_LEVEL_TRACE : LOG_LEVEL_VERBOSE));
								knownCommand = true;
							}
							break;
						case 0x06:
							if (commandLength == 0x05) {
								//locked
								newB = (receivedCommand[10] == 0x01);
								changed = ((changed) || (newChanged=(newB != locked->getBoolean())));
								locked->setBoolean(newB);
								receivedStates[4] = true;
								logIncomingCommand("locked_x06", (newChanged ? LOG_LEVEL_TRACE : LOG_LEVEL_VERBOSE));
								knownCommand = true;
							}
							break;
						case 0x65: //MODEL_BHT_002_GBLW
						case 0x68: //MODEL_BAC_002_ALW
							if (commandLength == 0x3A) {
								//schedules 0x65 at heater model, 0x68 at fan model, example
								//55 AA 00 06 00 3A 65 00 00 36
								//00 07 28 00 08 1E 1E 0B 1E 1E 0D 1E 00 11 2C 00 16 1E
								//00 06 28 00 08 28 1E 0B 28 1E 0D 28 00 11 28 00 16 1E
								//00 06 28 00 08 28 1E 0B 28 1E 0D 28 00 11 28 00 16 1E
                                bool valid = true;
                                for (unsigned i = 0; i < 54; i += 3)
                                    valid &= receivedCommand[i + 10] < 60 && receivedCommand[i + 11] < 24;
                                if (!valid) break;
								this->schedulesDataPoint = receivedCommand[6];
								//this->thermostatModel->setByte(this->schedulesDataPoint == 0x65 ? MODEL_BHT_002_GBLW : MODEL_BAC_002_ALW);
								for (int i = 0; i < 54; i++) {
									newByte = receivedCommand[i + 10];
									schedulesChanged = (newChanged=((schedulesChanged) || (newByte != schedules[i])));
									schedules[i] = newByte;
								}
								logIncomingCommand(getThermostatModel() == MODEL_BHT_002_GBLW ? "schedules_x65" : "schedules_x68", (newChanged ? LOG_LEVEL_TRACE : LOG_LEVEL_VERBOSE));
								if (schedulesChanged){
									updateCurrentSchedulePeriod();
									updateTargetTemperature();
									updateModeAndAction();
								}
								knownCommand = true;
							} else if (receivedCommand[5] == 0x05) {
								//Unknown permanently sent from MCU
								//55 aa 01 07 00 05 68 01 00 01 01
								knownCommand = true;
							}
							break;
						case 0x66:
							if (commandLength == 0x08) {
								//MODEL_BHT_002_GBLW - actualFloorTemperature
								//55 aa 01 07 00 08 66 02 00 04 00 00 00 00
								newValue = decodeMcuValue(receivedCommand + 10) / getTemperatureFactor();
								if (actualFloorTemperature != nullptr) {
									changed = ((changed) || (newChanged=!actualFloorTemperature->equalsDouble(newValue)));
									actualFloorTemperature->setDouble(newValue);
								}
								logIncomingCommand("actualFloorTemperature_x66", (newChanged ? LOG_LEVEL_TRACE : LOG_LEVEL_VERBOSE));
								knownCommand = true;
							} else if (commandLength == 0x05) {
								//MODEL_BAC_002_ALW - systemMode
								//cooling:     55 AA 00 06 00 05 66 04 00 01 00
								//heating:     55 AA 00 06 00 05 66 04 00 01 01
								//ventilation: 55 AA 00 06 00 05 66 04 00 01 02
								//this->thermostatModel->setByte(MODEL_BAC_002_ALW);
								changed = ((changed) || (newChanged=(receivedCommand[10] != this->getSystemModeAsByte())));
								if (systemMode != nullptr) {
									switch (receivedCommand[10]) {
									case 0x00 :
										systemMode->setString(SYSTEM_MODE_COOL);
										break;
									case 0x01 :
										systemMode->setString(SYSTEM_MODE_HEAT);
										break;
									case 0x02 :
										systemMode->setString(SYSTEM_MODE_FAN);
										break;
									default:
                                        // Unsupported MCU modes retain the last accepted value.
                                        break;
									}
								}
								logIncomingCommand("systemMode_x66", (newChanged ? LOG_LEVEL_TRACE : LOG_LEVEL_VERBOSE));
								knownCommand = true;
							}
							break;
						case 0x67:
							if (commandLength == 0x05) {
								//fanSpeed
								//auto   - 55 aa 01 07 00 05 67 04 00 01 00
								//low    - 55 aa 01 07 00 05 67 04 00 01 03
								//medium - 55 aa 01 07 00 05 67 04 00 01 02
								//high   - 55 aa 01 07 00 05 67 04 00 01 01
								changed = ((changed) || (newChanged=(receivedCommand[10] != this->getFanModeAsByte())));
								if (fanMode != nullptr) {
									switch (receivedCommand[10]) {
									case 0x00 :
										fanMode->setString(FAN_MODE_AUTO);
										break;
									case 0x03 :
										fanMode->setString(FAN_MODE_LOW);
										break;
									case 0x02 :
										fanMode->setString(FAN_MODE_MEDIUM);
										break;
									case 0x01 :
										fanMode->setString(FAN_MODE_HIGH);
										break;
									default:
                                        // Unsupported MCU fan modes retain the last accepted value.
                                        break;
									}
								}
								logIncomingCommand("fanSpeed_x67", (newChanged ? LOG_LEVEL_TRACE : LOG_LEVEL_VERBOSE));
								knownCommand = true;
							}
							break;
						default:
                            // Unsupported data points retain the unknown-command path.
                            break;
						}
                        if (knownCommand) {
                            bool complete = true;
                            for (unsigned i = 0; i < STATE_COMPLETE; ++i) complete &= receivedStates[i];
                            if (mcuInitializeState == 6 && complete) mcuInitializeState = 7;
							if (changed) {
								network->log()->notice(F("ReceivedSerial/Changed"));
								notifyState();
							} else if (schedulesChanged) {
								network->log()->notice(F("ReceivedSerial/schedulesChanged"));
								notifySchedules();
							}
						}
					} else if (receivedCommand[3] == 0x01) {
						// Product ID Answer
						// 55 aa 01 01 00 15
						// HE AD VR CM LENGT 
						network->log()->notice(F("Product ID Answer from MCU (commandLength: %d)"), commandLength);
						logIncomingCommand("productId" , LOG_LEVEL_NOTICE);
						knownCommand=true;
						if (commandLength>=5){
							unsigned int len=0;
							len = ((byte)receivedCommand[4] <<8) + (byte)receivedCommand[5];
                            char buf[33];
                            if (len > sizeof(buf) - 1) len = sizeof(buf) - 1;
							for (unsigned int i=0;i<len;i++){
								buf[i]=static_cast<char>(receivedCommand[6+i]);
							}
							buf[len]=0;
							this->mcuId->setString(buf); 
							if (mcuInitializeState==2) mcuInitializeState++;
							network->log()->notice(F("Product ID: '%s'"), buf);

						}
					} else if (receivedCommand[3] == 0x0C) {
						//Request for time sync from MCU : 55 aa 01 0c 00 00
						network->log()->notice(F("Request for GMT time sync from MCU"));
						this->sendActualTimeToBecaRequested(false);
						lastTimeRequested=now;
						knownCommand=true;
					} else if (receivedCommand[3] == 0x1C) {
						//Request for time sync from MCU : 55 aa 01 1c 00 00
						network->log()->notice(F("Request for local time sync from MCU"));
						this->sendActualTimeToBecaRequested(true);
						lastTimeRequested=now;
						knownCommand=true;
					}

				} //55 aa 00|01
			} // 55 aa
			this->receivingDataFromMcu = false;
			if (!knownCommand){
				logIncomingCommand("unknown", LOG_LEVEL_WARNING);
			}
    	} // command length

		
    }

    void deviceOnToMcu(WProperty* property) {
    	if (!this->receivingDataFromMcu) {
       		//55 AA 00 06 00 05 01 01 00 01 01
       		byte dt = (this->deviceOn->getBoolean() ? 0x01 : 0x00);
       		unsigned char deviceOnCommand[] = { 0x55, 0xAA, 0x00, 0x06, 0x00, 0x05,
       		                                    0x01, 0x01, 0x00, 0x01, dt};
       		commandCharsToSerial(11, deviceOnCommand);
       		//notifyState();
     	}
    }
	/* gets called:
	 * If MCU sends changed manualTemperature
	 * If MCU sends mode Change
	 * If Scheduler Period Changed
	 */
    void updateTargetTemperature() {
		if (ecoMode->getBoolean()) {
			targetTemperature->setSuppressOnChange();
			if (getThermostatModel() == MODEL_BAC_002_ALW &&
			 (this->systemMode->equalsString(SYSTEM_MODE_COOL) || this->systemMode->equalsString(SYSTEM_MODE_FAN))){
				targetTemperature->setDouble(ECOMODETEMP_COOL);
			} else {
				targetTemperature->setDouble(ECOMODETEMP);
			}
			updateRelaySimulation();
		} else if ((this->currentSchedulePeriod != -1) && (schedulesMode->equalsString(SCHEDULES_MODE_AUTO))) {
			double temp = (double) schedules[this->currentSchedulePeriod + 2] / getTemperatureFactor();
			String p = String(currentSchedulePeriod>=36 ? SCHEDULES_DAYS[2] : (currentSchedulePeriod>=18 ? SCHEDULES_DAYS[1] : SCHEDULES_DAYS[0]));
			p.concat(SCHEDULES_PERIODS[(this->currentSchedulePeriod %18) /3]);
			network->log()->notice((String(PSTR("We take temperature from period '%s', Schedule temperature is "))+String(temp)).c_str() , p.c_str());
			targetTemperature->setSuppressOnChange();
			targetTemperature->setDouble(temp);
			updateRelaySimulation();
		} else {
			targetTemperature->setDouble(targetTemperatureManualMode);
		}
	}

	void updateCurrentSchedulePeriod() {
		if ((receivedSchedules()) && (wClock->isValidTime())) {
    		byte weekDay = wClock->getWeekDay();
    		weekDay += getSchedulesDayOffset();
    		weekDay = weekDay % 7;
    		int startAddr = (weekDay == 0 ? 36 : (weekDay == 6 ? 18 : 0));
    		int period = 0;
    		if (wClock->isTimeEarlierThan(schedules[startAddr + period * 3 + 1], schedules[startAddr + period * 3 + 0])) {
    			//Jump back to day before and last schedule of day
                weekDay = (weekDay + 6) % 7;
    			startAddr = (weekDay == 0 ? 36 : (weekDay == 6 ? 18 : 0));
    			period = 5;
    		} else {
    			//check the schedules in same day
    			for (int i = 1; i < 6; i++) {
    				if (i < 5) {
    					if (wClock->isTimeBetween(schedules[startAddr + i * 3 + 1], schedules[startAddr + i * 3 + 0],
    							                  schedules[startAddr + (i + 1) * 3 + 1], schedules[startAddr + (i + 1) * 3 + 0])) {
    						period = i;
    						break;
    					}
    				} else if (wClock->isTimeLaterThan(schedules[startAddr + 5 * 3 + 1], schedules[startAddr + 5 * 3 + 0])) {
    					period = 5;
    				}
    			}
    		}


			int newPeriod = startAddr + period * 3;
			if (/*(getThermostatModel() != MODEL_ET_81_W) && */ (this->switchBackToAuto->getBoolean()) &&
				(this->currentSchedulePeriod > -1) && (newPeriod != this->currentSchedulePeriod) &&
				(this->schedulesMode->equalsString(SCHEDULES_MODE_OFF))) {
				network->log()->notice(PSTR("Changed automatically back to Schedule from Manual"));
				this->schedulesMode->setString(SCHEDULES_MODE_AUTO);
			}
			if (this->currentSchedulePeriod!=newPeriod){
				this->currentSchedulePeriod = newPeriod;
				network->log()->notice(PSTR("SchedulePeriod Changed"));
				updateTargetTemperature();
			}
    	} else {
			this->currentSchedulePeriod = -1;
    	}
    }

    void onChangeTargetTemperature(WProperty* property) {
		network->log()->trace(PSTR("Got new targetTemperature"));
		bool force=false;
		if (schedulesMode->equalsString(SCHEDULES_MODE_AUTO)){
			network->log()->trace(PSTR("Got new targetTemperature: Switching from Schdule to Manual"));
			schedulesMode->setSuppressOnChange();
			schedulesMode->setString(SCHEDULES_MODE_OFF);
			force=true;
		}
		if (schedulesMode->equalsString(SCHEDULES_MODE_OFF)){
			// only set targetTemperatureManualMode and targetTemperatureManualModeToMcu() if current mode is Manual
			if (force || !WProperty::isEqual(targetTemperatureManualMode, this->targetTemperature->getDouble(), 0.01)) {
				targetTemperatureManualMode = this->targetTemperature->getDouble();
				network->log()->trace((String(PSTR("onChangeTargetTemperature, temp: "))+String(targetTemperatureManualMode)).c_str());
				targetTemperatureManualModeToMcu();
				schedulesMode->setString(SCHEDULES_MODE_OFF);
			} else {
				network->log()->trace((String(PSTR("setTargetTemperatureNoChange, temp: "))+String(this->targetTemperature->getDouble())).c_str());
			}
		}
		updateRelaySimulation();
    }

    void targetTemperatureManualModeToMcu() {
    	if (!this->receivingDataFromMcu) {
    		network->log()->notice((String(F("Set target Temperature (manual mode) to "))+String(targetTemperatureManualMode)).c_str());
    	    //55 AA 00 06 00 08 02 02 00 04 00 00 00 2C
			const uint32_t value = static_cast<uint32_t>(round(targetTemperatureManualMode * getTemperatureFactor()));
    	    unsigned char setTemperatureCommand[] = { 0x55, 0xAA, 0x00, 0x06, 0x00, 0x08,
    	    		0x02, 0x02, 0x00, 0x04,
                    static_cast<byte>(value >> 24), static_cast<byte>(value >> 16),
                    static_cast<byte>(value >> 8), static_cast<byte>(value)};
    	    commandCharsToSerial(14, setTemperatureCommand);
    	}
    }

	void onChangeActualTemperature(WProperty *property) {
		updateRelaySimulation();
	}

	void updateRelaySimulation() {
		if (!actualTemperature || !targetTemperature || !deadzoneTemp) return;
		double actual=actualTemperature->getDouble();
		double target=targetTemperature->getDouble();
		int dz=deadzoneTemp->getByte();
		bool isHeating=false;
		bool isCooling=false;
		if (this->deviceOn->getBoolean()){
			if (getThermostatModel() == MODEL_BHT_002_GBLW){
				isHeating=true;
			} else if (getThermostatModel() == MODEL_BAC_002_ALW){
				if (!systemMode) return;
				if (this->systemMode->equalsString(SYSTEM_MODE_HEAT)){
					isHeating=true;
				} else if (this->systemMode->equalsString(SYSTEM_MODE_COOL) || this->systemMode->equalsString(SYSTEM_MODE_FAN)){
					isCooling=true;
				}
			}
		}
		if (!isSupportingHeatingRelay() && isHeating){
			/*
			network->log()->notice(F("RelaySimulation: Check Heating %s -> %s / %s -> %s (%s)"),
			((String)oldActualTemperature).c_str(), ((String)actual).c_str(), 
			((String)oldTargetTemperature).c_str(), ((String)target).c_str(), ((String)(target-dz)).c_str());
			*/
			if (actual>=target){
				network->log()->notice(F("RelaySimulation: State OFF"));
				this->state->setString(STATE_OFF);
				updateModeAndAction();
			} else if ((actual != oldActualTemperature || target!=oldTargetTemperature) && actual <= (target - dz)){
				this->state->setString(STATE_HEATING);
				network->log()->notice(F("RelaySimulation: State HEATING"));
				updateModeAndAction();
			} else {
				network->log()->notice(F("RelaySimulation: NOOP"));
			}
		}
		if (!isSupportingCoolingRelay() && isCooling){
			if (actual<=target){
				network->log()->notice(F("RelaySimulation: State OFF"));
				this->state->setString(STATE_OFF);
				updateModeAndAction();
			} else if ((actual != oldActualTemperature || target != oldTargetTemperature) && actual >= (target + dz)){
		
				if (this->systemMode->equalsString(SYSTEM_MODE_FAN)){
					this->state->setString(STATE_FAN);
					network->log()->notice(F("RelaySimulation: State FAN"));
				} else {
					this->state->setString(STATE_COOLING);
					network->log()->notice(F("RelaySimulation: State COOLING"));
				}
				updateModeAndAction();
			}
		}
		oldActualTemperature=actual;
		oldTargetTemperature=target;
	}

    void schedulesModeToMcu(WProperty* property) {
    	if (!this->receivingDataFromMcu) {
			network->log()->trace(F("schedulesModeToMcu %s"), property->c_str());
        	//55 AA 00 06 00 05 04 04 00 01 01
        	byte dt = (schedulesMode->equalsString(SCHEDULES_MODE_OFF) ? 0x01 : 0x00);
        	unsigned char deviceOnCommand[] = { 0x55, 0xAA, 0x00, 0x06, 0x00, 0x05,
        	                                    0x04, 0x04, 0x00, 0x01, dt};
        	commandCharsToSerial(11, deviceOnCommand);
			if (!schedulesMode->equalsString(SCHEDULES_MODE_OFF) && !schedulesMode->equalsString(SCHEDULES_MODE_AUTO)){
				// correct to valid value
				this->schedulesMode->setString(SCHEDULES_MODE_AUTO);
			}
			holdStateRequest(property);
			updateCurrentSchedulePeriod();
			updateTargetTemperature();
			updateModeAndAction();
        }
    }

	void holdStateToScheduleMode(WProperty* property) {
		if (holdState->equalsString(HOLD_STATE_MANUAL)){
			this->ecoMode->setBoolean(false);
			this->schedulesMode->setString(SCHEDULES_MODE_OFF);
		} else if (holdState->equalsString(HOLD_STATE_SCHEDULER)){
			this->ecoMode->setBoolean(false);
			this->schedulesMode->setString(SCHEDULES_MODE_AUTO);
		} else if (holdState->equalsString(HOLD_STATE_OFF)){
			this->ecoMode->setBoolean(false);
		} else if (holdState->equalsString(HOLD_STATE_ECO)){
			this->ecoMode->setBoolean(true);
		} else {
			// correct to valid value
			this->ecoMode->setBoolean(false);
			this->holdState->setString(HOLD_STATE_SCHEDULER);
			this->schedulesMode->setString(SCHEDULES_MODE_AUTO);
		}
	}

	void holdStateRequest(WProperty* property) {
		if (holdState->equalsString(HOLD_STATE_ECO)){
		} else if (schedulesMode->equalsString(SCHEDULES_MODE_OFF)){
			this->holdState->setString(HOLD_STATE_MANUAL);
		} else {
			this->holdState->setString(HOLD_STATE_SCHEDULER);
		}	
	}

	void holdFromScheduler(){
		if (ecoMode->getBoolean()){
			//if ecoMode is On we must not return an holdState
			holdState->setString(HOLD_STATE_ECO);
		} else if (schedulesMode->equalsString(SCHEDULES_MODE_OFF)){
			holdState->setString(HOLD_STATE_MANUAL);
		} else {
			holdState->setString(HOLD_STATE_SCHEDULER);
		}
	}

    void ecoModeToMcu(WProperty* property) {
       	if (!this->receivingDataFromMcu) {
       		//55 AA 00 06 00 05 05 01 00 01 01
       		byte dt = (this->ecoMode->getBoolean() ? 0x01 : 0x00);
       		unsigned char deviceOnCommand[] = { 0x55, 0xAA, 0x00, 0x06, 0x00, 0x05,
       		                                    0x05, 0x01, 0x00, 0x01, dt};
       		commandCharsToSerial(11, deviceOnCommand);
			holdFromScheduler();
       	}
    }
 	void modeToMcu(WProperty* property) {
		network->log()->trace(F("modeToMcu %s"), property->c_str());
		if (getThermostatModel() == MODEL_BHT_002_GBLW) {
			if (this->mode->equalsString(MODE_OFF)){
				this->deviceOn->setBoolean(false);
				this->schedulesMode->setString(SCHEDULES_MODE_OFF);
			} else {
				this->deviceOn->setBoolean(true);
				if (this->mode->equalsString(MODE_AUTO)){
					this->schedulesMode->setString(SCHEDULES_MODE_AUTO);
				} else if (this->mode->equalsString(MODE_HEAT)){
					this->schedulesMode->setString(SCHEDULES_MODE_OFF);
				} else {
					network->log()->warning(F("modeToMcu unknown mode %s"), property->c_str());
				}
			}
		} else if (getThermostatModel() == MODEL_BAC_002_ALW){		
			if (this->mode->equalsString(MODE_OFF)){
				this->deviceOn->setBoolean(false);
			} else {
				this->deviceOn->setBoolean(true);
				if (this->mode->equalsString(MODE_AUTO)){
					// not really supported
					this->schedulesMode->setString(SCHEDULES_MODE_AUTO);
					this->holdState->setString(HOLD_STATE_SCHEDULER);
					this->fanMode->setString(FAN_MODE_AUTO);
					this->systemMode->setString(SYSTEM_MODE_COOL);
				} else if (this->mode->equalsString(MODE_HEAT)){
					this->systemMode->setString(SYSTEM_MODE_HEAT);
				} else if (this->mode->equalsString(MODE_COOL)){
					this->systemMode->setString(SYSTEM_MODE_COOL);
				} else if (this->mode->equalsString(MODE_FAN)){
					this->systemMode->setString(SYSTEM_MODE_FAN);
				} else {
					network->log()->warning(F("modeToMcu unknown mode %s"), property->c_str());
				}
			}
		}
	}


	void presetToMcu(WProperty* property) {
		network->log()->trace(F("presetToMcu %s"), property->c_str());
		if (this->mode->equalsString(MODE_OFF)){
			//noop
		} else if (this->preset->equalsString(PRESET_AWAY)){
			this->ecoMode->setBoolean(true);
		} else if (getThermostatModel() == MODEL_BAC_002_ALW && this->preset->equalsString(PRESET_SCHEDULER)){
			this->ecoMode->setBoolean(false);
			this->schedulesMode->setString(SCHEDULES_MODE_AUTO);
			this->holdState->setString(HOLD_STATE_SCHEDULER);
		} else {
			this->ecoMode->setBoolean(false);
			if (getThermostatModel() == MODEL_BAC_002_ALW){
				this->schedulesMode->setString(SCHEDULES_MODE_OFF);
				this->holdState->setString(HOLD_STATE_MANUAL);
			}
		}
	}

    void updateModeAndAction() {
		if (!this->deviceOn->getBoolean()){
			this->mode->setString(MODE_OFF);
		} else {
			if (getThermostatModel() == MODEL_BHT_002_GBLW){
				if (this->schedulesMode->equalsString(SCHEDULES_MODE_AUTO)){
					this->mode->setString(MODE_AUTO);
				} else {
					this->mode->setString(MODE_HEAT);
				}
			} else if (getThermostatModel() == MODEL_BAC_002_ALW){
				if (this->systemMode->equalsString(SYSTEM_MODE_HEAT)){
					this->mode->setString(MODE_HEAT);
				} else if (this->systemMode->equalsString(SYSTEM_MODE_COOL)){
					this->mode->setString(MODE_COOL);
				} else if (this->systemMode->equalsString(SYSTEM_MODE_FAN)){
					this->mode->setString(MODE_FAN);
				} else {
					// BUG
				}
			}
		}

		// mode to action
		if (this->mode->equalsString(MODE_OFF)) this->action->setString(ACTION_OFF);
		else if (getThermostatModel() == MODEL_BAC_002_ALW) {
			if (this->state->equalsString(STATE_OFF)){
				this->action->setString(ACTION_IDLE);
			} else if (this->systemMode->equalsString(SYSTEM_MODE_HEAT)){
				this->action->setString(ACTION_HEATING);
			} else if (this->systemMode->equalsString(SYSTEM_MODE_COOL)){
				this->action->setString(ACTION_COOLING);
			} else if (this->systemMode->equalsString(SYSTEM_MODE_FAN)){
				this->action->setString(ACTION_FAN);
			} 
		} else if (getThermostatModel() == MODEL_BHT_002_GBLW){
			if (this->state->equalsString(STATE_OFF)){
				this->action->setString(ACTION_IDLE);
			} else this->action->setString(ACTION_HEATING);
		}
	}


	void updatePreset() {
		if (this->ecoMode->getBoolean()){
			this->preset->setString(PRESET_AWAY);
		} else if (getThermostatModel() == MODEL_BAC_002_ALW && this->schedulesMode->equalsString(SCHEDULES_MODE_AUTO)){
			this->preset->setString(PRESET_SCHEDULER);
		} else {
			this->preset->setString(PRESET_NONE);
		}
	}

    void lockedToMcu(WProperty* property) {
       	if (!this->receivingDataFromMcu) {
       		//55 AA 00 06 00 05 06 01 00 01 01
       		byte dt = (this->locked->getBoolean() ? 0x01 : 0x00);
       		unsigned char deviceOnCommand[] = { 0x55, 0xAA, 0x00, 0x06, 0x00, 0x05,
       		                                    0x06, 0x01, 0x00, 0x01, dt};
       		commandCharsToSerial(11, deviceOnCommand);
       		//notifyState();
       	}
    }

    bool receivedSchedules() {
    	return ((network->isDebug()) || (this->schedulesDataPoint != 0x00));
    }

    void notifyState() {
    	lastNotify = 0;
    }

    void notifySchedules() {
    	lastScheduleNotify = 0;
    }

    void resetAll() {
       	receiveIndex = -1;
       	commandLength = -1;
    }



    void saveSettings(WProperty*) {
        byte bits = becaBits1->getByte();
        if (switchBackToAuto->getBoolean()) bits &= ~BECABITS1_SWITCHBACKOFF;
        else bits |= BECABITS1_SWITCHBACKOFF;
        // Stored properties persist through their existing settings callback.
        becaBits1->setByte(bits);
    }

	bool hasDevicesWithHassAutodiscoverSupport(byte device){
		for (unsigned int i=0; i<sizeof(devicesWithHassAutodiscoverSupport); i++){
			if (devicesWithHassAutodiscoverSupport[i]==device) return true;
		}
		return false;
	}

	bool hasDevicesWithHassAutodiscoverSupport(){
		return hasDevicesWithHassAutodiscoverSupport(getThermostatModel());
	}

	bool hasInfoPage() override {
		return true;
	}

	void printInfoPage(AsyncResponseStream* page) override {

		htmlTableRowTitle(page, F("MCU-Initialized:"));
		page->print((this->isMcuInitialized() ? "Yes" : "No"));
		htmlTableRowEnd(page);

		htmlTableRowTitle(page, F("MCU-ID:"));
		char * mcuid=htmlEscape(this->mcuId->c_str());
		page->print(mcuid);
		free(mcuid);
		htmlTableRowEnd(page);

		htmlTableRowTitle(page, F("Device On:"));
		page->print((deviceOn->getBoolean() ? "Device On" : "Device Off"));
		htmlTableRowEnd(page);

		htmlTableRowTitle(page, F("Current Temperature:"));
		page->print(actualTemperature->getDouble());
		htmlTableRowEnd(page);

		if (getThermostatModel() == MODEL_BHT_002_GBLW && this->floorSensor->getBoolean()){
			htmlTableRowTitle(page, F("Current Floor-Temperature:"));
			page->print(actualFloorTemperature->getDouble());
			htmlTableRowEnd(page);
		}

		htmlTableRowTitle(page, F("Target Temperature:"));
		page->print(targetTemperature->getDouble());
		htmlTableRowEnd(page);

		htmlTableRowTitle(page, F("Current Mode:"));
		page->print(mode->c_str());
		htmlTableRowEnd(page);

		htmlTableRowTitle(page, F("Schedules Mode:"));
		page->print(schedulesMode->c_str());
		htmlTableRowEnd(page);

		htmlTableRowTitle(page, F("Eco Mode:"));
		page->print((ecoMode->getBoolean() ? "Eco On" : "Eco Off"));
		htmlTableRowEnd(page);

		htmlTableRowTitle(page, F("Hold State:"));
		page->print(holdState->c_str());
		htmlTableRowEnd(page);

		if (getThermostatModel() == MODEL_BAC_002_ALW){
			htmlTableRowTitle(page, F("BAC-System Mode:"));
			page->print(systemMode->c_str());
			htmlTableRowEnd(page);

			htmlTableRowTitle(page, F("Fan Mode:"));
			page->print(fanMode->c_str());
			htmlTableRowEnd(page);
		}

		htmlTableRowTitle(page, F("Current Action:"));
		page->print(action->c_str());
		htmlTableRowEnd(page);

		if ((isSupportingHeatingRelay()) || (isSupportingCoolingRelay())) {
			htmlTableRowTitle(page, F("Current State:"));
			page->print(state->c_str());
			htmlTableRowEnd(page);
		}


		htmlTableRowTitle(page, F("Last Heartbeat:"));
		if (lastHeartBeat>0){
			page->print((millis() - lastHeartBeat) / 1000);
			page->print(" seconds ago");
		} else {
			page->print("no pulse");
		}
		htmlTableRowEnd(page);

		htmlTableRowTitle(page, F("Last Time Request:"));
		if (lastTimeRequested>0){
			page->print((millis() - lastTimeRequested) / 1000);
			page->print(" seconds ago");
		} else {
			page->print("never requested");
		}
		htmlTableRowEnd(page);

		htmlTableRowTitle(page, F("Last Time Sent:"));
		if (lastTimeSent>0){
			page->print((millis() - lastTimeSent) / 1000);
			page->print(" seconds ago");
		} else {
			page->print("never requested");
		}
		htmlTableRowEnd(page);
	}
};


#endif
