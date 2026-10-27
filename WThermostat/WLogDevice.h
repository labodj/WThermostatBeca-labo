#ifndef LOGDEVICE_H
#define	LOGDEVICE_H

#include "Arduino.h"
#include <ESP8266WiFi.h>
#include <EEPROM.h>
#include "../lib/WAdapter/WAdapter/WDevice.h"

const char* ID_LOGDEVICE PROGMEM = "logging";
const char* NAME_LOGDEVICE PROGMEM = "Logging";

const char* PROP_LOGLEVELBYTE PROGMEM = "logLevelByte";
const char* PROP_LOGLEVEL PROGMEM = "logLevel";
const char* TITL_LOGLEVEL PROGMEM = "logLevel";
const char* PROP_LOGLEVELWEB PROGMEM = "logLevelWeb";
const char* PROP_LOGLEVELWEBBYTE PROGMEM = "logLevelWebByte";

const char* PROP_LOGRES1 PROGMEM = "logres1";
const char* PROP_LOGRES2 PROGMEM = "logres2";
const char* PROP_LOGRES3 PROGMEM = "logres3";
const char* PROP_LOGRES4 PROGMEM = "logres4";

const char* ID_PAGE_LIVEWEBLOG PROGMEM = "weblog";
const char* TITLE_PAGE_LIVEWEBLOG PROGMEM = "Live WebLog";

const char* LOG_MODE_SILENT  PROGMEM = "silent";
const char* LOG_MODE_FATAL   PROGMEM = "fatal";
const char* LOG_MODE_ERROR   PROGMEM = "error";
const char* LOG_MODE_WARNING PROGMEM = "warning";
const char* LOG_MODE_NOTICE  PROGMEM = "notice";
const char* LOG_MODE_TRACE   PROGMEM = "trace";
const char* LOG_MODE_VERBOSE PROGMEM = "verbose";


const char* URI_WSLOG PROGMEM = "/wslog";

const static char HTTP_WEBLOG[]         PROGMEM = R"=====(
    <label><input type="checkbox" id="pauseLog"> Pause display (new messages are skipped)</label>
	<label>Live device log<textarea readonly id="t1" rows="18" name="t1"></textarea></label>
	<p><a href="/logging">Configure logging</a>. Verbose logging includes all MCU communication.</p>
    <form action="/thermostat_reinit" method="post"><button type="submit">Reinitialize thermostat</button></form>
)=====";



const static char HTTP_WEBLOG_SCRIPT[]             PROGMEM = R"=====(<script>
	var ws = null;
	var pt = null;
	function ping() {
		if (!ws) return;
		if (ws.readyState !== 1) return;
		ws.send("heartbeat");

	}
	function msg(m){
        if (eb('pauseLog').checked) return;
        eb('t1').value = (eb('t1').value + m).slice(-65536);
		eb('t1').scrollTop=99999;
	}
	function wsinit(){
		try {
			var url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + "/wslog";
			msg('Connecting to ' + url + '\n');
			ws = new WebSocket(url, ["log"]);
		} catch(e){
			msg('Failed to connect\n');
			setTimeout(function(){ wsinit(); }, 3000);
			return;
		}
		ws.onopen = function(){
			msg('Connected\n');
	        if (pt) clearInterval(pt);
			pt=setInterval(function(){ping();}, 3000);
		}
		ws.onmessage = function(e){
			msg(e.data+'\n');
		}
		ws.onclose = function(e){
            if (pt) clearInterval(pt);
			msg('WebSocket Connection Closed! '+e.reason+'\n\n');
			delete ws;
			setTimeout(function(){ wsinit(); }, 3000);
		}
		ws.onerror = function(err) {
			msg('WebSocket Error! \n\n');
			//ws.close();
		}
	}
	if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wsinit, {once:true});
    else wsinit();
</script>
)=====";

AsyncWebSocket wslog(URI_WSLOG);

class WLogDevice: public WDevice {
public:

