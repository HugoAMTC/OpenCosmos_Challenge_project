# Flight Operations Simulator — Quick Reference Guide

## 🎯 What This Does

Automates the complete 7-phase Mantis satellite contact procedure with realistic spacecraft physics, command simulation, and anomaly injection.

**Total simulation covers:** T-30:00 (pre-contact) → T+00:00 (AOS) → T+09:30 (LOS) → phase 7 (post-contact)

---

## ⚡ 5-Minute Quick Start

### Step 1: Open Terminal
```bash
cd "d:\Profissional\Jobs\Open Cosmos\Satellite Flight Operator\Satellite Operations Challenge\Code\Flight_Operations"
```

### Step 2: Run Simulator
```bash
# Nominal pass (all systems green)
python main.py

# With anomaly (e.g., low battery)
python main.py --anomaly low_battery

# Save report for analysis
python main.py --save my_pass.json
```

### Step 3: Review Output
- Console shows real-time step execution
- Summary appears at end (pass/fail count)
- JSON file has detailed results (if saved)

---

## 📝 Common Commands

| Command | Purpose |
|---------|---------|
| `python main.py` | Run nominal pass |
| `python main.py --help` | Show all options |
| `python main.py --anomaly low_battery` | Test low battery scenario |
| `python main.py --anomaly comms_restart_fail` | Test COMMS failure |
| `python main.py --anomaly tm_lock_fail` | Test critical TM failure |
| `python main.py --speed 5` | Run 5x faster |
| `python main.py --save results.json` | Save detailed report |
| `python main.py --telemetry tel.json` | Save telemetry log |

---

## 🎲 Anomaly Presets

| Preset | Effect | Expected Outcome |
|--------|--------|---------|
| `none` | No anomalies | All nominal ✓ |
| `low_battery` | SoC → 38% (below Yellow 45%) | Phase 2 detects, Phase 5 defers |
| `high_obc_temp` | OBC → 58°C (Yellow limit) | Phase 2 detects, Phase 5 defers |
| `high_storage` | Storage → 88% (above Yellow) | Phase 2 detects, Phase 5 defers |
| `tm_lock_fail` | TM lock establishment fails | **Phase 1 CRITICAL FAILURE** ✘ |
| `comms_restart_fail` | CMD APPLY COMMS CONFIG fails | Phase 5 NACK, deferral |
| `safe_mode_entry` | Satellite enters SAFE mode | **Phase 1 CRITICAL FAILURE** ✘ |
| `payload_download_thermal` | OBC → 59°C during download | Phase 4 mid-transfer pause |

---

## 📊 Understanding the Output

### Phase Markers
```
=== PHASE 0: PRE-CONTACT PREPARATION ===
─────────────────────────────────────────
[INFO] Step 0.1: PASS — MCS login confirmed
[INFO] Step 0.2: PASS — Ops log reviewed
...
=== PHASE 1: CONTACT ACQUISITION ===
```

### Anomaly Alerts
```
[WARNING] ANOMALY: battery_soc=38.0 (YELLOW) → Monitor
[ERROR]   ANOMALY: tm_lock_fail (CRITICAL) → Escalate to SFO
```

### Pass Summary
```
╔═════════════════════════════════════╗
║   PASS EXECUTION SUMMARY            ║
╚═════════════════════════════════════╝

Status:              ✓ NOMINAL
Duration:            570 seconds (9.5 min)

Steps Executed:      31
  Passed:            31
  Failed:            0
  Deferred:          0

Phases Completed:
  ✓ PHASE_0 through PHASE_6

Data Downloads:
  Platform Log:      ✓
  Payload Data:      ✓
  COMMS Config:      ✓

Anomalies Detected:  0
```

---

## 🔧 Modifying Mission Parameters

**All mission constants are in `config.py`**

### To Change Link Speed:
```python
# In config.py, find:
UPLINK_BITRATE_KBPS = 50        # Change this
DOWNLINK_BITRATE_KBPS = 50      # And this
# New value takes effect immediately on next run
```

### To Change Battery Limit:
```python
# In config.py, find:
class OperationalLimits:
    battery_soc_yellow_min: float = 45.0    # Yellow threshold
    battery_soc_red_min: float = 30.0       # Red threshold (critical)
```

### To Change Anomaly Values:
```python
# In config.py, find ANOMALY_PRESETS:
"my_scenario": {
    "battery_soc": 25.0,          # Custom initial value
    "obc_temperature": 62.0,
    "trigger_phase": Phase.PHASE_4,
}
# Then run: python main.py --anomaly my_scenario
```

---

## 📋 Phase Overview

