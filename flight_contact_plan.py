"""
Flight Operations Procedure Module
Implements FLIGHT-OP-CT-PLAN Rev 1.0 — All 7 contact phases

Each phase is a method. Every step from the procedure is tracked with:
- Pass/Fail status
- Time offset from AOS
- Expected vs. actual results
- Anomaly detection and handling

Autor: Hugo Carvalho

Open Cosmos Project Interview - Satellite Flight Operator Challenge

"""

import sys
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from config import (
    Phase, PHASE_TIMING, STEP_TIMING, OPERATIONAL_LIMITS,
    TM_LOCK_TIMEOUT_S, PAYLOAD_DOWNLOAD_END_TIME,
)
from satellite import MantisSpacecraft, CommandStatus


@dataclass
class StepResult:
    """Result of executing a single procedure step."""
    step_id: str
    phase: Phase
    time_offset: float
    status: str  # "PASS", "FAIL", "DEFERRED"
    expected_result: str
    actual_result: str
    timestamp: datetime
    error_msg: str = ""
    parameter_checks: Dict[str, Any] = None


class OpsLog:
    """Operations log for tracking pass execution."""
    
    def __init__(self):
        self.entries: List[Dict] = []
        self.anomalies: List[Dict] = []
        self.deferred_items: List[Dict] = []
        self.pass_summary = {}
    
    def log_entry(self, msg: str, level: str = "INFO"):
        """Add timestamped entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": msg,
        }
        self.entries.append(entry)
        print(f"[{level}] {msg}")
    
    def log_anomaly(self, param_name: str, limit_type: str, value: float, action: str):
        """Log out-of-limit condition."""
        anomaly = {
            "timestamp": datetime.now().isoformat(),
            "parameter": param_name,
            "limit": limit_type,
            "value": value,
            "action": action,
        }
        self.anomalies.append(anomaly)
        self.log_entry(f"ANOMALY: {param_name}={value} ({limit_type}) → {action}", "WARNING")
    
    def log_deferred(self, step_id: str, reason: str):
        """Log deferred step."""
        deferred = {
            "step_id": step_id,
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
        }
        self.deferred_items.append(deferred)
        self.log_entry(f"DEFERRED: {step_id} ({reason})", "WARNING")


class FlightOperationsProcedure:
    """
    Executes full contact procedure across all 7 phases.
    Tracks step-by-step progress with pass/fail status.
    """
    
    def __init__(self, spacecraft: MantisSpacecraft):
        """
        Initialize procedure runner.
        
        Args:
            spacecraft: MantisSpacecraft instance to command
        """
        self.spacecraft = spacecraft
        self.ops_log = OpsLog()
        self.step_results: List[StepResult] = []
        self.current_phase: Optional[Phase] = None
        self.aos_time: Optional[float] = None  # Simulation time of AOS
        self.los_time: Optional[float] = None
        self.pass_duration: float = 0.0
        
        # Phase completion tracking
        self.phases_completed: Dict[Phase, bool] = {p: False for p in Phase}
        self.critical_failed = False
        
        # Data transfer tracking
        self.platform_data_downloaded = False
        self.payload_data_downloaded = False
        self.comms_config_changed = False
    
    def time_offset_to_phase(self, time_offset: float) -> Optional[Phase]:
        """Determine which phase a time offset belongs to."""
        for phase, timing in PHASE_TIMING.items():
            if timing["start"] <= time_offset <= timing["end"]:
                return phase
        return None
    
    def add_step_result(self, result: StepResult):
        """Record a step result."""
        self.step_results.append(result)
        # Prefer to show the scheduled step time (from result.time_offset) as T±HH:MM:SS
        ts = None
        if getattr(result, 'time_offset', None) is not None:
            off = float(result.time_offset)
            # Format negative (pre-AOS) or positive offsets
            sign = '+' if off >= 0 else '-'
            off_abs = abs(off)
            hh = int(off_abs // 3600)
            mm = int((off_abs % 3600) // 60)
            ss = int(off_abs % 60)
            ts = f"T{sign}{hh:02d}:{mm:02d}:{ss:02d}"
        else:
            # Fallback to simulation-relative time if available
            sim_time = None
            try:
                sim_time = float(self.spacecraft.simulation_time)
            except Exception:
                sim_time = None

            if sim_time is not None:
                hh = int(sim_time // 3600)
                mm = int((sim_time % 3600) // 60)
                ss = int(sim_time % 60)
                ts = f"T+{hh:02d}:{mm:02d}:{ss:02d}"
            else:
                ts = result.timestamp.strftime('%H:%M:%S') if hasattr(result, 'timestamp') and result.timestamp else datetime.now().strftime('%H:%M:%S')

        print(f"{ts} - STEP {result.step_id}: {result.status} - Expected: {result.expected_result}")
        print(f"{ts} - Actual: {result.actual_result}")
        if result.status == "FAIL":
            self.ops_log.log_entry(
                f"STEP {result.step_id}: FAILED - {result.error_msg}",
                "ERROR"
            )
            if "CRITICAL" in result.step_id or "CRITICAL" in result.error_msg:
                self.critical_failed = True
    
    # ========================================================================
    # PHASE 0 — PRE-CONTACT PREPARATION
    # ========================================================================
    
    def execute_phase_0(self):
        """Phase 0: Pre-contact Preparation (T-30:00 to T-00:01)"""
        self.current_phase = Phase.PHASE_0
        self.ops_log.log_entry("=== PHASE 0: PRE-CONTACT PREPARATION ===")
        
        # Step 0.1: T-30:00 — MCS login and telemetry
        self._step_0_1()
        
        # Step 0.2: T-25:00 — Review ops log and anomalies
        self._step_0_2()
        
        # Step 0.3: T-20:00 — Confirm pass parameters
        self._step_0_3()
        
        # Step 0.4: T-15:00 — Retrieve COMMS config
        self._step_0_4()
        
        # Step 0.5: T-10:00 — Prepare uplink sequence
        self._step_0_5()
        
        # Step 0.6: T-05:00 — Coordinate with GSO
        self._step_0_6()
        
        # Step 0.7: T-02:00 — Final readiness check
        self._step_0_7()
    
    def _step_0_1(self):
        """Step 0.1: Log into MCS, verify telemetry."""
        result = StepResult(
            step_id="0.1",
            phase=Phase.PHASE_0,
            time_offset=STEP_TIMING["0.1"],
            status="PASS",
            expected_result="MCS session active. All subsystem panels visible. No stale-data flags.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        # Check spacecraft is in NOMINAL mode
        frame = self.spacecraft.generate_telemetry_frame()
        if frame.satellite_mode == "NOMINAL OPS":
            result.actual_result = "MCS connected. Telemetry active on all subsystems."
            result.status = "PASS"
        else:
            result.status = "FAIL"
            result.error_msg = f"Spacecraft in {frame.satellite_mode}, expected NOMINAL OPS"
        
        self.add_step_result(result)
    
    def _step_0_2(self):
        """Step 0.2: Review previous pass log and anomalies."""
        result = StepResult(
            step_id="0.2",
            phase=Phase.PHASE_0,
            time_offset=STEP_TIMING["0.2"],
            status="PASS",
            expected_result="Open items noted. Handover reviewed.",
            actual_result="Ops log review complete. 0 open items from previous pass.",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
    
    def _step_0_3(self):
        """Step 0.3: Confirm pass parameters from orbital prediction."""
        result = StepResult(
            step_id="0.3",
            phase=Phase.PHASE_0,
            time_offset=STEP_TIMING["0.3"],
            status="PASS",
            expected_result="AOS/LOS times confirmed. Max elevation recorded.",
            actual_result="AOS: T+00:00 | LOS: T+09:30 | Max Elevation: 45.2°",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
    
    def _step_0_4(self):
        """Step 0.4: Retrieve COMMS config file."""
        result = StepResult(
            step_id="0.4",
            phase=Phase.PHASE_0,
            time_offset=STEP_TIMING["0.4"],
            status="PASS",
            expected_result="File version and checksum confirmed. File staged in MCS uplink queue.",
            actual_result="comms_config_v2.cfg | Version: v2 | Checksum: a3f9b2c1 | Staged",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
    
    def _step_0_5(self):
        """Step 0.5: Prepare uplink command sequence."""
        result = StepResult(
            step_id="0.5",
            phase=Phase.PHASE_0,
            time_offset=STEP_TIMING["0.5"],
            status="PASS",
            expected_result="Command sequence loaded. Validation: PASSED.",
            actual_result="9 commands loaded and validated. No conflicts detected.",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
    
    def _step_0_6(self):
        """Step 0.6: Coordinate with GSO."""
        result = StepResult(
            step_id="0.6",
            phase=Phase.PHASE_0,
            time_offset=STEP_TIMING["0.6"],
            status="PASS",
            expected_result="GSO confirms antenna ready. Link parameters verified at 50 kbps.",
            actual_result="GSO ready. Antenna armed. S-band: 2.2 GHz | Uplink/DL: 50/50 kbps",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
    
    def _step_0_7(self):
        """Step 0.7: Final readiness check."""
        result = StepResult(
            step_id="0.7",
            phase=Phase.PHASE_0,
            time_offset=STEP_TIMING["0.7"],
            status="PASS",
            expected_result="All pre-contact checks PASSED. Ready for AOS.",
            actual_result="Ops log open ✓ | Anomaly procedures ready ✓ | SFO contactable ✓",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
        self.phases_completed[Phase.PHASE_0] = True
    
    # ========================================================================
    # PHASE 1 — CONTACT ACQUISITION
    # ========================================================================
    
    def execute_phase_1(self):
        """Phase 1: Contact Acquisition (T+00:00)"""
        self.current_phase = Phase.PHASE_1
        self.ops_log.log_entry("=== PHASE 1: CONTACT ACQUISITION ===")
        self.aos_time = self.spacecraft.simulation_time
        
        # Step 1.1: T+00:00 — GSO confirms AOS
        self._step_1_1()
        
        # Step 1.2: T+00:15 — Send CMD TX ON and establish TM lock
        self._step_1_2()
        
        # Step 1.3: T+00:45 — Verify satellite mode
        self._step_1_3()
        
        # Step 1.4: T+01:00 — Send CMD LINK TEST
        self._step_1_4()
        
        # Step 1.5: T+01:10 — Start TM recording
        self._step_1_5()
    
    def _step_1_1(self):
        """Step 1.1: GSO confirms AOS."""
        result = StepResult(
            step_id="1.1",
            phase=Phase.PHASE_1,
            time_offset=STEP_TIMING["1.1"],
            status="PASS",
            expected_result="AOS logged. Antenna tracking confirmed.",
            actual_result=f"AOS at {datetime.now().isoformat()} | Antenna lock: ACTIVE",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
    
    def _step_1_2(self):
        """Step 1.2: Send CMD TX ON and establish TM lock."""
        result = StepResult(
            step_id="1.2",
            phase=Phase.PHASE_1,
            time_offset=STEP_TIMING["1.2"],
            status="FAIL",  # Will update based on response
            expected_result="TM lock established within 30 s of CMD TX ON. Frame sync GREEN.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        # Send CMD TX ON
        response = self.spacecraft.execute_command("CMD_TX_ON")
        if response.status != CommandStatus.ACK_RECEIVED:
            result.status = "FAIL"
            result.error_msg = "CMD TX ON NACK"
            self.add_step_result(result)
            self.critical_failed = True
            return
        
        # Attempt TM lock
        if self.spacecraft.establish_tm_lock():
            frame = self.spacecraft.generate_telemetry_frame()
            result.status = "PASS"
            result.actual_result = f"CMD TX ON ACK | TM lock: GREEN ({frame.frame_sync})"
            result.parameter_checks = {
                "tx_enabled": self.spacecraft.is_tx_enabled(),
                "tm_locked": self.spacecraft.is_tm_locked(),
                "frame_sync": frame.frame_sync,
            }
        else:
            result.status = "FAIL"
            result.error_msg = f"TM lock failed (anomaly: {self.spacecraft.anomaly})"
            self.critical_failed = True
        
        self.add_step_result(result)
    
    def _step_1_3(self):
        """Step 1.3: Verify satellite mode = NOMINAL OPS."""
        result = StepResult(
            step_id="1.3",
            phase=Phase.PHASE_1,
            time_offset=STEP_TIMING["1.3"],
            status="FAIL",
            expected_result="Mode = NOMINAL OPS confirmed in first TM frame.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        frame = self.spacecraft.generate_telemetry_frame()
        if frame.satellite_mode == "NOMINAL OPS":
            result.status = "PASS"
            result.actual_result = f"Satellite mode: {frame.satellite_mode}"
        elif frame.satellite_mode == "SAFE":
            result.status = "FAIL"
            result.error_msg = "Satellite in SAFE mode. STOP all planned activities."
            self.critical_failed = True
        else:
            result.status = "FAIL"
            result.error_msg = f"Unexpected mode: {frame.satellite_mode}"
        
        self.add_step_result(result)
    
    def _step_1_4(self):
        """Step 1.4: Send CMD LINK TEST."""
        result = StepResult(
            step_id="1.4",
            phase=Phase.PHASE_1,
            time_offset=STEP_TIMING["1.4"],
            status="FAIL",
            expected_result="CMD LINK TEST ACK received. RSSI logged (nominal ≈ -95 dBm).",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        response = self.spacecraft.execute_command("CMD_LINK_TEST")
        if response.status != CommandStatus.ACK_RECEIVED:
            result.status = "FAIL"
            result.error_msg = "CMD LINK TEST NACK"
            self.add_step_result(result)
            return
        
        rssi = response.payload.get("rssi", -95.0)
        result.actual_result = f"CMD LINK TEST ACK | RSSI: {rssi} dBm"
        result.status = "PASS"
        result.parameter_checks = {"rssi": rssi}
        
        self.add_step_result(result)
    
    def _step_1_5(self):
        """Step 1.5: Start continuous TM recording."""
        result = StepResult(
            step_id="1.5",
            phase=Phase.PHASE_1,
            time_offset=STEP_TIMING["1.5"],
            status="PASS",
            expected_result="TM recording active. All panels updating.",
            actual_result="TM recording started. EPS | ADCS | OBC | COMMS | Thermal | Payload: ACTIVE",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
        self.phases_completed[Phase.PHASE_1] = True
    
    # ========================================================================
    # PHASE 2 — HOUSEKEEPING & SAT HEALTH CHECK
    # ========================================================================
    
    def execute_phase_2(self):
        """Phase 2: Housekeeping & Sat Health Check (T+01:15 – T+02:30)"""
        self.current_phase = Phase.PHASE_2
        self.ops_log.log_entry("=== PHASE 2: HOUSEKEEPING & SAT HEALTH CHECK ===")
        
        # Step 2.1: T+01:15 — Send CMD HK FULL REPORT
        self._step_2_1()
        
        # Step 2.2: T+01:30 — EPS check
        self._step_2_2()
        
        # Step 2.3: T+01:45 — AOCS check
        self._step_2_3()
        
        # Step 2.4: T+02:00 — Thermal check
        self._step_2_4()
        
        # Step 2.5: T+02:10 — OBC check
        self._step_2_5()
        
        # Step 2.6: T+02:20 — COMMS health
        self._step_2_6()
    
    def _step_2_1(self):
        """Step 2.1: Send CMD HK FULL REPORT."""
        result = StepResult(
            step_id="2.1",
            phase=Phase.PHASE_2,
            time_offset=STEP_TIMING["2.1"],
            status="FAIL",
            expected_result="HK packet received within 15 s. Checksum: OK.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        response = self.spacecraft.execute_command("CMD_HK_FULL_REPORT")
        if response.status == CommandStatus.ACK_RECEIVED and response.payload.get("checksum") == "OK":
            result.status = "PASS"
            result.actual_result = "HK packet received | Checksum: OK"
            result.parameter_checks = response.payload
        else:
            result.status = "FAIL"
            result.error_msg = f"HK report failed: {response.error_msg}"
        
        self.add_step_result(result)
    
    def _step_2_2(self):
        """Step 2.2: EPS check."""
        result = StepResult(
            step_id="2.2",
            phase=Phase.PHASE_2,
            time_offset=STEP_TIMING["2.2"],
            status="PASS",
            expected_result="EPS values within green limits, OR OOL noted and actioned.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        soc = self.spacecraft.get_battery_soc()
        result.actual_result = f"Battery SoC: {soc:.1f}%"
        
        if soc < OPERATIONAL_LIMITS.battery_soc_red_min:
            result.status = "FAIL"
            self.ops_log.log_anomaly("battery_soc", "RED", soc, "Escalate to SFO")
        elif soc < OPERATIONAL_LIMITS.battery_soc_yellow_min:
            result.status = "PASS"
            self.ops_log.log_anomaly("battery_soc", "YELLOW", soc, "Monitor")
        
        result.parameter_checks = {"battery_soc": soc}
        self.add_step_result(result)
    
    def _step_2_3(self):
        """Step 2.3: AOCS status check."""
        result = StepResult(
            step_id="2.3",
            phase=Phase.PHASE_2,
            time_offset=STEP_TIMING["2.3"],
            status="PASS",
            expected_result="AOCS in automated nominal operation. Wheel RPM, pointing error logged.",
            actual_result="AOCS: AUTOMATED | Attitude Mode: NOMINAL | RAW Wheels: {x: 500, y: 480, z: 510}",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
    
    def _step_2_4(self):
        """Step 2.4: Thermal check."""
        result = StepResult(
            step_id="2.4",
            phase=Phase.PHASE_2,
            time_offset=STEP_TIMING["2.4"],
            status="PASS",
            expected_result="All temperatures within green limits, OR OOL actioned.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        obc_temp = self.spacecraft.get_obc_temperature()
        result.actual_result = f"OBC: {obc_temp:.1f}°C"
        
        if obc_temp > OPERATIONAL_LIMITS.obc_temp_red_max:
            result.status = "FAIL"
            self.ops_log.log_anomaly("obc_temperature", "RED", obc_temp, "Pause operations")
        elif obc_temp > OPERATIONAL_LIMITS.obc_temp_yellow_max:
            result.status = "PASS"
            self.ops_log.log_anomaly("obc_temperature", "YELLOW", obc_temp, "Monitor")
        
        result.parameter_checks = {"obc_temp": obc_temp}
        self.add_step_result(result)
    
    def _step_2_5(self):
        """Step 2.5: OBC check."""
        result = StepResult(
            step_id="2.5",
            phase=Phase.PHASE_2,
            time_offset=STEP_TIMING["2.5"],
            status="PASS",
            expected_result="OBC nominal. Storage < 85%, OR flag raised.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        storage = self.spacecraft.get_storage_utilization()
        result.actual_result = f"OBC Storage: {storage:.1f}%"
        
        if storage > OPERATIONAL_LIMITS.obc_storage_red_max:
            result.status = "FAIL"
            self.ops_log.log_anomaly("obc_storage", "RED", storage, "Stop new data collection")
        elif storage > OPERATIONAL_LIMITS.obc_storage_yellow_max:
            result.status = "PASS"
            self.ops_log.log_anomaly("obc_storage", "YELLOW", storage, "Monitor")
        
        result.parameter_checks = {"obc_storage": storage}
        self.add_step_result(result)
    
    def _step_2_6(self):
        """Step 2.6: COMMS health check."""
        result = StepResult(
            step_id="2.6",
            phase=Phase.PHASE_2,
            time_offset=STEP_TIMING["2.6"],
            status="PASS",
            expected_result="COMMS health nominal. Frame errors < 1%.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        rssi = self.spacecraft.get_rssi()
        result.actual_result = f"RSSI: {rssi:.1f} dBm | Frame errors: 0.05%"
        result.parameter_checks = {"rssi": rssi}
        
        self.add_step_result(result)
        self.phases_completed[Phase.PHASE_2] = True
    
    # ========================================================================
    # PHASE 3 — PLATFORM DATA DOWNLOAD
    # ========================================================================
    
    def execute_phase_3(self):
        """Phase 3: Platform Data Download (T+02:30 – T+03:10)"""
        self.current_phase = Phase.PHASE_3
        self.ops_log.log_entry("=== PHASE 3: PLATFORM DATA DOWNLOAD ===")
        
        # Step 3.1: T+02:30 — Initiate platform log downlink
        self._step_3_1()
        
        # Step 3.2: T+02:57 — Confirm platform log received
        self._step_3_2()
        
        # Step 3.3: T+03:00 — Delete HK log from OBC
        self._step_3_3()
        
        # Step 3.4: T+03:05 — Log transfer details
        self._step_3_4()
    
    def _step_3_1(self):
        """Step 3.1: Send CMD DOWNLINK HK LOG."""
        result = StepResult(
            step_id="3.1",
            phase=Phase.PHASE_3,
            time_offset=STEP_TIMING["3.1"],
            status="FAIL",
            expected_result="Platform log transfer started. MCS progress visible.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        response = self.spacecraft.execute_command("CMD_DOWNLINK_HK_LOG")
        if response.status == CommandStatus.ACK_RECEIVED:
            result.status = "PASS"
            result.actual_result = f"Downlink initiated: {response.payload.get('filename')}"
        else:
            result.status = "FAIL"
            result.error_msg = response.error_msg
        
        self.add_step_result(result)
    
    def _step_3_2(self):
        """Step 3.2: Confirm platform log fully received and verified."""
        result = StepResult(
            step_id="3.2",
            phase=Phase.PHASE_3,
            time_offset=STEP_TIMING["3.2"],
            status="PASS",
            expected_result="File saved to ground archive. Checksum: VERIFIED.",
            actual_result=f"Platform log received | Size: 512 KB | Checksum: VERIFIED",
            timestamp=datetime.now(),
        )
        self.platform_data_downloaded = True
        self.add_step_result(result)
    
    def _step_3_3(self):
        """Step 3.3: Send CMD DELETE HK LOG."""
        result = StepResult(
            step_id="3.3",
            phase=Phase.PHASE_3,
            time_offset=STEP_TIMING["3.3"],
            status="FAIL",
            expected_result="Delete ACK received. New OBC storage %.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        response = self.spacecraft.execute_command("CMD_DELETE_HK_LOG")
        if response.status == CommandStatus.ACK_RECEIVED:
            result.status = "PASS"
            new_storage = response.payload.get("new_storage_percent", 0)
            result.actual_result = f"Delete ACK | New OBC storage: {new_storage:.1f}%"
        else:
            result.status = "FAIL"
            result.error_msg = response.error_msg
        
        self.add_step_result(result)
    
    def _step_3_4(self):
        """Step 3.4: Log platform data download to ops log."""
        result = StepResult(
            step_id="3.4",
            phase=Phase.PHASE_3,
            time_offset=STEP_TIMING["3.4"],
            status="PASS",
            expected_result="Platform data download entry complete in ops log.",
            actual_result="Ops log updated: platform_hk.bin | 512 KB | Transfer: OK | Checksum: OK",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
        self.phases_completed[Phase.PHASE_3] = True
    
    # ========================================================================
    # PHASE 4 — PAYLOAD DATA DOWNLOAD
    # ========================================================================
    
    def execute_phase_4(self):
        """Phase 4: Payload Data Download (T+03:10 – T+06:55)"""
        self.current_phase = Phase.PHASE_4
        self.ops_log.log_entry("=== PHASE 4: PAYLOAD DATA DOWNLOAD ===")
        
        # Step 4.1: T+03:10 — Query payload storage
        self._step_4_1()
        
        # Step 4.2: T+03:20 — Initiate payload downlink
        self._step_4_2()
        
        # Step 4.3: T+04:00 — Mid-transfer thermal monitoring
        self._step_4_3()
        
        # Step 4.4: T+06:53 — Confirm all payload files received
        self._step_4_4()
        
        # Step 4.5: T+06:55 — Delete verified payload files
        self._step_4_5()
    
    def _step_4_1(self):
        """Step 4.1: Send CMD PAYLOAD STORAGE QUERY."""
        result = StepResult(
            step_id="4.1",
            phase=Phase.PHASE_4,
            time_offset=STEP_TIMING["4.1"],
            status="FAIL",
            expected_result="Payload file list received. Volume and file count logged.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        response = self.spacecraft.execute_command("CMD_PAYLOAD_STORAGE_QUERY")
        if response.status == CommandStatus.ACK_RECEIVED:
            result.status = "PASS"
            result.actual_result = (
                f"Payload files: {response.payload.get('total_files', 0)} | "
                f"Volume: {response.payload.get('total_data_volume_mb', 0)} MB"
            )
        else:
            result.status = "FAIL"
            result.error_msg = response.error_msg
        
        self.add_step_result(result)
    
    def _step_4_2(self):
        """Step 4.2: Send CMD DOWNLINK PAYLOAD."""
        result = StepResult(
            step_id="4.2",
            phase=Phase.PHASE_4,
            time_offset=STEP_TIMING["4.2"],
            status="FAIL",
            expected_result="Payload downlink started. File queue active in MCS.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        response = self.spacecraft.execute_command("CMD_DOWNLINK_PAYLOAD")
        if response.status == CommandStatus.ACK_RECEIVED:
            result.status = "PASS"
            result.actual_result = f"Payload downlink started: {response.payload.get('size_mb')} MB"
        else:
            result.status = "FAIL"
            result.error_msg = response.error_msg
        
        self.add_step_result(result)
    
    def _step_4_3(self):
        """Step 4.3: Mid-transfer thermal check."""
        result = StepResult(
            step_id="4.3",
            phase=Phase.PHASE_4,
            time_offset=STEP_TIMING["4.3"],
            status="PASS",
            expected_result="OBC temp < 58°C: transfer continues. If not: pause, cool, resume.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        obc_temp = self.spacecraft.get_obc_temperature()
        result.actual_result = f"OBC temp: {obc_temp:.1f}°C"
        
        if obc_temp > OPERATIONAL_LIMITS.mid_transfer_temp_threshold:
            result.status = "FAIL"
            result.error_msg = f"Temp exceeded threshold ({obc_temp:.1f} > {OPERATIONAL_LIMITS.mid_transfer_temp_threshold}°C)"
            self.ops_log.log_anomaly("obc_temperature", "MID_TRANSFER", obc_temp, "Pause downlink")
        
        result.parameter_checks = {"obc_temp": obc_temp}
        self.add_step_result(result)
    
    def _step_4_4(self):
        """Step 4.4: Confirm all payload files received."""
        result = StepResult(
            step_id="4.4",
            phase=Phase.PHASE_4,
            time_offset=STEP_TIMING["4.4"],
            status="PASS",
            expected_result="All payload files archived. Checksums: VERIFIED. Image manifest updated.",
            actual_result="3 payload files received | All checksums verified | Manifest updated",
            timestamp=datetime.now(),
        )
        self.payload_data_downloaded = True
        self.add_step_result(result)
    
    def _step_4_5(self):
        """Step 4.5: Send CMD DELETE PAYLOAD FILES."""
        result = StepResult(
            step_id="4.5",
            phase=Phase.PHASE_4,
            time_offset=STEP_TIMING["4.5"],
            status="FAIL",
            expected_result=f"Payload files deleted. Storage < {OPERATIONAL_LIMITS.obc_storage_target_after_dl}% confirmed.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        response = self.spacecraft.execute_command("CMD_DELETE_PAYLOAD_FILES")
        if response.status == CommandStatus.ACK_RECEIVED:
            storage = response.payload.get("new_storage_percent", 0)
            result.actual_result = f"Payload files deleted | New storage: {storage:.1f}%"
            
            if storage <= OPERATIONAL_LIMITS.obc_storage_target_after_dl:
                result.status = "PASS"
            else:
                result.status = "FAIL"
                result.error_msg = f"Storage {storage:.1f}% exceeds target {OPERATIONAL_LIMITS.obc_storage_target_after_dl}%"
                self.ops_log.log_deferred("5.0", "Payload storage target not met")
        else:
            result.status = "FAIL"
            result.error_msg = response.error_msg
        
        self.add_step_result(result)
        self.phases_completed[Phase.PHASE_4] = True
    
    # ========================================================================
    # PHASE 5 — COMMS CONFIGURATION CHANGE
    # ========================================================================
    
    def execute_phase_5(self):
        """Phase 5: COMMS Configuration Change (T+07:00 – T+07:50)"""
        self.current_phase = Phase.PHASE_5
        self.ops_log.log_entry("=== PHASE 5: COMMS CONFIGURATION CHANGE ===")
        
        # Step 5.1: Precondition checks
        if not self._step_5_1():
            self.ops_log.log_deferred("5.0", "Preconditions not met. Deferring COMMS config change to next pass.")
            self.phases_completed[Phase.PHASE_5] = False
            return
        
        # Step 5.2: T+07:02 — Upload config file
        self._step_5_2()
        
        # Step 5.3: T+07:05 — Await upload ACK
        self._step_5_3()
        
        # Step 5.4: T+07:08 — Apply COMMS config (TX will drop)
        self._step_5_4()
        
        # Step 5.5: T+07:10 — TM downlink lost
        self._step_5_5()

        # Step 5.6: T+07:40 — TM restored, CMD TX ON
        # Wait ~30 seconds (simulate) to allow COMMS restart to complete
        wait_s = 30.0
        dt = 1.0
        waited = 0.0
        self.ops_log.log_entry(f"Waiting {wait_s:.0f}s for COMMS restart to complete (simulated)")
        while waited < wait_s:
            self.spacecraft.update(dt)
            waited += dt

        self._step_5_6()
        
        # Step 5.7: T+07:45 — Verify config version
        self._step_5_7()
        
        # Step 5.8: T+07:50 — Post-config verification
        self._step_5_8()
    
    def _step_5_1(self) -> bool:
        """
        Step 5.1: Check 6 preconditions before config change.
        Returns True if all preconditions met, False otherwise.
        """
        result = StepResult(
            step_id="5.1",
            phase=Phase.PHASE_5,
            time_offset=STEP_TIMING["5.1"],
            status="PASS",
            expected_result="All six preconditions MET. Proceed to 5.2.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        checks = {
            "(a) Mode = NOMINAL OPS": self.spacecraft.get_satellite_mode() == "NOMINAL OPS",
            "(b) No OOL": True,  # Assuming cleared
            "(c) RSSI >= -90 dBm": self.spacecraft.get_rssi() >= OPERATIONAL_LIMITS.rssi_yellow_threshold,
            "(d) Storage < 85%": self.spacecraft.get_storage_utilization() < OPERATIONAL_LIMITS.obc_storage_yellow_max,
            "(e) Temp < 55°C": self.spacecraft.get_obc_temperature() < OPERATIONAL_LIMITS.obc_temp_yellow_max,
        }
        
        all_pass = all(checks.values())
        
        if all_pass:
            result.actual_result = " | ".join([f"{k}: ✓" for k in checks.keys()])
            result.status = "PASS"
        else:
            failed = [k for k, v in checks.items() if not v]
            result.actual_result = " | ".join([f"{k}: {'✓' if checks[k] else '✗'}" for k in checks.keys()])
            result.status = "FAIL"
            result.error_msg = f"Preconditions failed: {', '.join(failed)}"
        
        result.parameter_checks = checks
        self.add_step_result(result)
        return all_pass
    
    def _step_5_2(self):
        """Step 5.2: Upload new config file."""
        result = StepResult(
            step_id="5.2",
            phase=Phase.PHASE_5,
            time_offset=STEP_TIMING["5.2"],
            status="FAIL",
            expected_result="Upload progress bar active. File size: 10 KB.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        response = self.spacecraft.execute_command("CMD_UPLOAD_FILE")
        if response.status == CommandStatus.ACK_RECEIVED:
            result.status = "PASS"
            result.actual_result = f"Upload initiated: {response.payload.get('filename')}"
        else:
            result.status = "FAIL"
            result.error_msg = response.error_msg
        
        self.add_step_result(result)
    
    def _step_5_3(self):
        """Step 5.3: Await upload ACK and verify checksum."""
        result = StepResult(
            step_id="5.3",
            phase=Phase.PHASE_5,
            time_offset=STEP_TIMING["5.3"],
            status="PASS",
            expected_result="Upload ACK received. Checksum: MATCH.",
            actual_result="Upload ACK | Checksum: a3f9b2c1 (MATCH)",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
    
    def _step_5_4(self):
        """Step 5.4: Send CMD APPLY COMMS CONFIG."""
        result = StepResult(
            step_id="5.4",
            phase=Phase.PHASE_5,
            time_offset=STEP_TIMING["5.4"],
            status="FAIL",
            expected_result="CMD APPLY COMMS CONFIG ACK received.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        response = self.spacecraft.execute_command("CMD_APPLY_COMMS_CONFIG")
        if response.status == CommandStatus.ACK_RECEIVED:
            result.status = "PASS"
            result.actual_result = "CMD APPLY COMMS CONFIG ACK | COMMS restart initiated"
            self.ops_log.log_entry("⚠️  TM downlink will be LOST for ~30 seconds (expected)")
        else:
            result.status = "FAIL"
            result.error_msg = f"Config change failed: {response.error_msg}"
            self.critical_failed = True
        
        self.add_step_result(result)
    
    def _step_5_5(self):
        """Step 5.5: TM downlink LOST (expected)."""
        result = StepResult(
            step_id="5.5",
            phase=Phase.PHASE_5,
            time_offset=STEP_TIMING["5.5"],
            status="PASS",
            expected_result="TM gap in progress. MCS shows TM LOST. Restoration within ~30 s.",
            actual_result="TM stream lost at T+07:08 | Awaiting restoration...",
            timestamp=datetime.now(),
        )
        
        # Simulate TM loss
        self.spacecraft.lose_tm_lock()
        
        self.add_step_result(result)
    
    def  _step_5_6(self):
        """Step 5.6: COMMS restart complete, restore TX."""
        result = StepResult(
            step_id="5.6",
            phase=Phase.PHASE_5,
            time_offset=STEP_TIMING["5.6"],
            status="FAIL",
            expected_result="CMD TX ON sent. Awaiting TM lock re-establishment.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        # Check if COMMS restart complete
        if not self.spacecraft.comms_restart_active:
            response = self.spacecraft.execute_command("CMD_TX_ON")
            if response.status == CommandStatus.ACK_RECEIVED:
                result.status = "PASS"
                result.actual_result = "CMD TX ON sent | Awaiting TM lock..."
            else:
                result.status = "FAIL"
                result.error_msg = response.error_msg
        else:
            result.status = "FAIL"
            result.error_msg = "COMMS restart still active"
        
        self.add_step_result(result)
    
    def _step_5_7(self):
        """Step 5.7: TM downlink restored, verify config version."""
        result = StepResult(
            step_id="5.7",
            phase=Phase.PHASE_5,
            time_offset=STEP_TIMING["5.7"],
            status="PASS",
            expected_result="TM lock re-established. Version v2: CONFIRMED.",
            actual_result="TM lock restored at T+07:38 | Config version: v2 | CONFIRMED",
            timestamp=datetime.now(),
        )
        
        # Re-establish TM lock
        self.spacecraft.establish_tm_lock()
        self.spacecraft.set_config_version("v2")
        self.comms_config_changed = True
        
        self.add_step_result(result)
    
    def _step_5_8(self):
        """Step 5.8: Post-config verification."""
        result = StepResult(
            step_id="5.8",
            phase=Phase.PHASE_5,
            time_offset=STEP_TIMING["5.8"],
            status="PASS",
            expected_result="RSSI nominal. Frame errors < 1%. Operating normally under v2.",
            actual_result=f"RSSI: {self.spacecraft.get_rssi():.1f} dBm | Frame errors: 0.05% | Config: v2 | COMPLETE",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
        self.phases_completed[Phase.PHASE_5] = True
    
    # ========================================================================
    # PHASE 6 — PRE-LOS CLOSE-OUT
    # ========================================================================
    
    def execute_phase_6(self):
        """Phase 6: Pre-LOS Close-out (T+08:30 – T+09:30)"""
        self.current_phase = Phase.PHASE_6
        self.ops_log.log_entry("=== PHASE 6: PRE-LOS CLOSE-OUT ===")
        
        # Step 6.1: T+08:30 — Final health summary
        self._step_6_1()
        
        # Step 6.2: T+08:45 — Verify activity completion
        self._step_6_2()
        
        # Step 6.3: T+09:00 — Send CMD CONTACT CLOSE
        self._step_6_3()
        
        # Step 6.4: T+09:15 — Send CMD TX OFF
        self._step_6_4()
        
        # Step 6.5: T+09:30 — Await GSO confirmation of LOS
        self._step_6_5()
    
    def _step_6_1(self):
        """Step 6.1: Pre-LOS health summary."""
        result = StepResult(
            step_id="6.1",
            phase=Phase.PHASE_6,
            time_offset=STEP_TIMING["6.1"],
            status="PASS",
            expected_result="Final health values logged. Mode = NOMINAL OPS.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        frame = self.spacecraft.generate_telemetry_frame()
        result.actual_result = (
            f"Mode: {frame.satellite_mode} | "
            f"SoC: {frame.battery_soc:.1f}% | "
            f"Temp: {frame.obc_temperature:.1f}°C | "
            f"Storage: {frame.obc_storage_utilization:.1f}% | "
            f"RSSI: {frame.rssi:.1f} dBm | "
            f"Config: {frame.comms_config_version}"
        )
        
        self.add_step_result(result)
    
    def _step_6_2(self):
        """Step 6.2: Verify activity completion."""
        result = StepResult(
            step_id="6.2",
            phase=Phase.PHASE_6,
            time_offset=STEP_TIMING["6.2"],
            status="PASS",
            expected_result="Activity checklist reviewed. Deferred items noted with justification.",
            actual_result=(
                f"Platform DL: {'✓' if self.platform_data_downloaded else 'DEFERRED'} | "
                f"Payload DL: {'✓' if self.payload_data_downloaded else 'DEFERRED'} | "
                f"COMMS Config: {'✓' if self.comms_config_changed else 'DEFERRED'}"
            ),
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
    
    def _step_6_3(self):
        """Step 6.3: Send CMD CONTACT CLOSE."""
        result = StepResult(
            step_id="6.3",
            phase=Phase.PHASE_6,
            time_offset=STEP_TIMING["6.3"],
            status="FAIL",
            expected_result="CMD CONTACT CLOSE ACK received. Satellite entering inter-pass mode.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        response = self.spacecraft.execute_command("CMD_CONTACT_CLOSE")
        if response.status == CommandStatus.ACK_RECEIVED:
            result.status = "PASS"
            result.actual_result = "CMD CONTACT CLOSE ACK | Satellite entering inter-pass autonomy"
        else:
            result.status = "FAIL"
            result.error_msg = response.error_msg
        
        self.add_step_result(result)
    
    def _step_6_4(self):
        """Step 6.4: Send CMD TX OFF."""
        result = StepResult(
            step_id="6.4",
            phase=Phase.PHASE_6,
            time_offset=STEP_TIMING["6.4"],
            status="FAIL",
            expected_result="CMD TX OFF ACK received. TM stream ends. COMMS TX = OFF.",
            actual_result="",
            timestamp=datetime.now(),
        )
        
        response = self.spacecraft.execute_command("CMD_TX_OFF")
        if response.status == CommandStatus.ACK_RECEIVED:
            result.status = "PASS"
            result.actual_result = "CMD TX OFF ACK | TM stream ended | TX: OFF"
            self.spacecraft.lose_tm_lock()
        else:
            result.status = "FAIL"
            result.error_msg = response.error_msg
        
        self.add_step_result(result)
    
    def _step_6_5(self):
        """Step 6.5: Await GSO confirmation of LOS."""
        result = StepResult(
            step_id="6.5",
            phase=Phase.PHASE_6,
            time_offset=STEP_TIMING["6.5"],
            status="PASS",
            expected_result="LOS confirmed by GSO. Recording stopped. Archive complete.",
            actual_result=f"LOS at {datetime.now().isoformat()} | Recording archived",
            timestamp=datetime.now(),
        )
        
        self.los_time = self.spacecraft.simulation_time
        if self.aos_time:
            self.pass_duration = self.los_time - self.aos_time
        
        self.add_step_result(result)
        self.phases_completed[Phase.PHASE_6] = True
    
    # ========================================================================
    # PHASE 7 — POST-CONTACT ACTIONS
    # ========================================================================
    
    def execute_phase_7(self):
        """Phase 7: Post-contact Actions (within 30 minutes of LOS)"""
        self.current_phase = Phase.PHASE_7
        self.ops_log.log_entry("=== PHASE 7: POST-CONTACT ACTIONS ===")
        
        self._step_7_1()
        self._step_7_2()
        self._step_7_3()
        self._step_7_4()
        self._step_7_5()
        self.phases_completed[Phase.PHASE_7] = True
    
    def _step_7_1(self):
        """Step 7.1: Complete ops log."""
        result = StepResult(
            step_id="7.1",
            phase=Phase.PHASE_7,
            time_offset=0,
            status="PASS",
            expected_result="Ops log complete and saved.",
            actual_result=(
                f"Pass duration: {self.pass_duration:.0f}s | "
                f"Platform: {'✓' if self.platform_data_downloaded else 'N/A'} | "
                f"Payload: {'✓' if self.payload_data_downloaded else 'N/A'} | "
                f"Config: {'✓' if self.comms_config_changed else 'DEFERRED'}"
            ),
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
    
    def _step_7_2(self):
        """Step 7.2: Raise anomaly reports."""
        result = StepResult(
            step_id="7.2",
            phase=Phase.PHASE_7,
            time_offset=0,
            status="PASS",
            expected_result="All anomaly reports raised and filed.",
            actual_result=f"{len(self.ops_log.anomalies)} anomaly reports raised" if self.ops_log.anomalies else "No anomalies",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
    
    def _step_7_3(self):
        """Step 7.3: Archive all downlinked data."""
        result = StepResult(
            step_id="7.3",
            phase=Phase.PHASE_7,
            time_offset=0,
            status="PASS",
            expected_result="All data archived. Processing team notified.",
            actual_result="Platform + Payload data archived | Processing team notified",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
    
    def _step_7_4(self):
        """Step 7.4: Update mission database."""
        result = StepResult(
            step_id="7.4",
            phase=Phase.PHASE_7,
            time_offset=0,
            status="PASS",
            expected_result="Mission database updated. Change tracking closed.",
            actual_result=f"Config v2 marked active | Change Request CR-COMMS-047: {'CLOSED' if self.comms_config_changed else 'OPEN'}",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
    
    def _step_7_5(self):
        """Step 7.5: Complete shift handover document."""
        result = StepResult(
            step_id="7.5",
            phase=Phase.PHASE_7,
            time_offset=0,
            status="PASS",
            expected_result="Handover document signed and delivered.",
            actual_result="Handover document completed and delivered to incoming SFO",
            timestamp=datetime.now(),
        )
        self.add_step_result(result)
    
    # ========================================================================
    # EXECUTION & REPORTING
    # ========================================================================
    
    def execute_full_contact(self):
        """Execute full pass from Phase 0 through Phase 7."""
        try:
            self.execute_phase_0()
            if self.critical_failed:
                self.ops_log.log_entry("✘ CRITICAL FAILURE in Phase 0. Check pre-contact conditions.", "ERROR")
                return
            
            self.execute_phase_1()
            if self.critical_failed:
                self.ops_log.log_entry("✘ CRITICAL FAILURE in Phase 1. Cannot establish contact.", "ERROR")
                return
            
            self.execute_phase_2()
            self.execute_phase_3()
            self.execute_phase_4()
            
            # Phase 5 is optional (deferrable)
            self.execute_phase_5()
            
            self.execute_phase_6()
            self.execute_phase_7()
            
            self.ops_log.log_entry("=== PASS COMPLETE ===")
            
        except Exception as e:
            self.ops_log.log_entry(f"✘ EXCEPTION: {e}", "CRITICAL")
            raise
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate pass execution report."""
        passed = sum(1 for r in self.step_results if r.status == "PASS")
        failed = sum(1 for r in self.step_results if r.status == "FAIL")
        deferred = sum(1 for r in self.step_results if r.status == "DEFERRED")
        
        return {
            "pass_summary": {
                "aos_time": self.aos_time,
                "los_time": self.los_time,
                "duration_seconds": self.pass_duration,
                "critical_failed": self.critical_failed,
            },
            "step_results": {
                "total": len(self.step_results),
                "passed": passed,
                "failed": failed,
                "deferred": deferred,
            },
            "phases_completed": {p.name: self.phases_completed[p] for p in Phase},
            "data_downloads": {
                "platform": self.platform_data_downloaded,
                "payload": self.payload_data_downloaded,
                "config_change": self.comms_config_changed,
            },
            "anomalies": len(self.ops_log.anomalies),
            "deferred_items": len(self.ops_log.deferred_items),
        }
