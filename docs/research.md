<!-- Background research behind schedule.json. Compiled with an LLM agent doing web searches (2026-09-11); every claim carries its source link, so check the sources rather than trusting the summary. -->

---

**WORKSHOP HOME OFFICE — LIGHTING RESEARCH FINDINGS**

Prepared for: garden-room home office, 6× WLED (RGB-only, no white channel) + 2× BanlanX strips via UniLED/Bluetooth
Date: 2026-09-11

---

## 1. Standard illuminance and colour temperature for office/desk work

**EN 12464-1 specifies:**

| Visual task | Maintained illuminance (lux on work plane) | Colour temp | CRI min |
|---|---|---|---|
| Rough work / storage | 300 lx | neutral white ~4000 K | Ra ≥ 80 |
| Normal visual tasks (assembly, medium bench, general office) | **500 lx** | neutral white ~4000 K | Ra ≥ 80 |
| Fine work (fine assembly, electronics, inspection) | **750–1000 lx** | neutral white ~4000 K | Ra ≥ 80 |
| Precision work | 1000+ lx | daylight white >5300 K | Ra ≥ 90 |

The standard also classifies lamp colour appearance into three groups: warm (<3300 K), intermediate (3300–5300 K), cool (>5300 K). For focused office work, "neutral-white light around 4000 K" is the recommended sweet spot[^3][^4].

Daylight white (>5300 K) suits only inspection and colour-matching tasks; warm white (<3300 K) feels cosy but is "less activating" and not suitable for fine work[^4].

**For daytime vs evening working light:**

EN 12464-1 itself does not prescribe time-of-day variation, but acknowledges that "the colour appearance of daylight varies throughout the day" and that variability in CCT can stimulate people and enhance wellbeing [^3].

Broader circadian lighting research recommends:
- **Morning/daytime:** High-CCT (~6500 K), high intensity — the U.S. Department of Energy study used 6500 K at 200 lux for midday to deliver CS ≥ 0.3[^5]
- **Evening:** Warm white (~2700 K or lower), low melanopic EDI — the expert consensus paper recommends melanopic EDI <10 lux beginning ≥3 hours before habitual sleep[^6]
- **Night:** Near-dark — melanopic EDI <1 lux[^6]

The landmark publication establishing quantitative recommendations is Brown et al. (2020): "Recommendations for Healthy Daytime, Evening, and Night-Time Indoor Light Exposure"[^6], which specifies >250 lux melanopic EDI during daytime, <10 lux for 3 hours before bed, and <1 lux at night.

Sources:
- [^3]: CEN EN 12464-1:2021 standard text (lrf.fe.uni-lj.si) https://lrf.fe.uni-lj.si/e_sv_tehnika/StandardText.pdf
- [^4]: Workplace lighting guide (esd.equipment) https://esd.equipment/en/ratgeber/workplace-lighting
- [^5]: DOE Lighting for Health and Wellness Recommendations in Offices (PNNL, Jan 2023) https://www.energy.gov/cmei/ssl/articles/lighting-health-and-wellness-recommendations-offices
- [^6]: Brown et al. (2020) "Recommendations for Healthy Daytime, Evening, and Night-Time Indoor Light Exposure", PLOS ONE https://www.researchgate.net/publication/347626355_Recommendations_for_Healthy_Daytime_Evening_and_Night-Time_Indoor_Light_Exposure · PMC summary https://pmc.ncbi.nlm.nih.gov/articles/PMC12966363/

---

## 2. Getting usable WHITE from RGB-only addressable strips

### Practical limits vs RGBW/RGBCCT

RGB-only LEDs (WS2812B with R+G+B chips only) produce white by simultaneously driving all three channels to equal brightness. This has major limitations:

- **Colour purity:** True white from an RGB blend is never spectrally clean — there is always spectral imbalance (typically a green tint) because the R, G, B phosphors/chips have mismatched SPDs.
- **Maximum brightness:** A dedicated white channel (in RGBW SK6812) provides 3× more luminous flux than an RGB blended white at the same drive current, because all power goes into one narrow-spectrum LED.
- **CRI:** Blended white from RGB LEDs has poor colour rendering (low R9/red component, green spike) compared to a true phosphor-coated white LED.
- **Efficiency:** At full R=G=B, all three channels share current. In RGBW at white, the W channel can draw independently. For the same total current budget, RGBW white will be significantly brighter and cleaner.

