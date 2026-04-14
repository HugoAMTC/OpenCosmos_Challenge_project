"""
Flight Operations Configuration Module
Rev 1 — Flight Operational Contact Plan & Procedure

All mission constants, operational limits, satellite state, and anomaly presets.

Autor: Hugo Carvalho
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any

# ============================================================================
# TIMING CONSTANTS (all times in seconds relative to contact phase)
# ============================================================================

class Phase(Enum):
    """Contact procedure phases."""
    PHASE_0 = 0  # Pre-contact Preparation
    PHASE_1 = 1  # Contact Acquisition
    PHASE_2 = 2  # Housekeeping & Sat Health Check
    PHASE_3 = 3  # Platform Data Download
    PHASE_4 = 4  # Payload Data Download
    PHASE_5 = 5  # COMMS Configuration Change
    PHASE_6 = 6  # Pre-LOS Close-out
    PHASE_7 = 7  # Post-contact Actions


# Phase timing boundaries (relative to T+00:00 = AOS)
PHASE_TIMING = {
    Phase.PHASE_0: {"start": -1800, "end": -1},      # T-30:00 to T-00:01
    Phase.PHASE_1: {"start": 0, "end": 60},          # T+00:00 to T+01:00
    Phase.PHASE_2: {"start": 75, "end": 150},        # T+01:15 to T+02:30
    Phase.PHASE_3: {"start": 150, "end": 190},       # T+02:30 to T+03:10
    Phase.PHASE_4: {"start": 190, "end": 415},       # T+03:10 to T+06:55
    Phase.PHASE_5: {"start": 420, "end": 470},       # T+07:00 to T+07:50
    Phase.PHASE_6: {"start": 510, "end": 570},       # T+08:30 to T+09:30
}

# Step timing offsets (relative to AOS, T+00:00)
STEP_TIMING = {
    "0.1": -1800, "0.2": -1500, "0.3": -1200, "0.4": -900,
    "0.5": -600, "0.6": -300, "0.7": -120,
    "1.1": 0, "1.2": 15, "1.3": 45, "1.4": 60, "1.5": 70,
    "2.1": 75, "2.2": 90, "2.3": 105, "2.4": 120, "2.5": 130, "2.6": 140,
    "3.1": 150, "3.2": 177, "3.3": 180, "3.4": 185,
    "4.1": 190, "4.2": 200, "4.3": 240, "4.4": 413, "4.5": 415,
    "5.1": 420, "5.2": 422, "5.3": 425, "5.4": 428, "5.5": 430,
    "5.6": 460, "5.7": 465, "5.8": 470,
    "6.1": 510, "6.2": 525, "6.3": 540, "6.4": 555, "6.5": 570,
}

# ============================================================================
# SATELLITE COMMS & LINK PARAMETERS
# ============================================================================

# Satellite and ground station identifiers
SATELLITE_NAME = "Mantis-2"
GroundStation_NAME = "Svalbard, Norway"

# Communication parameters
UPLINK_BITRATE_KBPS = 50        # 50 kbps
DOWNLINK_BITRATE_KBPS = 50      # 50 kbps
TM_LOCK_TIMEOUT_S = 30            # seconds
CMD_ACK_TIMEOUT_S = 5             # seconds (default for most commands)
HK_PACKET_RX_TIME = 15          # seconds to receive HK packet
LINK_TEST_ACK_TIMEOUT = 5       # seconds

HK_LOG_SIZE_BYTES = 150000    # Average size of one HK log entry

# Platform data download params
PLATFORM_LOG_SIZE_BYTES = 500000  # 0.5 MB platform housekeeping log size
PLATFORM_LOG_TX_TIME = 30       # seconds (T+02:30 to T+03:00)

# Payload data download params
PAYLOAD_DATA_SIZE_BYTES = 1200000  # 1.2 MB payload data size
PAYLOAD_DOWNLOAD_START_TIME = 200     # T+03:20
PAYLOAD_DOWNLOAD_END_TIME = 413       # T+06:53 (expected)
PAYLOAD_DOWNLOAD_DURATION = PAYLOAD_DOWNLOAD_END_TIME - PAYLOAD_DOWNLOAD_START_TIME

# Config file upload params
CONFIG_FILE_SIZE_KB = 10
CONFIG_FILE_UPLOAD_TIME = 3     # seconds to upload

# ============================================================================
# OPERATIONAL LIMITS (Yellow and Red thresholds)
# ============================================================================

@dataclass
class OperationalLimits:
    """Subsystem operational limits."""
    # EPS
    battery_soc_yellow_min: float = 45.0        # % (Yellow limit, minimum safe)
    battery_soc_red_min: float = 30.0           # % (Red limit, critical)
    
    # Thermal
    obc_temp_yellow_max: float = 55.0           # °C
    obc_temp_red_max: float = 65.0              # °C
    battery_temp_yellow_max: float = 45.0       # °C
    battery_temp_red_max: float = 55.0          # °C
    payload_temp_yellow_max: float = 50.0       # °C
    payload_temp_red_max: float = 60.0          # °C
    transceiver_temp_yellow_max: float = 60.0   # °C
    transceiver_temp_red_max: float = 70.0      # °C
    
    # OBC Storage
    obc_storage_yellow_max: float = 85.0        # % (Yellow limit)
    obc_storage_red_max: float = 95.0           # % (Red limit)
    obc_storage_target_after_dl: float = 60.0   # % (Target after Phase 4)
    
    # COMMS
    rssi_nominal_range: tuple = (-95, -50)      # dBm (nominal range)
    rssi_yellow_threshold: float = -90.0        # dBm (acceptable for comms config change)
    frame_error_rate_yellow: float = 1.0        # % (Yellow limit)
    
    # Mid-transfer checks
    mid_transfer_temp_threshold: float = 58.0   # °C (OBC temp during payload DL)


OPERATIONAL_LIMITS = OperationalLimits()

# ============================================================================
# INITIAL SATELLITE STATE
# ============================================================================

INITIAL_SATELLITE_STATE = {
    # EPS
    "battery_soc": 72.0,                        # % (Battery State of Charge)
    "bus_voltage": 3.3,                         # V
    "solar_array_current": 2.5,                 # A
    
    # Thermal
    "obc_temperature": 28.0,                    # °C
    "battery_temperature": 25.0,                # °C
    "payload_temperature": 22.0,                # °C
    "transceiver_temperature": 30.0,            # °C
    
    # OBC
    "uptime_counter": 145600,                   # seconds (~40 hours)
    "software_mode": "NOMINAL",
    "ram_usage": 45.0,                          # %
    "storage_utilization": 62.0,                # %
    "error_log_entries": 2,
    
    # COMMS
    "tx_enabled": False,                        # TX OFF at start
    "rx_enabled": True,
    "config_version": "v1",
    "rssi": -92.0,                              # dBm
    "uplink_frame_error_rate": 0.1,             # %
    "downlink_frame_error_rate": 0.05,          # %
    "active_antenna": "primary",
    
    # ADCS
    "attitude_mode": "NOMINAL",
    "pointing_error": 0.5,                      # degrees
    "wheel_rpm": {"x": 500, "y": 480, "z": 510},
    "magnetorquer_status": "NOMINAL",
    
    # Mode
    "satellite_mode": "NOMINAL OPS",
}

# ============================================================================
# ANOMALY INJECTION PRESETS
# ============================================================================

ANOMALY_PRESETS = {
    "none": {},
    
    "low_battery": {
        "battery_soc": 38.0,  # Below Yellow limit (45%)
        "trigger_phase": Phase.PHASE_2,
    },
    
    "high_obc_temp": {
        "obc_temperature": 58.0,  # Above Yellow, below Red
        "trigger_phase": Phase.PHASE_4,
    },
    
    "high_storage": {
        "storage_utilization": 88.0,  # Above Yellow limit (85%)
        "trigger_phase": Phase.PHASE_2,
    },
    
    "tm_lock_fail": {
        "tm_lock_failure": True,
        "trigger_phase": Phase.PHASE_1,
    },
    
    "comms_restart_fail": {
        "comms_restart_failure": True,
        "trigger_phase": Phase.PHASE_5,
    },
    
    "safe_mode_entry": {
        "satellite_mode": "SAFE",
        "trigger_phase": Phase.PHASE_1,
    },
    
    "payload_download_thermal": {
        "obc_temperature": 59.0,  # Will trigger mid-transfer pause
        "trigger_phase": Phase.PHASE_4,
    },
}

# ============================================================================
# COMMAND DEFINITIONS
# ============================================================================

COMMANDS = {
    "CMD_TX_ON": {"ack_timeout": 5, "expected_effect": "tx_enabled=True"},
    "CMD_TX_OFF": {"ack_timeout": 5, "expected_effect": "tx_enabled=False"},
    "CMD_HK_FULL_REPORT": {"ack_timeout": 15, "expected_effect": "hk_packet_downlink"},
    "CMD_LINK_TEST": {"ack_timeout": 5, "expected_effect": "link_test_ack"},
    "CMD_DOWNLINK_HK_LOG": {"ack_timeout": 5, "expected_effect": "platform_log_downlink"},
    "CMD_DELETE_HK_LOG": {"ack_timeout": 5, "expected_effect": "hk_log_deleted"},
    "CMD_PAYLOAD_STORAGE_QUERY": {"ack_timeout": 5, "expected_effect": "payload_manifest"},
    "CMD_DOWNLINK_PAYLOAD": {"ack_timeout": 5, "expected_effect": "payload_downlink"},
    "CMD_DELETE_PAYLOAD_FILES": {"ack_timeout": 5, "expected_effect": "payload_deleted"},
    "CMD_UPLOAD_FILE": {"ack_timeout": 5, "expected_effect": "file_uploaded"},
    "CMD_APPLY_COMMS_CONFIG": {"ack_timeout": 5, "expected_effect": "comms_config_applied"},
    "CMD_CONTACT_CLOSE": {"ack_timeout": 5, "expected_effect": "contact_closed"},
}

# ============================================================================
# SIMULATION PARAMETERS
# ============================================================================

SIMULATION_CONFIG = {
    "timestep": 1.0,                # Simulation timestep in seconds
    "real_time_factor": 1.0,        # Speedup factor (1.0 = real-time)
    "physics_enabled": True,         # Enable thermal/power physics
    "log_level": "INFO",            # Logging level: DEBUG, INFO, WARNING
}

# ============================================================================
# PHYSICS PARAMETERS
# ============================================================================

PHYSICS = {
    # Power parameters
    "solar_generation_rate": 3.5,           # W (when in sunlight)
    "payload_download_power": 15.0,         # W (during payload download)
    "obc_idle_power": 8.0,                  # W (idle)
    "comms_tx_power": 25.0,                 # W (during TX)
    "battery_discharge_rate_base": 10.0,    # W (baseline when not in sunlight)
    
    # Thermal parameters
    "obc_idle_temp_rise": 0.1,              # °C/s (passive)
    "obc_active_temp_rise": 0.3,            # °C/s (during high load)
    "obc_passive_cooling_rate": 0.05,       # °C/s (natural dissipation)
    "ambient_temp": 20.0,                   # °C (space proxy)
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_time_label(time_offset: float) -> str:
    """Convert time offset to readable label (T±HH:MM format)."""
    if time_offset < 0:
        sign = "-"
        total = int(abs(time_offset))
    else:
        sign = "+" if time_offset > 0 else ""
        total = int(time_offset)
    
    hours = total // 3600
    minutes = (total % 3600) // 60
    return f"T{sign}{hours:02d}:{minutes:02d}"


def get_operational_limit(param_name: str, limit_type: str = None) -> Any:
    """
    Retrieve operational limit for a parameter.
    limit_type: 'yellow' or 'red' or None for default/range
    """
    limits_dict = {
        "battery_soc": {
            "yellow_min": OPERATIONAL_LIMITS.battery_soc_yellow_min,
            "red_min": OPERATIONAL_LIMITS.battery_soc_red_min,
        },
        "obc_temperature": {
            "yellow_max": OPERATIONAL_LIMITS.obc_temp_yellow_max,
            "red_max": OPERATIONAL_LIMITS.obc_temp_red_max,
        },
        "obc_storage": {
            "yellow_max": OPERATIONAL_LIMITS.obc_storage_yellow_max,
            "red_max": OPERATIONAL_LIMITS.obc_storage_red_max,
        },
        "rssi": {
            "nominal_range": OPERATIONAL_LIMITS.rssi_nominal_range,
            "yellow_threshold": OPERATIONAL_LIMITS.rssi_yellow_threshold,
        },
    }
    
    if param_name in limits_dict:
        if limit_type and limit_type in limits_dict[param_name]:
            return limits_dict[param_name][limit_type]
        return limits_dict[param_name]
    return None
