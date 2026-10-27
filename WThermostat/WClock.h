
/*********************************************************************************************\
*  TimeZone Handling based on
*        Time by Michael Margolis and Paul Stoffregen (https://github.com/PaulStoffregen/Time)
*        Timezone by Jack Christensen (https://github.com/JChristensen/Timezone)
*        Tasmota by Theo Arends (https://github.com/arendst/Tasmota)
\*********************************************************************************************/

#ifndef W_CLOCK_H
#define W_CLOCK_H

#include <utility>
#include <ESP8266WiFi.h>
#include <NTPClient.h>
#include <TimeLib.h>
#include <WiFiUdp.h>

#include "../lib/WAdapter/WAdapter/WDevice.h"
#include "../lib/WAdapter/WAdapter/WNetwork.h"
#include "Arduino.h"

//#define NTPTESTSTART 1585555170 // Full Hour Test
//#define NTPTESTSTART (1585447200 - 70 - (1*60*60)) // DST Test Berlin
//#define NTPTESTSTART (1603594800 - 70 - (2*60*60)) // STD Test Berlin
//#define NTPTESTSTART (1586055600 - 70 - (11*60*60)) // STD Test Sydney
//#define NTPTESTSTART (1601776800 - 70 - (10*60*60)) // DST Test Sydney

const static char* DEFAULT_NTP_SERVER PROGMEM = "pool.ntp.org";
const static char* DEFAULT_TIME_ZONE PROGMEM = "99";
const static char* DEFAULT_TIME_DST PROGMEM = "0,3,0,2,120";
const static char* DEFAULT_TIME_STD PROGMEM = "0,10,0,3,60";

const static char HTTP_TEXT_CLOCK_HOWTO[] PROGMEM = R"=====(
<div>
See <a href="https://github.com/fashberg/WThermostatBeca/blob/master/Configuration.md#4-configure-clock-settings"
target="_blank" rel="noopener">clock configuration documentation (opens a new tab)</a>
for Howto set Timezone and Daylight-Savings
</div>
)=====";

typedef struct {
    bool initialized = false;
    uint16_t week = 0;   // bits 1 - 3   = 0=Last week of the month, 1=First, 2=Second, 3=Third, 4=Fourth
    uint16_t month = 0;  // bits 4 - 7   = 1=Jan, 2=Feb, ... 12=Dec
    uint16_t dow = 0;    // bits 8 - 10  = day of week, 1=Sun, 2=Mon, ... 7=Sat
    uint16_t hour = 0;   // bits 11 - 15 = 0-23
    int16_t offset = 0;
} TimeRule;

typedef struct {
    uint8_t second = 0;
    uint8_t minute = 0;
    uint8_t hour = 0;
    uint8_t day_of_week = 0;  // sunday is day 1
    uint8_t day_of_month = 0;
    uint8_t month = 0;
    char name_of_month[4]{};
    uint16_t day_of_year = 0;
    uint16_t year = 0;
    unsigned long days = 0;
    unsigned long valid = 0;
} TIME_T;

typedef struct {
    uint32_t utc_time = 0;
    uint32_t local_time = 0;
    uint32_t daylight_saving_time = 0;
    uint32_t standard_time = 0;
    uint32_t ntp_time = 0;
    uint32_t midnight = 0;
    uint32_t restart_time = 0;
    int32_t time_timezone = 0;
    uint8_t ntp_sync_minute = 0;
    bool midnight_now = false;
    bool user_time_entry = false;               // Override NTP by user setting
} RTC;

#define LEAP_YEAR(Y) ((( Y) > 0) && !((Y) % 4) && (((Y) % 100) || !((Y) % 400)))

static const uint8_t kDaysInMonth[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};  // API starts months from 1, this array starts from 0
static const char kMonthNames[] = "JanFebMarAprMayJunJulAugSepOctNovDec";
const uint32_t START_VALID_TIME = 1451602800;  // Time is synced and after 2016-01-01

const char* ID_CLOCK PROGMEM = "clock";
const char* NAME_CLOCK PROGMEM = "Clock";


