// MACS-Bus (Electrolux/AEG-Trockner): frame-genaue Rohdaten für den device-bus-analyzer.
//
// Warum nicht einfach "alle Bytes bis zur Ruhezeit"? Die Pausen zwischen den Bytes eines MACS-Frames sind nicht
// verlässlich kürzer als die Pausen zwischen zwei Frames; eine reine Zeitgrenze zerschneidet lange Frames. Dieser
// Rekorder setzt deshalb Frames anhand der Längenangabe zusammen (C9 DD SS LL <LL Bytes> XX, danach optional der ACK
// 98 XX XX2) und schreibt je Frame (mit seinem ACK) EINEN RAW1-Burst. Bytes, die zu keinem Frame passen, gehen
// unverändert und ungedeutet als eigener Burst raus ("rest"). Nichts wird gesendet, nichts verworfen.
//
// Format der Zeilen: docs/LOGFORMAT.md (RAW1 / HB1). Dekodiert wird erst im Analyzer; die kleinen Dekoder hier
// (Zustand, Programm) füttern nur Home-Assistant-Sensoren und sind so unsicher wie in spec/macs.yaml markiert.
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

#ifdef MACS_HOST_TEST
#include <cstdarg>
#define ESP_LOGI(tag, fmt, ...) std::printf(fmt "\n", ##__VA_ARGS__)
#else
#include "esphome/core/log.h"
#endif

namespace macs {

static const uint8_t MARKER = 0xC9;
static const uint8_t ACK = 0x98;

struct Counters {
  uint32_t ok = 0;          // Frames mit gültiger Prüfsumme
  uint32_t crc = 0;         // Kandidaten mit falscher Prüfsumme (Resync um ein Byte)
  uint32_t noack = 0;       // gültige Frames ohne ACK
  uint32_t rest = 0;        // Bytes, die keinem Frame zugeordnet werden konnten
};

static inline uint8_t xor_sum(const uint8_t *d, size_t n) {
  uint8_t c = 0;
  for (size_t i = 0; i < n; i++) c ^= d[i];
  return c;
}

class Recorder {
 public:
  Counters c;
  uint32_t seq = 0, bursts = 0, bytes_total = 0;
  // Zuletzt gesehene Werte (nur für HA-Sensoren, Status "assumed", siehe spec/macs.yaml)
  int state = -1;           // 2a/2252 Byte 1: 0b aus, 01 bereit, 02 läuft, 04 pausiert
  int program = -1;         // 22/2a50 Byte 13: Programmnummer
  int last_command = -1;    // 22/2a51 Byte 1: 60 Start, 61 angewählt, 62 Stopp
  bool inverter_seen = false;  // Verkehr vom Kompressor-Board (0x30) gesehen

  // Neue UART-Bytes. now_us32 = micros(), now_ms = millis().
  void on_bytes(const std::vector<uint8_t> &bytes, uint32_t now_us32, uint32_t now_ms) {
    tick_(now_us32);
    last_rx_ms_ = now_ms;
    buf_.insert(buf_.end(), bytes.begin(), bytes.end());
    drain_(false);
  }

  // Regelmäßig aufrufen (z. B. alle 20 ms): gibt festhängende Bytes nach 40 ms Ruhe frei.
  void on_idle(uint32_t now_us32, uint32_t now_ms) {
    tick_(now_us32);
    if (!buf_.empty() && (uint32_t)(now_ms - last_rx_ms_) >= 40) drain_(true);
  }

  void heartbeat(uint32_t now_us32, long long epoch) {
    tick_(now_us32);
    ESP_LOGI("dbus_raw", "HB1 seq=%u t_us=%llu epoch=%lld bytes=%u bursts=%u ok=%u crc=%u noack=%u rest=%u",
             (unsigned) seq, (unsigned long long) us64_, epoch, (unsigned) bytes_total, (unsigned) bursts,
             (unsigned) c.ok, (unsigned) c.crc, (unsigned) c.noack, (unsigned) c.rest);
  }

  size_t pending() const { return buf_.size(); }

 private:
  std::vector<uint8_t> buf_;
  uint64_t us64_ = 0, prev_burst_us_ = 0;
  uint32_t last_us32_ = 0, last_rx_ms_ = 0;

