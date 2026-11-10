"""A synchronous lwIP error callback may destroy the aborting client."""

import unittest

import test_regressions as native


class TcpAbortTests(unittest.TestCase):
    compile_run = native.NativeTests.compile_run

    def test_abort_callback_can_delete_client_without_late_access(self):
        path = native.tcp_source()
        abort = native.method(path, "AsyncClient::abort")
        self.compile_run(r'''
#include <cassert>
#include <memory>
using err_t = int;
constexpr err_t ERR_ABRT = -13;
struct tcp_pcb {};
struct Tracker { err_t error = 0; };
struct AsyncClient {
    tcp_pcb* _pcb = nullptr;
    std::shared_ptr<Tracker> tracker = std::make_shared<Tracker>();
    void setCloseError(err_t e) { tracker->error = e; }
    void abort();
};
AsyncClient* active = nullptr;
unsigned calls = 0;
bool detached = false, marked = false;
void tcp_abort(tcp_pcb* pcb) {
    assert(pcb != nullptr);
    ++calls;
    detached = active->_pcb == nullptr;
    marked = active->tracker->error == ERR_ABRT;
    delete active;
    active = nullptr;
}
''' + abort + r'''
int main() {
    tcp_pcb pcb;
    active = new AsyncClient;
    active->_pcb = &pcb;
    auto tracker = active->tracker;
    active->abort();
    assert(active == nullptr && calls == 1 && tracker->error == ERR_ABRT);
    assert(detached && marked);
    AsyncClient empty;
    empty.abort();
    assert(calls == 1 && empty.tracker->error == 0);
}
''', "tcp_abort_lifetime")
