#ifndef W_JSON_PARSER_H
#define W_JSON_PARSER_H

#include <utility>
#include "Arduino.h"
#include "WJson.h"
#include <functional>
#include <cstring>

// WebThings properties and schedules are flat maps of scalar values.
class WJsonParser {
public:
    typedef std::function<void(const char*, const char*)> TProcessKeyValueFunction;
    typedef std::function<bool(const char*, const char*)> TValidateKeyValueFunction;
    explicit WJsonParser(bool = false) {}

    bool parse(const char* payload, TProcessKeyValueFunction callback,
               TValidateKeyValueFunction validator = nullptr) {
        device = nullptr;
        process = std::move(callback);
        validate = std::move(validator);
        return run(payload);
    }

    WProperty* parse(const char* payload, WDevice* target) {
        device = target;
        process = nullptr;
        validate = nullptr;
        lastProperty = nullptr;
        return run(payload) ? lastProperty : nullptr;
    }

    bool isValid() const { return valid; }

private:
    const char* cursor = nullptr;
    WDevice* device = nullptr;
    WProperty* lastProperty = nullptr;
    TProcessKeyValueFunction process;
    TValidateKeyValueFunction validate;
    bool valid = false;

    void whitespace() {
        while (*cursor == ' ' || *cursor == '\t' || *cursor == '\r' || *cursor == '\n') ++cursor;
    }

    bool hex4(unsigned& value) {
        value = 0;
        for (unsigned i = 0; i < 4; ++i) {
            const char c = *cursor;
            if (!c) return false;
            const int digit = c >= '0' && c <= '9' ? c - '0' :
                              c >= 'a' && c <= 'f' ? c - 'a' + 10 :
                              c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
            if (digit < 0) return false;
            value = value * 16 + digit;
            ++cursor;
        }
        return true;
    }

    bool string(char* out, size_t capacity) {
        if (*cursor != '"') return false;
        ++cursor;
        size_t size = 0;
        while (*cursor && *cursor != '"') {
            unsigned char c = *cursor++;
            if (c < 0x20) return false;
            if (c == '\\') {
                c = *cursor++;
                if (!c) return false;
                switch (c) {
                    case '"': case '\\': case '/': break;
                    case 'b': c = '\b'; break;
                    case 'f': c = '\f'; break;
                    case 'n': c = '\n'; break;
                    case 'r': c = '\r'; break;
                    case 't': c = '\t'; break;
                    case 'u': {
                        unsigned point;
                        if (!hex4(point) || point == 0) return false;
                        if (point >= 0xd800 && point <= 0xdbff) {
                            if (*cursor != '\\') return false;
                            ++cursor;
                            if (*cursor != 'u') return false;
                            ++cursor;
                            unsigned low;
                            if (!hex4(low) || low < 0xdc00 || low > 0xdfff) return false;
                            point = 0x10000 + ((point - 0xd800) << 10) + low - 0xdc00;
                        } else if (point >= 0xdc00 && point <= 0xdfff) return false;
                        unsigned char bytes[4];
                        unsigned count;
                        if (point < 0x80) { bytes[0] = point; count = 1; }
                        else if (point < 0x800) {
                            bytes[0] = 0xc0 | (point >> 6); bytes[1] = 0x80 | (point & 63); count = 2;
                        } else if (point < 0x10000) {
                            bytes[0] = 0xe0 | (point >> 12); bytes[1] = 0x80 | ((point >> 6) & 63);
                            bytes[2] = 0x80 | (point & 63); count = 3;
                        } else {
                            bytes[0] = 0xf0 | (point >> 18); bytes[1] = 0x80 | ((point >> 12) & 63);
                            bytes[2] = 0x80 | ((point >> 6) & 63); bytes[3] = 0x80 | (point & 63); count = 4;
                        }
                        if (size + count >= capacity) return false;
                        for (unsigned i = 0; i < count; ++i) out[size++] = static_cast<char>(bytes[i]);
                        continue;
                    }
                    default: return false;
                }
            }
            if (size + 1 >= capacity) return false;
            out[size++] = static_cast<char>(c);
        }
        if (*cursor != '"') return false;
        ++cursor;
        out[size] = 0;
        return true;
    }

    bool scalar(char* out, size_t capacity) {
        if (*cursor == '"') return string(out, capacity);
        const char* begin = cursor;
        for (const char* literal : {"true", "false", "null"}) {
            const size_t size = strlen(literal);
            if (strncmp(cursor, literal, size) == 0) {
                memcpy(out, literal, size + 1);
                cursor += size;
                return true;
            }
        }
        if (*cursor == '-') ++cursor;
        if (*cursor == '0') ++cursor;
        else {
            if (*cursor < '1' || *cursor > '9') return false;
            while (*cursor >= '0' && *cursor <= '9') ++cursor;
        }
        if (*cursor == '.') {
            ++cursor;
            if (*cursor < '0' || *cursor > '9') return false;
            while (*cursor >= '0' && *cursor <= '9') ++cursor;
        }
        if (*cursor == 'e' || *cursor == 'E') {
            ++cursor;
            if (*cursor == '+' || *cursor == '-') ++cursor;
            if (*cursor < '0' || *cursor > '9') return false;
            while (*cursor >= '0' && *cursor <= '9') ++cursor;
        }
        const size_t size = cursor - begin;
        if (size == 0 || size >= capacity) return false;
        memcpy(out, begin, size);
        out[size] = 0;
        return true;
    }

    bool pass(const char* payload, bool apply) {
        cursor = payload;
        whitespace();
        if (*cursor != '{') return false;
        ++cursor;
        whitespace();
        if (*cursor != '}') {
            for (;;) {
                char key[64], value[128];
                if (!string(key, sizeof(key))) return false;
                whitespace();
                if (*cursor != ':') return false;
                ++cursor;
                whitespace();
                const bool isNull = strncmp(cursor, "null", 4) == 0;
                if (!scalar(value, sizeof(value))) return false;
                if (!isNull) {
                    if (device) {
                        WProperty* property = device->getPropertyById(key);
                        if (property && !property->isReadOnly()) {
                            if (!property->canParse(value)) return false;
                            if (apply && property->parse(value)) lastProperty = property;
                        }
                    } else {
                        if (validate && !validate(key, value)) return false;
                        if (apply && process) process(key, value);
                    }
                }
                whitespace();
                if (*cursor != ',') break;
                ++cursor;
                whitespace();
            }
        }
        if (*cursor != '}') return false;
        ++cursor;
        whitespace();
        return *cursor == 0;
    }

    bool run(const char* payload) {
        valid = payload && pass(payload, false);
        // Validate the complete command before invoking any actuator callback.
        if (valid) valid = pass(payload, true);
        return valid;
    }
};

#endif
