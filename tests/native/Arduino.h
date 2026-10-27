#pragma once
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <cstdarg>
#include <functional>
#include <string>
#include <vector>
#include <cassert>
#include <cctype>
#include <climits>
using byte = uint8_t;
using boolean = bool;
#define PROGMEM
#define HEX 16
#define DEC 10
#define PSTR(s) (s)
#define snprintf_P snprintf
#define pgm_read_byte(p) (*(p))
struct __FlashStringHelper {};
using PGM_P = const char*;
#define F(s) reinterpret_cast<const __FlashStringHelper*>(s)
#define FPSTR(s) F(s)
inline unsigned long testMillis = 0;
inline unsigned long millis() { return testMillis; }
inline void yield() { ++testMillis; }
inline void delay(unsigned long value) { testMillis += value; }
template<class T, class L, class H> T constrain(T value,L low,H high) { return std::min<T>(high,std::max<T>(low,value)); }
class String : public std::string {
public:
    using std::string::string;
    String(std::string value) : std::string(value) {}
    String(const __FlashStringHelper* value) : std::string(reinterpret_cast<const char*>(value)) {}
    String(int value, int base = 10) { char b[64]; snprintf(b,sizeof(b),base==16?"%x":"%d",value); assign(b); }
    String(unsigned value, int base = 10) { char b[64]; snprintf(b,sizeof(b),base==16?"%x":"%u",value); assign(b); }
    String(long value) : std::string(std::to_string(value)) {}
    String(unsigned long value) : std::string(std::to_string(value)) {}
    String(double value) : std::string(std::to_string(value)) {}
    bool equals(const char* value) const { return compare(value)==0; }
    bool equals(String value) const { return compare(value)==0; }
    bool equalsIgnoreCase(const char* value) const { return strcasecmp(c_str(),value)==0; }
    long toInt() const { return strtol(c_str(),nullptr,10); }
    double toDouble() const { return strtod(c_str(),nullptr); }
    char charAt(size_t i) const { return i<size()?at(i):0; }
    bool endsWith(const char* value) const {size_t n=strlen(value);return size()>=n&&compare(size()-n,n,value)==0;}
    bool startsWith(const char* value) const { return find(value)==0; }
    bool startsWith(String value) const { return find(value)==0; }
    String substring(size_t a,size_t b) const { return a<size()?substr(a,b-a):""; }
    String substring(size_t a) const { return a<size()?substr(a):""; }
    int indexOf(const char* value) const { auto p=find(value);return p==npos?-1:static_cast<int>(p); }
    void toLowerCase(){std::transform(begin(),end(),begin(),[](unsigned char c){return std::tolower(c);});}
    void trim(){while(size()&&isspace(back()))pop_back();while(size()&&isspace(front()))erase(0,1);}
    void replace(const char* oldValue,const char* newValue){size_t p=0;while((p=find(oldValue,p))!=npos){std::string::replace(p,strlen(oldValue),newValue);p+=strlen(newValue);}}
    void concat(String value){append(value);}
};
inline String operator+(const char* a,const String& b){return std::string(a)+std::string(b);}
inline String operator+(const String& a,const char* b){return std::string(a)+b;}
inline String operator+(const String& a,const String& b){return std::string(a)+std::string(b);}
inline char* dtostrf(double number,signed char width,unsigned char precision,char* out){sprintf(out,"%*.*f",width,precision,number);return out;}
inline void itoa(int number,char* out,int base){sprintf(out,base==16?"%x":"%d",number);}
struct TestSerial {
    std::vector<byte> input, output;
    size_t position = 0;
    int available(){return position<input.size();}
    int read(){return input[position++];}
    size_t write(byte c){output.push_back(c);return 1;}
    size_t write(const byte* p,size_t n){output.insert(output.end(),p,p+n);return n;}
    void println(String){}
} inline Serial;
// glibc 2.38+ provides strlcpy, including a fortified inline on Ubuntu.
#if !defined(__GLIBC__) || __GLIBC__ < 2 || (__GLIBC__ == 2 && __GLIBC_MINOR__ < 38)
inline size_t strlcpy(char* out,const char* text,size_t capacity){size_t length=strlen(text);if(capacity){size_t n=std::min(length,capacity-1);memcpy(out,text,n);out[n]=0;}return length;}
#endif
