"""Exercise bounded segmented page storage, early release and allocation failures."""
import unittest
import native_support as native


class PageResponseTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_fragmented_storage_failures_and_lifetime(self):
        self.compile_run(r'''
#include "Arduino.h"
#include <cstdlib>
#include <new>
#include <limits>
void*blocks[64]={};size_t live=0,largest=0;
size_t remaining=std::numeric_limits<size_t>::max();
void*operator new(size_t size){void*p=std::malloc(size);if(!p)throw std::bad_alloc();return p;}
void operator delete(void*p)noexcept{
 for(auto&block:blocks)if(block==p&&p){block=nullptr;--live;break;}
 std::free(p);
}
void operator delete(void*p,size_t)noexcept{::operator delete(p);}
void*operator new(size_t size,const std::nothrow_t&)noexcept{
 if(!remaining)return nullptr;--remaining;largest=std::max(largest,size);
 // Even an 8 KiB page must fit when no contiguous allocation exceeds 300 bytes.
 if(size>300)return nullptr;
 void*p=::operator new(size);for(auto&block:blocks)if(!block){block=p;++live;return p;}
 assert(false);return nullptr;
}
#include "lib/WAdapter/WAdapter/WPageResponse.h"
int main(){
 std::string expected;for(size_t n=0;n<8192;++n)expected+=char(n%251);
 for(size_t quota:{1U,7U,256U,536U,1072U}){
  remaining=100;WPageResponse response("text/html");
  assert(response.write(reinterpret_cast<const uint8_t*>(expected.data()),expected.size())==expected.size());
  assert(response._sourceValid()&&response.contentLength()==8192&&live==32);
  response.startForTest();assert(response.write(uint8_t('x'))==0);
  uint8_t data[1072];std::string actual;
  while(size_t n=response._fillBuffer(data,quota))actual.append(reinterpret_cast<char*>(data),n);
  assert(actual==expected&&live==0&&response.contentLength()==8192);
 }
 for(size_t failure=0;failure<32;++failure){
  {remaining=failure;WPageResponse response("text/html");
   assert(response.write(reinterpret_cast<const uint8_t*>(expected.data()),expected.size())<expected.size());
   assert(!response._sourceValid());assert(response.write(uint8_t('x'))==0);
  }assert(live==0);
 }
 {remaining=100;WPageResponse response("text/html");
  assert(response.write(reinterpret_cast<const uint8_t*>(expected.data()),8192)==8192);
  assert(response.write(uint8_t('x'))==0&&!response._sourceValid());
 }assert(live==0&&largest<=300);
 puts("PASS segmented pages, fragmented heap, exact binary bytes, allocation failures and early release");
}
''', "segmented_page_response")