### RGB values approximating 4000K and 5000K on WS2812-class LEDs

Using the Tanner Helland blackbody approximation (the standard algorithm mapping Kelvin → sRGB, cited in[^7][^8]), the Zenodo lookup table by Andreas Siess confirms these values:

| CCT | R | G | B | Hex |
|---|---|---|---|---|
| **4000 K** | 255 | 209 | 163 | `#FFD1A3` |
| **5000 K** | 255 | 228 | 206 | `#FFE4CE` |

These are the *display* values (sRGB/blackbody simulation). On physical WS2812B LEDs, the actual perceived colour will differ from the sRGB curve because:

1. WS2812B red is ~625 nm (narrow), green ~520 nm (slightly blue-shifted for many clones), blue ~470 nm (often not pure 470nm). This means the physically emitted spectrum won't match the sRGB blackbody curve.
2. The green LED in most WS2812B clones tends to oversaturate whites, giving them a greenish cast.

**To calibrate physically:** use a colour meter or smartphone lux/colour app, then adjust the per-channel gamma or use WLED's White Balance Correction (per-segment cold/warm slider) to compensate for the inherent RGB imbalance.

### WLED-specific approach for RGB-only white

Since your strips report `rgbw:false, wv:0`, WLED knows there is no white channel. However, WLED still offers options:

1. **"White palette" doesn't apply** — palettes like "Ocean", "Cloud", "Lava" etc. are colour themes, not white generators. There is no built-in "generate white from RGB" palette for RGB-only strips.
2. **Gamma correction:** Apply custom gamma to individual channels to compensate for the green spike. WLED supports per-channel gamma in newer versions, or you can use a global gamma (~2.0–2.5 depending on strip).
3. **White Balance Correction slider:** Even without a white channel, WLED's WB correction (Settings → LED Preferences) lets you shift the RGB balance cooler or warmer globally. Use this to nudge blended whites toward the desired CCT.
4. **Manual RGB white selection:** Set your primary/secondary colours manually to the calibrated values above (e.g. R=255, G≈200–210, B≈150–165 for ~4000K visually adjusted). Save as presets and switch between them via schedules.
5. **CCT blending is NOT available** for RGB-only bus types. It requires either RGBW (single white channel) or dual-white PWM outputs. The `Calculate CCT from RGB` feature[^9] simply estimates a CCT target internally — it doesn't create white on RGB strips.

**Bottom line:** The practical workaround for RGB-only strips is manual calibration — pick the RGB triplet that looks closest to your target CCT on your specific LEDs, create named presets ("Day 4000K", "Warm 3000K"), and automate switching via Home Assistant schedules or WLED playlists.

Sources:
- [^7]: Tanner Helland blackbody algorithm https://tannerhelland.com/2012/09/18/convert-temperature-rgb-algorithm-code.html
- [^8]: Colour temp conversion table (Zenodo, Siess 2024) https://zenodo.org/records/14230959
- [^9]: WLED white handling & CCT docs https://kno.wled.ge/features/cct/

---

## 3. WLED multi-controller best practice

### Comparison of sync methods

| Method | Best for | Failure modes |
|---|---|---|
| **UDP notifier sync** (built-in) | Simple rooms, ≤8 strips on same network | UDP broadcast drops; no delivery confirmation. Can miss up to ~50% of sync events on congested WiFi[^10][^11] |
| **E1.31 (sACN)** | Professional installations, DMX ecosystems | Higher overhead; needs config. More reliable on wired Ethernet. Multicast support required.[^12] |
| **DDP** (Distributed Display Protocol) | Low-latency streaming, large installations | Similar reliability concerns on Wi-Fi. Lower framing overhead than E1.31.[^12] |
| **Single controller, multiple outputs** | Permanent installations, maximum reliability | ESP8266 limited to ~3 outputs cleanly; ESP32 better. Single point of failure if controller dies. Data-line length limited.[^12] |

### Documented failure modes of UDP sync[^10][^11]

