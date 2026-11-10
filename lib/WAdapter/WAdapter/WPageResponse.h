#ifndef W_PAGE_RESPONSE_H
#define W_PAGE_RESPONSE_H

#include <WebResponseImpl.h>
#include <Print.h>
#include <algorithm>
#include <cstring>
#include <new>

// Small allocations tolerate fragmented ESP8266 heaps; sent blocks are released early.
class WPageResponse final : public AsyncAbstractResponse, public Print {
public:
    WPageResponse(const WPageResponse&) = delete;
    WPageResponse& operator=(const WPageResponse&) = delete;
    explicit WPageResponse(const char* contentType) {
        _code = 200;
        _contentLength = 0;
        _contentType = contentType;
        failed = _contentType.length() != std::strlen(contentType);
    }
    ~WPageResponse() override {
        while (first) releaseFirst();
    }
    using Print::write;
    size_t write(uint8_t value) override { return write(&value, 1); }
    size_t write(const uint8_t* data, size_t length) override {
        if (failed || _started()) return 0;
        if (length > 8192U - _contentLength) { failed = true; return 0; }
        size_t written = 0;
        while (written < length) {
            if (!last || last->length == sizeof(last->data)) {
                Block* block = new (std::nothrow) Block;
                if (!block) { failed = true; break; }
                if (last) last->next = block;
                else first = block;
                last = block;
            }
            const size_t count = std::min(length - written, sizeof(last->data) - last->length);
            std::memcpy(last->data + last->length, data + written, count);
            last->length += count;
            written += count;
        }
        _contentLength += written;
        return written;
    }
    bool _sourceValid() const override { return !failed; }
    size_t _fillBuffer(uint8_t* output, size_t length) override {
        size_t copied = 0;
        while (first && copied < length) {
            const size_t count = std::min(length - copied, first->length - offset);
            std::memcpy(output + copied, first->data + offset, count);
            copied += count;
            offset += count;
            if (offset == first->length) releaseFirst();
        }
        return copied;
    }
private:
    struct Block {
        Block* next = nullptr;
        size_t length = 0;
        uint8_t data[256];
    };
    void releaseFirst() {
        Block* old = first;
        first = first->next;
        delete old;
        offset = 0;
        if (!first) last = nullptr;
    }
    Block* first = nullptr;
    Block* last = nullptr;
    size_t offset = 0;
    bool failed = false;
};
#endif
