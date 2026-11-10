#ifndef W_CHECKED_PRINT_H
#define W_CHECKED_PRINT_H
#include <Print.h>
#include <cstdarg>
#include <memory>
#include <new>

// Keep allocation and short-write failures sticky until the response is sent.
class WCheckedPrint final : public Print {
public:
    explicit WCheckedPrint(Print* target) : target(target) {}
    size_t write(uint8_t value) override { return write(&value, 1); }
    size_t write(const uint8_t* data, size_t size) override {
        if (failed || size > 8192 - written) { failed = true; return 0; }
        const size_t result = target->write(data, size);
        written += result;
        failed = result != size;
        return result;
    }
    bool ok() const { return !failed; }
    Print* getTarget() const { return target; }
    size_t format(PGM_P text, ...) __attribute__((format(printf, 2, 3))) {
        va_list args;
        va_start(args, text);
        const size_t result = formatToTarget(text, args);
        va_end(args);
        return result;
    }
private:
    size_t formatToTarget(PGM_P text, va_list args) __attribute__((format(printf, 2, 0))) {
        if (failed) return 0;
        char local[256];
        va_list copy;
        va_copy(copy, args);
        const int length = vsnprintf_P(local, sizeof(local), text, copy);
        va_end(copy);
        if (length < 0 || static_cast<size_t>(length) > 8192 - written) { failed = true; return 0; }
        const size_t size = static_cast<size_t>(length);
        if (size < sizeof(local)) return write(reinterpret_cast<const uint8_t*>(local), size);
        std::unique_ptr<char[]> buffer(new (std::nothrow) char[size + 1]);
        if (!buffer || vsnprintf_P(buffer.get(), size + 1, text, args) != length) { failed = true; return 0; }
        return write(reinterpret_cast<const uint8_t*>(buffer.get()), size);
    }
    Print* target;
    size_t written = 0;
    bool failed = false;
};
#endif