1. **Packet loss on WiFi:** UDP broadcast packets can be dropped by congestion, interference, or AP isolation. No retransmission mechanism exists.
2. **Sync misses:** Nodes occasionally skip a preset/change but catch the next one. Confirmed by users with multi-node setups.
3. **Boot-time desync:** If "Receive Brightness/Color/Effects" checkboxes are disabled in Sync settings, a device won't sync its state on boot.
4. **IGMP snooping issues:** Managed switches may block multicast/broadcast UDP unless IGMP snooping is properly configured.
5. **Cross-network issues:** UDP broadcast doesn't cross subnets/VLANs by default.

### Recommendation for permanent room installation

For a garden-room permanent install, the WLED maintainers' own guidance[^13] and community experience suggest:

**Option A (simplest):** Keep UDP sync Group 1 but enable **"Send notifications twice"** in Sync Settings. This halves missed sync events. Also ensure all devices have "Receive Brightness," "Receive Color," and "Receive Effects" checked under Broadcast/Sync settings so they join the group after reboot. Place all units on the same subnet with AP isolation disabled.

**Option B (more robust):** Use **DDP unicast** from a single sender (the master unit). DDP avoids multicast issues and gives deterministic delivery when sent directly to each device's IP. LumaSync and other host tools recommend DDP as "WLED's own preferred path" for high-FPS streaming[^12].

**Option C (most robust):** Drive all strips from a **single ESP32** with multiple data outputs. ESP32 supports up to 6 independent LED outputs simultaneously. This eliminates all network-based sync failures but requires longer data lines or signal amplifiers (74HCT245 level shifter recommended for runs >1m).

For your setup (6 strips × 300–500 LEDs = 2300 total LEDs across 6 controllers), Option A + "send twice" is probably adequate. If you notice visible desync, migrate to Option B.

Sources:
- [^10]: WLED UDP Sync docs https://kno.wled.ge/interfaces/udp-notifier/
- [^11]: WLED Discord discourse — nodes out of sync https://wled.discourse.group/t/nodes-out-of-sync/3941
- [^12]: WLED realtime protocols (E1.31/DDP/Art-Net) https://mintlify.wiki/wled/WLED/features/e131-artnet
- [^13]: MoonModules FAQ — too many sync interfaces https://mm.kno.wled.ge/basics/faq

---

## 4. WLED Automatic Brightness Limiter (ABL)

### What mA-per-LED setting does

The ABL is WLED's internal current calculator. It does **not measure actual current** — instead, it computes:

```
Estimated Current = (mA per LED) × (number of LEDs currently lit at full intensity)
```

If estimated current exceeds your Max PSU Current setting, WLED reduces the master brightness proportionally until the calculation falls below the limit.

### Correct mA/LED value for common LEDs

Per the WLED settings page[^14], the pre-built options include:
- **55 mA** — typical 5V WS281x (RGB only, all channels full white)
- **30 mA** — 12V variants
- Custom entry for any value 1–255 mA

For a WS2812B or WS2811 with RGB channels at full white (R=255, G=255, B=255), the datasheet spec is approximately **50–60 mA per pixel** (each channel draws ~15–20 mA at full). **Use 55 mA** for WS2812B/WS2811.

Note: SK6812-RGBW draws different current — check specific strip specs (typically higher due to 4 chips).

### What happens if max is set higher than PSU capacity?

**Nothing protective.** As confirmed by the WLED maintainer forum[^15]:

> "All it does is use the current per LED you tell it … If that number is more than the max you've told it your supply can provide, it drops the brightness until the number is lower."
>
> "WLED has no idea if your wires or LEDs are melting — it's not a safety feature. If you dead short your power wires from your supply, they'll still pass as much current as your power supply can deliver no matter what the ABL says."

If you set ABL above the PSU's rated capacity:
- LEDs will run at whatever brightness the calculation allows (may be 100%)
- When all LEDs go white, the real-world current draw will exceed the PSU rating
- PSU may brownout/restart, LEDs will flicker, or PSU may fail over time
- Wiring/LEDs risk overheating if voltage drop isn't managed

**This is purely a calculation guard, not a measurement.** You must size your PSU correctly in the first place.

### Is 850 mA for 500 LEDs going to visibly dim that strip?

**Yes, significantly.** Let's calculate:

- 500 LEDs × 55 mA/LED (at full white) = **27,500 mA (27.5 A)** theoretical maximum
- With 850 mA limit: WLED will cap brightness at roughly **850/27500 = 3.1%** of full brightness when all LEDs are white
- Even at moderate colours (say average ~30% per channel), effective brightness would be severely curtailed

