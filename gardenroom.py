#!/usr/bin/env python3
"""
Garden-room WLED controller — deterministic, no LLM in the loop.

Drives a room's worth of WLED strips straight over the WLED JSON API, so it
works whether or not Home Assistant can see them. Units live in devices.json,
the time-of-day phases in schedule.json. Optionally hands each phase to a Home
Assistant webhook as well, for lights WLED can't reach (see ha_webhook.json).

The strips have NO white channel (`rgbw:false`, `wv:0`), so a colour temperature
is RENDERED to RGB with the Tanner Helland planckian approximation. "5000 K" here
means "the RGB triple that reads as 5000 K", not a real white LED.
"""
import argparse
import datetime as dt
import json
import math
import os
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEVICES = os.path.join(HERE, "devices.json")
SCHEDULE = os.path.join(HERE, "schedule.json")
HA_WEBHOOK = os.path.join(HERE, "ha_webhook.json")
# Optional: an OpenWrt-style router whose /tmp/dhcp.leases maps MAC -> IP, used to
# find a unit again when DHCP moves it. Leave unset to skip that fallback.
ROUTER = os.environ.get("GARDENROOM_ROUTER")            # e.g. root@192.168.1.1
ROUTER_KEY = os.environ.get("GARDENROOM_ROUTER_KEY")    # e.g. ~/.ssh/router
TIMEOUT = 4


# ── colour ──────────────────────────────────────────────────────────────────
def kelvin_to_rgb(k):
    """Tanner Helland's planckian approximation. Good enough for 1000-40000 K."""
    t = max(1000, min(40000, k)) / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 255.0 if t >= 66 else (0.0 if t <= 19 else
                                   138.5177312231 * math.log(t - 10) - 305.0447927307)
    else:
        r = 329.698727446 * (t - 60) ** -0.1332047592
        g = 288.1221695283 * (t - 60) ** -0.0755148492
        b = 255.0
    return [int(max(0, min(255, round(v)))) for v in (r, g, b)]


# ── config ──────────────────────────────────────────────────────────────────
def load(path):
    if not os.path.exists(path):
        sys.exit("missing %s (copy the matching *.example.json and fill it in)" % path)
    with open(path) as fh:
        return json.load(fh)


def _mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def phase_for(now, schedule):
    """First phase whose [from,to) window contains `now`. Windows tile the day."""
    cur = now.hour * 60 + now.minute
    for ph in schedule["phases"]:
        if _mins(ph["from"]) <= cur < _mins(ph["to"]):
            return ph
    return schedule["phases"][-1]


def phase_named(name, schedule):
    for ph in schedule["phases"]:
        if ph["name"] == name:
            return ph
    sys.exit("no such phase: %s (have: %s)" %
             (name, ", ".join(p["name"] for p in schedule["phases"])))


# ── WLED transport ──────────────────────────────────────────────────────────
def wled(ip, path="/json", payload=None):
    url = "http://%s%s" % (ip, path)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        body = r.read().decode()
    return json.loads(body) if body.strip() else {}


