"""JSON batches and scalar command validation."""
import unittest
import test_temperature_commands as temperature
import native_support as native


class ParsersTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_json_properties_mqtt_and_stream(self):
        self.compile_run(None, "parsers")

    def test_state_batch(self):
        s = (
            temperature.TemperatureCommandTests()
            .source()
            .replace('eco{"eco",', 'eco{"ecoMode",')
            + r"""
        #include "lib/WAdapter/WAdapter/WJsonParser.h"
        int main(){
         Probe p;p.eco.parse("true");assert(p.eco.getBoolean()&&p.target.isReadOnly());
         WDevice dev;dev.properties={&p.eco,&p.target};WJsonParser parser;
         auto* result=parser.parse("{\"ecoMode\":false,\"targetTemperature\":999}",&dev);
         printf("Invalid batch: valid=%d eco_after=%d result=%p\n",parser.isValid(),p.eco.getBoolean(),static_cast<void*>(result));
         assert(!parser.isValid()&&p.eco.getBoolean());
        }
        """
        )
        self.compile_run(s, "state_batch")
