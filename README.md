# garden-room-lights

Time-of-day lighting for one room built from cheap WLED strips, plus a
Bluetooth-only white LED controller (BanlanX SP630E) brought into Home Assistant
through a cheap ESP32. One Python script and one `schedule.json`: warm and dim early
and late, neutral and bright in working hours.

It's a side project from my own garden room (about 15 m², six WLED strips, one
white strip), so it isn't a polished product. But it works, and most of the value
is in the things below that took a while to find.

## What's in here

| Path | What it is |
|---|---|
| `gardenroom.py` | Drives every WLED unit directly over its JSON API: `status`, `apply`, `white`, `off`, `resolve`. No dependencies beyond Python 3. |
| `schedule.json` | The day split into phases (kelvin, brightness, on/off). The only schedule. |
| `devices.example.json` | Your WLED units, identified by MAC. |
| `ha_webhook.example.json` | Optional: also send each phase to Home Assistant, for lights WLED can't reach. |
| `esphome/bt-proxy.yaml` | ESPHome Bluetooth proxy so HA can reach the Bluetooth-only SP630E. |
| `home-assistant/automation.banlanx_webhook.yaml` | Receives the phase from `gardenroom.py` and drives the SP630E. |
| `home-assistant/script.apply_room_lighting.yaml` + `automation.room_lighting_schedule.yaml` | Optional HA-only version that drives every light in an area (Govee, WiZ, Tuya…), whatever the brand. |
| `patches/uniled-attr-color-temp.md` | One-line fix so UniLED works on current Home Assistant. |
| `docs/research.md` | Where the schedule's numbers come from (EN 12464-1, Brown et al. 2020), with sources. |

## Quick start

```bash
cp devices.example.json devices.json      # add your WLED units (MAC + last known IP)
python3 gardenroom.py status              # what each unit is doing, and any faults
python3 gardenroom.py apply --dry-run     # what the current phase would set
python3 gardenroom.py apply               # do it
```

Then run it every 10 minutes from cron (`cron.example`). The script reads the
clock and picks the phase itself, so the cron line never changes when the clocks
go forward or back.

`apply --phase evening`, `white`, `off`, `--kelvin 4000`, `--bri 120` and `--json`
do what they say.

If you have an OpenWrt-type router, set `GARDENROOM_ROUTER=root@192.168.1.1` (and
`GARDENROOM_ROUTER_KEY`). The script then finds a strip by its MAC in the DHCP
leases when its IP moves, and `resolve` writes the new IPs back to `devices.json`.

## Things I learned the hard way

**1. The power limiter was flattening the whole schedule.** WLED's automatic
brightness limiter (ABL) estimates current as `ledma × (r+g+b)/765` per LED plus
about 1 mA idle, and scales the strip down once that passes `maxpwr`. With the
default 55 mA/LED and a 3 A limit on 300 LEDs, it cuts in at a raw brightness of
roughly 43 (cool white) to 79 (very warm). My schedule asked for 90 to 255, so
**wake, work, afternoon, wind-down and evening all came out at exactly the same
brightness**. Only the colour ever changed. `status` showed every unit sitting
on its cap.

So `gardenroom.py` now treats `bri` in `schedule.json` as a *share of what each
unit can really deliver* at that colour (255 = just under its limiter). It reads
each unit's `/json/cfg` and works out the raw value per unit, so the phases
genuinely differ. If you raise `maxpwr` later, it scales up on its own. Don't
raise `maxpwr` past what your power supply is actually rated for: ABL is a sum,
not a measurement, and it can't protect a PSU it's been told is bigger than it is.

**2. WLED sync groups span the whole house.** One strip had "send
notifications" on, group 1, and every other WLED unit in the house receives group
1. So every schedule change here quietly changed the kitchen and the 3D printer
lights too. The script writes each unit directly and doesn't need sync; `status`
warns if any unit is broadcasting and prints the curl to turn it off.

**3. `lc: 0` means colour silently does nothing.** Two strips ignored every colour
and showed plain white, with no error anywhere. The tell is `info.leds.lc == 0`
(no light capability registered on the bus), seen on WLED 0.15.x after upgrading
from 0.14. Re-posting the unchanged LED bus config to `/json/cfg` fixes it;
`status` detects it and prints the exact command.

**4. RGB strips don't do white.** No white channel means "4000 K" is an RGB mix
with a green cast and poor colour rendering. That's why the white strip matters.

**5. The SP630E is Bluetooth only.** It has no WiFi (that's the SP530E). To get
it into Home Assistant:

- flash any plain ESP32 with `esphome/bt-proxy.yaml` (web.esphome.io over USB
  first, then over the air)
- install [UniLED](https://github.com/monty68/uniled) from HACS and apply
  `patches/uniled-attr-color-temp.md`. The latest release crashes on current HA,
  and it looks like a Bluetooth fault when it isn't.
- **close the BanlanX phone app.** The controller only allows one Bluetooth
  connection at a time, and the app takes it.
- give the ESP32 **good WiFi**. Mine joined a distant mesh node at -83 dBm and
  every Bluetooth connect timed out through the lag. Putting the nearby access
  point first in the config fixed it.

Then copy `ha_webhook.example.json` to `ha_webhook.json` with a long random id,
put the same id in `home-assistant/automation.banlanx_webhook.yaml`, and add
that automation to HA. Each run posts the phase to it. The webhook is
`local_only`, so it needs no HA token. The strip follows its own `bri_white`
column: full in working hours, off in the evening, because a plain white strip
can't go warm.

## How much light a room actually needs

EN 12464-1 asks for about 300 lux for general use and 500 lux at a desk. In
15 m², with strips bouncing light off walls and ceiling, that's somewhere around
10,000 to 20,000 lumens installed. Six 300-LED WS2812B strips on 3 A supplies
give roughly 1,200 to 1,800 lumens, about 25 to 40 lux. That's my estimate from
WLED's own current figures, not a measurement. In other words they're mood
lighting, and the working light has to come from real white LEDs. Measure yours
with a phone lux app before trusting any of these numbers, mine included.

## Licence

MIT. See `LICENSE`.
