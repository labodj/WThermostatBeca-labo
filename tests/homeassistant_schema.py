"""Validate firmware output with the installed, pinned Home Assistant schemas.

Run explicitly in the isolated HA environment; never silently skip this check.
"""
from copy import deepcopy
import json
import tempfile
import unittest

import probatio

from homeassistant.components.mqtt import climate, discovery, sensor
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

from test_homeassistant import discovery_records


def normalized(payload):
    value = json.loads(payload)
    discovery._replace_all_abbreviations(value)
    discovery._replace_topic_base(value)
    return value


class OfficialSchemaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="wthermostat-ha-")
        self.hass = HomeAssistant(self.directory.name)

    async def asyncTearDown(self):
        await self.hass.async_stop()
        self.directory.cleanup()

    async def test_all_emitted_configs_and_templates(self):
        checked = 0
        for case, topic, retained, payload in discovery_records():
            if not topic.startswith("homeassistant/") or not payload:
                continue
            with self.subTest(case=case, topic=topic):
                component = topic.split("/")[1]
                self.assertIsNotNone(discovery.TOPIC_MATCHER.fullmatch(topic.removeprefix("homeassistant/")))
                config = normalized(payload)
                schema = climate.DISCOVERY_SCHEMA if component == "climate" else sensor.DISCOVERY_SCHEMA
                validated = schema(deepcopy(config))
                # HA ignores unknown discovery keys: catch typos rather than accept that fallback.
                self.assertFalse(set(config) - set(validated))
                self.assertTrue(retained)
                self.assertTrue(validated["device"]["identifiers"])
                state = {"temperature": 21.5, "floorTemperature": 22.5, "targetTemperature": 23.5,
                         "mode": "heat", "action": "heating", "preset": "none", "fanMode": "low",
                         "rssi": -62, "ip": "192.0.2.1"}
                for key, value in validated.items():
                    if isinstance(value, Template):
                        value.ensure_valid()
                        property_name = value.template.split("value_json.")[1].split("}")[0]
                        self.assertEqual(str(state[property_name]),
                                         value.async_render_with_possible_json_value(json.dumps(state)))
                checked += 1
        self.assertEqual(126, checked)

    async def test_bad_configs_are_rejected(self):
        payload = next(payload for _, topic, _, payload in discovery_records() if "/climate/" in topic)
        config = normalized(payload)
        for mutation in ({"temperature_unit": "K"}, {"precision": 0.2}, {"preset_modes": ["none"]},
                         {"availability_mode": "invalid"}, {"temperature_command_topic": "bad/#"}):
            with self.subTest(mutation=mutation), self.assertRaises(probatio.Invalid):
                climate.DISCOVERY_SCHEMA(config | mutation)


if __name__ == "__main__":
    unittest.main(verbosity=2)
