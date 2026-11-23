// Host harness for src/device_bus_analyzer/firmware/macs_recorder.h. stdin: one command per line:
//   "<hex>"   -> bytes arrive (one UART callback), time advances 5 ms
//   "IDLE"    -> 100 ms of silence, then on_idle()
//   "HB"      -> heartbeat line
//   "BUF <n>" -> use_buffer(n);  "LIVE 0|1" -> set_live();  "FLUSH <n>" -> flush(n)
// stdout: the log lines the firmware would write, followed by "STATE <state> <program> <last_command> <inverter_seen>".
#define MACS_HOST_TEST
#include "../../src/device_bus_analyzer/firmware/macs_recorder.h"
#include <iostream>

int main() {
  macs::Recorder r;
  uint32_t us = 1000, ms = 1;
  std::string line;
  while (std::getline(std::cin, line)) {
    if (line == "IDLE") { us += 100000; ms += 100; r.on_idle(us, ms); continue; }
    if (line == "HB") { r.heartbeat(us, 1800000000LL); continue; }
    if (line.rfind("BUF ", 0) == 0) { r.use_buffer(std::stoul(line.substr(4))); continue; }
    if (line.rfind("LIVE ", 0) == 0) { r.set_live(line.substr(5) == "1"); continue; }
    if (line.rfind("FLUSH ", 0) == 0) { std::printf("FLUSHED %zu\n", r.flush(std::stoul(line.substr(6)))); continue; }
    std::vector<uint8_t> b;
    for (size_t i = 0; i + 1 < line.size(); i += 2) b.push_back((uint8_t) std::stoi(line.substr(i, 2), nullptr, 16));
    us += 5000; ms += 5;
    r.on_bytes(b, us, ms);
  }
  std::printf("STATE %d %d %d %d pending=%zu buffered=%zu dropped=%u\n", r.state, r.program, r.last_command,
              (int) r.inverter_seen, r.pending(), r.buffered(), (unsigned) r.dropped);
}