const char* PROP_NTPSERVER PROGMEM = "ntpServer";
const char* PROP_TIMEZONE PROGMEM = "timeZone";
const char* PROP_TIMEDST PROGMEM = "timeDST";
const char* PROP_TIMESTD PROGMEM = "timeSTD";

const char* PROP_EPOCHTIME PROGMEM = "epochTime";
const char* PROP_EPOCHTIMELOCALFORMATTED PROGMEM = "epochTimeLocalFormatted";
const char* PROP_VALIDTIME PROGMEM = "validTime";
const char* PROP_OFFSET PROGMEM = "offset";
const char* PROP_UPTIME PROGMEM = "uptime";

WiFiUDP ntpUDP;
NTPClient ntpClient(ntpUDP);

class WClock : public WDevice {
   public:
    typedef std::function<void(void)> THandlerFunction;
    typedef std::function<void(const char*)> TErrorHandlerFunction;

    //WClock(bool debug, WNetwork *network) {
    WClock(WNetwork* network, const String& applicationName)
        : WDevice(network, ID_CLOCK, NAME_CLOCK, network->getIdx(), DEVICE_TYPE_TEXT_DISPLAY) {
        this->mainDevice = false;
        this->visibility = MQTT;

        if (network->getSettingsOld()){
            if (network->getSettingsOld()->getNetworkSettingsVersion()==NETWORKSETTINGS_PRE_FAS114
             || network->getSettingsOld()->getApplicationSettingsVersion()==network->getSettingsOld()->getApplicationSettingsCurrent()-1){
                network->log()->notice(F("Reading WClockSettings PRE_FAS114/FLAG_OPTIONS_APPLICATION-1"));
                network->getSettingsOld()->setString(PROP_NTPSERVER, 32, DEFAULT_NTP_SERVER);
                network->getSettingsOld()->setString(PROP_TIMEZONE, 6, DEFAULT_TIME_ZONE);
                network->getSettingsOld()->setString(PROP_TIMEDST, 14, DEFAULT_TIME_DST);
                network->getSettingsOld()->setString(PROP_TIMESTD, 14, DEFAULT_TIME_STD);
            }
        }
        this->ntpServer = network->getSettings()->setString(PROP_NTPSERVER, 32,
            (network->getSettingsOld() && network->getSettingsOld()->existsSetting(PROP_NTPSERVER) ? network->getSettingsOld()->getString(PROP_NTPSERVER) : DEFAULT_NTP_SERVER));
        this->ntpServer->setReadOnly(true);
        this->ntpServer->setVisibility(MQTT);
        this->addProperty(ntpServer);
        this->timeZoneConfig = network->getSettings()->setString(PROP_TIMEZONE, 6,
         (network->getSettingsOld() && network->getSettingsOld()->existsSetting(PROP_TIMEZONE) ? network->getSettingsOld()->getString(PROP_TIMEZONE) : DEFAULT_TIME_ZONE));
        // upgrade hack
        String tzval=(String)this->timeZoneConfig->c_str();
        if (tzval.startsWith("http://")){
            network->log()->warning(PSTR("Changing old http Timezone to default"));
            this->timeZoneConfig->setString(DEFAULT_TIME_ZONE);
        }
        this->timeZoneConfig->setReadOnly(true);
        this->timeZoneConfig->setVisibility(MQTT);
        this->addProperty(timeZoneConfig);
        this->timeDST = network->getSettings()->setString(PROP_TIMEDST, 14,
            (network->getSettingsOld() && network->getSettingsOld()->existsSetting(PROP_TIMEDST) ? network->getSettingsOld()->getString(PROP_TIMEDST) : DEFAULT_TIME_DST));
        this->timeDST->setReadOnly(true);
        this->timeDST->setVisibility(MQTT);
        this->addProperty(timeDST);
        this->timeSTD = network->getSettings()->setString(PROP_TIMESTD, 14,
            (network->getSettingsOld() && network->getSettingsOld()->existsSetting(PROP_TIMESTD) ? network->getSettingsOld()->getString(PROP_TIMESTD) : DEFAULT_TIME_STD));
        this->timeSTD->setReadOnly(true);
        this->timeSTD->setVisibility(MQTT);
        this->addProperty(timeSTD);

        parseTimeZone(this->timeZoneConfig->c_str(), &this->timezone_hours, &this->timezone_minutes);
        if (this->timezone_hours == 99) {
            if (!parseTimeRule(this->timeDST->c_str(), &this->timeRuleDst)) parseTimeRule(DEFAULT_TIME_DST, &this->timeRuleDst);
            if (!parseTimeRule(this->timeSTD->c_str(), &this->timeRuleStd)) parseTimeRule(DEFAULT_TIME_STD, &this->timeRuleStd);
        } else {
            resetTimeRule(&this->timeRuleStd);
            resetTimeRule(&this->timeRuleDst);
        }

        network->log()->notice(PSTR("TimeZoneAndRules: TZ:%s, DST:%s, STD:%s"),
                               getTimeZoneIntegerToString(this->timezone_hours, this->timezone_minutes).c_str(),
                               getTimeRuleToString(this->timeRuleDst).c_str(),
                               getTimeRuleToString(this->timeRuleStd).c_str()
                               );


        Rtc.utc_time = 0;
        BreakTime(Rtc.utc_time, RtcTime);

        this->epochTime = new WProperty(PROP_EPOCHTIME, PROP_EPOCHTIME, UNSIGNED_LONG);
        this->epochTime->setAtType(ATTYPE_LONG);
        this->epochTime->setReadOnly(true);
        this->epochTime->setOnValueRequest([this](WProperty* p) {
            p->setUnsignedLong(getEpochTime());
        });
        this->addProperty(epochTime);
        this->epochTimeLocalFormatted = new WStringProperty(PROP_EPOCHTIMELOCALFORMATTED, nullptr, 20);
        this->epochTimeLocalFormatted->setReadOnly(true);
        this->epochTimeLocalFormatted->setOnValueRequest([this](WProperty* p) { updateLocalFormattedTime(); });
        this->addProperty(epochTimeLocalFormatted);
        this->validTime = new WOnOffProperty(PROP_VALIDTIME, nullptr);
        this->validTime->setBoolean(false);
        this->validTime->setReadOnly(true);
        this->addProperty(validTime);
        this->offset = new WIntegerProperty(PROP_OFFSET, nullptr);
        this->offset->setInteger(0);
        this->offset->setReadOnly(true);
        this->addProperty(offset);

        this->uptime = new WLongProperty(PROP_UPTIME);
        this->uptime->setReadOnly(true);
        this->uptime->setOnValueRequest([this](WProperty* p) {
            p->setLong(static_cast<long>(getUptime()));
        });
        this->addProperty(uptime);
        lastTry = lastNtpSync = ntpTime = lastRun = 0;
        lastDiff = 0;

        ntpClient = NTPClient(ntpUDP, ntpServer->c_str());
    }

