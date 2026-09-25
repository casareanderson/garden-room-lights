# UniLED v2.2.6 on current Home Assistant: `ImportError: ATTR_COLOR_TEMP`

UniLED v2.2.6 (the latest release, Nov 2024) fails to set up any light on newer
Home Assistant (seen on 2026.7) with:

```
ImportError: cannot import name 'ATTR_COLOR_TEMP' from 'homeassistant.components.light'
```

HA removed the old mired-based `ATTR_COLOR_TEMP` constant. The Bluetooth side
connects fine, then setup dies while loading `light.py`, so it looks like a
connection problem when it isn't.

UniLED only uses it as a dictionary key whose value was `"color_temp"`, so the
fix is to stop importing it and define it locally. In
`custom_components/uniled/light.py`, remove `ATTR_COLOR_TEMP,` from the
`from homeassistant.components.light import (...)` block and add, below it:

```python
# ATTR_COLOR_TEMP (mireds) was removed from homeassistant.components.light;
# UniLED only uses it as a channel key, so keep the old string value locally.
ATTR_COLOR_TEMP = "color_temp"
```

Then restart HA. Check every module imports before you restart:

```bash
docker exec -w /config homeassistant python3 -c '
import importlib, pkgutil, sys
sys.path.insert(0, "/config")
import custom_components.uniled as u
for m in pkgutil.walk_packages(u.__path__, "custom_components.uniled."):
    importlib.import_module(m.name)
print("ok")'
```

A HACS reinstall or update of UniLED puts the old file back.
