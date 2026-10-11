# Setting up garden-room-lights

About 20 minutes for the WLED part. The Bluetooth SP630E part is optional and takes longer. The steps
marked **CI checks this** run every week on a fresh Ubuntu machine against a fake WLED unit
([`scripts/fake_wled.py`](../scripts/fake_wled.py)), because GitHub has no LED strips. That proves the
commands, the config files and the HTTP calls. It can't prove your strips look right.

## What you need

| | |
|---|---|
| Lights | one or more LED strips on controllers running [WLED](https://kno.wled.ge/), on your network |
| A box that's always on | Linux (a Pi, a small server, a container). It runs the script every 10 minutes from cron. |
| Python | 3.10 or newer. **No packages to install**: the script uses the standard library only. |
| Optional | an OpenWrt-style router you can SSH into, so the script can find a unit again when DHCP moves it |
| Optional, for the SP630E | Home Assistant, an ESP32 board, and the UniLED integration from HACS |

## 1. Get it (CI checks this)

```bash
git clone https://github.com/casareanderson/garden-room-lights && cd garden-room-lights
python3 gardenroom.py --help
```

Run anything before you've made `devices.json` and it tells you what's missing:

```
missing /path/to/garden-room-lights/devices.json (copy the matching *.example.json and fill it in)
```

## 2. Tell it about your strips (CI checks this)

```bash
cp devices.example.json devices.json
```

For each WLED unit, fill in:

| field | what to put |
|---|---|
| `key` | a short name you'll see in the output, e.g. `gr1` |
| `name` | anything readable |
| `mac` | the unit's MAC address. This is its identity: it never changes. WLED shows it under Info. |
| `ip` | its current IP. If DHCP moves it, the script can find it again by MAC (step 5). |
| `entity` | its Home Assistant entity id, for your own reference. The script doesn't call HA for these. |

`devices.json` is git-ignored, so your addresses never end up in a commit.

## 3. Check, then apply (CI checks this)

```bash
python3 gardenroom.py status              # every unit: reachable, on, brightness, colour, power draw
python3 gardenroom.py apply --dry-run     # what the current phase would set, sends nothing
python3 gardenroom.py apply               # do it
```

Success is a line per unit ending in `ok` and the brightness it set:

```
phase 'work' -> ON bri=255 6000K rgb=[255, 246, 237]
  gr1    192.0.2.50      ok         bri=43
```

If a unit can't be reached, `apply` lists it under `⚠ not applied to:` and exits 1, so cron mail or a
monitor can catch it.

The other actions:

| command | what it does |
|---|---|
| `apply --phase evening` | force a named phase instead of the clock |
| `apply --kelvin 4000 --bri 120` | override colour temperature and/or brightness (0–255) |
| `white` | task light: stays on the current tier if it's a daytime `working` phase, otherwise jumps to `work` |
| `off` | apply the `off` phase |
| `resolve` | look every MAC up in the router's leases and rewrite `devices.json` (step 5) |

Every action takes `--dry-run`, `--json`, `--transition` (tenths of a second, default 14) and
`--no-resolve`.

## 4. Run it every 10 minutes

The script picks the phase from the clock itself, so cron is a dumb 10-minute tick and there's nothing
to re-tune when the clocks change.

```bash
sudo cp -r . /opt/garden-room-lights
sudo cp cron.example /etc/cron.d/garden-room-lights
tail -f /var/log/garden-room-lights.log      # a new block every 10 minutes
```

**Timezone:** the script uses the machine's local clock. `schedule.json` has a `timezone` key, but the
code doesn't read it yet, so make sure the box itself is on your timezone (`timedatectl` on most Linux).

## 5. Optional: find units again when DHCP moves them

If your router is OpenWrt-style (it has `/tmp/dhcp.leases`) and you can SSH in with a key, set these
(uncomment them in the cron file, or export them):

```bash
GARDENROOM_ROUTER=root@192.0.2.1
GARDENROOM_ROUTER_KEY=/root/.ssh/router
```

When a unit stops answering at its stored IP, the script looks its MAC up in the leases and tries the new
address. `gardenroom.py resolve` rewrites `devices.json` with the new IPs. A unit with **no** lease is
off at the wall or stuck off WiFi, and the script says so.

## 6. Tune the schedule

`schedule.json` holds 8 phases from `00:00` to `24:00`. Each has `name`, `from`, `to`, `power`,
`kelvin`, `bri`, `bri_white` and optional `working`. The windows are checked in order and must cover the
whole day with no gaps (CI checks the shipped file does).

Two things that aren't obvious:
- These strips have **no white channel**, so `kelvin` is rendered to an RGB colour. "5000 K" means
  "the RGB that reads as 5000 K".
- `bri` is a **share of what each unit can really deliver**, not raw WLED brightness. WLED's power
  limiter (ABL) dims a strip once it hits its configured current, and above that ceiling every raw value
  looks the same. The script works out each unit's ceiling from its own `/json/cfg`, so 255 means "as
  bright as this strip can go at this colour".

The numbers in the shipped schedule, and their sources, are in [research.md](research.md).

## 7. Optional: the Bluetooth-only SP630E (not checked by CI)

This is the long part. Full steps are in the README under "Bring in the Bluetooth-only SP630E". In short:
flash an ESP32 with `esphome/bt-proxy.yaml` (copy `esphome/secrets.example.yaml` to `secrets.yaml`
first), install UniLED and apply `patches/uniled-attr-color-temp.md`, **close the BanlanX phone app**
(the controller takes one Bluetooth connection), give the ESP32 strong WiFi, then copy
`ha_webhook.example.json` to `ha_webhook.json` with a long random id and add
`home-assistant/automation.banlanx_webhook.yaml` to HA with the same id.

From then on every run POSTs `{phase, power, bri, kelvin}` to that webhook. It's `local_only`, so it
needs no HA token. CI checks the POST goes out with the right body, to a fake endpoint.

## Common errors

| you see | what's wrong |
|---|---|
| `missing .../devices.json` | step 2 not done, or you're running a copy in another folder. The script reads config from its own folder. |
| `DOWN (no answer at the configured IP, and no other lease for ...)` | the unit is off, or its IP changed and there's no router lookup set (step 5). |
| `could not read the router lease table (set GARDENROOM_ROUTER, currently None)` | you ran `resolve` without step 5. |
| `no such phase: <name>` | the name doesn't match one in `schedule.json`. The error lists the ones you have. |
| `⚠ ABL-capped` | WLED is dimming that strip at its current limit. Expected on long strips. Raise `maxpwr` in WLED only if your power supply can really take it. |
| `⚠⚠ NO COLOUR CAPABILITY (lc=0)` | WLED thinks the strip has no colour channels, so it will render white. The status output prints the exact `curl` that fixes the LED type. |
| everything `ok` but colours differ between strips | another WLED sync group is broadcasting. Check WLED → Sync settings. |

## Updating

```bash
cd garden-room-lights && git pull
sudo cp gardenroom.py /opt/garden-room-lights/     # if you run the installed copy
```

`devices.json` and `ha_webhook.json` are yours and git-ignored, so a pull keeps them. Check
`schedule.json` after a pull if you've edited it.

## Uninstalling

```bash
sudo rm -f /etc/cron.d/garden-room-lights /var/log/garden-room-lights.log
sudo rm -rf /opt/garden-room-lights
```

## What CI can't prove

The weekly check runs every command against a fake WLED unit and a fake webhook: the missing-config
message, status with one unit up and one down, dry run sending nothing, apply sending the right colour
and an in-range brightness, the exit code when a unit is missing, the webhook body, and that the shipped
schedule covers the whole day. It can't prove real hardware: how your strips look, your router's lease
file, the ESP32 Bluetooth proxy, or UniLED inside Home Assistant.
