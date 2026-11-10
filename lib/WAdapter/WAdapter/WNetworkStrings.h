#ifndef W_NETWORK_STRINGS_H
#define W_NETWORK_STRINGS_H

#include "WSettings.h"

// Keep legacy fields, BSSID and Wi-Fi password storage at their original offsets.
class WNetworkStrings {
public:
    static unsigned limit(unsigned field) { return field < 2 ? 32U : 64U; }
    static unsigned legacyLength(unsigned field) { return field < 2 ? 16U : 32U; }

    const char* get(unsigned field, const char* legacy) const {
        return extended[field].length() ? extended[field].c_str() : legacy;
    }

    bool loadAndMigrate(const char* const legacy[4], const char* const old[4]) {
        if (!load(legacy)) return false;
        if (!old) return true;
        String full[4];
        bool migrate = false;
        for (unsigned field = 0; field < 4; ++field) {
            const bool longer = strlen(old[field]) > legacyLength(field);
            const char* value = longer ? old[field] : get(field, legacy[field]);
            full[field] = value;
            if (full[field].length() != strlen(value) || full[field].length() > limit(field)) return false;
            migrate |= longer;
        }
        if (!migrate) return true;
        // Keep full values in RAM even if flash fails; callers must then block writes.
        for (unsigned field = 0; field < 4; ++field) {
            extended[field] = full[field].length() > legacyLength(field) ? full[field] : String();
            if (full[field].length() > legacyLength(field) && extended[field].length() != full[field].length()) return false;
        }
        return save(full);
    }

    static bool save(const String (&values)[4], bool staged = false) {
        byte record[recordSize]{};
        unsigned position = 8;
        bool needed = false;
        for (unsigned field = 0; field < 4; ++field) {
            const unsigned length = values[field].length();
            if (length > limit(field) || strlen(values[field].c_str()) != length) return false;
            if (length > legacyLength(field)) {
                memcpy(record + position, values[field].c_str(), length);
                needed = true;
            }
            position += limit(field) + 1;
        }
        if (needed) {
            record[0] = 0x4E; record[1] = 0x53; record[2] = 1;
            const uint32_t hash = checksum(record);
            for (unsigned i = 0; i < 4; ++i) record[4 + i] = static_cast<byte>(hash >> (8 * i));
        } else memset(record, 0xFF, sizeof(record));
        if (!staged) EEPROM.begin(EEPROM_SIZE);
        if (EEPROM.length() != EEPROM_SIZE) { if (!staged) EEPROM.end(); return false; }
        bool changed = false;
        for (unsigned i = 0; i < recordSize; ++i) changed |= EEPROM.read(static_cast<int>(address + i)) != record[i];
        if (changed)
            for (unsigned i = 0; i < recordSize; ++i) EEPROM.write(static_cast<int>(address + i), record[i]);
        const bool saved = staged || !changed || EEPROM.commit();
        if (!staged) {
            if (!saved) EEPROM.begin(EEPROM_SIZE);
            EEPROM.end();
        }
        return saved;
    }

private:
    static constexpr unsigned address = 640;
    static constexpr unsigned recordSize = 204;
    static_assert(address + recordSize <= EEPROM_SIZE, "Network strings exceed EEPROM");
    String extended[4];

    static uint32_t checksum(const byte* record) {
        uint32_t hash = 2166136261UL;
        for (unsigned i = 8; i < recordSize; ++i) hash = (hash ^ record[i]) * 16777619UL;
        return hash;
    }

    bool load(const char* const legacy[4]) {
        for (String& value : extended) value = String();
        EEPROM.begin(EEPROM_SIZE);
        if (EEPROM.length() != EEPROM_SIZE) { EEPROM.end(); return false; }
        byte record[recordSize];
        for (unsigned i = 0; i < recordSize; ++i) record[i] = EEPROM.read(static_cast<int>(address + i));
        EEPROM.end();
        if (record[0] != 0x4E || record[1] != 0x53 || record[2] != 1) return true;
        uint32_t stored = 0;
        for (unsigned i = 0; i < 4; ++i) stored |= static_cast<uint32_t>(record[4 + i]) << (8 * i);
        if (stored != checksum(record)) return true;
        unsigned position = 8;
        for (unsigned field = 0; field < 4; ++field) {
            const char* value = reinterpret_cast<const char*>(record + position);
            const void* end = memchr(value, 0, limit(field) + 1);
            const size_t length = end ? static_cast<size_t>(static_cast<const char*>(end) - value) : 0;
            if (length > legacyLength(field) && strlen(legacy[field]) == legacyLength(field) && !strncmp(value, legacy[field], legacyLength(field))) {
                extended[field] = value;
                if (extended[field].length() != length) return false;
            }
            position += limit(field) + 1;
        }
        return true;
    }
};

#endif