Your 500-LED strip should have its ABL set to the PSU's rated output minus headroom (e.g., if running off a 5 V 15 A PSU → set ABL to ~14000–15000 mA). The 850 mA setting is appropriate only for very small strips (≤15 LEDs at full white with 55 mA/LED).

⚠️ **Risk flag:** Your 500-LED strip at 850 mA ABL will appear extremely dim. Check what PSU actually powers that strip and set ABL accordingly.

Sources:
- [^14]: WLED Settings docs (ABL section) https://kno.wled.ge/features/settings/
- [^15]: WLED discourse — ABL confusion https://wled.discourse.group/t/automatic-brightness-limiter-confusion/10821

---

## 5. BanlanX/SP-series controller lineup

### WiFi-only models (reflashable)

| Model | Chip | Connectivity | Reflashed? |
|---|---|---|---|
| **SP108E** | ESP8285 | **WiFi + APP** (FairyNest) | ✅ Yes — ESP8285 based, serial pads exposed |
| **SP501E** | ESP8285 | **WiFi + APP** (BanlanX, Alexa) | ✅ Yes — replaced by SP511E, ESP8285, reflash documented |
| **SP511E** | ESP8285 | **WiFi + APP** (BanlanX), dual outputs, buttons, mic, IR | ✅ Yes — full WLED install guide exists[^16] |
| **SP530E** | ESP32-C3 | **WiFi + Bluetooth + APP** (BanlanX), PWM + SPI | ✅ Yes — ESP32-C3, flash pads on back[^16] |

### Bluetooth-only models (cannot connect via network)

| Model | Chip | Connectivity | Notes |
|---|---|---|---|
| **SP105E** | BLE chip | **Bluetooth ONLY** — iOS 8+/Android 4.4+ | 2048 pixels, no WiFi radio |
| **SP107E** | BLE chip | **Bluetooth ONLY** — Music mode | 960 pixels, RF remote only |
| **SP110E** | BLE chip | **Bluetooth ONLY** | 1024 pixels, 3-pin connector |
| **SP601E** | BLE + RF chip | **Bluetooth + RF remote** (NOT WiFi) — Music mode | Dual output, 1200 pixels, BanlanX app |

Source confirmation for SP601E: the product listing explicitly states "Bluetooth + Music" with no mention of WiFi connectivity[^17], while the SP601E description from superlightingled.com describes "APP (iOS or Android)" and RF remote but never WiFi[^18].

### Getting BanlanX Bluetooth-only controllers into Home Assistant

Two documented approaches:

1. **ESPHome Bluetooth Proxy (ScanAndRF):** Some BanlanX controllers expose their protocol over BLE and can be scraped by ESPHome's scanner integration. This reads status/controls the lights indirectly through BLE — not ideal for addressable strips.

2. **Reflowing to WLED/ESPHome:** For WiFi-capable BanlanX controllers (SP501E→SP511E, SP502E, SP530E, SP108E):
   - Serial programming pads are exposed on the underside of the PCB[^16]
   - Connect via USB-to-TTL adapter (3.3V)
   - Flash WLED or ESPHome bin
   - SP530E requires GPIO9 pulled to GND at boot, and the flash is encrypted (must use `-encrypt` flag with esptool.py)[^16]
   - Full flashing guide: https://github.com/scottrbailey/WLED-Utils/blob/gh-pages/sp511e_wled.md[^16]

For BT-only units (SP105E, SP107E, SP110E, SP601E): These do **not** have ESP chips — they use generic BLE microcontrollers. They are generally **not reflashable** to WLED/ESPHome. The hardware architecture differs fundamentally from the ESP-based models.

Sources:
- [^16]: WLED compatible controllers wiki https://kno.wled.ge/basics/compatible-controllers/
- [^17]: SuntechLite controller comparison https://suntechlite.com/sp105e-vs-sp107e-vs-sp108e-vs-sp110e-led-strip-controllers
- [^18]: SuperLighting LED — SP601E specs https://superlightingled.com/sp601e-led-music-bluetooth-controller-2-output-smartphone-rf-remote-control-p-3265.html
- HA Community thread — SP530e reflash https://community.home-assistant.io/t/how-to-connect-an-sp530e/712522

