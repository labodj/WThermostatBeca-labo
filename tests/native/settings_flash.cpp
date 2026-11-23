#include "Arduino.h"
#include <array>
#include <algorithm>

// The journal reuses the SDK's EEPROM session buffer and field accessors.
struct EEPROMClass {
protected:
    uint32_t _sector = 1;
    uint8_t* _data = nullptr;
    size_t _size = 0;
    bool _dirty = false;
public:
    size_t length() const { return _size; }
    uint8_t read(size_t i) const { assert(i < _size); return _data[i]; }
    void write(size_t i, uint8_t value) {
        assert(i < _size);
        _dirty |= _data[i] != value;
        _data[i] = value;
    }
};

struct NorFlash {
    std::array<uint8_t, 8192> bytes;
    int remaining = -1;
    unsigned erases = 0;
    bool readError = false;
    bool step() { return remaining < 0 || (remaining > 0 && remaining--); }
    bool flashRead(unsigned address, void* output, size_t count) {
        assert(address + count <= bytes.size());
        if (readError) return false;
        memcpy(output, bytes.data() + address, count);
        return true;
    }
    bool flashWrite(unsigned address, const void* data, size_t count) {
        assert(address + count <= bytes.size());
        auto* src = static_cast<const uint8_t*>(data);
        for (size_t i = 0; i < count; ++i) {
            if (!step()) return false;
            bytes[address + i] &= src[i];
        }
        return true;
    }
    bool flashEraseSector(unsigned sector) {
        assert(sector < 2);
        ++erases;
        for (unsigned i = 0; i < 4096; ++i) {
            if (!step()) return false;
            bytes[sector * 4096 + i] = 0xff;
        }
        return true;
    }
} ESP;

#include "lib/WAdapter/WAdapter/WSettingsFlash.h"

using Image = std::array<uint8_t, 1024>;

static Image readBoot() {
    WSettingsFlash store(0);
    store.begin(1024);
    assert(store.length() == 1024);
    Image image;
    for (unsigned i = 0; i < image.size(); ++i) image[i] = store.read(i);
    assert(store.commit());
    store.end();
    return image;
}

static bool save(const Image& image) {
    WSettingsFlash store(0);
    store.begin(image.size());
    for (unsigned i = 0; i < image.size(); ++i) store.write(i, image[i]);
    bool ok = store.commit();
    store.end();
    return ok;
}

int main() {
    ESP.bytes.fill(0xff);
    Image old, next, previous;
    for (unsigned i = 0; i < old.size(); ++i) old[i] = static_cast<uint8_t>(i);
    std::copy(old.begin(), old.end(), ESP.bytes.begin() + 4096);
    // First migration, first replacement of legacy storage, then slot reuse.
    for (unsigned round = 0; round < 3; ++round) {
        for (unsigned i = 0; i < next.size(); ++i) next[i] = old[i] ^ (0xab + round);
        const auto baseline = ESP.bytes;
        constexpr int operations = 4096 + 1024 + 12;
        for (int cut = 0; cut <= operations; ++cut) {
            ESP.bytes = baseline;
            ESP.remaining = cut;
            bool ok = save(next);
            ESP.remaining = -1;
            unsigned erases = ESP.erases;
            Image recovered = readBoot();
            assert(recovered == old || recovered == next);
            if (ok) assert(recovered == next);
            assert(ESP.erases == erases);
        }
        unsigned erases = ESP.erases;
        assert(save(next) && ESP.erases == erases);
        previous = old;
        old = next;
    }
    // Latest image is in sector 0. Fall back on a damaged payload.
    ESP.bytes[100] ^= 1;
    assert(readBoot() == previous);
    // Generation zero is the successor to UINT32_MAX.
    uint32_t sequence = UINT32_MAX;
    memcpy(ESP.bytes.data()+4096+1028, &sequence, 4);
    uint32_t crc = crc32(previous.data(), previous.size(), crc32(&sequence, sizeof(sequence)));
    memcpy(ESP.bytes.data()+4096+1032, &crc, 4);
    assert(save(next) && readBoot() == next);
    WSettingsFlash mounted(0);
    mounted.begin(1024);
    mounted.end();
    ESP.bytes[20] ^= 1;
    mounted.begin(1024);
    assert(!mounted.length() && !mounted.commit());
    mounted.end();
    const auto before = ESP.bytes;
    WSettingsFlash unreadable(0);
    ESP.readError = true;
    unreadable.begin(1024);
    ESP.readError = false;
    unreadable.begin(1024);
    assert(!unreadable.length() && !unreadable.commit() && before == ESP.bytes);
    unreadable.end();

    // Leave every torn erase/write in place for the next boot and save.
    ESP.bytes.fill(0xff);
    Image committed = readBoot();
    uint32_t random = 12;
    for (unsigned day = 0; day < 3653; ++day) {
        Image proposed = committed;
        random = random * 1664525U + 1013904223U;
        proposed[(random >> 16) % proposed.size()] ^= 0x80;
        ESP.remaining = day % 7 == 6 ? -1 : static_cast<int>(random % (4096 + 1024 + 12));
        const bool saved = save(proposed);
        ESP.remaining = -1;
        unsigned erases = ESP.erases;
        const Image recovered = readBoot();
        assert(recovered == proposed || (!saved && recovered == committed));
        committed = recovered;
        assert(save(committed) && ESP.erases == erases);
    }
}
