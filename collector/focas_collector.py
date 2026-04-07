import ctypes
import ctypes.wintypes
import os
import sys
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DLL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Fwlib64.dll")

try:
    fwlib = ctypes.WinDLL(DLL_PATH)
    logging.info(f"FOCAS2 DLL loaded from: {DLL_PATH}")
except Exception as e:
    raise RuntimeError(f"Failed to load FOCAS2 DLL from {DLL_PATH}: {e}")

EW_OK   = 0
TIMEOUT = 2

class ODBST(ctypes.Structure):
    _fields_ = [
        ("dummy",     ctypes.c_short),
        ("tmmode",    ctypes.c_short),
        ("aut",       ctypes.c_short),
        ("run",       ctypes.c_short),
        ("motion",    ctypes.c_short),
        ("mstb",      ctypes.c_short),
        ("emergency", ctypes.c_short),
        ("alarm",     ctypes.c_short),
        ("edit",      ctypes.c_short),
    ]

class ODBPRO(ctypes.Structure):
    _fields_ = [
        ("dummy",  ctypes.c_short),
        ("dummy2", ctypes.c_short),
        ("data",   ctypes.c_long),
        ("mdata",  ctypes.c_long),
    ]

class ODBACT(ctypes.Structure):
    _fields_ = [
        ("dummy", ctypes.c_short),
        ("data",  ctypes.c_long),
    ]

class ODBACT2(ctypes.Structure):
    _fields_ = [
        ("dummy", ctypes.c_short),
        ("data",  ctypes.c_long),
    ]

class ALMMSG(ctypes.Structure):
    _fields_ = [
        ("alm_no",  ctypes.c_long),
        ("type",    ctypes.c_short),
        ("axis",    ctypes.c_short),
        ("msg_len", ctypes.c_short),
        ("alm_msg", ctypes.c_char * 32),
    ]

class ODBALMMSG(ctypes.Structure):
    _fields_ = [
        ("data_num", ctypes.c_short),
        ("alm",      ALMMSG * 10),
    ]

class IODBPSD(ctypes.Structure):
    _fields_ = [
        ("datano", ctypes.c_short),
        ("type",   ctypes.c_short),
        ("data",   ctypes.c_long),
    ]

class IODBSGNL(ctypes.Structure):
    """Operator panel signals (0i-style layout from fwlib64.h)."""

    _pack_ = 4
    _fields_ = [
        ("datano", ctypes.c_short),
        ("type", ctypes.c_short),
        ("mode", ctypes.c_short),
        ("hndl_ax", ctypes.c_short),
        ("hndl_mv", ctypes.c_short),
        ("rpd_ovrd", ctypes.c_short),
        ("jog_ovrd", ctypes.c_short),
        ("feed_ovrd", ctypes.c_short),
        ("spdl_ovrd", ctypes.c_short),
        ("blck_del", ctypes.c_short),
        ("sngl_blck", ctypes.c_short),
        ("machn_lock", ctypes.c_short),
        ("dry_run", ctypes.c_short),
        ("mem_prtct", ctypes.c_short),
        ("feed_hold", ctypes.c_short),
    ]

# Function signatures
fwlib.cnc_allclibhndl3.argtypes = [ctypes.c_char_p, ctypes.c_ushort, ctypes.c_long, ctypes.POINTER(ctypes.c_ushort)]
fwlib.cnc_allclibhndl3.restype  = ctypes.c_short
fwlib.cnc_freelibhndl.argtypes  = [ctypes.c_ushort]
fwlib.cnc_freelibhndl.restype   = ctypes.c_short
fwlib.cnc_statinfo.argtypes     = [ctypes.c_ushort, ctypes.POINTER(ODBST)]
fwlib.cnc_statinfo.restype      = ctypes.c_short
fwlib.cnc_rdprgnum.argtypes     = [ctypes.c_ushort, ctypes.POINTER(ODBPRO)]
fwlib.cnc_rdprgnum.restype      = ctypes.c_short
fwlib.cnc_acts.argtypes         = [ctypes.c_ushort, ctypes.POINTER(ODBACT)]
fwlib.cnc_acts.restype          = ctypes.c_short
fwlib.cnc_actf.argtypes         = [ctypes.c_ushort, ctypes.POINTER(ODBACT2)]
fwlib.cnc_actf.restype          = ctypes.c_short
fwlib.cnc_rdparam.argtypes      = [ctypes.c_ushort, ctypes.c_short, ctypes.c_short, ctypes.c_short, ctypes.c_void_p]
fwlib.cnc_rdparam.restype       = ctypes.c_short
fwlib.cnc_rdalmmsg.argtypes     = [ctypes.c_ushort, ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.POINTER(ODBALMMSG)]
fwlib.cnc_rdalmmsg.restype      = ctypes.c_short
fwlib.cnc_rdprogline2.argtypes  = [ctypes.c_ushort, ctypes.c_long, ctypes.c_ulong, ctypes.c_char_p, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong)]
fwlib.cnc_rdprogline2.restype   = ctypes.c_short
fwlib.cnc_rdexecprog.argtypes   = [ctypes.c_ushort, ctypes.POINTER(ctypes.c_ushort), ctypes.POINTER(ctypes.c_short), ctypes.c_char_p]
fwlib.cnc_rdexecprog.restype    = ctypes.c_short
fwlib.cnc_rdopnlsgnl.argtypes   = [ctypes.c_ushort, ctypes.c_short, ctypes.POINTER(IODBSGNL)]
fwlib.cnc_rdopnlsgnl.restype    = ctypes.c_short