    void loop(unsigned long now) override {
        TIME_T tmpTime;
        const int ntpRetryMinutes = 1;
        const int ntpResyncMinutes = 5;
        const int ntpInvalidateHours = 48;
        bool notify=false;
        //Invalid after 48 hours failed sync
        if (isValidTime() && !(now - lastNtpSync < (ntpInvalidateHours * 60UL * 60 * 1000) )){
            network->log()->error(F("No valid NTP Time since %d hours -> invalidating"), ntpInvalidateHours);
        }
        validTime->setBoolean((lastNtpSync > 0) && (now - lastNtpSync < (ntpInvalidateHours * 60UL * 60 * 1000)));

        Rtc.utc_time=getEpochTime();
        // calc retry - faster 3 minutes after boot
        const unsigned long syncInterval = lastTry != lastNtpSync
            ? ntpRetryMinutes * (now < 3UL * 60 * 1000 ? 20UL : 60UL) * 1000
            : ntpResyncMinutes * 60UL * 1000;
        if ((
                (!isValidTime() && lastTry == 0) 
                || (now - lastTry >= syncInterval)
            ) && (WiFi.status() == WL_CONNECTED)) {
            network->log()->trace(F("Time via NTP server '%s'"), ntpServer->c_str());
            network->logHeap(PSTR("NTP Start"));
            lastTry = now;
            const uint32_t oldutc = getEpochTime();
            if (ntpClient.update()) {
                network->logHeap(PSTR("NTP GotTime"));
                ntpTime = ntpClient.getEpochTime();
                #ifdef NTPTESTSTART
                ntpTime = NTPTESTSTART + (millis()/1000);
                #endif
                if (ntpTime > START_VALID_TIME) {
                    if (validTime->getBoolean()){
                        // don't save first diff
                        lastDiff=static_cast<int64_t>(ntpTime) - oldutc;
                    }
                    Rtc.utc_time = ntpTime;
                    BreakTime(ntpTime, tmpTime);
                    RtcTime.year = tmpTime.year;
                    Rtc.daylight_saving_time = RuleToTime(this->timeRuleDst, RtcTime.year);
                    Rtc.standard_time = RuleToTime(this->timeRuleStd, RtcTime.year);
                    network->log()->notice(F("NTP time synced: (%04d-%02d-%02d %02d:%02d:%02d, Weekday: %d, Epoch: %d, Dst: %d, Std: %d, OldUTC: %d, ntpTime: %d, Diff: %lld, Uptime: %d)"),
                            tmpTime.year, tmpTime.month, tmpTime.day_of_month, tmpTime.hour, tmpTime.minute, tmpTime.second, tmpTime.day_of_week,
                            ntpTime, Rtc.daylight_saving_time, Rtc.standard_time, oldutc, ntpTime, static_cast<long long>(lastDiff), getUptime() );

                    validTime->setBoolean(true);
                    notify=true;
                    lastNtpSync = now;
                } else {
                    network->log()->error(F("NTP reports invalid time. (%d)"), ntpTime);
                }
            } else {
                network->log()->warning(F("NTP sync failed. "));
            }
                 
        }

        // -------------
        if (!notify && now - lastRun < 1000) return;
        lastRun=now;

        //network->log()->verbose(F("Clock: epoch: %d,timezone_diff: %d, millis: %d, nextSync: %d, lastTry: %d, lastSync: %d"),
        //    getEpochTime(), Rtc.time_timezone, now, nextSync, lastTry, lastNtpSync);

        Rtc.local_time = Rtc.utc_time + Rtc.time_timezone;
        BreakTime(Rtc.local_time, RtcTime);

        if (notify || (RtcTime.minute==0 && RtcTime.second==0)){
            if (Rtc.local_time > START_VALID_TIME) {  // 2016-01-01
                network->log()->trace(F("Clock Recalc Timezone %d"),  Rtc.local_time);
                int32_t newTz;
                if (this->timezone_hours!= 99) {
                    newTz = (this->timezone_hours * 3600L) + (this->timezone_minutes * 60L * (this->timezone_hours < 0 ? -1 : 1));

                } else {
                    int32_t dstoffset = this->timeRuleDst.offset * 60L;
                    int32_t stdoffset = this->timeRuleStd.offset * 60L;
                    
                    if (Rtc.standard_time < Rtc.daylight_saving_time) { 
                        // Southern hemisphere
                        network->log()->trace(F("This year switch to DST/STD: %d / %d (Southern)"),
                        Rtc.daylight_saving_time, Rtc.standard_time);
                        if ((Rtc.utc_time >= (Rtc.standard_time - dstoffset)) && (Rtc.utc_time < (Rtc.daylight_saving_time - stdoffset))) {
                            newTz = stdoffset;  // Standard Time
                        } else {
                            newTz = dstoffset;  // Daylight Saving Time
                        }
                    } else {
                        // Northern hemisphere
                        network->log()->trace(F("This year switch to DST/STD: %d / %d (Northern)"),
                        Rtc.standard_time, Rtc.daylight_saving_time);
                        if ((Rtc.utc_time >= (Rtc.daylight_saving_time - stdoffset)) && (Rtc.utc_time < (Rtc.standard_time - dstoffset))) {
                            newTz = dstoffset;  // Daylight Saving Time
                        } else {
                            newTz = stdoffset;  // Standard Time
                        }
                    }
                }
                if (Rtc.time_timezone!=newTz){
                    network->log()->notice(F("TZ Change %d -> %d"), Rtc.time_timezone, newTz);
                    Rtc.time_timezone = newTz;
                    notify=true;
                    Rtc.local_time = Rtc.utc_time + Rtc.time_timezone;
                    BreakTime(Rtc.local_time, RtcTime);
                } 
            }
        }

        /* 
        if (RtcTime.valid) {
            if (!Rtc.midnight) {
                Rtc.midnight = Rtc.local_time - (RtcTime.hour * 3600) - (RtcTime.minute * 60) - RtcTime.second;
            }
            if (!RtcTime.hour && !RtcTime.minute && !RtcTime.second) {
                Rtc.midnight = Rtc.local_time;
                Rtc.midnight_now = true;
            }
        }
        */

        if (notify){
            this->offset->setReadOnly(false);
            this->offset->setInteger(Rtc.time_timezone);
            this->offset->setReadOnly(true);
            network->log()->notice(F("NotifyNewDateTime"));
            notifyOnTimeUpdate();
        }
    }

