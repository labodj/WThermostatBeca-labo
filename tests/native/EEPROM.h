#pragma once
#include "Arduino.h"
#include <array>
struct Eeprom {
    std::array<byte,640> bytes{};
    unsigned commits=0;
    bool begin(size_t size){assert(size==bytes.size());return true;}
    size_t length(){return bytes.size();}
    void end(){}
    byte read(size_t address){assert(address<bytes.size());return bytes[address];}
    void write(size_t address,byte value){assert(address<bytes.size());bytes[address]=value;}
    template<class T> void get(size_t address,T& value){assert(address+sizeof(T)<=bytes.size());memcpy(&value,bytes.data()+address,sizeof(T));}
    template<class T> void put(size_t address,const T& value){assert(address+sizeof(T)<=bytes.size());memcpy(bytes.data()+address,&value,sizeof(T));}
    bool commit(){++commits;return true;}
} inline EEPROM;
