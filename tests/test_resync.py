"""Run the real resync page callbacks without accessing a thermostat."""
import unittest

import test_regressions as native


class ResyncTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_only_explicit_post_confirmation_starts_resync(self):
        source = native.BECA.read_text()
        constants = "\n".join(line for line in source.splitlines()
                              if line.startswith(("const char* ID_PAGE_REINIT ", "const char* TITLE_PAGE_REINIT ")))
        setup = source[source.index("WPage * reinitPage="):source.index("this->addPage(reinitPage);") + len("this->addPage(reinitPage);")]
        self.compile_run(r'''
#include "Arduino.h"
struct AsyncWebServerRequest;
#include "lib/WAdapter/WAdapter/WPage.h"
constexpr int HTTP_GET=1,HTTP_POST=2;
struct AsyncWebServerRequest {
    struct Parameter {String text;const String&value(){return text;}} confirmation;
    int verb=HTTP_GET;bool bodyConfirm=false,queryConfirm=false;
    int method(){return verb;}
    bool hasParam(const char*name,bool body){return !strcmp(name,"confirm")&&(body?bodyConfirm:queryConfirm);}
    Parameter*getParam(const char*name,bool body){return hasParam(name,body)?&confirmation:nullptr;}
};
struct Capture:Print {
    std::string text;
    size_t write(uint8_t c)override{text+=static_cast<char>(c);return 1;}
    size_t write(const uint8_t*data,size_t size)override{text.append(reinterpret_cast<const char*>(data),size);return size;}
};
struct Network {const char*getCsrfToken(){return "resync-test-token";}};
''' + constants + r'''
struct Thermostat {
    Network net;Network*network=&net;WPage*page=nullptr;unsigned resyncs=0;
    ~Thermostat(){delete page;}
    void addPage(WPage*value){page=value;}
    void startMcuInitialize(){++resyncs;}
    void install(){
''' + setup + r'''
    }
};
int main(){
    Thermostat thermostat;thermostat.install();assert(thermostat.resyncs==0);
    assert(!strcmp(thermostat.page->getId(),"reinit"));
    assert(!strcmp(thermostat.page->getTitle(),"Resync thermostat"));
    for(int verb:{HTTP_GET,HTTP_POST}){
        AsyncWebServerRequest r;r.verb=verb;r.bodyConfirm=true;r.confirmation.text="1";
        Capture out;WCheckedPrint page(&out);thermostat.page->printPage(&r,&page);
        assert(page.ok()&&thermostat.resyncs==0);
        assert(out.text.find("/save_thermostat_reinit")!=std::string::npos);
        assert(out.text.find("resync-test-token")!=std::string::npos);
        assert(out.text.find(">Cancel</button>")!=std::string::npos);
    }
    for(int scenario=0;scenario<5;++scenario){
        AsyncWebServerRequest r;r.verb=scenario==0?HTTP_GET:HTTP_POST;
        r.bodyConfirm=scenario==0||scenario==2||scenario==4;r.queryConfirm=scenario==3;
        r.confirmation.text=scenario==2?"0":scenario==4?"":"1";
        Capture out;WCheckedPrint page(&out);thermostat.page->submittedPage(&r,&page);
        assert(page.ok()&&thermostat.resyncs==0);
        assert(out.text.find("No action was taken")!=std::string::npos);
    }
    AsyncWebServerRequest confirmed;confirmed.verb=HTTP_POST;
    confirmed.bodyConfirm=true;confirmed.confirmation.text="1";
    Capture out;WCheckedPrint page(&out);thermostat.page->submittedPage(&confirmed,&page);
    assert(page.ok()&&thermostat.resyncs==1);
    assert(out.text.find("Resynchronization requested")!=std::string::npos);
}
''', "explicit_resync")
