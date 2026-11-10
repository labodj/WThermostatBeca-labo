#pragma once
#include "Arduino.h"
#include <array>
struct Eeprom {
    std::array<byte,1024> bytes{}, buffer{};
    bool dirty=false;
    unsigned commits=0;
    bool commitOk=true;
    unsigned failCommits=0;
    bool begin(size_t size){assert(size==bytes.size());buffer=bytes;dirty=false;return true;}
    size_t length(){return bytes.size();}
    void end(){if(dirty)commit();dirty=false;}
    byte read(size_t address){assert(address<bytes.size());return buffer[address];}
    void write(size_t address,byte value){assert(address<bytes.size());dirty|=buffer[address]!=value;buffer[address]=value;}
    template<class T> void get(size_t address,T& value){assert(address+sizeof(T)<=bytes.size());memcpy(&value,buffer.data()+address,sizeof(T));}
    template<class T> void put(size_t address,const T& value){assert(address+sizeof(T)<=bytes.size());const byte* raw=reinterpret_cast<const byte*>(&value);for(size_t i=0;i<sizeof(T);++i)write(address+i,raw[i]);}
    bool commit(){if(!dirty)return true;++commits;if(failCommits){--failCommits;return false;}if(!commitOk)return false;bytes=buffer;dirty=false;return true;}
} inline EEPROM;