# Read feed (bit 5) and spindle (bit 6) override fields; some models leave spdl_ovrd unused.
_SIGNAL_FEED_OVRD = 0x20
_SIGNAL_SPDL_OVRD = 0x40

CNC_MODES = {
    0: "MDI",
    1: "MEM",
    2: "RMT",
    3: "EDIT",
    4: "HANDLE",
    5: "JOG",
    6: "INC",
    7: "TEACH",
    8: "MDI_JOG",
    9: "REF_HOME",
    10: "OTHER",
}

def decode_status(stat: ODBST, spindle_speed: float, feed_rate: float) -> str:
    if stat.emergency == 1:
        return "emergency_stop"
    if stat.alarm == 1:
        return "alarm"
    if spindle_speed != 0 or feed_rate != 0:
        return "running"
    return "idle"

def get_focas_machine_data(machine: dict) -> dict:
    ip         = machine["ip"]
    port       = machine["port"]
    name       = machine["name"]
    machine_id = machine["id"]

    handle = ctypes.c_ushort(0)

    default = {
        "machine_id":       machine_id,
        "machine_name":     name,
        "status":           "offline",
        "mode":             None,
        "program_number":   None,
        "program_comment":  "",
        "part_count":       None,
        "feed_rate":        0.0,
        "spindle_speed":    0.0,
        "feed_override_pct":   None,
        "spindle_override_pct": None,
        "alarm":            None,
    }

    # --- CONNECT ---
    ret = fwlib.cnc_allclibhndl3(
        ip.encode("utf-8"),
        ctypes.c_ushort(port),
        ctypes.c_long(TIMEOUT),
        ctypes.byref(handle)
    )

    if ret != EW_OK:
        logging.warning(f"{name}: Connection failed (code {ret})")
        default["_connection_failed"] = True
        return default

    logging.info(f"{name}: Connected (handle {handle.value})")

    try:
        result = dict(default)

        # --- MACHINE STATUS (raw data) ---
        stat = ODBST()
        ret = fwlib.cnc_statinfo(handle, ctypes.byref(stat))
        if ret == EW_OK:
            result["mode"] = CNC_MODES.get(stat.aut, f"UNKNOWN({stat.aut})")
            logging.info(
                f"{name}: STATUS raw -> "
                f"aut={stat.aut}({result['mode']}) | "
                f"run={stat.run} | "
                f"motion={stat.motion} | "
                f"emergency={stat.emergency} | "
                f"alarm={stat.alarm} | "
                f"edit={stat.edit}"
            )
        else:
            logging.warning(f"{name}: cnc_statinfo failed (code {ret})")

        # --- SPINDLE SPEED (before status decode) ---
        acts = ODBACT()
        ret = fwlib.cnc_acts(handle, ctypes.byref(acts))
        if ret == EW_OK:
            result["spindle_speed"] = float(acts.data)
            logging.info(f"{name}: SPINDLE SPEED = {acts.data} RPM")
        else:
            logging.warning(f"{name}: cnc_acts failed (code {ret})")

        # --- FEED RATE (before status decode) ---
        actf = ODBACT2()
        ret = fwlib.cnc_actf(handle, ctypes.byref(actf))
        if ret == EW_OK:
            result["feed_rate"] = float(actf.data)
            logging.info(f"{name}: FEED RATE = {actf.data} mm/min")
        else:
            logging.warning(f"{name}: cnc_actf failed (code {ret})")

        # --- FEED / SPINDLE OVERRIDE (operator panel %) ---
        sgnl = IODBSGNL()
        ret_sg = fwlib.cnc_rdopnlsgnl(
            handle,
            ctypes.c_short(_SIGNAL_FEED_OVRD | _SIGNAL_SPDL_OVRD),
            ctypes.byref(sgnl),
        )
        if ret_sg == EW_OK:
            result["feed_override_pct"] = int(sgnl.feed_ovrd)
            spdl = int(sgnl.spdl_ovrd)
            # On many 0i builds spdl_ovrd is unused (always 0); then override alerting uses feed only.
            result["spindle_override_pct"] = spdl if spdl > 0 else None
            logging.info(
                f"{name}: OVR feed={result['feed_override_pct']}% "
                f"spindle={result['spindle_override_pct']}%"
            )
        else:
            logging.warning(f"{name}: cnc_rdopnlsgnl failed (code {ret_sg})")

        # --- DECODE STATUS based on spindle/feed ---
        result["status"] = decode_status(stat, result["spindle_speed"], result["feed_rate"])
        logging.info(f"{name}: STATUS decoded = {result['status']}")

        # --- PROGRAM NUMBER ---
        prgnum = ODBPRO()
        ret = fwlib.cnc_rdprgnum(handle, ctypes.byref(prgnum))
        if ret == EW_OK:
            raw       = prgnum.data
            raw_main  = prgnum.mdata
            program_no = raw >> 16  # Upper 16 bits = program number
            logging.info(
                f"{name}: PROGRAM raw data={raw} | "
                f"mdata={raw_main} | "
                f"data>>16={program_no} | "
                f"data&0xFFFF={raw & 0xFFFF}"
            )
            result["program_number"] = program_no
        else:
            logging.warning(f"{name}: cnc_rdprgnum failed (code {ret})")

        # --- PROGRAM COMMENT ---
        result["program_comment"] = ""
        if result["program_number"]:
            import re
            length = ctypes.c_ushort(1024)
            blknum = ctypes.c_short()
            exec_buf = ctypes.create_string_buffer(1024)
            ret = fwlib.cnc_rdexecprog(handle, ctypes.byref(length), ctypes.byref(blknum), exec_buf)
            if ret == EW_OK and length.value > 0:
                exec_data = exec_buf.value.decode("utf-8", errors="ignore").strip()
                match = re.search(r'\(([^)]+)\)', exec_data)
                if match:
                    result["program_comment"] = match.group(1).strip()
                    logging.info(f"{name}: PROGRAM COMMENT = {result['program_comment']}")
                else:
                    logging.debug(f"{name}: No comment found in program header")
            else:
                logging.warning(f"{name}: cnc_rdexecprog failed (code {ret})")

        # --- PART COUNT (parameter 6711) ---
        param = IODBPSD()
        ret = fwlib.cnc_rdparam(handle, 6711, 0, ctypes.sizeof(param), ctypes.byref(param))
        if ret == EW_OK:
            result["part_count"] = int(param.data)
            logging.info(f"{name}: PART COUNT = {param.data}")
        else:
            logging.warning(f"{name}: cnc_rdparam (part count param 6711) failed (code {ret})")

        # --- ALARMS ---
        if result["status"] == "alarm":
            num = ctypes.c_short(10)
            almmsg = ODBALMMSG()
            ret = fwlib.cnc_rdalmmsg(handle, ctypes.c_short(-1), ctypes.byref(num), ctypes.byref(almmsg))
            if ret == EW_OK and almmsg.data_num > 0:
                first = almmsg.alm[0]
                alarm_msg = first.alm_msg.decode("utf-8", errors="ignore").strip()
                result["alarm"] = {
                    "code":    str(first.alm_no),
                    "message": alarm_msg,
                }
                logging.info(f"{name}: ALARM [{first.alm_no}] {alarm_msg}")
            else:
                result["alarm"] = {
                    "code":    "UNKNOWN",
                    "message": "Alarm active - details unavailable",
                }
                logging.warning(f"{name}: cnc_rdalmmsg failed (code {ret})")

        # --- SUMMARY ---
        logging.info(
            f"{name}: SUMMARY -> "
            f"status={result['status']} | "
            f"mode={result['mode']} | "
            f"program={result['program_number']} | "
            f"comment={result['program_comment'][:30]} | "
            f"parts={result['part_count']} | "
            f"spindle={result['spindle_speed']} RPM | "
            f"feed={result['feed_rate']} mm/min"
        )

        return result

    except Exception as e:
        logging.error(f"{name}: Unexpected error: {e}")
        return default

    finally:
        fwlib.cnc_freelibhndl(handle)
        logging.info(f"{name}: Disconnected")
