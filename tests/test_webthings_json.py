"""HTTP JSON must be complete or return a storage/allocation error."""

import re
import unittest

import test_regressions as native
from test_regressions import BECA, NETWORK, ROOT, method


class WebThingsResponseTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_complete_schema_and_failed_streams(self):
        dev = ROOT / "lib/WAdapter/WAdapter/WDevice.h"
        text = BECA.read_text()
        const = text[
            text.index("#define COUNT_DEVICE_MODELS") : text.index("//typedef")
        ]
        constructor = text[
            text.index("    WBecaDevice(WNetwork*") : text.index(
                "    virtual void printConfigPage"
            )
        ]
        fields = [
            "switchBackToAuto",
            "actualTemperature",
            "actualFloorTemperature",
            "targetTemperature",
            "deviceOn",
            "schedulesMode",
            "ecoMode",
            "locked",
            "mode",
            "preset",
            "action",
            "state",
            "mcuId",
        ]
        creates = {
            f: (cls, args)
            for f, cls, args in re.findall(
                r"this->(\w+)\s*=\s*new (W\w*Property)\((.*?)\);",
                constructor,
                re.DOTALL,
            )
        }
        s = (
            r"""
        #include "Arduino.h"
        #include "Stream.h"
        #include "lib/WAdapter/WAdapter/WProperty.h"
        #include "lib/WAdapter/WAdapter/WTargetTemperatureProperty.h"
        #include "lib/WAdapter/WAdapter/WTemperatureProperty.h"
        #include "lib/WAdapter/WAdapter/WOnOffProperty.h"
        #include "lib/WAdapter/WAdapter/WStringStream.h"
        """
            + const
        )
        s += dev.read_text()[
            dev.read_text().index(
                "const char* DEVICE_TYPE_ON_OFF_SWITCH"
            ) : dev.read_text().index("class WNetwork;")
        ]
        s += "struct Device;using WDevice=Device;\nstruct Device{WProperty*firstProperty=nullptr,*lastProperty=nullptr;\n"
        s += "WProperty*" + ",*".join(fields) + ";\n"
        s += (
            r"""
         const char*getFullName(){return "room_Thermostat";}const char*getId(){return "thermostat";}const char*getType(){return "Thermostat";}
         int getThermostatModel(){return 0;}void onPropertyChange(){}
        """
            + method(dev, "addProperty")
            + method(dev, "toJsonStructure")
            + "\nDevice(){\n"
        )
        for f in fields:
            cls, args = creates[f]
            s += f"{f}=new {cls}({args});addProperty({f});\n"
            # Read-only, type and visibility metadata are taken from the constructor.
            for call in re.findall(
                r"this->"
                + f
                + r"->((?:setAtType|setReadOnly|setVisibility)\([^;]*\));",
                constructor,
            ):
                s += f"{f}->{call};\n"
        for f in fields:
            for enum in re.findall(
                r"this->" + f + r"->addEnumString\((\w+)\);", constructor
            ):
                if enum in [
                    "MODE_COOL",
                    "MODE_FAN",
                    "PRESET_SCHEDULER",
                    "ACTION_COOLING",
                    "ACTION_FAN",
                ]:
                    continue
                s += f"{f}->addEnumString({enum});\n"
        s += "targetTemperature->setMultipleOf(0.5);\n"
        s += "}\n~Device(){for(WProperty*p=firstProperty;p;){WProperty*n=p->next;delete p;p=n;}}\n};\n"
        s += (
            r"""
        using WDevice=Device;
        const char*APPLICATION_JSON="application/json",*URI_THINGS="/things";
        struct Log{template<class...T>void verbose(T...){}};

        #include "lib/WAdapter/WAdapter/WCheckedPrint.h"
        struct AsyncResponseStream:Print{
         std::string body;size_t limit;explicit AsyncResponseStream(size_t limit):limit(limit){}
         size_t write(uint8_t b)override{return write(&b,1);}
         size_t write(const uint8_t*p,size_t n)override{size_t count=std::min(n,limit-body.size());body.append(reinterpret_cast<const char*>(p),count);return count;}
        };
        struct AsyncWebServerRequest{
         int status=0;std::string body;bool allocationFails=false;size_t limit=10000;
         AsyncResponseStream*beginResponseStream(const char*){return allocationFails?nullptr:new AsyncResponseStream(limit);}
         void send(int code){status=code;body.clear();}
         void send(AsyncResponseStream*r){status=200;body=r->body;delete r;}
        };
        struct Probe{Log logger;Log*wlog=&logger;
        """
            + "template<class Serializer>\n"
            + method(NETWORK, "sendJson")
            + method(NETWORK, "sendDeviceStructure")
            + r"""
        };
        int main(){Device device;WStringStream full(16384);WJson json(&full);device.toJsonStructure(&json,"/things",WEBTHING);
         Probe p;AsyncWebServerRequest request;p.sendDeviceStructure(&request,&device);

         assert(full.length()>2048&&request.status==200&&request.body==full.c_str());
         for(size_t limit:{0U,1U,2048U}){AsyncWebServerRequest failed;failed.limit=limit;p.sendDeviceStructure(&failed,&device);assert(failed.status==503&&failed.body.empty());}
         AsyncWebServerRequest failed;failed.allocationFails=true;p.sendDeviceStructure(&failed,&device);assert(failed.status==503);
         AsyncWebServerRequest oversized;p.sendJson(&oversized,[](WJson& json){json.beginObject();json.propertyString("large",std::string(9000,'x').c_str());json.endObject();});
         assert(oversized.status==503&&oversized.body.empty());
         puts("PASS complete BHT/floor schema beyond 2048 bytes, failed allocation/writes and response-size limit");}

        """
        )
        self.compile_run(s, "webthings_json")
