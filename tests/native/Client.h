#pragma once
#include "Stream.h"
#include "IPAddress.h"
struct Client : Stream {
    std::vector<uint8_t> data, sent;
    size_t pos=0;
    bool live=true;
    int available(){return data.size()-pos;}
    int read(){return pos<data.size()?data[pos++]:-1;}
    int peek() override {return pos<data.size()?data[pos]:-1;}
    bool connected(){return live;}
    void stop(){live=false;}
    void flush(){}
    int connect(const char*,uint16_t){live=true;return 1;}
    int connect(IPAddress,uint16_t){live=true;return 1;}
    size_t write(const uint8_t* p,size_t n) override {sent.insert(sent.end(),p,p+n);return n;}
    size_t write(uint8_t c) override {sent.push_back(c);return 1;}
};
