#ifndef W_WIFI_PASSWORD_H
#define W_WIFI_PASSWORD_H

#include "WSettings.h"

// Leave all legacy fields and the BSSID at 504..510 in their original slots.
class WWifiPassword {
public:
    static bool valid(const String& password) {
        if (!password.length()) return true;
        if (password.length() < 8 || password.length() > 64 || strlen(password.c_str()) != password.length()) return false;
        if (password.length() == 64)
            for (unsigned i = 0; i < 64; ++i)
                if (!isxdigit(static_cast<unsigned char>(password[i]))) return false;
        return true;
    }

    static uint32_t checksum(const char* ssid, const char* password) {
        uint32_t hash = 2166136261UL;
        for (const char* text : {ssid, password}) {
            do { hash = (hash ^ static_cast<unsigned char>(*text)) * 16777619UL; } while (*text++);
        }
        return hash;
    }

    static String load(const char* ssid, const char* legacyPassword) {
        String result;
        settingsFlash.begin(EEPROM_SIZE);
        if (settingsFlash.length() != EEPROM_SIZE) { settingsFlash.end(); return result; }
        const int length = settingsFlash.read(514);
        if (settingsFlash.read(512) == 0x57 && settingsFlash.read(513) == 1 && length > 32 && length <= 64) {
            char password[65]{};
            for (int i = 0; i < length; ++i) password[i] = settingsFlash.read(520 + i);
            uint32_t stored;
            settingsFlash.get(516, stored);
            if (strlen(legacyPassword) == 32 && !strncmp(password, legacyPassword, 32) &&
                valid(String(password)) && strlen(password) == static_cast<unsigned>(length) && checksum(ssid, password) == stored)
                result = password;
        }
        settingsFlash.end();
        return result;
    }

    static bool save(const char* ssid, const String& password, bool staged = false) {
        if (!valid(password)) return false;
        if (!staged) settingsFlash.begin(EEPROM_SIZE);
        if (settingsFlash.length() != EEPROM_SIZE) { if (!staged) settingsFlash.end(); return false; }
        settingsFlash.write(512, password.length() > 32 ? 0x57 : 0xFF);
        settingsFlash.write(513, 1);
        settingsFlash.write(514, static_cast<byte>(password.length()));
        settingsFlash.write(515, 0);
        const uint32_t hash = checksum(ssid, password.c_str());
        settingsFlash.put(516, hash);
        for (int i = 0; i < 64; ++i)
            settingsFlash.write(520 + i, i < static_cast<int>(password.length()) ? static_cast<byte>(password[i]) : 0);
        const bool saved = staged || settingsFlash.commit();
        if (!staged) {
            if (!saved) settingsFlash.begin(EEPROM_SIZE);
            settingsFlash.end();
        }
        return saved;
    }
};

#endif
