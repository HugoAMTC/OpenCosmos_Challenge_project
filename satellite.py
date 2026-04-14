"""
Mantis Spacecraft Simulation Module
Simulates subsystems: EPS, OBC, COMMS, ADCS, Thermal, Payload

Provides realistic command/response interface with ACK/NACK handling,
physics simulation (power, thermal), and state management.
"""

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import hashlib
import random

from config import (
    INITIAL_SATELLITE_STATE, OPERATIONAL_LIMITS, COMMANDS, PHYSICS,
    CONFIG_FILE_SIZE_KB, PLATFORM_LOG_SIZE_MB, PAYLOAD_DATA_SIZE_MB,
    UPLINK_BITRATE_KBPS, DOWNLINK_BITRATE_KBPS,
)


class CommandStatus(Enum):
    """Command execution status."""
    PENDING = "PENDING"
    ACK_RECEIVED = "ACK_RECEIVED"
    NACK_RECEIVED = "NACK_RECEIVED"
    TIMEOUT = "TIMEOUT"


@dataclass
class CommandResponse:
    """Encapsulates command response from satellite."""
    cmd_name: str
    status: CommandStatus
    timestamp: float
    payload: Dict[str, Any] = field(default_factory=dict)
    error_msg: str = ""


@dataclass
class TelemetryFrame:
    """Single telemetry frame snapshot."""
    timestamp: float
    satellite_mode: str
    battery_soc: float
    obc_temperature: float
    battery_temperature: float
    payload_temperature: float
    transceiver_temperature: float
    obc_storage_utilization: float
    rssi: float
    frame_sync: str  # "GREEN", "YELLOW", "RED"
    tx_enabled: bool
    comms_config_version: str