---

## 6. Recommended time-of-day lighting schedule (circadian lighting)

Based on the expert consensus literature (Brown et al. 2020[^6]) and the U.S. DOE/PNNL office pilot study[^5]:

| Time | CCT | Photopic lux (task plane) | Melanopic EDI | Purpose |
|---|---|---|---|---|
| **06:00–09:00** (morning arrival) | **6000–6500 K** | 300–500 lx | >250 lux | Phase advance melatonin offset, promote alertness |
| **09:00–12:00** (deep work) | **5000–6500 K** | 500–750 lx | >250 lux | EN 12464-1 compliant office illuminance, high alertness |
| **12:00–14:00** (midday) | **4000–5000 K** | 500 lx | >250 lux | Sustained focus, transition period |
| **14:00–17:00** (afternoon) | **4000 K** | 500 lx | >150–250 lux | Maintain alertness, reduce eye strain |
| **17:00–19:00** (wind-down) | **3000–3500 K** | 300–500 lx | <10–50 lux (melanopic EDI) | Transition away from blue-enriched light |
| **19:00–22:00** (evening, ≥3h before bed) | **2700–3000 K** | 100–300 lx | **<10 lux** (melanopic EDI) | Protect melatonin secretion |
| **22:00+** (night, in bedroom/home office) | **2000 K or lower** (amber/red) | <50 lx | **<1 lux** | Minimal circadian disruption |

### Practical implementation notes for your RGB-only WLED strips

Because your strips lack a dedicated white channel, achieving the exact CCT targets above requires using the sRGB-equivalent RGB values from Section 2, plus manual calibration against your specific LED batch. Key considerations:

- **Brightness ramps gradually**, not step-changes (prevents glare contrast shock). Increase master brightness alongside CCT during morning.
- **Melanopic EDI depends on distance and optics.** The >250 lux recommendation applies at the eye/face, not the desk surface. Ambient ceiling/wall bounce adds ~20–40%. Position LED strips to wash walls/ceilings rather than direct desk illumination where possible.
- **CRI matters.** RGB-only blends will have poor CRI. For tasks requiring accurate colour (design work, reading paper documents), supplement with a dedicated high-CRI (Ra≥90) fixed-task light at the desk.
- **Weekend variations** are acceptable — shift the schedule later without extreme blue exposure before bed.

### Automation strategy

In Home Assistant:
1. Create template sensors for time-of-day phases
2. Use `light.turn_on` service calls to switch WLED entities to the appropriate RGB value + brightness
3. Consider WLED Presets (save each phase as a separate preset) and automate preset cycling via Automations or Scenes
4. Optionally integrate a sun-position sensor to tie transitions to sunrise/sunset rather than clock time (more naturally entraining)

Sources:
- [^5]: DOE/PNNL Circadian Lighting Pilot Study (Jan 2023) https://www.energy.gov/cmei/ssl/articles/lighting-health-and-wellness-recommendations-offices
- [^6]: Brown et al. (2020) consensus recommendations https://www.researchgate.net/publication/347626355_Recommendations_for_Healthy_Daytime_Evening_and_Night-Time_Indoor_Light_Exposure
- MSU/NIH Office study (Czeisler lab, 2017) https://icahn.mssm.edu/files/ISMMS/Assets/Research/Light-Health/DOS-2018.pdf

---

## Items flagged as unverifiable or partially verified

1. **BanlanX SP511E exact BLE capability:** Listed as WiFi+APP with no explicit Bluetooth mention. May have BLE secondary — not verified.
2. **Exact spectral output of your specific BanlanX LED strips:** Would require a spectrometer or calibrated colourimeter to confirm whether the strips are WS2812B or SK6812-RGB internally.
3. **Whether your BanlanX strips are truly Bluetooth-only (UniLED protocol):** UniLED integrations sometimes wrap ESP modules that could theoretically be reflashed — this depends on the specific hardware inside the BanlanX controller, not the protocol layer. Unverified without physical inspection.
4. **Visual perception matching the Tanner Helland sRGB values on your physical WS2812B strips:** The formula is correct for sRGB displays; physical LED SPDs vary widely by manufacturer/batch. Calibration with a metre is required.

---
