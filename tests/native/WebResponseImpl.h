#pragma once
#include "Arduino.h"

// Minimal response contract; the firmware build checks the actual SDK interface.
class AsyncAbstractResponse {
protected:
    int _code = 0;
    size_t _contentLength = 0;
    String _contentType;
    bool started = false;
    bool _started() const { return started; }
public:
    virtual ~AsyncAbstractResponse() = default;
    virtual bool _sourceValid() const { return false; }
    virtual size_t _fillBuffer(uint8_t*, size_t) { return 0; }
    bool addHeader(const char*, const char*) { return true; }
    void startForTest() { started = true; }
    size_t contentLength() const { return _contentLength; }
};
