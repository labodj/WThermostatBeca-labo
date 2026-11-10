#pragma once
#include "Arduino.h"
String genRandomMD5();
bool checkDigestAuthentication(const char*,const char*,const char*,const char*,const char*,bool,const char*,const char*,const char*);
