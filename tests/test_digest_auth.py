"""Test the boot-local replay guard with the pinned verifier and hashlib vectors."""

import hashlib
import json
import unittest

import test_regressions as native
from test_regressions import ROOT, method


class DigestAuthTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_nonce_uri_password_counter_expiry_and_parallel_requests(self):
        sdk = (
            ROOT
            / ".pio/libdeps/wthermostat/ESPAsyncWebServer/src/WebAuthentication.cpp"
        )
        if not sdk.exists():
            self.fail(
                "Install the pinned PlatformIO dependencies before running Digest integration tests"
            )
        hashes = {}

        def md5(text):
            result = hashlib.md5(text.encode()).hexdigest()
            hashes[text] = result
            return result

        vectors = []
        passwords = [
            "test-password",
            "a" * 63,
            "A" * 64,
            " !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~ ",
            "èéàü☃-password",
        ]
        for password in passwords:
            for uri in [
                "/firmware",
                "/save_network",
                "/wifi?",
                "/things/a%20b?x=a%2Bb&y=",
            ]:
                for count in [1, 2, 3, 4, 33, 34, 35, 40]:
                    nonce, opaque = f"{1:032x}", f"{2:032x}"
                    nc = f"{count:08x}"
                    response = md5(
                        ":".join(
                            [
                                md5("admin:WThermostat:" + password),
                                nonce,
                                nc,
                                "client",
                                "auth",
                                md5("POST:" + uri),
                            ]
                        )
                    )
                    header = f'Digest username="admin", realm="WThermostat", nonce="{nonce}", opaque="{opaque}", uri="{uri}", response="{response}", qop=auth, nc={nc}, cnonce="client"'
                    vectors.append((password, uri, count, header))
        source = r"""
#include "Arduino.h"
#include <map>
#include "lib/WAdapter/WAdapter/WDigestAuth.h"
unsigned randomCounter=0;
String genRandomMD5(){char value[33];snprintf(value,sizeof(value),"%032x",++randomCounter);return value;}
namespace asyncsrv{const String emptyString;}
"""
        source += (
            "namespace asyncsrv{"
            + "".join(
                f'const char*T_{key}="{key}";'
                for key in [
                    "username",
                    "realm",
                    "nonce",
                    "opaque",
                    "uri",
                    "response",
                    "qop",
                    "nc",
                    "cnonce",
                ]
            )
            + "}\nusing namespace asyncsrv;\n"
        )
        source += (
            "String stringMD5(const String& input){static const std::map<String,String> hashes={"
            + ",".join(
                "{" + json.dumps(a, ensure_ascii=False) + "," + json.dumps(b) + "}"
                for a, b in hashes.items()
            )
            + "};auto it=hashes.find(input);return it==hashes.end()?String():it->second;}\n"
        )
        source += method(sdk, "checkDigestAuthentication") + "\n"
        source += (
            "struct Vector{String password,uri;unsigned count;String header;};\nVector vectors[]={"
            + ",".join(
                "{"
                + ",".join(
                    [
                        json.dumps(p, ensure_ascii=False),
                        json.dumps(u),
                        str(c),
                        json.dumps(h),
                    ]
                )
                + "}"
                for p, u, c, h in vectors
            )
            + "};\n"
        )
        source += r"""
struct Param{String key,text;bool isPost()const{return false;}bool isFile()const{return false;}String name()const{return key;}String value()const{return text;}};
struct Request{
 String path="/firmware";Param auth;bool valid=false;std::vector<Param> query;
 bool hasHeader(const char* name){return !strcmp(name,"Authorization")&&!auth.text.empty();}
 Param*getHeader(const char*){return &auth;}
 bool getAttribute(const char*,bool fallback){return valid?true:fallback;}
 void setAttribute(const char*,bool value){valid=value;}
 String url(){return path;}const char*methodToString(){return "POST";}
 unsigned params(){return query.size();}const Param*getParam(unsigned i){return &query.at(i);}
 String urlDecode(const String& input){String result;for(size_t i=0;i<input.size();++i){
  if(input[i]=='%'&&i+2<input.size()){char hex[]={input[i+1],input[i+2],0};result.push_back(strtol(hex,nullptr,16));i+=2;}
  else result.push_back(input[i]=='+'?' ':input[i]);}return result;}
};
String header(const String& password,const String& uri,unsigned count){for(const auto&v:vectors)if(v.password==password&&v.uri==uri&&v.count==count)return v.header;assert(false);return "";}
int main(){
 for(const auto&v:vectors){randomCounter=0;testMillis=100;WDigestAuth auth;assert(!auth.challenge().empty());Request r;r.auth.text=v.header;
  if(v.uri=="/save_network")r.path=v.uri;
  if(v.uri=="/wifi?")r.path="/wifi";
  if(v.uri.indexOf("?x=")>=0){r.path="/things/a b";r.query={{"x","a+b"},{"y",""}};}
  assert(auth.authenticate(&r,v.password.c_str()));assert(auth.authenticate(&r,v.password.c_str()));
  Request replay=r;replay.valid=false;assert(!auth.authenticate(&replay,v.password.c_str()));
 }
 randomCounter=0;testMillis=100;WDigestAuth auth;auth.challenge();
 Request wrong;wrong.auth.text=header("test-password","/firmware",1);assert(!auth.authenticate(&wrong,"incorrect"));
 wrong.auth.text=header("test-password","/save_network",1);assert(!auth.authenticate(&wrong,"test-password"));
 wrong.auth.text=header("test-password","/firmware",1);assert(auth.authenticate(&wrong,"test-password"));
 for(const auto& expected:std::vector<std::pair<unsigned,bool>>{{3,true},{2,true},{35,true},{34,true},{4,true},{40,true},{3,false},{34,false}}){Request r;r.auth.text=header("test-password","/firmware",expected.first);
  assert(auth.authenticate(&r,"test-password")==expected.second);}
 Request stale;stale.auth.text=header("test-password","/firmware",33);testMillis=300100;assert(!auth.authenticate(&stale,"test-password"));
 randomCounter=0;testMillis=0;WDigestAuth evicted;for(int i=0;i<5;++i)evicted.challenge();
 Request first;first.auth.text=header("test-password","/firmware",1);assert(!evicted.authenticate(&first,"test-password"));
 for(const char* malformed:{"Digest", "Basic abc", "Digest username", "Digest username=", "Digest username=\"", "Digest username=\"admin\",username=\"admin\""}){
  Request r;r.auth.text=malformed;assert(!evicted.authenticate(&r,"test-password"));}
 puts("PASS real Digest verifier, long/UTF-8 passwords, URI/query binding, replay window, request reuse, expiry and eviction");
}
"""
        self.compile_run(source, "digest_auth")