def router_leases():
    """MAC -> IP from the router's live lease file. The MAC never moves; the IP does."""
    if not ROUTER:
        return {}
    key = ["-i", os.path.expanduser(ROUTER_KEY)] if ROUTER_KEY else []
    try:
        out = subprocess.run(
            ["ssh"] + key + ["-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=6",
             ROUTER, "cat /tmp/dhcp.leases"],
            capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return {}
    leases = {}
    for line in out.splitlines():
        f = line.split()
        if len(f) >= 3:
            leases[f[1].lower()] = f[2]
    return leases


def probe(dev, leases=None, allow_resolve=True):
    """Return (ip, json) for a device, re-resolving by MAC if the stored IP is dead."""
    try:
        return dev["ip"], wled(dev["ip"])
    except Exception:
        pass
    if not allow_resolve:
        return None, None
    if leases is None:
        leases = router_leases()
    ip = leases.get(dev["mac"].lower())
    if ip and ip != dev["ip"]:
        try:
            return ip, wled(ip)
        except Exception:
            return None, None
    return None, None


# ── reporting ───────────────────────────────────────────────────────────────
def summarise(j):
    s, i = j["state"], j["info"]
    seg = (s.get("seg") or [{}])[0]
    led = i.get("leds", {})
    return {
        "name": i.get("name"),
        "version": i.get("ver"),
        "on": s.get("on"),
        "bri": s.get("bri"),
        "fx": seg.get("fx"),
        "col": (seg.get("col") or [[None]])[0][:3],
        "leds": led.get("count"),
        "pwr_ma": led.get("pwr"),
        "maxpwr_ma": led.get("maxpwr"),
        "abl_capped": bool(led.get("maxpwr")) and (led.get("pwr") or 0) >= led["maxpwr"],
        "lc": led.get("lc"),
        "sync_send": (s.get("udpn") or {}).get("send"),
        "sync_recv": (s.get("udpn") or {}).get("recv"),
    }


def collect(devices, allow_resolve=True):
    leases = None
    rows = []
    for d in devices:
        ip, j = probe(d, leases, allow_resolve)
        if j is None and leases is None and allow_resolve:
            leases = router_leases()          # resolved once, reused
            ip, j = probe(d, leases, True)
        rows.append({"key": d["key"], "configured_ip": d["ip"], "ip": ip,
                     "mac": d["mac"], "entity": d["entity"],
                     "reachable": j is not None,
                     "state": summarise(j) if j else None})
    return rows


def in_sync(rows):
    """Do all REACHABLE units agree on on/colour/effect?

    bri is left out on purpose: apply() scales it per unit to that unit's ABL
    ceiling, so gr2 (500 LEDs on 850 mA) legitimately runs a far lower bri.
    """
    live = [r["state"] for r in rows if r["reachable"]]
    if len(live) < 2:
        return True, []
    keys = ("on", "fx", "col")
    disagree = [k for k in keys if len({json.dumps(s[k]) for s in live}) > 1]
    return not disagree, disagree


# ── actions ─────────────────────────────────────────────────────────────────
# ── brightness budget ───────────────────────────────────────────────────────
IDLE_MA = 1   # WLED's ABL books ~1 mA per LED even when it is dark


def abl_ceiling(ip, rgb):
    """The WLED bri at which this unit's ABL starts clamping `rgb` (255 = never).

    WLED estimates ledma * (r+g+b)/765 per LED at full bri, plus ~1 mA idle, and
    scales the whole strip down once that passes maxpwr. Above this ceiling every
    bri looks identical -- measured 2026-09-25, wake through evening all sat at the
    cap (ceiling ~43-63 on the 300-LED units, ~4 on gr2), so the schedule's ramp
    only ever changed colour. Bus values win over the global ones.
    """
    try:
        led = wled(ip, "/json/cfg")["hw"]["led"]
    except Exception:
        return 255
    bus = (led.get("ins") or [{}])[0]
    count = led.get("total") or bus.get("len") or 0
    maxpwr = bus.get("maxpwr") or led.get("maxpwr") or 0
    ledma = bus.get("ledma") or led.get("ledma") or 55
    frac = sum(rgb) / 765.0
    if not (count and maxpwr and frac):
        return 255                      # ABL off: bri is honoured as-is
    budget = maxpwr - count * IDLE_MA
    if budget <= 0:
        return 1
    return max(1, min(255, int(255 * budget / (count * ledma * frac))))


def apply(devices, target, dry_run=False, transition=14):
    """target = {power, bri, rgb}. Written to every unit individually.

    target["bri"] is a share of what each unit can actually deliver (255 = its
    ABL ceiling for this colour), so the phases differ in brightness and not just
    colour. Rows are (device, ip, result, wled_bri).
    """
    if target["power"]:
        payload = {
            "on": True,
            "transition": transition,
            "seg": [{"id": 0, "on": True, "fx": 0, "pal": 0, "sx": 128, "ix": 128,
                     "col": [list(target["rgb"]), [0, 0, 0], [0, 0, 0]]}],
        }
    else:
        payload = {"on": False, "transition": transition}

    results = []
    for d in devices:
        ip, j = probe(d)
        if j is None:
            results.append((d, None, "unreachable", None))
            continue
        body, bri = payload, None
        if target["power"]:
            ceiling = abl_ceiling(ip, target["rgb"])
            bri = max(1, round(int(target["bri"]) * ceiling / 255.0))
            body = dict(payload, bri=bri)
        if dry_run:
            results.append((d, ip, "would-set", bri))
            continue
        try:
            wled(ip, "/json/state", body)
            results.append((d, ip, "ok", bri))
        except Exception as exc:
            results.append((d, ip, "FAILED: %s" % exc, bri))
    return results


def ha_push(target, phase_name, dry_run=False):
    """Hand the phase to HA for the Bluetooth-only SP630E (see ha_webhook.json).

    Returns a results row like apply()'s, or None when the file is absent. The
    webhook answers 200 whatever the automation then does, so "ok" means HA got it.
    """
    if not os.path.exists(HA_WEBHOOK):
        return None
    cfg = load(HA_WEBHOOK)
    dev = {"key": cfg["key"], "ip": "HA webhook"}
    bri = int(target["bri_white"]) if target["power"] else 0
    if dry_run:
        return (dev, None, "would-set", bri)
    body = json.dumps({"phase": phase_name, "power": bool(target["power"]) and bri > 0,
                       "bri": bri, "kelvin": int(target["kelvin"])}).encode()
    req = urllib.request.Request(cfg["url"], data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=TIMEOUT).read()
        return (dev, None, "ok", bri)
    except Exception as exc:
        return (dev, None, "FAILED: %s" % exc, bri)


# ── cli ─────────────────────────────────────────────────────────────────────
def print_status(rows, phase, target):
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M %Z").strip()
    print("garden room — %s — phase '%s' -> %s bri=%s rgb=%s" % (
        now, phase["name"],
        "ON" if target["power"] else "OFF", target["bri"], target["rgb"]))
    print("%-5s %-15s %-8s %-5s %-5s %-18s %-6s %s" %
          ("KEY", "IP", "REACH", "ON", "BRI", "COL", "FX", "POWER"))
    for r in rows:
        s = r["state"]
        if not r["reachable"]:
            print("%-5s %-15s %-8s  (no answer at the configured IP, and no other "
                  "lease for %s)" % (r["key"], r["configured_ip"], "DOWN", r["mac"]))
            continue
        moved = "" if r["ip"] == r["configured_ip"] else "  <- MOVED"
        pw = "%s/%smA%s" % (s["pwr_ma"], s["maxpwr_ma"], " ABL-CAPPED" if s["abl_capped"] else "")
        print("%-5s %-15s %-8s %-5s %-5s %-18s %-6s %s%s" % (
            r["key"], r["ip"], "up", s["on"], s["bri"], s["col"], s["fx"], pw, moved))

    ok, fields = in_sync(rows)
    down = [r["key"] for r in rows if not r["reachable"]]
    if down:
        print("\n⚠ offline: %s — these cannot be in sync with anything." % ", ".join(down))
    if ok:
        print("✓ every reachable unit agrees on on/colour/effect (bri is per-unit, scaled to ABL).")
    else:
        print("⚠ reachable units DISAGREE on: %s" % ", ".join(fields))
    # ⚠️ A unit with udpn.send=true BROADCASTS every change onto its WLED sync
    # group — and that group spans the whole house, not just this room. On
    # 2026-09-11 gr4 was broadcasting on group 1 and dragged the KITCHEN and the
    # 3D-PRINTER strips along with every schedule change.
    senders = [r["key"] for r in rows if r["reachable"] and r["state"].get("sync_send")]
    if senders:
        print("\n⚠⚠ BROADCASTING on the WLED sync group: %s — every change here is "
              "being pushed to EVERY WLED unit in the house that receives on the "
              "same group (other rooms included). This script "
              "writes each unit directly, so the broadcast is pure side effect. "
              "Turn it off:" % ", ".join(senders))
        for r in rows:
            if r["reachable"] and r["state"].get("sync_send"):
                print("   curl -X POST -H 'Content-Type: application/json' \\\n"
                      "     -d '{\"if\":{\"sync\":{\"send\":{\"dir\":false,\"btn\":false,"
                      "\"va\":false,\"hue\":false,\"macro\":false,\"grp\":1,\"ret\":0}}}}' \\\n"
                      "     http://%s/json/cfg" % r["ip"])

    # lc is WLED's light-capability bitmask: 1=RGB, 2=white channel, 4=CCT.
    # 0 means the LED bus registered no capability at all, which makes the unit
    # silently ignore colour and render pure white. Seen on 0.15.x after an
    # upgrade from 0.14.x. It is invisible in HA and in the WLED UI.
    nocap = [r["key"] for r in rows if r["reachable"] and r["state"].get("lc") == 0]
    if nocap:
        print("\n⚠⚠ NO COLOUR CAPABILITY (lc=0) on: %s — these will render WHITE "
              "whatever colour you send. Re-save the LED bus config to rebuild it:"
              % ", ".join(nocap))
        for r in rows:
            if r["reachable"] and r["state"].get("lc") == 0:
                print("   curl -X POST -H 'Content-Type: application/json' \\\n"
                      "     -d '{\"hw\":{\"led\":{\"total\":%s,\"maxpwr\":%s,\"ledma\":55,"
                      "\"ins\":[{\"start\":0,\"len\":%s,\"pin\":[2],\"order\":0,"
                      "\"rev\":false,\"skip\":0,\"type\":22,\"ref\":false,"
                      "\"rgbwm\":0,\"freq\":0}]}}}' \\\n     http://%s/json/cfg"
                      % (r["state"]["leds"], r["state"]["maxpwr_ma"],
                         r["state"]["leds"], r["ip"]))

    capped = [r["key"] for r in rows if r["reachable"] and r["state"]["abl_capped"]]
    if capped:
        print("⚠ ABL-capped (WLED is dimming these below the brightness you asked "
              "for, because their configured max current is reached): %s" % ", ".join(capped))


def main():
    p = argparse.ArgumentParser(description="Garden-room WLED time-of-day controller")
    p.add_argument("action", choices=["status", "apply", "white", "off", "resolve"])
    p.add_argument("--phase", help="force a named phase instead of the clock")
    p.add_argument("--kelvin", type=int, help="override the phase colour temperature")
    p.add_argument("--bri", type=int, help="override the phase brightness (0-255)")
    p.add_argument("--transition", type=int, default=14, help="WLED transition, 1/10 s")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--no-resolve", action="store_true",
                   help="do not fall back to the router lease table")
    a = p.parse_args()

    devices = load(DEVICES)["devices"]
    schedule = load(SCHEDULE)

    if a.action == "resolve":
        leases = router_leases()
        if not leases:
            sys.exit("could not read the router lease table (set GARDENROOM_ROUTER, "
                     "currently %r)" % ROUTER)
        changed = 0
        for d in devices:
            ip = leases.get(d["mac"].lower())
            if ip and ip != d["ip"]:
                print("%s: %s -> %s" % (d["key"], d["ip"], ip))
                d["ip"] = ip
                changed += 1
            elif not ip:
                print("%s: %s holds NO lease (off at the wall, or WiFi wedged)" %
                      (d["key"], d["mac"]))
        if changed and not a.dry_run:
            with open(DEVICES, "w") as fh:
                json.dump({"devices": devices}, fh, indent=2)
            print("rewrote %s (%d changed)" % (DEVICES, changed))
        else:
            print("no address changes")
        return

    phase = phase_named(a.phase, schedule) if a.phase else phase_for(dt.datetime.now(), schedule)
    if a.action == "white" and not a.phase:
        # Stay on the current tier if it is already a daytime task tier, so asking
        # for white at 15:00 does not drag the room back to 6000 K morning light.
        if not phase.get("working"):
            phase = phase_named("work", schedule)
    if a.action == "off":
        phase = phase_named("off", schedule)

    target = {
        "power": phase["power"],
        "bri": a.bri if a.bri is not None else phase["bri"],
        "rgb": kelvin_to_rgb(a.kelvin if a.kelvin is not None else phase["kelvin"]),
        "kelvin": a.kelvin if a.kelvin is not None else phase["kelvin"],
        # The SP630E is the room's only real white: it follows its own column
        # (task light by day, off in the evening). --bri drives both.
        "bri_white": a.bri if a.bri is not None else phase.get("bri_white", phase["bri"]),
    }
    if a.bri is not None and a.bri > 0:
        target["power"] = True

    if a.action == "status":
        rows = collect(devices, allow_resolve=not a.no_resolve)
        if a.json:
            print(json.dumps({"phase": phase["name"], "target": target, "units": rows}, indent=2))
        else:
            print_status(rows, phase, target)
        return

    results = apply(devices, target, dry_run=a.dry_run, transition=a.transition)
    ha = ha_push(target, phase["name"], dry_run=a.dry_run)
    if ha:
        results.append(ha)
    if a.json:
        print(json.dumps({"phase": phase["name"], "target": target,
                          "results": [{"key": d["key"], "ip": ip, "result": r, "bri": b}
                                      for d, ip, r, b in results]}, indent=2))
        return
    print("phase '%s' -> %s bri=%s %sK rgb=%s%s" % (
        phase["name"], "ON" if target["power"] else "OFF", target["bri"],
        target["kelvin"], target["rgb"], "  [DRY RUN]" if a.dry_run else ""))
    for d, ip, r, b in results:
        print("  %-6s %-15s %-10s %s" % (d["key"], ip or d["ip"], r, "" if b is None else "bri=%s" % b))
    bad = [d["key"] for d, _, r, _ in results if r not in ("ok", "would-set")]
    if bad:
        print("⚠ not applied to: %s" % ", ".join(bad))
        sys.exit(1)


if __name__ == "__main__":
    main()