class MantisSpacecraft:
    """
    Mantis spacecraft simulator from Open Cosmos.
    Simulates all subsystems with realistic physics and command interface.
    """
    
    def __init__(self, initial_state: Dict[str, Any] = None, anomaly: Dict = None):
        """
        Initialize Mantis spacecraft.
        
        Args:
            initial_state: Dict overriding defaults from config
            anomaly: Dict with anomaly parameters to inject
        """
        self.state = INITIAL_SATELLITE_STATE.copy()
        if initial_state:
            self.state.update(initial_state)
        
        self.anomaly = anomaly or {}
        self.simulation_time = 0.0  # Elapsed time since start
        self.last_tm_frame = None
        self.tm_lock_active = False
        self.tm_lock_time = None
        
        # Command tracking
        self.pending_commands: Dict[str, CommandResponse] = {}
        self.command_history: list = []
        
        # Data buffers
        self.platform_log_buffer = bytearray()
        self.payload_buffer = bytearray()
        self.config_buffer = bytearray()
        
        # File checksums
        self.platform_log_checksum = None
        self.payload_checksum = None
        self.config_file_checksum = None
        
        # Downlink state
        self.current_downlink = None  # "platform_log", "payload", etc.
        self.downlink_progress = 0.0  # 0.0 to 1.0
        
        # Comms restart tracking
        self.comms_restart_active = False
        self.comms_restart_start_time = None
        
    def update(self, dt: float):
        """
        Update spacecraft simulation by dt seconds.
        Applies physics: power drain, thermal changes, data transfers.
        
        Args:
            dt: Time delta in seconds
        """
        self.simulation_time += dt
        
        # Inject anomaly if triggered
        self._check_and_apply_anomalies()
        
        # Update thermal model
        self._update_thermal_model(dt)
        
        # Update power model
        self._update_power_model(dt)
        
        # Update downlinks
        self._update_downlink_progress(dt)
        
        # Update COMMS restart if active
        self._update_comms_restart(dt)
        
        # Check operational limits and set mode if needed
        self._update_satellite_mode()
    
    def _check_and_apply_anomalies(self):
        """Check and apply injected anomalies."""
        if not self.anomaly:
            return
        
        # Apply state mutations from anomaly
        for key, value in self.anomaly.items():
            if key in self.state and key != "trigger_phase":
                self.state[key] = value
    
    def _update_thermal_model(self, dt: float):
        """Update thermal state based on power profile and cooling."""
        # OBC temperature update
        if self.state["tx_enabled"] or self.current_downlink:
            temp_rise_rate = PHYSICS["obc_active_temp_rise"]
        else:
            temp_rise_rate = PHYSICS["obc_idle_temp_rise"]
        
        delta_t = (temp_rise_rate - PHYSICS["obc_passive_cooling_rate"]) * dt
        self.state["obc_temperature"] = min(
            self.state["obc_temperature"] + delta_t,
            PHYSICS["ambient_temp"] + 60.0  # Upper bound
        )
        
        # Battery temperature (slower response)
        if self.current_downlink:
            battery_rise = 0.1 * dt
        else:
            battery_rise = -0.02 * dt
        self.state["battery_temperature"] = max(
            PHYSICS["ambient_temp"],
            self.state["battery_temperature"] + battery_rise
        )
        
        # Payload temperature (couples to OBC)
        payload_rise = (self.state["obc_temperature"] - self.state["payload_temperature"]) * 0.05 * dt
        self.state["payload_temperature"] += payload_rise
        
        # Transceiver temperature (active during TX)
        if self.state["tx_enabled"]:
            xvr_rise = 0.2 * dt
        else:
            xvr_rise = -0.05 * dt
        self.state["transceiver_temperature"] += xvr_rise
    
    def _update_power_model(self, dt: float):
        """Update battery state of charge based on power consumption."""
        # Estimate power draw
        power_draw = PHYSICS["obc_idle_power"]
        
        if self.state["tx_enabled"]:
            power_draw += PHYSICS["comms_tx_power"]
        
        if self.current_downlink:
            power_draw += PHYSICS["payload_download_power"]
        
        # Battery discharge: convert W to % using assumed capacity
        # Assume ~3600 Wh battery (reasonable for small sat)
        battery_capacity_wh = 3600.0
        discharge_rate = (power_draw / battery_capacity_wh) * 100.0 / 3600.0  # %/sec
        
        self.state["battery_soc"] = max(
            0.0,
            self.state["battery_soc"] - (discharge_rate * dt)
        )
    
    def _update_downlink_progress(self, dt: float):
        """Update file transfer progress."""
        if not self.current_downlink or not self.state["tx_enabled"]:
            return
        
        # Calculate transfer rate (bits per second)
        transfer_rate_bps = DOWNLINK_BITRATE_KBPS * 1000.0
        
        # Determine file size
        if self.current_downlink == "platform_log":
            total_bits = PLATFORM_LOG_SIZE_MB * 8 * 1024 * 1024
        elif self.current_downlink == "payload":
            total_bits = PAYLOAD_DATA_SIZE_MB * 8 * 1024 * 1024
        else:
            return
        
        bits_transferred = transfer_rate_bps * dt
        self.downlink_progress = min(1.0, self.downlink_progress + bits_transferred / total_bits)
    
    def _update_comms_restart(self, dt: float):
        """Update COMMS restart state machine."""
        if not self.comms_restart_active or not self.comms_restart_start_time:
            return
        
        elapsed = self.simulation_time - self.comms_restart_start_time
        
        # COMMS restart takes ~30 seconds
        if elapsed < 5.0:
            # TX just turned off, RX still down
            self.state["tx_enabled"] = False
            self.state["rx_enabled"] = False
        elif elapsed < 30.0:
            # Restart in progress
            self.state["tx_enabled"] = False
            self.state["rx_enabled"] = False
        else:
            # Restart complete: RX restored, awaiting CMD TX ON
            self.state["rx_enabled"] = True
            self.comms_restart_active = False
    
    def _update_satellite_mode(self):
        """Check limits and update satellite mode if needed."""
        # Only transition to SAFE mode if severely out of limits
        if (self.state["battery_soc"] < OPERATIONAL_LIMITS.battery_soc_red_min or
            self.state["obc_temperature"] > OPERATIONAL_LIMITS.obc_temp_red_max or
            self.state["battery_temperature"] > OPERATIONAL_LIMITS.battery_temp_red_max):
            if self.anomaly.get("satellite_mode") == "SAFE":
                self.state["satellite_mode"] = "SAFE"
    
    def generate_telemetry_frame(self) -> TelemetryFrame:
        """Generate current telemetry frame snapshot."""
        # Determine frame sync status
        if self.tm_lock_active:
            if abs(self.state["rssi"]) > -100:
                frame_sync = "GREEN"
            else:
                frame_sync = "YELLOW"
        else:
            frame_sync = "RED"
        
        frame = TelemetryFrame(
            timestamp=self.simulation_time,
            satellite_mode=self.state["satellite_mode"],
            battery_soc=self.state["battery_soc"],
            obc_temperature=self.state["obc_temperature"],
            battery_temperature=self.state["battery_temperature"],
            payload_temperature=self.state["payload_temperature"],
            transceiver_temperature=self.state["transceiver_temperature"],
            obc_storage_utilization=self.state["storage_utilization"],
            rssi=self.state["rssi"],
            frame_sync=frame_sync,
            tx_enabled=self.state["tx_enabled"],
            comms_config_version=self.state["config_version"],
        )
        self.last_tm_frame = frame
        return frame
    
    def execute_command(self, cmd_name: str, payload: Dict = None) -> CommandResponse:
        """
        Execute a command on the satellite.
        Returns CommandResponse with ACK/NACK status.
        
        Args:
            cmd_name: Command name from config.COMMANDS
            payload: Optional command payload dict
        
        Returns:
            CommandResponse with status and result
        """
        payload = payload or {}
        response = CommandResponse(
            cmd_name=cmd_name,
            status=CommandStatus.ACK_RECEIVED,
            timestamp=self.simulation_time,
            payload={}
        )
        
        # Check if command exists
        if cmd_name not in COMMANDS:
            response.status = CommandStatus.NACK_RECEIVED
            response.error_msg = f"Unknown command: {cmd_name}"
            return response
        
        # Execute command handler
        handler_name = f"_cmd_{cmd_name.lower()}"
        if hasattr(self, handler_name):
            handler = getattr(self, handler_name)
            response = handler(payload) or response
        
        self.command_history.append(response)
        return response
    
    # ========================================================================
    # COMMAND HANDLERS
    # ========================================================================
    
    def _cmd_cmd_tx_on(self, payload: Dict) -> CommandResponse:
        """CMD TX ON: Enable transmitter."""
        response = CommandResponse(
            cmd_name="CMD_TX_ON",
            status=CommandStatus.ACK_RECEIVED,
            timestamp=self.simulation_time,
        )
        
        # Check COMMS status
        if self.comms_restart_active and not self.state["rx_enabled"]:
            response.status = CommandStatus.NACK_RECEIVED
            response.error_msg = "COMMS restart in progress"
            return response
        
        self.state["tx_enabled"] = True
        response.payload = {"tx_status": "ON"}
        return response
    
    def _cmd_cmd_tx_off(self, payload: Dict) -> CommandResponse:
        """CMD TX OFF: Disable transmitter."""
        response = CommandResponse(
            cmd_name="CMD_TX_OFF",
            status=CommandStatus.ACK_RECEIVED,
            timestamp=self.simulation_time,
        )
        self.state["tx_enabled"] = False
        response.payload = {"tx_status": "OFF"}
        return response
    
    def _cmd_cmd_hk_full_report(self, payload: Dict) -> CommandResponse:
        """CMD HK FULL REPORT: Downlink housekeeping packet."""
        response = CommandResponse(
            cmd_name="CMD_HK_FULL_REPORT",
            status=CommandStatus.ACK_RECEIVED,
            timestamp=self.simulation_time,
        )
        
        response.payload = {
            "battery_soc": self.state["battery_soc"],
            "bus_voltage": self.state["bus_voltage"],
            "solar_array_current": self.state["solar_array_current"],
            "obc_temperature": self.state["obc_temperature"],
            "battery_temperature": self.state["battery_temperature"],
            "payload_temperature": self.state["payload_temperature"],
            "transceiver_temperature": self.state["transceiver_temperature"],
            "uptime_counter": self.state["uptime_counter"],
            "ram_usage": self.state["ram_usage"],
            "storage_utilization": self.state["storage_utilization"],
            "attitude_mode": self.state["attitude_mode"],
            "pointing_error": self.state["pointing_error"],
            "wheel_rpm": self.state["wheel_rpm"],
            "rssi": self.state["rssi"],
            "uplink_frame_error_rate": self.state["uplink_frame_error_rate"],
            "downlink_frame_error_rate": self.state["downlink_frame_error_rate"],
            "config_version": self.state["config_version"],
            "checksum": "OK",
        }
        return response
    
    def _cmd_cmd_link_test(self, payload: Dict) -> CommandResponse:
        """CMD LINK TEST: Test uplink/downlink."""
        response = CommandResponse(
            cmd_name="CMD_LINK_TEST",
            status=CommandStatus.ACK_RECEIVED,
            timestamp=self.simulation_time,
        )
        response.payload = {
            "rssi": self.state["rssi"],
            "link_quality": "GOOD" if self.state["rssi"] > -95 else "DEGRADED",
        }
        return response
    
    def _cmd_cmd_downlink_hk_log(self, payload: Dict) -> CommandResponse:
        """CMD DOWNLINK HK LOG: Start platform log downlink."""
        response = CommandResponse(
            cmd_name="CMD_DOWNLINK_HK_LOG",
            status=CommandStatus.ACK_RECEIVED,
            timestamp=self.simulation_time,
        )
        
        # Simulate file generation and transfer initiation
        self.current_downlink = "platform_log"
        self.downlink_progress = 0.0
        self.platform_log_buffer = bytearray(
            int(PLATFORM_LOG_SIZE_MB * 1024 * 1024)
        )
        # Generate checksum
        self.platform_log_checksum = hashlib.md5(self.platform_log_buffer).hexdigest()[:8]
        
        response.payload = {
            "filename": f"platform_hk_{int(self.simulation_time)}.bin",
            "size_bytes": len(self.platform_log_buffer),
            "checksum": self.platform_log_checksum,
            "transfer_started": True,
        }
        return response
    
    def _cmd_cmd_delete_hk_log(self, payload: Dict) -> CommandResponse:
        """CMD DELETE HK LOG: Delete platform log from OBC."""
        response = CommandResponse(
            cmd_name="CMD_DELETE_HK_LOG",
            status=CommandStatus.ACK_RECEIVED,
            timestamp=self.simulation_time,
        )
        
        # Update storage utilization
        old_storage = self.state["storage_utilization"]
        log_size_percent = (PLATFORM_LOG_SIZE_MB * 1024) / 100.0  # Assume 100 MB total
        self.state["storage_utilization"] = max(0.0, old_storage - log_size_percent)
        
        response.payload = {
            "deleted_size_mb": PLATFORM_LOG_SIZE_MB,
            "new_storage_percent": self.state["storage_utilization"],
        }
        return response
    
    def _cmd_cmd_payload_storage_query(self, payload: Dict) -> CommandResponse:
        """CMD PAYLOAD STORAGE QUERY: Query payload storage status."""
        response = CommandResponse(
            cmd_name="CMD_PAYLOAD_STORAGE_QUERY",
            status=CommandStatus.ACK_RECEIVED,
            timestamp=self.simulation_time,
        )
        response.payload = {
            "total_files": 3,
            "total_data_volume_mb": PAYLOAD_DATA_SIZE_MB,
            "oldest_file_timestamp": self.simulation_time - 3600,
        }
        return response
    
    def _cmd_cmd_downlink_payload(self, payload: Dict) -> CommandResponse:
        """CMD DOWNLINK PAYLOAD: Start payload data downlink."""
        response = CommandResponse(
            cmd_name="CMD_DOWNLINK_PAYLOAD",
            status=CommandStatus.ACK_RECEIVED,
            timestamp=self.simulation_time,
        )
        
        self.current_downlink = "payload"
        self.downlink_progress = 0.0
        self.payload_buffer = bytearray(
            int(PAYLOAD_DATA_SIZE_MB * 1024 * 1024)
        )
        self.payload_checksum = hashlib.md5(self.payload_buffer).hexdigest()[:8]
        
        response.payload = {
            "filename": f"payload_{int(self.simulation_time)}.bin",
            "size_mb": PAYLOAD_DATA_SIZE_MB,
            "checksum": self.payload_checksum,
            "file_count": 3,
            "transfer_started": True,
        }
        return response
    
    def _cmd_cmd_delete_payload_files(self, payload: Dict) -> CommandResponse:
        """CMD DELETE PAYLOAD FILES: Delete verified payload files."""
        response = CommandResponse(
            cmd_name="CMD_DELETE_PAYLOAD_FILES",
            status=CommandStatus.ACK_RECEIVED,
            timestamp=self.simulation_time,
        )
        
        # Update storage
        old_storage = self.state["storage_utilization"]
        payload_size_percent = (PAYLOAD_DATA_SIZE_MB * 1024) / 100.0
        self.state["storage_utilization"] = max(0.0, old_storage - payload_size_percent)
        
        response.payload = {
            "deleted_size_mb": PAYLOAD_DATA_SIZE_MB,
            "new_storage_percent": self.state["storage_utilization"],
        }
        return response
    
    def _cmd_cmd_upload_file(self, payload: Dict) -> CommandResponse:
        """CMD UPLOAD FILE: Upload configuration file."""
        response = CommandResponse(
            cmd_name="CMD_UPLOAD_FILE",
            status=CommandStatus.ACK_RECEIVED,
            timestamp=self.simulation_time,
        )
        
        self.config_buffer = bytearray(CONFIG_FILE_SIZE_KB * 1024)
        self.config_file_checksum = hashlib.md5(self.config_buffer).hexdigest()[:8]
        
        response.payload = {
            "filename": "comms_config_v2.cfg",
            "size_kb": CONFIG_FILE_SIZE_KB,
            "checksum": self.config_file_checksum,
            "upload_started": True,
        }
        return response
    
    def _cmd_cmd_apply_comms_config(self, payload: Dict) -> CommandResponse:
        """CMD APPLY COMMS CONFIG: Apply new config and restart COMMS."""
        response = CommandResponse(
            cmd_name="CMD_APPLY_COMMS_CONFIG",
            status=CommandStatus.ACK_RECEIVED,
            timestamp=self.simulation_time,
        )
        
        # Check for anomaly-injected restart failure
        if self.anomaly.get("comms_restart_failure"):
            response.status = CommandStatus.NACK_RECEIVED
            response.error_msg = "COMMS restart failed"
            return response
        
        # Initiate restart sequence
        self.comms_restart_active = True
        self.comms_restart_start_time = self.simulation_time
        self.state["tx_enabled"] = False
        self.state["rx_enabled"] = False
        
        response.payload = {
            "action": "COMMS restart initiated",
            "expected_tm_down_time": "~30 seconds",
        }
        return response
    
    def _cmd_cmd_contact_close(self, payload: Dict) -> CommandResponse:
        """CMD CONTACT CLOSE: Close contact and enter inter-pass mode."""
        response = CommandResponse(
            cmd_name="CMD_CONTACT_CLOSE",
            status=CommandStatus.ACK_RECEIVED,
            timestamp=self.simulation_time,
        )
        response.payload = {
            "action": "Contact closed",
            "new_mode": "INTER_PASS",
        }
        return response
    
    # ========================================================================
    # TM LOCK MANAGEMENT
    # ========================================================================
    
    def establish_tm_lock(self) -> bool:
        """
        Attempt to establish TM lock.
        Can fail if anomaly injected or conditions not met.
        Returns True if lock established.
        """
        if self.anomaly.get("tm_lock_failure"):
            self.tm_lock_active = False
            return False
        
        self.tm_lock_active = True
        self.tm_lock_time = self.simulation_time
        return True
    
    def is_tm_locked(self) -> bool:
        """Check if TM lock is currently active."""
        return self.tm_lock_active
    
    def lose_tm_lock(self):
        """Lose TM lock (e.g., during COMMS restart)."""
        self.tm_lock_active = False
    
    # ========================================================================
    # STATE QUERIES
    # ========================================================================
    
    def get_battery_soc(self) -> float:
        """Get battery state of charge."""
        return self.state["battery_soc"]
    
    def get_obc_temperature(self) -> float:
        """Get OBC temperature."""
        return self.state["obc_temperature"]
    
    def get_storage_utilization(self) -> float:
        """Get OBC storage utilization."""
        return self.state["storage_utilization"]
    
    def get_rssi(self) -> float:
        """Get RSSI."""
        return self.state["rssi"]
    
    def get_satellite_mode(self) -> str:
        """Get current satellite mode."""
        return self.state["satellite_mode"]
    
    def get_config_version(self) -> str:
        """Get current COMMS config version."""
        return self.state["config_version"]
    
    def is_tx_enabled(self) -> bool:
        """Check if TX is enabled."""
        return self.state["tx_enabled"]
    
    def set_config_version(self, version: str):
        """Set new config version after successful change."""
        self.state["config_version"] = version
    
    def get_downlink_progress(self) -> float:
        """Get progress of current downlink (0.0 to 1.0)."""
        return self.downlink_progress
    
    def is_downlink_active(self) -> bool:
        """Check if file downlink is in progress."""
        return self.current_downlink is not None and self.downlink_progress < 1.0
    
    def complete_downlink(self) -> Dict[str, Any]:
        """Finalize current downlink and return transfer info."""
        result = {
            "downlink_type": self.current_downlink,
            "progress": self.downlink_progress,
        }
        self.current_downlink = None
        self.downlink_progress = 0.0
        return result
