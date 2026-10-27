#pragma once
#include "Arduino.h"
class Print {
public:
    virtual ~Print() = default;
    size_t printf(const char* format, ...){char buffer[8192];va_list args;va_start(args,format);int n=vsnprintf(buffer,sizeof(buffer),format,args);va_end(args);if(n<0)return 0;return write(reinterpret_cast<const uint8_t*>(buffer),std::min<size_t>(n,sizeof(buffer)-1));}
    virtual size_t write(uint8_t) { return 1; }
    virtual size_t write(const uint8_t* data,size_t size){for(size_t i=0;i<size;++i)write(data[i]);return size;}
    template<class T> size_t print(T value){String s(value);return write(reinterpret_cast<const uint8_t*>(s.c_str()),s.size());}
    size_t print(const char* value){return write(reinterpret_cast<const uint8_t*>(value),strlen(value));}
    template<class T> void println(T value){print(value);write(static_cast<uint8_t>('\n'));}
    size_t print(char value){return write(static_cast<uint8_t>(value));}
    size_t print(const char* value,int){return print(value);}
    template<class T> size_t print(T value,int){return print(value);}
    template<class... T> size_t printf_P(const char* format,T...args){char out[8192];int n=snprintf(out,sizeof(out),format,args...);assert(n>=0&&size_t(n)<sizeof(out));return write(reinterpret_cast<const uint8_t*>(out),n);}
};
class Stream : public Print {
public:
    virtual int available() = 0;
    virtual int read() = 0;
    virtual int peek() = 0;
    virtual void flush() = 0;
protected:
    unsigned long _startMillis;
};
