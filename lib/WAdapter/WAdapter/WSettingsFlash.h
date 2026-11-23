#pragma once

#include <Arduino.h>
#include <EEPROM.h>
#include <coredecls.h>
#include <new>

// This symbol exists only in the firmware layout that reserves the second sector.
extern "C" uint32_t _settings_backup_start;

class WSettingsFlash : public EEPROMClass {
public:
    explicit WSettingsFlash(uint32_t backupSector) : backupSector(backupSector) {}

    WSettingsFlash(const WSettingsFlash&) = delete;
    WSettingsFlash& operator=(const WSettingsFlash&) = delete;

    void begin(size_t size) {
        _dirty = false;
        _size = 0;
        if (fault || size != imageSize) return;
        if (!_data) _data = new (std::nothrow) uint8_t[imageSize];
        if (!_data || !load()) {
            // Boot may now hold defaults for fields it couldn't read. Never
            // write those over a good snapshot, even via a later form save.
            fault = true;
            return;
        }
        _size = imageSize;
    }

    void end() {
        delete[] _data;
        _data = nullptr;
        _size = 0;
        _dirty = false;
    }

    bool commit() {
        if (!_size || fault) return false;
        if (!_dirty) return true;
        const uint32_t target = active == _sector ? backupSector : _sector;
        const uint32_t address = target * sectorSize;
        const Header header = {magic, generation + 1, checksum(generation + 1)};
        if (!ESP.flashEraseSector(target) ||
            !ESP.flashWrite(address, _data, imageSize)) return false;
        // Verify before publishing the header. The active sector stays intact.
        uint32_t chunk[16];
        for (size_t pos = 0; pos < imageSize; pos += sizeof(chunk)) {
            if (!ESP.flashRead(address + pos, chunk, sizeof(chunk)) ||
                memcmp(_data + pos, chunk, sizeof(chunk)) != 0) return false;
        }
        Header stored;
        if (!ESP.flashWrite(address + imageSize, reinterpret_cast<const uint8_t*>(&header), sizeof(header)) ||
            !readHeader(target, stored) || memcmp(&header, &stored, sizeof(header)) != 0) {
            // The marker might have reached flash. Resolve it again on reboot.
            fault = true;
            return false;
        }
        active = target;
        generation = header.generation;
        activeCrc = header.crc;
        hasHeader = true;
        _dirty = false;
        return true;
    }

private:
    struct Header { uint32_t tag, generation, crc; };
    static constexpr uint32_t magic = 0x31535457; // WTS1
    static constexpr uint32_t sectorSize = 4096;
    static constexpr size_t imageSize = 1024;
    static_assert(sizeof(Header) == 12 && imageSize + sizeof(Header) <= sectorSize, "Settings record layout");
    const uint32_t backupSector;
    uint32_t active = UINT32_MAX;
    uint32_t generation = 0;
    uint32_t activeCrc = 0;
    bool hasHeader = false;
    bool fault = false;

    uint32_t checksum(uint32_t sequence) const {
        return crc32(_data, imageSize, crc32(&sequence, sizeof(sequence)));
    }

    static bool readHeader(uint32_t sector, Header& header) {
        return ESP.flashRead(sector * sectorSize + imageSize, reinterpret_cast<uint8_t*>(&header), sizeof(header));
    }

    bool load() {
        if (active != UINT32_MAX) {
            return ESP.flashRead(active * sectorSize, _data, imageSize) &&
                (!hasHeader || checksum(generation) == activeCrc);
        }
        uint32_t sectors[] = {_sector, backupSector};
        Header headers[2];
        if (!readHeader(sectors[0], headers[0]) || !readHeader(sectors[1], headers[1])) return false;
        unsigned newest = headers[1].tag == magic && (headers[0].tag != magic ||
            static_cast<int32_t>(headers[1].generation - headers[0].generation) > 0) ? 1 : 0;
        for (unsigned i = 0; i < 2; ++i) {
            const unsigned slot = newest ^ i;
            const Header& h = headers[slot];
            if (h.tag != magic) continue;
            if (!ESP.flashRead(sectors[slot] * sectorSize, _data, imageSize)) return false;
            if (checksum(h.generation) == h.crc) {
                active = sectors[slot];
                generation = h.generation;
                activeCrc = h.crc;
                hasHeader = true;
                return true;
            }
        }
        // Legacy images have no header. The first changed save always targets
        // the spare sector, so a cut during migration leaves this image usable.
        if (headers[0].tag != UINT32_MAX || headers[0].generation != UINT32_MAX ||
            headers[0].crc != UINT32_MAX || !ESP.flashRead(_sector * sectorSize, _data, imageSize)) return false;
        active = _sector;
        return true;
    }
};