    WLogDevice(WNetwork* network) 
        	: WDevice(network, ID_LOGDEVICE, NAME_LOGDEVICE, network->getIdx(), DEVICE_TYPE_LOG) {
		
		this->providingConfigPage = true;
		this->configNeedsReboot = false;
		this->mainDevice = false;
		this->visibility = MQTT;

		/* properties */

		if (network->getSettingsOld()){
			if (network->getSettingsOld()->getNetworkSettingsVersion()==NETWORKSETTINGS_PRE_FAS114){
				network->log()->notice(F("Reading WLogSettings PRE_FAS114"));
				network->getSettingsOld()->setByte(PROP_LOGLEVELBYTE, LOG_LEVEL_WARNING);
			} else if (network->getSettingsOld()->getApplicationSettingsVersion()==network->getSettingsOld()->getApplicationSettingsCurrent()-1){
				network->log()->notice(F("Reading WLogSettings FLAG_OPTIONS_APPLICATION -1"));
				network->getSettingsOld()->setByte(PROP_LOGLEVELBYTE, LOG_LEVEL_WARNING);
			}
		}

		logLevelByte=nullptr;
		logLevelWebByte=nullptr;
		this->logLevelByte = network->getSettings()->setByte(PROP_LOGLEVELBYTE,
			(network->getSettingsOld() && network->getSettingsOld()->existsSetting(PROP_LOGLEVELBYTE) ? network->getSettingsOld()->getByte(PROP_LOGLEVELBYTE) : LOG_LEVEL_WARNING));
		this->logLevelByte->setVisibility(NONE);
    	this->addProperty(logLevelByte);
		setlogLevelByte(constrain(getlogLevelByte(),LOG_LEVEL_SILENT, LOG_LEVEL_VERBOSE ));

		this->logLevelWebByte = network->getSettings()->setByte(PROP_LOGLEVELWEBBYTE,
			(network->getSettingsOld() && network->getSettingsOld()->existsSetting(PROP_LOGLEVELWEBBYTE) ? network->getSettingsOld()->getByte(PROP_LOGLEVELWEBBYTE) : LOG_LEVEL_TRACE));
        setlogLevelWebByte(constrain(getlogLevelWebByte(), LOG_LEVEL_SILENT, LOG_LEVEL_VERBOSE));
		this->logLevel = new WProperty(PROP_LOGLEVEL, TITL_LOGLEVEL, STRING, 8);
		this->logLevel->setAtType(PROP_LOGLEVEL);
		this->logLevel->addEnumString(LOG_MODE_SILENT);
		this->logLevel->addEnumString(LOG_MODE_FATAL);
		this->logLevel->addEnumString(LOG_MODE_ERROR);
		this->logLevel->addEnumString(LOG_MODE_WARNING);
		this->logLevel->addEnumString(LOG_MODE_NOTICE);
		this->logLevel->addEnumString(LOG_MODE_TRACE);
		this->logLevel->addEnumString(LOG_MODE_VERBOSE);
		this->logLevel->setVisibility(MQTT);
		this->addProperty(logLevel);
		this->logLevelWeb = new WProperty(PROP_LOGLEVELWEB, TITL_LOGLEVEL, STRING, 8);
		this->logLevelWeb->setAtType(PROP_LOGLEVELWEB);
		this->logLevelWeb->addEnumString(LOG_MODE_SILENT);
		this->logLevelWeb->addEnumString(LOG_MODE_FATAL);
		this->logLevelWeb->addEnumString(LOG_MODE_ERROR);
		this->logLevelWeb->addEnumString(LOG_MODE_WARNING);
		this->logLevelWeb->addEnumString(LOG_MODE_NOTICE);
		this->logLevelWeb->addEnumString(LOG_MODE_TRACE);
		this->logLevelWeb->addEnumString(LOG_MODE_VERBOSE);
		this->logLevelWeb->setVisibility(MQTT);
		this->addProperty(logLevelWeb);

		// some reserved Bytes
		network->getSettings()->setByte(PROP_LOGRES1, 255);
		network->getSettings()->setByte(PROP_LOGRES2, 255);
		network->getSettings()->setByte(PROP_LOGRES3, 255);
		network->getSettings()->setByte(PROP_LOGRES4, 255);

		// first apply stored Byte value from EEPROM
		this->setlogLevelMqtt(getlogLevelByte());
		this->setlogLevelWeb(getlogLevelWebByte());
		// then set Handler, because now logLevelByte follows String logLevel
		this->logLevel->setOnChange(std::bind(&WLogDevice::onlogLevelMqttChange, this, std::placeholders::_1));
		this->logLevelWeb->setOnChange(std::bind(&WLogDevice::onlogLevelWebChange, this, std::placeholders::_1));

		// Pages		
		WPage * weblogPage=new WPage(ID_PAGE_LIVEWEBLOG, TITLE_PAGE_LIVEWEBLOG);
		weblogPage->setPrintPage([this,weblogPage](AsyncWebServerRequest *request, AsyncResponseStream* page) {
			this->network->log()->notice(PSTR("weblog"));
			page->print(FPSTR(HTTP_WEBLOG));
			page->print(FPSTR(HTTP_HOME_BUTTON));
			page->print(FPSTR(HTTP_WEBLOG_SCRIPT));
		});
		this->addPage(weblogPage);
    
    }

