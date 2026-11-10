#ifndef W_DIGEST_AUTH_H
#define W_DIGEST_AUTH_H

#include <Arduino.h>
#include "WebAuthentication.h"

// Bounded, boot-local challenges. A sliding counter window tolerates parallel browser requests.
class WDigestAuth {
public:
    String challenge() {
        const String nonce = genRandomMD5(), opaque = genRandomMD5();
        if (nonce.length() != 32 || opaque.length() != 32) return String();
        String header = String("Digest realm=\"WThermostat\", qop=\"auth\", algorithm=MD5, charset=UTF-8, nonce=\"") + nonce + "\", opaque=\"" + opaque + "\"";
        Slot& slot = slots[next];
        slot.nonce = nonce; slot.opaque = opaque;
        if (slot.nonce.length() != 32 || slot.opaque.length() != 32) return String();
        slot.issued = millis(); slot.highest = 0; slot.seen = 0;
        next = (next + 1) % 4;
        return header;
    }

    template<class Request>
    bool authenticate(Request* request, const char* password) {
        // Body/upload callbacks may authorize the same request more than once.
        if (request->getAttribute(attribute, false)) return true;
        if (!request->hasHeader("Authorization")) return false;
        const String header = request->getHeader("Authorization")->value();
        if (!header.startsWith("Digest ") || header.length() > 2048 || strlen(header.c_str()) != header.length()) return false;
        const char* names[] = {"username", "realm", "nonce", "opaque", "uri", "response", "qop", "nc", "cnonce"};
        String values[9];
        unsigned present = 0;
        const char* p = header.c_str() + 7;
        while (*p) {
            while (*p == ' ' || *p == '\t') ++p;
            const char* begin = p;
            while (*p && *p != '=' && *p != ' ' && *p != '\t' && *p != ',') ++p;
            const String name = header.substring(static_cast<unsigned>(begin - header.c_str()), static_cast<unsigned>(p - header.c_str()));
            while (*p == ' ' || *p == '\t') ++p;
            if (*p != '=') return false;
            ++p;
            while (*p == ' ' || *p == '\t') ++p;
            const bool quoted = *p == '"';
            if (quoted) ++p;
            begin = p;
            while (*p && (quoted ? *p != '"' : *p != ',' && *p != ' ' && *p != '\t')) {
                // The upstream verifier splits on commas and does not unescape quoted pairs.
                if (*p == '\\' || *p == ',') return false;
                ++p;
            }
            const String value = header.substring(static_cast<unsigned>(begin - header.c_str()), static_cast<unsigned>(p - header.c_str()));
            if (quoted) {
                if (*p != '"') return false;
                ++p;
            }
            for (unsigned i = 0; i < 9; ++i) if (name == names[i]) {
                if (present & (1U << i)) return false;
                present |= 1U << i; values[i] = value;
            }
            while (*p == ' ' || *p == '\t') ++p;
            if (*p) {
                if (*p != ',') return false;
                ++p;
            }
        }
        if (present != 511 || values[0] != "admin" || values[1] != "WThermostat" || values[6] != "auth" ||
            values[7].length() != 8 || !values[8].length() || values[8].length() > 128 || !matchesTarget(request, values[4])) return false;
        uint32_t count = 0;
        for (unsigned i = 0; i < 8; ++i) {
            const unsigned char c = static_cast<unsigned char>(values[7][i]);
            if (!isxdigit(static_cast<unsigned char>(c))) return false;
            const uint32_t digit = static_cast<uint32_t>(c <= '9' ? c - '0' : tolower(c) - 'a' + 10);
            count = (count << 4U) | digit;
        }
        if (!count) return false;
        for (Slot& slot : slots) {
            if (values[2] != slot.nonce || values[3] != slot.opaque || millis() - slot.issued >= 300000UL) continue;
            const uint32_t behind = slot.highest - count;
            if (count <= slot.highest && (behind >= 32 || (slot.seen & (1UL << behind)))) return false;
            if (!checkDigestAuthentication(header.c_str() + 7, request->methodToString(), "admin", password,
                    "WThermostat", false, slot.nonce.c_str(), slot.opaque.c_str(), values[4].c_str())) return false;
            if (count > slot.highest) {
                const uint32_t ahead = count - slot.highest;
                slot.seen = ahead >= 32 ? 1U : (slot.seen << ahead) | 1U;
                slot.highest = count;
            } else slot.seen |= 1UL << behind;
            request->setAttribute(attribute, true);
            return request->getAttribute(attribute, false);
        }
        return false;
    }

private:
    struct Slot { String nonce, opaque; unsigned long issued = 0; uint32_t highest = 0, seen = 0; };
    Slot slots[4];
    unsigned next = 0;
    static constexpr const char* attribute = "wthermostat.digest.valid";

    template<class Request>
    static bool matchesTarget(Request* request, const String& uri) {
        const int question = uri.indexOf('?');
        if (request->urlDecode(question < 0 ? uri : uri.substring(0, static_cast<unsigned>(question))) != request->url()) return false;
        // The server exposes decoded query parameters, rather than the raw request target.
        unsigned index = 0;
        const String query = question < 0 ? String() : uri.substring(static_cast<unsigned>(question) + 1U);
        unsigned start = 0;
        while (start < query.length()) {
            const int separator = query.indexOf('&', start);
            const unsigned end = separator < 0 ? query.length() : static_cast<unsigned>(separator);
            const String pair = query.substring(start, end);
            if (pair.length()) {
                const int equal = pair.indexOf('=');
                const String name = request->urlDecode(equal < 0 ? pair : pair.substring(0, static_cast<unsigned>(equal)));
                const String value = equal < 0 ? String() : request->urlDecode(pair.substring(static_cast<unsigned>(equal) + 1U));
                while (index < request->params() && (request->getParam(index)->isPost() || request->getParam(index)->isFile())) ++index;
                if (index >= request->params()) return false;
                const auto* parameter = request->getParam(index);
                ++index;
                if (parameter->name() != name || parameter->value() != value) return false;
            }
            start = end + 1;
        }
        while (index < request->params()) {
            const auto* parameter = request->getParam(index);
            ++index;
            if (!parameter->isPost() && !parameter->isFile()) return false;
        }
        return true;
    }
};
#endif