    void setOnTimeUpdate(THandlerFunction onTimeUpdate) {
        this->onTimeUpdate = std::move(onTimeUpdate);
    }

    void setOnError(TErrorHandlerFunction onError) {
        this->onError = std::move(onError);
    }

    unsigned long getEpochTime() {
        #ifdef NTPTESTSTART
        return NTPTESTSTART + (millis()/1000);
        #endif
        return (lastNtpSync > 0 ? ntpClient.getEpochTime() : 0);
    }

    unsigned long getEpochTimeLocal() {
        #ifdef NTPTESTSTART
        return (lastNtpSync > 0 ? NTPTESTSTART + (millis()/1000) + getOffset() : 0);
        #endif
        return (lastNtpSync > 0 ? ntpClient.getEpochTime() + getOffset() : 0);
    }

    unsigned long getUptime() {
        return millis() / 1000;
    }

    byte getWeekDay() {
        return RtcTime.day_of_week -1;
    }

    byte getWeekDay(unsigned long epochTime) {
        //weekday from 0 to 6, 0 is Sunday
        TIME_T tmpTime;
        BreakTime(epochTime, tmpTime);
        return tmpTime.day_of_week -1;
    }

    byte getHours() {
        return RtcTime.hour;
    }

    byte getHours(unsigned long epochTime) {
        TIME_T tmpTime;
        BreakTime(epochTime, tmpTime);
        return tmpTime.hour;
    }

