#pragma once
#include "Arduino.h"
#define W_JSON_H
struct WJson {
    template<class...T> WJson& beginObject(T...){return *this;}
    template<class...T> WJson& endObject(T...){return *this;}
    template<class...T> WJson& beginArray(T...){return *this;}
    template<class...T> WJson& endArray(T...){return *this;}
    template<class...T> WJson& string(T...){return *this;}
    template<class...T> WJson& propertyString(T...){return *this;}
    template<class...T> WJson& propertyDouble(T...){return *this;}
    template<class...T> WJson& propertyInteger(T...){return *this;}
    template<class...T> WJson& propertyLong(T...){return *this;}
    template<class...T> WJson& propertyUnsignedLong(T...){return *this;}
    template<class...T> WJson& propertyByte(T...){return *this;}
    template<class...T> WJson& propertyBoolean(T...){return *this;}
};
#include "lib/WAdapter/WAdapter/WProperty.h"
struct WDevice {
    std::vector<WProperty*> properties;
    WProperty* getPropertyById(const char* name){for(auto* p:properties)if(!strcmp(p->getId(),name))return p;return nullptr;}
};
