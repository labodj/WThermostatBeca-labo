"""Run the documented rules through production conversion against zoneinfo."""
import json
import unittest
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo
import native_support as native
from native_support import ROOT, method


class DocumentedTimezoneTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_examples_match_regional_offsets_and_transitions(self):
        clock = ROOT / 'WThermostat/WClock.h'
        text = clock.read_text()
        source = '#include "properties.h"\n#define SECS_PER_DAY 86400UL\n#define SECS_PER_HOUR 3600UL\n#define SECS_PER_MIN 60UL\n'
        source += text[text.index('typedef struct {'):text.index('WiFiUDP ntpUDP')]
        source += '\nstruct Probe{\n'
        for name in ['resetTimeRule', 'parseTimeRule', 'parseTimeZone', 'parseTimeZoneComponents', 'BreakTime', 'MakeTime', 'RuleToTime']:
            source += method(clock, name) + '\n'
        source += '\n};\nint main(){Probe p;TimeRule rule;int16_t h,m;\n'
        examples = {}
        for line in (ROOT / 'Configuration.md').read_text().splitlines():
            if line.strip().startswith('|'):
                parts = [part.strip() for part in line.split('|')[1:]]
                if len(parts) >= 5:
                    examples[parts[0]] = parts[1:4]
        for label in ['UTC', 'Pacific/Honolulu', 'Asia/Shanghai (Beijing time)', 'Europe/Berlin', 'Europe/London', 'America/New_York', 'Australia/Sydney']:
            zone = ZoneInfo(label.split(' (')[0])
            fixed, dst, standard = examples[label]
            if fixed != '99':
                expected = int(datetime(2026, 1, 1, tzinfo=zone).utcoffset().total_seconds())
                source += f'assert(p.parseTimeZone({json.dumps(fixed)},&h,&m));assert(h*3600L+m*60L*(h<0?-1:1)=={expected});\n'
                continue
            for year in [2026, 2027]:
                instant = datetime(year, 1, 1, tzinfo=UTC)
                previous = instant.astimezone(zone).utcoffset()
                while instant.year == year:
                    offset = instant.astimezone(zone).utcoffset()
                    if offset != previous:
                        selected = dst if offset > previous else standard
                        source += f'assert(p.parseTimeRule({json.dumps(selected)},&rule));assert(p.RuleToTime(rule,{year})-({int(previous.total_seconds())}L)=={int(instant.timestamp())}UL);assert(rule.offset*60L=={int(offset.total_seconds())});\n'
                    previous = offset
                    instant += timedelta(hours=1)
        source += 'puts("PASS documented fixed offsets and all 2026/2027 seasonal transitions");}\n'
        self.compile_run(source, 'documented_timezones')
