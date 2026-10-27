#ifndef W_LEVEL_PROPERTY_H
#define W_LEVEL_PROPERTY_H

#include "WProperty.h"

const char* ATTYPE_LEVEL PROGMEM = "LevelProperty";

class WLevelProperty: public WProperty {
public:
	WLevelProperty(const char* id, const char* title, double minimum, double maximum)
        : WLevelProperty(id, title, WMinimum<double>(minimum), maximum) {}

    WLevelProperty(const char* id, const char* title, WMinimum<double> minimum, double maximum)
        : WProperty(id, title, DOUBLE) {
		this->atType = ATTYPE_LEVEL;
		this->minimum = minimum.value;
		this->maximum = maximum;
	}

	double getMinimum() {
		return minimum;
	}

	void setMinimum(double minimum) {
		this->minimum = minimum;
	}

	double getMaximum() {
		return maximum;
	}

	void setMaximum(double maximum) {
		this->maximum = maximum;
	}

	void toJsonStructureAdditionalParameters(WJson* json) override {
		json->propertyDouble(STR_MINIMUM, this->getMinimum());
		json->propertyDouble(STR_MAXIMUM, this->getMaximum());
	}

protected:

private:
	double minimum, maximum;
};

#endif