    virtual void printConfigPage(AsyncWebServerRequest *request, AsyncResponseStream* page) override {
    	network->log()->notice(F("Log config page"));
    	page->printf_P(HTTP_CONFIG_PAGE_BEGIN, getId());
    	//ComboBox with model selection

		page->printf_P(HTTP_COMBOBOX_BEGIN, PSTR("MQTT Log Mode:"), "lm");
		page->printf_P(HTTP_COMBOBOX_ITEM, "0", (getlogLevelByte() == LOG_LEVEL_SILENT  ? HTTP_SELECTED : ""), PSTR("Logging Disabled"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "1", (getlogLevelByte() == LOG_LEVEL_FATAL   ? HTTP_SELECTED : ""), PSTR("Fatal Messages"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "2", (getlogLevelByte() == LOG_LEVEL_ERROR   ? HTTP_SELECTED : ""), PSTR("Error Messages"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "3", (getlogLevelByte() == LOG_LEVEL_WARNING ? HTTP_SELECTED : ""), PSTR("Warning Messages"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "4", (getlogLevelByte() == LOG_LEVEL_NOTICE  ? HTTP_SELECTED : ""), PSTR("Notice Messages"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "5", (getlogLevelByte() == LOG_LEVEL_TRACE   ? HTTP_SELECTED : ""), PSTR("Trace Messages"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "6", (getlogLevelByte() == LOG_LEVEL_VERBOSE ? HTTP_SELECTED : ""), PSTR("Verbose Messages"));
		page->printf_P(HTTP_COMBOBOX_END);

		page->printf_P(HTTP_COMBOBOX_BEGIN, PSTR("Web Log Mode:"), "lw");
		page->printf_P(HTTP_COMBOBOX_ITEM, "0", (getlogLevelWebByte() == LOG_LEVEL_SILENT  ? HTTP_SELECTED : ""), PSTR("Logging Disabled"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "1", (getlogLevelWebByte() == LOG_LEVEL_FATAL   ? HTTP_SELECTED : ""), PSTR("Fatal Messages"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "2", (getlogLevelWebByte() == LOG_LEVEL_ERROR   ? HTTP_SELECTED : ""), PSTR("Error Messages"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "3", (getlogLevelWebByte() == LOG_LEVEL_WARNING ? HTTP_SELECTED : ""), PSTR("Warning Messages"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "4", (getlogLevelWebByte() == LOG_LEVEL_NOTICE  ? HTTP_SELECTED : ""), PSTR("Notice Messages"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "5", (getlogLevelWebByte() == LOG_LEVEL_TRACE   ? HTTP_SELECTED : ""), PSTR("Trace Messages"));
		page->printf_P(HTTP_COMBOBOX_ITEM, "6", (getlogLevelWebByte() == LOG_LEVEL_VERBOSE ? HTTP_SELECTED : ""), PSTR("Verbose Messages"));
		page->printf_P(HTTP_COMBOBOX_END);

    	page->printf_P(HTTP_CONFIG_SAVE_BUTTON);
		page->printf_P(HTTP_HOME_BUTTON);
    }
    void saveConfigPage(AsyncWebServerRequest *request) override {
        const String mqtt = getValueOrEmpty(request, "lm"), web = getValueOrEmpty(request, "lw");
        if (mqtt.length() != 1 || mqtt[0] < '0' || mqtt[0] > '6' || web.length() != 1 || web[0] < '0' || web[0] > '6') {
            request->send(400, "text/plain", "Invalid log level"); return;
        }
		network->log()->notice(F("Log Beca config save lm=%s/%d"), getValueOrEmpty(request, "lm").c_str(), getValueOrEmpty(request, "lm").toInt());
		setlogLevelByte(constrain(getValueOrEmpty(request, "lm").toInt(),LOG_LEVEL_SILENT, LOG_LEVEL_VERBOSE ));
		this->setlogLevelMqtt(getlogLevelByte());
		network->log()->notice(F("Log Beca config save lw=%s/%d"), getValueOrEmpty(request, "lw").c_str(), getValueOrEmpty(request, "lw").toInt());
		setlogLevelWebByte(constrain(getValueOrEmpty(request, "lw").toInt(),LOG_LEVEL_SILENT, LOG_LEVEL_VERBOSE ));
		this->setlogLevelWeb(getlogLevelWebByte());
    }

    void loop(unsigned long now) override {
		wslog.cleanupClients();
    }

    void handleUnknownMqttCallback(const String&, const String&, const String&, unsigned int) override {}

	byte getlogLevelByte() {
		if (!logLevelByte) return LOG_LEVEL_SILENT;
		return logLevelByte->getByte();
	}
	byte getlogLevelWebByte() {
		if (!logLevelWebByte) return LOG_LEVEL_SILENT;
		return logLevelWebByte->getByte();
	}
	void setlogLevelByte(byte lm) {
		network->log()->notice(F("WLogDevice setlogLevelByte (%d)"), lm);
		logLevelByte->setByte(lm);
		setMinLogLevel();
	}
	void setlogLevelWebByte(byte lw) {
		network->log()->notice(F("WLogDevice setlogLevelWebByte (%d)"), lw);
		logLevelWebByte->setByte(lw);
		setMinLogLevel();
	}

	void setMinLogLevel(){
		int toSet=LOG_LEVEL_SILENT;
		if (getlogLevelByte() > toSet) toSet=getlogLevelByte();
		if (getlogLevelWebByte() > toSet) toSet=getlogLevelWebByte();
		network->log()->setLevelNetwork(toSet);

	}

    void onlogLevelMqttChange(WProperty* property) {
		if (property->equalsString(LOG_MODE_FATAL)) setlogLevelByte(LOG_LEVEL_FATAL);
		else if (property->equalsString(LOG_MODE_ERROR)) setlogLevelByte(LOG_LEVEL_ERROR);
		else if (property->equalsString(LOG_MODE_WARNING)) setlogLevelByte(LOG_LEVEL_WARNING);
		else if (property->equalsString(LOG_MODE_NOTICE)) setlogLevelByte(LOG_LEVEL_NOTICE);
		else if (property->equalsString(LOG_MODE_TRACE)) setlogLevelByte(LOG_LEVEL_TRACE);
		else if (property->equalsString(LOG_MODE_VERBOSE)) setlogLevelByte(LOG_LEVEL_VERBOSE);
		else setlogLevelByte(LOG_LEVEL_SILENT);
    }

	void onlogLevelWebChange(WProperty* property) {
		if (property->equalsString(LOG_MODE_FATAL)) setlogLevelWebByte(LOG_LEVEL_FATAL);
		else if (property->equalsString(LOG_MODE_ERROR)) setlogLevelWebByte(LOG_LEVEL_ERROR);
		else if (property->equalsString(LOG_MODE_WARNING)) setlogLevelWebByte(LOG_LEVEL_WARNING);
		else if (property->equalsString(LOG_MODE_NOTICE)) setlogLevelWebByte(LOG_LEVEL_NOTICE);
		else if (property->equalsString(LOG_MODE_TRACE)) setlogLevelWebByte(LOG_LEVEL_TRACE);
		else if (property->equalsString(LOG_MODE_VERBOSE)) setlogLevelWebByte(LOG_LEVEL_VERBOSE);
		else setlogLevelWebByte(LOG_LEVEL_SILENT);
	}

	void setlogLevelMqtt(byte lm) {
		const char * lms;
		lms=logLevelByteToString(lm);
		logLevel->setString(lms);
	}

	void setlogLevelWeb(byte lw) {
		const char * lws;
		lws=logLevelByteToString(lw);
		logLevelWeb->setString(lws);
	}

	const char * logLevelByteToString(byte lm) {
		if (lm == LOG_LEVEL_FATAL) return LOG_MODE_FATAL;
		else if (lm == LOG_LEVEL_ERROR) return LOG_MODE_ERROR;
		else if (lm == LOG_LEVEL_WARNING) return LOG_MODE_WARNING;
		else if (lm == LOG_LEVEL_NOTICE) return LOG_MODE_NOTICE;
		else if (lm == LOG_LEVEL_TRACE) return LOG_MODE_TRACE;
		else if (lm == LOG_LEVEL_VERBOSE) return LOG_MODE_VERBOSE;
		else return LOG_MODE_SILENT;
    }

	void sendLog(int level, const char* message) override {

		if (level<=getlogLevelWebByte()){
			wslog.printfAll(PSTR("%s: %s"), logLevelByteToString(level), message);
		}
		if (level<=getlogLevelByte()){
			String t = (String)network->getMqttTopic()+ "/" + MQTT_TELE +"/log" ;
			//network->log()->verbose(F("sendLog (%s)"), t.c_str());
			if (network->isMqttConnected()){
				network->publishMqtt(t.c_str(), ((String)logLevelByteToString(level)+": "+message).c_str());
			}
		}
	};

	

    void wsOnEvent(AsyncWebSocket*, AsyncWebSocketClient* client, AwsEventType type, void*, uint8_t*, size_t) {
        if (!client || client->status() != WS_CONNECTED || !client->canSend()) return;
        if (type == WS_EVT_CONNECT) {
            client->printf(PSTR("Hello WebSocket Client #%u\n"), client->id());
            client->printf(PSTR("Now you see all logs for logSeverity %s (or more important)\n"), logLevelWeb->c_str());
            client->ping();
        } else if (type == WS_EVT_DATA) client->ping();
    }

void webserverInitHook(AsyncWebServer *webServer) override {
    wslog.addMiddleware([this](AsyncWebServerRequest* request, const ArMiddlewareNext& next) {
        if (network->authorize(request)) next();
    });
	wslog.onEvent([this](AsyncWebSocket * server, AsyncWebSocketClient * client, AwsEventType type, void * arg, uint8_t *data, size_t len){
		this->wsOnEvent(server, client, type, arg, data, len);
	});
	webServer->addHandler(&wslog);
}
void webserverDeinitHook(AsyncWebServer *webServer) override {
	wslog.closeAll();
}

private:
	WProperty* logLevel;
	WProperty* logLevelByte;
	WProperty* logLevelWeb;
	WProperty* logLevelWebByte;

};


#endif
