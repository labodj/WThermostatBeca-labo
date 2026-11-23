#pragma once
#include <cstddef>
#include <cstdint>

inline uint32_t crc32(const void* data, size_t size, uint32_t crc = UINT32_MAX) {
    const auto* bytes = static_cast<const uint8_t*>(data);
    while (size--) {
        crc ^= static_cast<uint32_t>(*bytes++) << 24;
        for (unsigned i = 0; i < 8; ++i)
            crc = (crc << 1) ^ ((crc >> 31) ? 0x04c11db7U : 0U);
    }
    return crc;
}