    byte getMinutes() {
        return RtcTime.minute;
    }

    byte getMinutes(unsigned long epochTime) {
        TIME_T tmpTime;
        BreakTime(epochTime, tmpTime);
        return tmpTime.minute;
    }

    byte getSeconds() {
        return RtcTime.second;
    }

    byte getSeconds(unsigned long epochTime) {
        TIME_T tmpTime;
        BreakTime(epochTime, tmpTime);
        return tmpTime.second;
    }

    int getYear() {
        return RtcTime.year;
    }

    int getYear(unsigned long epochTime) {
        TIME_T tmpTime;
        BreakTime(epochTime, tmpTime);
        return tmpTime.year;
    }

    byte getMonth() {
        return RtcTime.month;
    }

    byte getMonth(unsigned long epochTime) {
        TIME_T tmpTime;
        BreakTime(epochTime, tmpTime);
        //month from 1 to 12
        return tmpTime.month;
    }

    byte getDay() {
        return RtcTime.day_of_month;
    }

    byte getDay(unsigned long epochTime) {
        TIME_T tmpTime;
        BreakTime(epochTime, tmpTime);
        //day from 1 to 31
        return tmpTime.day_of_month;
    }

    bool isTimeLaterThan(byte hours, byte minutes) {
        return ((getHours() > hours) || ((getHours() == hours) && (getMinutes() >= minutes)));
    }

    bool isTimeEarlierThan(byte hours, byte minutes) {
        return ((getHours() < hours) || ((getHours() == hours) && (getMinutes() < minutes)));
    }

    bool isTimeBetween(byte hours1, byte minutes1, byte hours2, byte minutes2) {
        return ((isTimeLaterThan(hours1, minutes1)) && (isTimeEarlierThan(hours2, minutes2)));
    }

