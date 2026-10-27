#include "properties.h"
#include "lib/WAdapter/WAdapter/WJsonParser.h"
#include "lib/WAdapter/WAdapter/cstrreplace.h"
#include "lib/WAdapter/WAdapter/WStringStream.h"
#include "lib/WAdapter/WAdapter/WLevelIntProperty.h"
enum {INPUT,OUTPUT,INPUT_PULLUP};
int configured=-1;
void pinMode(int pin,int){configured=pin;}
#include "lib/WAdapter/WAdapter/WPin.h"
class AsyncWebServerRequest;class AsyncResponseStream;
#include "lib/WAdapter/WAdapter/WPage.h"

struct Callback {
    static int copies,calls;
    Callback()=default;
    Callback(const Callback&){++copies;}
    void operator()(WProperty*)const{++calls;}
};
int Callback::copies=0;int Callback::calls=0;
int main(){
    WProperty value("value","Value",BOOLEAN);
    WProperty::TOnPropertyChange callback=Callback{};
    const int copies=Callback::copies;
    value.setOnChange(std::move(callback));assert(!callback&&Callback::copies==copies);
    value.setBoolean(true);assert(Callback::calls==1);
    struct Case{const char* text;const char* pattern;const char* replacement;const char* expected;};
    for(const auto& test:std::vector<Case>{{"aaaa","aa","b","bb"},{"aaa","aa","xyzz","xyzza"},{"room","o","","rm"},{"hello","","x","hello"},{"","a","long",""},{"abc","z","x","abc"}}){
        char* result=cstrReplace(test.text,test.pattern,test.replacement);
        assert(result&&!strcmp(result,test.expected));free(result);
    }
    assert(!cstrReplace(nullptr,"x","y"));assert(!cstrReplace("x",nullptr,"y"));
    WPin disabled(-1,OUTPUT);assert(configured==-1);
    WPin valid(4,OUTPUT);assert(configured==4);
    struct Inspect:WStringStream {Inspect():WStringStream(8){}unsigned long start(){return _startMillis;}} stream;
    assert(stream.start()==0&&stream.available()==0);
    WLevelIntProperty level("level","Level",-10,20);
    assert(!strcmp(level.getAtType(),ATTYPE_LEVELINT));assert(level.getMinimum()==-10&&level.getMaximum()==20);
    bool destroyed=false;
    struct Page:WPage {bool& flag;Page(bool& flag):WPage("id","Title"),flag(flag){}~Page(){flag=true;}};
    WPage* page=new Page(destroyed);assert(!strcmp(page->getId(),"id")&&!strcmp(page->getTitle(),"Title"));
    delete page;assert(destroyed);
    puts("PASS callback ownership, replacement bounds, pin/stream initialization and level metadata");
}