  void tick_(uint32_t now32) {          // 32-Bit-Überlauf (alle 71 min) abfangen
    us64_ += (uint32_t)(now32 - last_us32_);
    last_us32_ = now32;
  }

  void emit_(const uint8_t *d, size_t n) {
    if (n == 0) return;
    uint64_t dt = us64_ - prev_burst_us_;
    prev_burst_us_ = us64_;
    seq++;
    bursts++;
    bytes_total += (uint32_t) n;
    static const char *H = "0123456789abcdef";
    std::string hex;
    hex.reserve(n * 2);
    for (size_t i = 0; i < n; i++) {
      hex += H[d[i] >> 4];
      hex += H[d[i] & 15];
    }
    ESP_LOGI("dbus_raw", "RAW1 seq=%u t_us=%llu dt_us=%llu n=%u hex=%s", (unsigned) seq,
             (unsigned long long) us64_, (unsigned long long) dt, (unsigned) n, hex.c_str());
  }

  void learn_(const uint8_t *f, size_t n) {   // f = kompletter, geprüfter Frame
    if (n < 6) return;
    uint8_t dest = f[1], src = f[2], type = f[4];
    const uint8_t *data = f + 5;          // Nutzdaten ohne Typ-Byte
    size_t dlen = (size_t) f[3] - 1;
    if (src == 0x30 || dest == 0x30) inverter_seen = true;
    if (src == 0x22 && dest == 0x2A && type == 0x52 && dlen > 1) state = data[1];
    if (src == 0x2A && dest == 0x22 && type == 0x50 && dlen > 13) program = data[13];
    if (src == 0x2A && dest == 0x22 && type == 0x51 && dlen > 1) last_command = data[1];
  }

  // Zerlegt buf_. force = true: Rest nach Ruhezeit freigeben, auch wenn ein Frame unvollständig ist.
  void drain_(bool force) {
    size_t i = 0;
    while (i < buf_.size()) {
      size_t avail = buf_.size() - i;
      const uint8_t *p = &buf_[i];
      if (p[0] == MARKER) {
        if (avail < 4) {
          if (!force) break;
          c.rest += avail; emit_(p, avail); i += avail; break;
        }
        size_t total = (size_t) p[3] + 5;
        if (avail < total) {
          if (!force) break;
          c.rest += avail; emit_(p, avail); i += avail; break;
        }
        if (xor_sum(p, total - 1) != p[total - 1]) {
          c.crc++;                      // Prüfsumme falsch: dieses Byte als Rest ausgeben und neu aufsetzen
          c.rest++;
          emit_(p, 1);
          i += 1;
          continue;
        }
        size_t rem = avail - total;
        size_t unit = total;
        if (rem == 0 && !force) break;  // ACK könnte noch kommen
        if (rem >= 1 && p[total] == ACK) {
          if (rem < 3 && !force) break;
          if (rem >= 3 && p[total + 1] == p[total - 1] && p[total + 2] == (uint8_t)(ACK ^ p[total - 1])) {
            unit = total + 3;
          } else {
            c.noack++;
          }
        } else {
          c.noack++;
        }
        c.ok++;
        learn_(p, total);
        emit_(p, unit);
        i += unit;
        continue;
      }
      if (p[0] == ACK && avail < 3 && !force) break;
      // alles bis zum nächsten möglichen Frame-/ACK-Anfang ist Rest (ein verwaister ACK zählt auch dazu)
      size_t n = 1;
      while (n < avail && p[n] != MARKER && p[n] != ACK) n++;
      c.rest += (uint32_t) n;
      emit_(p, n);
      i += n;
    }
    buf_.erase(buf_.begin(), buf_.begin() + (std::ptrdiff_t) i);
  }
};

// Einziges Rekorder-Objekt. Bewusst KEINE ESPHome-`globals`-Variable: ESPHome legt deren Typ vor den eigenen
// Includes in main.cpp an, der Typ wäre dort noch unbekannt ("'macs' was not declared in this scope").
inline Recorder &rec() {
  static Recorder r;
  return r;
}

}  // namespace macs
