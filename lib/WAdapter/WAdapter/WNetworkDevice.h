#ifndef NETWORKDEVICE_H
#define	NETWORKDEVICE_H

#include "Arduino.h"
#include <ESP8266WiFi.h>
#include <EEPROM.h>
#include "WDevice.h"

class WNetworkDev: public WDevice {
public:

    WNetworkDev(WNetwork* network, const String& applicationName) 
            : WDevice(network, "network", "network", network->getIdx(), DEVICE_TYPE_NETWORK) {
		
        this->providingConfigPage = false;
        this->configNeedsReboot = false;
        this->stateNotifyInterval = 30000;
        this->mainDevice = false;
        this->setMqttRetain(true);
        this->setVisibility(MQTT);

        lastLongLoop = lastVeryLongLoop = 0;
		
        /* properties */
        this->rssi = new WProperty("rssi", "rssi", INTEGER);
        this->rssi->setVisibility(MQTT);
        this->rssi->setReadOnly(true);
        this->rssi->setMqttSendChangedValues(true);
        this->rssi->setOnValueRequest([this](WProperty* p) {updateRssi();});
        this->addProperty(this->rssi);
    
    }

    virtual void printConfigPage(AsyncWebServerRequest *request, AsyncResponseStream* page) override {

    }
    void saveConfigPage(AsyncWebServerRequest* request) override {

    }

    void loop(unsigned long now) override {
        // to tasks only every second
        if (lastLongLoop + 1000 < now ){
            lastLongLoop=now;
        }
        // to tasks only every 30 seconds
        if (lastVeryLongLoop + 30000 < now ){
            lastVeryLongLoop=now;
        }

        // properties are getting read during stateNotify
    }

    void handleUnknownMqttCallback(const String&, const String&, const String&, unsigned int) override {}


    void updateRssi() {
        this->rssi->setInteger(WiFi.RSSI());
    }

    void connectionChange(){
        this->rssi->setInteger(WiFi.RSSI());
    }

private:
    WProperty* rssi;
    unsigned long lastLongLoop, lastVeryLongLoop;
};


#endif
