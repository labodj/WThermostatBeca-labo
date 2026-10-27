#ifndef W_ARGUMENTS_H
#define W_ARGUMENTS_H

#include <stdint.h>

// Explicit roles prevent argument swaps; legacy overloads keep existing calls valid.
template<typename T, typename Role> struct WArgument {
    T value;
    explicit constexpr WArgument(T value) : value(value) {}
};

using WMqttTopic = WArgument<const char*, struct WMqttTopicRole>;
using WTextTitle = WArgument<const char*, struct WTextTitleRole>;
using WDeviceType = WArgument<const char*, struct WDeviceTypeRole>;
using WJsonName = WArgument<const char*, struct WJsonNameRole>;
template<typename T> using WMinimum = WArgument<T, struct WMinimumRole>;
using WConsoleLogLevel = WArgument<int, struct WConsoleLogLevelRole>;
using WStatusLedPin = WArgument<int, struct WStatusLedPinRole>;
using WTolerance = WArgument<double, struct WToleranceRole>;
using WEepromAddress = WArgument<int, struct WEepromAddressRole>;
using WHoursOutput = WArgument<int16_t*, struct WHoursOutputRole>;

#endif
