#ifndef WEBSERVERHELPER_H
#define	WEBSERVERHELPER_H


#include <ESPAsyncWebServer.h>

const String& getValueOrEmpty(AsyncWebServerRequest* request, const char* name) {
    const auto* parameter = request->getParam(name, true);
    if (!parameter) parameter = request->getParam(name);
    return parameter ? parameter->value() : emptyString;
}


#endif
