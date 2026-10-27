import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


def raw_constant(path, name):
    text = path.read_text()
    match = re.search(re.escape(name) + r'\[\].*?R"=====\((.*?)\)=====";', text, re.S)
    if not match:
        raise AssertionError(f"Missing embedded asset {name}")
    return match.group(1)


@unittest.skipUnless(shutil.which("node"), "Node.js is needed to test embedded JavaScript")
class WebUiTests(unittest.TestCase):
    def test_post_forms_and_csrf_token(self):
        script = raw_constant(ROOT / "lib/WAdapter/WAdapter/WHtmlPages.h", "PAGE_JS")
        probe = r'''
const vm = require('node:vm'), assert = require('node:assert/strict');
const forms = ['/save_network','/reset','/thermostat_reinit','/info','/firmware'].map(action => ({action,method:action==='/firmware'?'post':'get',children:[],appendChild(node){this.children.push(node);}}));
let callback;
const document = {addEventListener(name,fn){assert.equal(name,'DOMContentLoaded');callback=fn;},querySelectorAll(){return forms;},createElement(){return {};}};
vm.runInNewContext(SOURCE,{document,URL,location:{href:'http://thermostat/'},window:{csrfToken:'test-token'}});
callback();
for(const form of forms.slice(0,3)){assert.equal(form.method,'post');assert.equal(form.children.length,1);assert.equal(form.children[0].name,'csrf');assert.equal(form.children[0].value,'test-token');}
assert.equal(forms[3].method,'get');assert.equal(forms[4].method,'post');
'''
        subprocess.run(["node", "-e", "const SOURCE=" + json.dumps(script) + ";\n" + probe], check=True)

    def test_web_log_has_one_ping_timer_and_bounded_text(self):
        script = raw_constant(ROOT / "WThermostat/WLogDevice.h", "HTTP_WEBLOG_SCRIPT")
        script = script.replace("<script>", "").replace("</script>", "")
        probe = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const text={value:'',scrollTop:0},intervals=new Map(),timeouts=[];
let next=0;
class Socket{constructor(){this.readyState=1;}send(){} }
const scope={location:{host:'thermostat'},document:{getElementById(){return text;}},eb(){return text;},WebSocket:Socket,
setInterval(fn){intervals.set(++next,fn);return next;},clearInterval(id){intervals.delete(id);},
setTimeout(fn){timeouts.push(fn);return next++;},clearTimeout(){}};
vm.runInNewContext(SOURCE,scope);scope.ws.onopen();assert.equal(intervals.size,1);
for(let i=0;i<20;i++)scope.ping();assert.equal(timeouts.length,0);
scope.ws.onmessage({data:'x'.repeat(100000)});assert.equal(text.value.length,65536);
scope.ws.onclose({reason:'test'});assert.equal(intervals.size,0);assert.equal(timeouts.length,1);
'''
        subprocess.run(["node", "-e", "const SOURCE=" + json.dumps(script) + ";\n" + probe], check=True)

    def test_checkbox_groups_have_distinct_branches(self):
        script = raw_constant(ROOT / "lib/WAdapter/WAdapter/WHtmlPages.h", "PAGE_JS")
        probe = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const nodes={staticIpEnabled:{checked:false},staticIpGroup:{style:{}},mqttEnabled:{checked:false},mqttGroup:{style:{}}};
const scope={document:{addEventListener(){},getElementById(id){return nodes[id];}}};
vm.runInNewContext(SOURCE,scope);
for(const enabled of [false,true]){
    nodes.staticIpEnabled.checked=enabled;nodes.mqttEnabled.checked=enabled;
    scope.hideStaticIpGroup();scope.hideMqttGroup();
    assert.equal(nodes.staticIpGroup.style.display,enabled?'block':'none');
    assert.equal(nodes.mqttGroup.style.display,enabled?'block':'none');
}
'''
        subprocess.run(["node", "-e", "const SOURCE=" + json.dumps(script) + ";\n" + probe], check=True)