    void updateLocalFormattedTime() {
        updateFormattedTimeImpl(getEpochTimeLocal());
    }

    void updateFormattedTimeImpl(unsigned long rawTime) {
        TIME_T time;
        BreakTime(rawTime, time);
        char buffer[32];
        snprintf(buffer, sizeof(buffer), "%04u-%02u-%02u %02u:%02u:%02u",
            time.year, time.month, time.day_of_month, time.hour, time.minute, time.second);
        epochTimeLocalFormatted->setString(buffer);
    }

    bool isValidTime() {
        return validTime->getBoolean();
    }

    bool isClockSynced() {
        return (lastNtpSync > 0);
    }

    long getOffset() {
        return offset->getInteger();
    }

    void printConfigPage(AsyncWebServerRequest *request, AsyncResponseStream* page) override {
        network->log()->notice(F("Clock config page"));
        page->printf_P(HTTP_CONFIG_PAGE_BEGIN, getId());
        page->printf_P(HTTP_TEXT_FIELD, "NTP server:", "ntp", 32, htmlEscapedString(ntpServer->c_str()).c_str());
        page->printf_P(HTTP_TEXT_FIELD, "Timezone:", "tzone", 6, htmlEscapedString(timeZoneConfig->c_str()).c_str());
        page->printf_P(HTTP_TEXT_FIELD, "TimeRule switch to Daylight Saving Time:", "tdst", 14, htmlEscapedString(timeDST->c_str()).c_str());
        page->printf_P(HTTP_TEXT_FIELD, "TimeRule switch Back to Standard Time:", "tstd", 14, htmlEscapedString(timeSTD->c_str()).c_str());
        page->printf_P(HTTP_TEXT_CLOCK_HOWTO);
        page->printf_P(HTTP_CONFIG_SAVEANDREBOOT_BUTTON);
        page->printf_P(HTTP_HOME_BUTTON);
    }

    void saveConfigPage(AsyncWebServerRequest *request) override {
        const String server = getValueOrEmpty(request, "ntp"), zone = getValueOrEmpty(request, "tzone");
        const String dst = getValueOrEmpty(request, "tdst"), standard = getValueOrEmpty(request, "tstd");
        int16_t hours, minutes;
        TimeRule rule;
        bool valid = server.length() > 0 && server.length() <= 32 && zone.length() <= 6 && dst.length() <= 14 && standard.length() <= 14;
        for (size_t i = 0; i < server.length(); ++i)
            valid &= isalnum(static_cast<unsigned char>(server[i])) || server[i] == '-' || server[i] == '.';
        valid &= parseTimeZone(zone.c_str(), &hours, &minutes);
        if (hours == 99) valid &= parseTimeRule(dst.c_str(), &rule) && parseTimeRule(standard.c_str(), &rule);
        if (!valid) { request->send(400, "text/plain", "Invalid clock configuration"); return; }
        network->log()->notice(F("Save clock config page"));
        this->ntpServer->setString(getValueOrEmpty(request, "ntp").c_str());
        this->timeZoneConfig->setString(getValueOrEmpty(request, "tzone").c_str());
        this->timeDST->setString(getValueOrEmpty(request, "tdst").c_str());
        this->timeSTD->setString(getValueOrEmpty(request, "tstd").c_str());
        network->log()->notice(F("Save clock config page DONE"));
        /* reboot follows */
    }

   private:
    THandlerFunction onTimeUpdate;
    TErrorHandlerFunction onError;
    unsigned long lastTry, lastNtpSync, ntpTime, lastRun;
    int64_t lastDiff;
    WProperty* epochTime;
    WProperty* epochTimeLocalFormatted;
    WProperty* validTime;
    WProperty* uptime;
    WProperty* ntpServer;
    WProperty* timeZoneConfig;
    WProperty* timeDST;
    WProperty* timeSTD;
    WProperty* offset;

    TimeRule timeRuleStd;
    TimeRule timeRuleDst;
    int16_t timezone_hours;
    int16_t timezone_minutes;

    RTC Rtc;
    TIME_T RtcTime;



    void notifyOnTimeUpdate() {
        if (onTimeUpdate) {
            onTimeUpdate();
        }
    }