| Phase | Time | Key Activity | Status |
|-------|------|--------------|--------|
| **0** | T-30:00 to T-00:01 | Pre-contact checks | Not critical |
| **1** | T+00:00 to T+01:15 | **Establish TM lock** | **CRITICAL** |
| **2** | T+01:15 to T+02:30 | Health checks | Deferrable |
| **3** | T+02:30 to T+03:10 | Platform DL | Deferrable |
| **4** | T+03:10 to T+06:55 | Payload DL | Deferrable |
| **5** | T+07:00 to T+07:50 | **COMMS config** | **Deferrable** |
| **6** | T+08:30 to T+09:30 | Close-out | Normal |
| **7** | +00:00 to +30:00 | Post-contact | Administrative |

---

## ⚠️ Critical Checks

### Phase 1: TM Lock (Must Succeed)
```
If TM lock fails → CRITICAL FAILURE
Result: Contact aborted, pass starts over next opportunity
```

### Phase 5: Preconditions (6-point check)
```
Before config change, verify:
(a) Satellite mode = NOMINAL OPS
(b) No out-of-limit values
(c) RSSI ≥ -90 dBm
(d) Storage < 85%
(e) Temperature < 55°C
(f) All systems ready

If ANY fail → DEFER to next pass
```

---

## 💾 JSON Report Structure

```json
{
  "pass_summary": {
    "duration_seconds": 570,
    "critical_failed": false,
    "aos_time": 0.0,
    "los_time": 570.0
  },
  "step_results": [
    {
      "step_id": "1.2",
      "status": "PASS",
      "expected": "TM lock within 30s",
      "actual": "TM lock established",
      "checks": {"tx_enabled": true, "tm_locked": true}
    }
  ],
  "phases_completed": {
    "PHASE_0": true,
    "PHASE_1": true,
    ...
  },
  "data_downloads": {
    "platform": true,
    "payload": true,
    "config_change": true
  },
  "anomalies": 0
}
```

---

## 🧪 Test Scenarios

### Scenario 1: Validate Nominal Operation
```bash
python main.py --save nominal.json
# Expected: All 31 steps PASS
```

### Scenario 2: Test Low Battery Handling
```bash
python main.py --anomaly low_battery --save low_bat.json
# Expected: Phase 2 finds issue, Phase 5 defers
```

### Scenario 3: Test Critical Failure
```bash
python main.py --anomaly tm_lock_fail --save critical.json
# Expected: Phase 1 FAILS immediately, contact aborted
```

### Scenario 4: Test COMMS Restart Failure
```bash
python main.py --anomaly comms_restart_fail --save comms_fail.json
# Expected: Phase 5 fails with NACK, operation deferred
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| "No module named config" | Run from correct directory |
| Anomaly not injecting | Check spelling: `python main.py --anomaly low_battery` |
| Report not saved | Check file permissions, try absolute path |
| Very slow execution | Use `--speed 10` flag to accelerate |

---

## 📈 Real-Time Metrics Tracked

As simulator runs, these values update:

- **Battery SoC**: Drains during transmission/download, min 30% (red)
- **OBC Temperature**: Rises during payload download, max 65°C (red)
- **OBC Storage**: Increases with downlinks, max 95% (red)
- **RSSI**: Signal strength, nominal -95 dBm
- **TM Lock**: Frame sync GREEN/YELLOW/RED
- **Config Version**: Changes from v1 → v2 after Phase 5

---

## 🎓 What Each Module Does

| File | Responsibility |
|------|-----------------|
| **config.py** | All mission constants (edit here to change mission) |
| **satellite.py** | Spacecraft physics & command execution |
| **procedure.py** | All 7 phases and 31 steps |
| **main.py** | CLI interface and report generation |

---

## ✅ Verification Checklist

After running, confirm:

- [ ] All Phase 0 checks pass (pre-contact)
- [ ] Phase 1 establishes TM lock (critical)
- [ ] Phase 2 detects any out-of-limits
- [ ] Phase 3 completes platform download
- [ ] Phase 4 completes payload download
- [ ] Phase 5 either completes or defers (if preconditions fail)
- [ ] Phase 6 exits cleanly with LOS
- [ ] Final battery SoC > 30% (safe)
- [ ] Final temp < 65°C (safe)
- [ ] All checksums verified

---

## 💡 Pro Tips

1. **Start simple**: Run `python main.py` first to see all features
2. **Save everything**: Always use `--save report.json` for analysis
3. **Test anomalies**: Try each preset to understand failure modes
4. **Modify config.py**: This is the lever to change everything
5. **Speed matters**: Use `--speed 10` when testing many passes
6. **Combine flags**: `python main.py --anomaly X --speed 5 --save rep.json`

---

## 🚀 Ready to Go!

```bash
# Your first command:
python main.py

# Watch the procedure execute in real-time
# Results at end of console output
```

---

**Questions?** See README_SIMULATOR.md for full documentation
**Ready to modify?** Edit config.py to change mission parameters
**Need a report?** Use `--save filename.json` flag

✨ **Happy flying!** 🛰️
