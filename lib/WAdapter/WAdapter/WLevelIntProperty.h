#ifndef W_LEVEL_INT_PROPERTY_H
#define W_LEVEL_INT_PROPERTY_H

#include "WProperty.h"

const char* ATTYPE_LEVELINT PROGMEM = "LevelIntProperty";

class WLevelIntProperty: public WProperty {
public:
	WLevelIntProperty(const char* id, const char* title, int minimum, int maximum)
        : WLevelIntProperty(id, title, WMinimum<int>(minimum), maximum) {}

    WLevelIntProperty(const char* id, const char* title, WMinimum<int> minimum, int maximum)
        : WProperty(id, title, INTEGER) {
		this->atType = ATTYPE_LEVELINT;
		this->minimum = minimum.value;
		this->maximum = maximum;
	}

	int getMinimum() {
		return minimum;
	}

	void setMinimum(int minimum) {
		this->minimum = minimum;
	}

	int getMaximum() {
		return maximum;
	}

	void setMaximum(int maximum) {
		this->maximum = maximum;
	}

	void toJsonStructureAdditionalParameters(WJson* json) override {
		json->propertyInteger(STR_MINIMUM, this->getMinimum());
		json->propertyInteger(STR_MAXIMUM, this->getMaximum());
	}

protected:

private:
	int minimum, maximum;
};

#endif