    void notifyOnError(const char* error) {
        network->log()->notice(F("%s"), error);
        if (onError) {
            onError(error);
        }
    }

    void resetTimeRule(TimeRule* tr) {
        tr->week = 0;
        tr->month = 0;
        tr->dow = 0;
        tr->hour = 0;
        tr->offset = 0;
        tr->initialized = false;
    }

    bool parseTimeRule(const char* text, TimeRule* rule) {
        resetTimeRule(rule);
        if (!text || !*text) return false;
        long values[5];
        const char* cursor = text;
        for (unsigned i = 0; i < 5; ++i) {
            char* end;
            values[i] = strtol(cursor, &end, 10);
            if (end == cursor) return false;
            cursor = end;
            while (*cursor == ' ') ++cursor;
            if (i < 4) { if (*cursor != ',') return false; ++cursor; }
        }
        if (*cursor || values[0] < 0 || values[0] > 4 || values[1] < 1 || values[1] > 12 ||
            values[2] < 0 || values[2] > 7 || values[3] < 0 || values[3] > 23 || values[4] < -900 || values[4] > 900) return false;
        rule->week = values[0]; rule->month = values[1]; rule->dow = values[2] == 0 ? 1 : values[2];
        rule->hour = values[3]; rule->offset = static_cast<int16_t>(values[4]); rule->initialized = true;
        return true;
    }

    String getTimeRuleToString(TimeRule tr) {
        char buf[64];
        size_t size = sizeof buf;
        snprintf_P(buf, size, PSTR("\"Week\":%d,\"Month\":%d,\"Day\":%d,\"Hour\":%d,\"Offset\":%d"),
                   tr.week, tr.month, tr.dow, tr.hour, tr.offset);
        return (String)buf;
    }

    String getTimeZoneIntegerToString(int16_t hours, int16_t minutes) {
        if (hours == 99) return String("DSTSTD");
        char buffer[16];
        const int length = snprintf(buffer, sizeof(buffer), "%c%02d:%02d", hours < 0 || minutes < 0 ? '-' : '+', abs(hours), abs(minutes));
        if (length < 0 || static_cast<size_t>(length) >= sizeof(buffer)) return String();
        return String(buffer);
    }

    bool parseTimeZone(const char* text, int16_t* hours, int16_t* minutes) {
        return parseTimeZoneComponents(text, WHoursOutput(hours), minutes);
    }

    bool parseTimeZoneComponents(const char* text, WHoursOutput hours, int16_t* minutes) {
        *hours.value = 99; *minutes = 0;
        if (!text || !*text || !strcmp(text, "99")) return true;
        const bool negative = *text == '-';
        char* end;
        const long hour = strtol(text, &end, 10);
        if (end == text || hour < -14 || hour > 14) return false;
        long minute = 0;
        if (*end == ':') {
            const char* begin = end + 1;
            if (*begin < '0' || *begin > '9') return false;
            minute = strtol(begin, &end, 10);
        }
        if (*end || minute < 0 || minute > 59 || (abs(hour) == 14 && minute != 0)) return false;
        *hours.value = static_cast<int16_t>(hour);
        *minutes = static_cast<int16_t>(hour == 0 && negative ? -minute : minute);
        return true;
    }

    void BreakTime(uint32_t time_input, TIME_T& tm) {
        // break the given time_input into time components
        // this is a more compact version of the C library localtime function
        uint8_t year;
        uint8_t month;
        uint8_t month_length;
        uint32_t time;
        uint32_t days;

        time = time_input;
        tm.second = time % 60;
        time /= 60;  // now it is minutes
        tm.minute = time % 60;
        time /= 60;  // now it is hours
        tm.hour = time % 24;
        time /= 24;  // now it is days
        tm.days = time;
        tm.day_of_week = ((time + 4) % 7) + 1;  // Sunday is day 1

        year = 0;
        days = 0;
        while (static_cast<unsigned>((days += (LEAP_YEAR(year+1970) ? 366 : 365)) <= time)) {
            year++;
        }
        tm.year = year+1970;  // year is offset from 1970

        days -= LEAP_YEAR(tm.year) ? 366 : 365;
        time -= days;  // now it is days in this year, starting at 0
        tm.day_of_year = time;

        for (month = 0; month < 12; month++) {
            if (1 == month) {  // february
                if (LEAP_YEAR(tm.year)) {
                    month_length = 29;
                } else {
                    month_length = 28;
                }
            } else {
                month_length = kDaysInMonth[month];
            }

            if (time >= month_length) {
                time -= month_length;
            } else {
                break;
            }
        }
        strlcpy(tm.name_of_month, kMonthNames + (static_cast<size_t>(month) * 3), 4);
        tm.month = month + 1;                        // jan is month 1
        tm.day_of_month = time + 1;                  // day of month
        tm.valid = (time_input > START_VALID_TIME);  // 2016-01-01
    }

