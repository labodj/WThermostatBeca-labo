#ifndef W_COLOR_PROPERTY_H
#define W_COLOR_PROPERTY_H

#include "WProperty.h"


const char* ATTYPE_COLOR PROGMEM = "ColorProperty";

class WColorProperty: public WProperty {
public:
	WColorProperty(const char* id, const char* title, byte red, byte green, byte blue)
	: WProperty(id, title, STRING, 7), changeValue(false), red(0), green(0), blue(0) {
		this->atType = ATTYPE_COLOR;
		this->setRGB(red, green, blue);
		this->changeValue = false;
	}

	byte getRed() {
		return this->red;
	}

	byte getGreen() {
		return this->green;
	}

	byte getBlue() {
		return this->blue;
	}

	void setRGB(byte red, byte green, byte blue) {
		if (isNull() || (this->red != red) || (this->green != green) || (this->blue != blue)) {
			this->red = red;
			this->green = green;
			this->blue = blue;
			const char* rgbString = createRGBString();
			this->changeValue = true;
			setString(rgbString);
			this->changeValue = false;
			delete[] rgbString;
		}
	}

	const char* createRGBString() {
		// The caller owns this array, as in setRGB().
		char* result = new char[8];
		snprintf(result, 8, "#%02x%02x%02x", red, green, blue);
		return result;
	}

	void parseRGBString() {
		char buffer[3];
		buffer[2] = '\0';
		buffer[0] = c_str()[1];
		buffer[1] = c_str()[2];
		this->red = strtol(buffer, NULL, 16);
		buffer[0] = c_str()[3];
		buffer[1] = c_str()[4];
		this->green = strtol(buffer, NULL, 16);
		buffer[0] = c_str()[5];
		buffer[1] = c_str()[6];
		this->blue = strtol(buffer, NULL, 16);
	}

	bool canParse(const String& value) override {
		if (isReadOnly()) return false;
		if (value.startsWith("#") && value.length() == 7) {
			for (unsigned i = 1; i < 7; ++i)
				if (!isxdigit(static_cast<unsigned char>(value[i]))) return false;
			return true;
		}
		if (!value.startsWith("rgb(") || !value.endsWith(")")) return false;
		const char* cursor = value.c_str() + 4;
		for (unsigned i = 0; i < 3; ++i) {
			if (!isdigit(static_cast<unsigned char>(*cursor))) return false;
			char* end;
			errno = 0;
			const long component = strtol(cursor, &end, 10);
			if (errno || component > 255 || *end != (i < 2 ? ',' : ')')) return false;
			cursor = end + 1;
		}
		return *cursor == 0;
	}

	bool parse(const String& value) override {
		if (!canParse(value)) return false;
		if (value.startsWith("#")) {
			setString(value.c_str());
		} else {
			byte components[3];
			const char* cursor = value.c_str() + 4;
			for (unsigned i = 0; i < 3; ++i) {
				char* end;
				components[i] = static_cast<byte>(strtol(cursor, &end, 10));
				cursor = end + 1;
			}
			setRGB(components[0], components[1], components[2]);
		}
		return true;
	}


protected:
	virtual void valueChanged() override {
		if (!changeValue) {
			parseRGBString();
		}
	}
private:
	bool changeValue;
	byte red, green, blue;
};

#endif
