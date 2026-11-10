#ifndef W_TARGET_TEMPERATURE_PROPERTY_H
#define W_TARGET_TEMPERATURE_PROPERTY_H

#include "WProperty.h"

const char* ATTYPE_TARGETTEMPERATUR PROGMEM = "TargetTemperatureProperty";

class WTargetTemperatureProperty: public WProperty {
public:
	WTargetTemperatureProperty(const char* id, const char* title, float minimum = 5, float maximum = 35)
        : WTargetTemperatureProperty(id, title, WMinimum<float>(minimum), maximum) {}

    WTargetTemperatureProperty(const char* id, const char* title, WMinimum<float> minimum, float maximum = 35)
        : WProperty(id, title, DOUBLE), minimum(minimum.value), maximum(maximum) {
		this->atType = ATTYPE_TARGETTEMPERATUR;
		this->setUnit(STR_CELSIUS);
	}


    bool isValidValue(const String& value) override {
        return WProperty::isValidValue(value) && value.toDouble() >= minimum && value.toDouble() <= maximum;
    }

protected:

private:
    float minimum, maximum;

};

#endif