        uint32_t MakeTime(TIME_T& tm) {
        // assemble time elements into time_t

        int i;
        uint32_t seconds;

        // seconds from 1970 till 1 jan 00:00:00 of the given year
        seconds = (tm.year - 1970) * (SECS_PER_DAY * 365);
        for (i = 1970; i < tm.year; i++) {
            if (LEAP_YEAR(i)) {
                seconds += SECS_PER_DAY;  // add extra days for leap years
            }
        }

        // add days for this year, months start from 1
        for (i = 1; i < tm.month; i++) {
            if ((2 == i) && LEAP_YEAR(tm.year)) {
                seconds += SECS_PER_DAY * 29;
            } else {
                seconds += SECS_PER_DAY * kDaysInMonth[i - 1];  // monthDay array starts from 0
            }
        }
        seconds += (tm.day_of_month - 1) * SECS_PER_DAY;
        seconds += tm.hour * SECS_PER_HOUR;
        seconds += tm.minute * SECS_PER_MIN;
        seconds += tm.second;
        return seconds;
    }

    uint32_t RuleToTime(TimeRule r, int yr) {
        TIME_T tm;
        uint32_t t;
        uint8_t m;
        uint8_t w;  // temp copies of r.month and r.week

        m = r.month;
        w = r.week;
        if (0 == w) {        // Last week = 0
            if (++m > 12) {  // for "Last", go to the next month
                m = 1;
                yr++;
            }
            w = 1;  // and treat as first week of next month, subtract 7 days later
        }

        tm.hour = r.hour;
        tm.minute = 0;
        tm.second = 0;
        tm.day_of_month = 1;
        tm.month = m;
        tm.year = yr;
        t = MakeTime(tm);  // First day of the month, or first day of next month for "Last" rules
        BreakTime(t, tm);
        t += (7 * (w - 1) + (r.dow - tm.day_of_week + 7) % 7) * SECS_PER_DAY;
        if (0 == r.week) {
            t -= 7 * SECS_PER_DAY;  // back up a week if this is a "Last" rule
        }
        return t;
    }

    bool hasInfoPage() override {
        return true;
    }

    void printInfoPage(AsyncResponseStream* page) override {
        htmlTableRowTitle(page, F("Time-Valid:"));
        page->print((isValidTime()  ? "Yes" : "No"));
        htmlTableRowEnd(page);

        htmlTableRowTitle(page, F("Current local Time:"));
        page->print(epochTimeLocalFormatted->c_str());
        htmlTableRowEnd(page);

        htmlTableRowTitle(page, F("Current UTC-Offset:"));
        page->print(offset->getInteger());
        htmlTableRowEnd(page);

        page->print(F("<tr><th>Last-NTP-Sync Try:</th><td>"));
        if (lastTry){
            page->printf("%lu Seconds ago", (millis()-lastTry)/1000);
        } else {
            page->print(F("Never"));
        }        
        htmlTableRowEnd(page);

        htmlTableRowTitle(page, F("Last-NTP-Sync with Success:"));
        if (lastNtpSync){
            page->printf("%lu Seconds ago", (millis()-lastNtpSync)/1000);
        } else {
            page->print(F("Never"));
        }
        htmlTableRowEnd(page);

        htmlTableRowTitle(page, F("Last-NTP-Sync Delta:"));
        page->print(lastDiff);
        page->print(" sec");
        htmlTableRowEnd(page);
    }

};

#endif
