#!/usr/bin/env bash
# Runs docs/SETUP.md against a FAKE WLED unit (scripts/fake_wled.py), because CI has no lights.
# It proves the commands, the config files and the HTTP calls; it can't prove your strips.
# Used by .github/workflows/setup-check.yml. Leaves your own devices.json alone.
set -euo pipefail
step() { printf '\n== %s\n' "$*"; }
P1=${P1:-18081}; P2=${P2:-18082}
work=$(mktemp -d); cp gardenroom.py schedule.json devices.example.json ha_webhook.example.json "$work/"
cd "$work"

step "1. no devices.json yet -> clear message"
set +e; err=$(python3 gardenroom.py status 2>&1); rc=$?; set -e
echo "$err"; [ "$rc" -ne 0 ] && grep -q "missing .*devices.json (copy the matching \*.example.json" <<<"$err"

step "2. configure one fake unit and one that isn't there"
python3 "$OLDPWD/scripts/fake_wled.py" "$P1" & fake=$!
trap 'kill $fake 2>/dev/null || true' EXIT
for i in $(seq 1 20); do curl -sf "localhost:$P1/json" >/dev/null && break; sleep 0.3; done
python3 - "$P1" "$P2" <<'PY'
import json, sys
d = json.load(open("devices.example.json"))
d["devices"][0]["ip"] = "127.0.0.1:" + sys.argv[1]
d["devices"][1]["ip"] = "127.0.0.1:" + sys.argv[2]          # nothing listens here
del d["_comment"]
json.dump(d, open("devices.json", "w"), indent=2)
PY

step "3. status"
python3 gardenroom.py status --no-resolve | tee status.txt
grep -q "gr1" status.txt
python3 gardenroom.py status --json --no-resolve | python3 -c "
import json,sys; d=json.load(sys.stdin); u={r['key']:r for r in d['units']}
assert u['gr1']['reachable'] and not u['gr2']['reachable'], u; print('gr1 up, gr2 unreachable')"

step "3. apply --dry-run changes nothing"
python3 gardenroom.py apply --phase work --dry-run --no-resolve | tee dry.txt || true
grep -q "\[DRY RUN\]" dry.txt && grep -q "would-set" dry.txt
curl -sf "localhost:$P1/_last" | python3 -c "import json,sys; assert json.load(sys.stdin)=={} ; print('fake unit untouched')"

step "3. apply --phase work: sets the unit, exits 1 because gr2 is missing"
set +e; python3 gardenroom.py apply --phase work --no-resolve | tee apply.txt; rc=${PIPESTATUS[0]}; set -e
[ "$rc" -eq 1 ] && grep -q "not applied to: gr2" apply.txt
curl -sf "localhost:$P1/_last" | python3 -c "
import json,sys; b=json.load(sys.stdin)['/json/state']
assert b['on'] is True and 1 <= b['bri'] <= 255 and b['seg'][0]['col'][0]==[255,246,237], b
print('fake unit got on=True bri=%s rgb=%s' % (b['bri'], b['seg'][0]['col'][0]))"

step "4. optional HA webhook gets the phase"
python3 - "$P1" <<'PY'
import json, sys
json.dump({"key": "sp630e", "entity": "light.sp630e_strip",
           "url": "http://127.0.0.1:%s/api/webhook/test" % sys.argv[1]}, open("ha_webhook.json", "w"))
PY
python3 gardenroom.py off --no-resolve || true
curl -sf "localhost:$P1/_last" | python3 -c "
import json,sys; b=json.load(sys.stdin)['/api/webhook/test']
assert b['phase']=='off' and b['power'] is False, b; print('webhook got', b)"

step "every action loads"
python3 gardenroom.py --help >/dev/null
set +e; err=$(python3 gardenroom.py apply --phase nope --no-resolve 2>&1); set -e
grep -q "no such phase: nope" <<<"$err" && echo "unknown phase refused"

step "schedule.json tiles the whole day"
python3 - <<'PY'
import json
ph = json.load(open("schedule.json"))["phases"]
m = lambda s: int(s[:2]) * 60 + int(s[3:])
assert ph[0]["from"] == "00:00" and ph[-1]["to"] in ("24:00", "23:59"), (ph[0], ph[-1])
for a, b in zip(ph, ph[1:]):
    assert a["to"] == b["from"], (a["name"], b["name"])
print(len(ph), "phases, no gaps")
PY

printf '\nSETUP CHECK PASSED\n'
