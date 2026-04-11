"""Real-time serial data logger with live force-time plot.

Reads Modbus RTU data from serial port, writes to Excel, and plots force in real-time.
Single script, no conflicts.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

try:
    import serial  # type: ignore
except ImportError:
    serial = None

try:
    from openpyxl import Workbook, load_workbook  # type: ignore
    from openpyxl.utils import get_column_letter  # type: ignore
except ImportError:
    Workbook = None
    load_workbook = None
    get_column_letter = None

try:
    import numpy as np  # type: ignore
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from runtime_paths import get_app_root, get_config_runtime_base


TYPE_REGISTER_COUNT = {
    "uint16": 1, "int16": 1, "uint32": 2, "int32": 2, "float32": 2,
}

MODBUS_EXCEPTION_CODES = {
    1: "Illegal function", 2: "Illegal data address", 3: "Illegal data value",
    4: "Slave device failure", 5: "Acknowledge", 6: "Slave device busy",
    8: "Memory parity error", 10: "Gateway path unavailable",
    11: "Gateway target failed to respond",
}


@dataclass(frozen=True)
class FieldConfig:
    name: str
    function_code: int
    address: int
    data_type: str
    scale: float = 1.0
    offset: float = 0.0
    precision: Optional[int] = None
    byte_order: str = "big"
    word_order: str = "big"

    @property
    def register_count(self) -> int:
        return TYPE_REGISTER_COUNT[self.data_type]


@dataclass(frozen=True)
class AppConfig:
    port: str
    baudrate: int
    bytesize: int
    parity: str
    stopbits: float
    timeout: float
    slave_id: int
    poll_interval_seconds: float
    inter_request_delay_seconds: float
    retries: int
    workbook_path: Path
    sheet_name: str
    timestamp_format: str
    autosave_every_rows: int
    autosave_interval_seconds: float
    fields: List[FieldConfig]


def load_config(config_path: Path) -> AppConfig:
    config_path = config_path.resolve()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    project_root = get_config_runtime_base(config_path)

    workbook_path_str = payload.get("workbook_path", "logs/485_data_{start_time}.xlsx")
    workbook_path = Path(workbook_path_str.replace("{start_time}", datetime.now().strftime("%Y%m%d_%H%M%S")))
    if not workbook_path.is_absolute():
        workbook_path = project_root / workbook_path

    fields = [FieldConfig(
        name=str(f["name"]), function_code=int(f["function_code"]),
        address=int(f["address"]), data_type=str(f["data_type"]).lower(),
        scale=float(f.get("scale", 1.0)), offset=float(f.get("offset", 0.0)),
        precision=int(f["precision"]) if f.get("precision") is not None else None,
        byte_order=str(f.get("byte_order", "big")).lower(),
        word_order=str(f.get("word_order", "big")).lower(),
    ) for f in payload.get("fields", [])]

    return AppConfig(
        port=str(payload["port"]), baudrate=int(payload.get("baudrate", 115200)),
        bytesize=int(payload.get("bytesize", 8)), parity=str(payload.get("parity", "N")).upper(),
        stopbits=float(payload.get("stopbits", 1)), timeout=float(payload.get("timeout", 1.0)),
        slave_id=int(payload.get("slave_id", 1)),
        poll_interval_seconds=float(payload.get("poll_interval_seconds", 0.1)),
        inter_request_delay_seconds=float(payload.get("inter_request_delay_seconds", 0.0)),
        retries=int(payload.get("retries", 1)), workbook_path=workbook_path,
        sheet_name=str(payload.get("sheet_name", "data")),
        timestamp_format=str(payload.get("timestamp_format", "%Y-%m-%d %H:%M:%S.%f")),
        autosave_every_rows=int(payload.get("autosave_every_rows", 10)),
        autosave_interval_seconds=float(payload.get("autosave_interval_seconds", 2.0)),
        fields=fields,
    )


def modbus_crc(frame: bytes) -> int:
    crc = 0xFFFF
    for value in frame:
        crc ^= value
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def append_crc(frame: bytes) -> bytes:
    crc = modbus_crc(frame)
    return frame + bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def build_request(slave_id: int, function_code: int, address: int, quantity: int) -> bytes:
    return append_crc(struct.pack(">BBHH", slave_id, function_code, address, quantity))


def read_registers(client, slave_id: int, function_code: int, address: int, quantity: int) -> Tuple[List[int], bytes]:
    request = build_request(slave_id, function_code, address, quantity)
    client.reset_input_buffer()
    client.write(request)
    client.flush()
    expected_length = 5 + quantity * 2
    response = client.read(expected_length)
    if len(response) < 5:
        raise TimeoutError("Incomplete response for address {0}".format(address))
    expected_crc = modbus_crc(response[:-2])
    actual_crc = response[-2] | (response[-1] << 8)
    if expected_crc != actual_crc:
        raise IOError("CRC failed")
    if response[1] == (function_code | 0x80):
        raise IOError("Modbus exception 0x{0:02X}".format(response[2]))
    data_bytes = response[3:-2]
    registers = [int.from_bytes(data_bytes[i:i+2], byteorder="big") for i in range(0, len(data_bytes), 2)]
    return registers, response


def read_with_retries(client, config: AppConfig, function_code: int, address: int, quantity: int) -> Tuple[List[int], bytes]:
    last_err = None
    for _ in range(config.retries + 1):
        try:
            return read_registers(client, config.slave_id, function_code, address, quantity)
        except Exception as e:
            last_err = e
            time.sleep(0.2)
    raise last_err  # type: ignore


def registers_to_bytes(registers: Sequence[int], byte_order: str, word_order: str) -> bytes:
    chunks = [v.to_bytes(2, byteorder="big", signed=False) for v in registers]
    if byte_order == "little":
        chunks = [c[::-1] for c in chunks]
    if word_order == "little":
        chunks = list(reversed(chunks))
    return b"".join(chunks)


def decode_value(field: FieldConfig, registers: Sequence[int]) -> Any:
    payload = registers_to_bytes(registers, field.byte_order, field.word_order)
    if field.data_type == "uint16":
        value = int.from_bytes(payload, byteorder="big", signed=False)
    elif field.data_type == "int16":
        value = int.from_bytes(payload, byteorder="big", signed=True)
    elif field.data_type == "uint32":
        value = int.from_bytes(payload, byteorder="big", signed=False)
    elif field.data_type == "int32":
        value = int.from_bytes(payload, byteorder="big", signed=True)
    elif field.data_type == "float32":
        value = struct.unpack(">f", payload)[0]
    else:
        value = int.from_bytes(payload, byteorder="big", signed=False)
    if field.scale != 1.0 or field.offset != 0.0:
        value = value * field.scale + field.offset
    if field.precision is not None:
        value = round(value, field.precision)
    return value


class ExcelLogger:
    def __init__(self, workbook_path: Path, sheet_name: str, field_names: Sequence[str],
                 autosave_every_rows: int, autosave_interval_seconds: float) -> None:
        self.workbook_path = workbook_path
        self.sheet_name = sheet_name
        self.autosave_every_rows = autosave_every_rows
        self.autosave_interval_seconds = autosave_interval_seconds
        self.pending_rows: List[List[Any]] = []
        self.expected_headers = ["timestamp", "unix_time", "port", "baudrate", "slave_id",
                                  "status", "error", "raw_frames"] + list(field_names)
        self.workbook_path.parent.mkdir(parents=True, exist_ok=True)
        self.headers = self._initialize_workbook()
        self.last_save_monotonic = time.monotonic()
        self.unsaved_rows = 0

    def _initialize_workbook(self) -> List[str]:
        assert Workbook is not None
        if self.workbook_path.exists():
            try:
                assert load_workbook is not None
                wb = load_workbook(self.workbook_path)
            except Exception:
                wb = Workbook()
        else:
            wb = Workbook()
        ws = wb.active
        if ws is None or ws.title != self.sheet_name:
            ws = wb.create_sheet(self.sheet_name)
        existing = [str(c.value) for c in ws[1] if c.value] if ws.max_row >= 1 else []
        headers = list(existing)
        for h in self.expected_headers:
            if h not in headers:
                ws.cell(row=1, column=len(headers) + 1, value=h)
                headers.append(h)
        self.headers = headers
        self._save(wb)
        wb.close()
        return headers

    def _save(self, wb) -> None:
        ws = wb.active
        if ws is not None:
            ws.freeze_panes = "A2"
            last_col = get_column_letter(len(self.headers)) if get_column_letter else "H"
            ws.auto_filter.ref = "A1:{0}{1}".format(last_col, max(ws.max_row, 1))
        tmp = self.workbook_path.with_name("{0}.tmp{1}".format(self.workbook_path.stem, self.workbook_path.suffix))
        try:
            wb.save(tmp)
            import os as _os
            _os.replace(tmp, self.workbook_path)
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise

    def append_row(self, row_data: Dict[str, Any]) -> None:
        ordered = [row_data.get(h, "") for h in self.headers]
        self.pending_rows.append(ordered)
        self.unsaved_rows += 1
        if self.unsaved_rows >= self.autosave_every_rows or \
           time.monotonic() - self.last_save_monotonic >= self.autosave_interval_seconds:
            self.flush()

    def flush(self) -> None:
        if not self.pending_rows:
            return
        assert load_workbook is not None
        try:
            wb = load_workbook(self.workbook_path)
            ws = wb[self.sheet_name] if self.sheet_name in wb.sheetnames else wb.active
            for row in self.pending_rows:
                ws.append(row)
            self._save(wb)
            wb.close()
            print("  [Saved {0} rows to {1}]".format(len(self.pending_rows), self.workbook_path.name))
        except Exception as e:
            print("  [Save error: {0}]".format(e))
        self.pending_rows.clear()
        self.unsaved_rows = 0
        self.last_save_monotonic = time.monotonic()

    def close(self) -> None:
        if self.pending_rows:
            self.flush()


class LivePlotter:
    COLORS = ["b", "r", "g", "m", "c", "y"]

    def __init__(self, channel_names: List[str], window_seconds: int = 60, smooth: bool = False, calc_window: int = 10, tare_seconds: float = 2.0) -> None:
        self.channel_names = channel_names
        self.window_seconds = window_seconds
        self.calc_window = calc_window
        self.smooth = smooth
        self.tare_seconds = tare_seconds
        self.offsets: Dict[str, float] = {name: 0.0 for name in channel_names}
        self.tare_done = False
        self.tare_start: Optional[datetime] = None
        self.tare_buffer: Dict[str, List[float]] = {name: [] for name in channel_names}
        self.all_times: List[datetime] = []
        self.all_values: Dict[str, List[float]] = {name: [] for name in channel_names}
        self.raw_lines: Dict[str, Any] = {}
        self.smooth_lines: Dict[str, Any] = {}
        self.wavg_lines: Dict[str, Any] = {}
        self.savg_lines: Dict[str, Any] = {}

        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        for i, name in enumerate(channel_names):
            color = self.COLORS[i % len(self.COLORS)]
            raw_line, = self.ax.plot([], [], color=color, linewidth=0.8, alpha=0.3, markersize=2)
            self.raw_lines[name] = raw_line
            smooth_line, = self.ax.plot([], [], color=color, linewidth=2.0, label=name)
            self.smooth_lines[name] = smooth_line
            wavg_line, = self.ax.plot([], [], color=color, linestyle="--", linewidth=1.5, label="W-Avg {0}".format(name))
            self.wavg_lines[name] = wavg_line
            savg_line, = self.ax.plot([], [], color=color, linestyle=":", linewidth=1.5, label="S-Avg {0}".format(name))
            self.savg_lines[name] = savg_line

        self.ax.set_title("Taring... ({0:.1f}s remaining)".format(tare_seconds))
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Force (g)")
        self.ax.grid(True, alpha=0.3)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        self.ax.legend(loc="upper right", fontsize=8)
        self.fig.autofmt_xdate()
        plt.ion()
        plt.show(block=False)

    def _tare(self, ts: datetime, values: Dict[str, float]) -> bool:
        if self.tare_start is None:
            self.tare_start = ts
        elapsed = (ts - self.tare_start).total_seconds()
        for name in self.channel_names:
            if name in values:
                self.tare_buffer[name].append(values[name])
        remaining = max(0.0, self.tare_seconds - elapsed)
        self.ax.set_title("Taring... ({0:.1f}s remaining)".format(remaining))
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        if elapsed >= self.tare_seconds:
            for name in self.channel_names:
                buf = self.tare_buffer.get(name, [])
                if buf:
                    self.offsets[name] = sum(buf) / len(buf)
            self.tare_done = True
            return True
        return False

    def add_point(self, ts: datetime, values: Dict[str, float]) -> None:
        if not self.tare_done:
            if self._tare(ts, values):
                pass
            return

        zeroed = {}
        for name in self.channel_names:
            if name in values:
                zeroed[name] = values[name] - self.offsets[name]

        self.all_times.append(ts)
        for name in self.channel_names:
            if name in zeroed:
                self.all_values[name].append(zeroed[name])
        cutoff = ts.timestamp() - self.window_seconds
        while self.all_times and self.all_times[0].timestamp() < cutoff:
            self.all_times.pop(0)
            for name in self.channel_names:
                if self.all_values[name]:
                    self.all_values[name].pop(0)
        self._update()

    def _calc_averages(self, name: str, now: datetime) -> Tuple[float, float, float]:
        cutoff = now.timestamp() - self.calc_window
        times = self.all_times
        vals = self.all_values.get(name, [])

        recent = [(t.timestamp(), v) for t, v in zip(times, vals) if t.timestamp() >= cutoff]
        if not recent:
            return 0.0, 0.0, 0.0

        now_ts = now.timestamp()
        weights = []
        values = []
        for t, v in recent:
            age = now_ts - t
            w = math.exp(-age / self.calc_window)
            weights.append(w)
            values.append(v)

        total_w = sum(weights)
        if total_w == 0:
            return 0.0, 0.0, 0.0

        weighted_avg = sum(w * v for w, v in zip(weights, values)) / total_w
        weighted_var = sum(w * (v - weighted_avg) ** 2 for w, v in zip(weights, values)) / total_w
        weighted_std = math.sqrt(weighted_var)

        simple_avg = sum(values) / len(values)

        return weighted_avg, simple_avg, weighted_std

    def _update(self) -> None:
        if not self.all_times:
            return

        status_parts = []
        now = self.all_times[-1]

        for name in self.channel_names:
            vals = self.all_values.get(name, [])
            if not vals:
                continue

            self.raw_lines[name].set_data(self.all_times, vals)

            if HAS_NUMPY and len(vals) > 3:
                win = max(3, len(vals) // 30)
                kernel = np.ones(win) / win
                padded = np.pad(vals, (win // 2, win // 2), mode="edge")
                smoothed = list(np.convolve(padded, kernel, mode="valid")[:len(vals)])
                self.smooth_lines[name].set_data(self.all_times, smoothed)
            else:
                self.smooth_lines[name].set_data(self.all_times, vals)

            w_avg, s_avg, w_std = self._calc_averages(name, now)

            w_avg_vals = [w_avg] * len(self.all_times)
            self.wavg_lines[name].set_data(self.all_times, w_avg_vals)

            s_avg_vals = [s_avg] * len(self.all_times)
            self.savg_lines[name].set_data(self.all_times, s_avg_vals)

            status_parts.append("{0}: {1:.2f} ±{2:.2f}".format(name, s_avg, w_std))

        self.ax.relim()
        self.ax.autoscale_view()
        self.ax.set_xlim([self.all_times[0], self.all_times[-1]])
        self.ax.set_title(" | ".join(status_parts))
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def close(self) -> None:
        plt.close(self.fig)


def poll_once(client, config: AppConfig, logger: ExcelLogger) -> Dict[str, Any]:
    timestamp = datetime.now()
    row_data: Dict[str, Any] = {
        "timestamp": timestamp.strftime(config.timestamp_format),
        "unix_time": round(time.time(), 3),
        "port": config.port, "baudrate": config.baudrate, "slave_id": config.slave_id,
    }
    raw_frames: Dict[str, str] = {}
    errors: List[str] = []

    # Group fields by function_code and address range
    sorted_fields = sorted(config.fields, key=lambda f: (f.function_code, f.address))
    groups: List[Tuple[int, int, int, List[FieldConfig]]] = []
    if sorted_fields:
        cur_fc = sorted_fields[0].function_code
        cur_start = sorted_fields[0].address
        cur_end = cur_start + sorted_fields[0].register_count
        cur_fields = [sorted_fields[0]]
        for f in sorted_fields[1:]:
            if f.function_code == cur_fc and f.address <= cur_end:
                cur_fields.append(f)
                cur_end = max(cur_end, f.address + f.register_count)
            else:
                groups.append((cur_fc, cur_start, cur_end - cur_start, cur_fields))
                cur_fc = f.function_code
                cur_start = f.address
                cur_end = cur_start + f.register_count
                cur_fields = [f]
        groups.append((cur_fc, cur_start, cur_end - cur_start, cur_fields))

    for fc, start_addr, qty, grp_fields in groups:
        try:
            registers, response = read_with_retries(client, config, fc, start_addr, qty)
            frame_hex = response.hex(" ").upper()
            for f in grp_fields:
                offset = f.address - start_addr
                field_regs = registers[offset:offset + f.register_count]
                row_data[f.name] = decode_value(f, field_regs)
                raw_frames[f.name] = frame_hex
        except Exception as exc:
            for f in grp_fields:
                row_data[f.name] = ""
                raw_frames[f.name] = ""
                errors.append("{0}: {1}".format(f.name, exc))
        if config.inter_request_delay_seconds > 0:
            time.sleep(config.inter_request_delay_seconds)

    row_data["status"] = "ok" if not errors else "partial_error"
    row_data["error"] = "; ".join(errors)
    row_data["raw_frames"] = json.dumps(raw_frames, ensure_ascii=False)
    logger.append_row(row_data)
    return row_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serial data logger with live force-time plot.")
    parser.add_argument("--config", default="config/logger_config.json", help="Config file path.")
    parser.add_argument("--port", help="Override serial port from config, for example COM4.")
    parser.add_argument("--plot-window", type=int, default=60, help="Plot time window in seconds.")
    parser.add_argument("--smooth", action="store_true", help="Apply smoothing to plot.")
    parser.add_argument("--once", action="store_true", help="Read one sample and exit.")
    return parser


def resolve_config_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve()
    return (get_app_root() / path).resolve()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config_path = resolve_config_path(args.config)
    config = load_config(config_path)
    if args.port:
        config = replace(config, port=str(args.port).strip())

    print("Connecting to {0}...".format(config.port))
    print("Saving to: {0}".format(config.workbook_path))
    parity_map = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}
    stopbits_map = {1.0: serial.STOPBITS_ONE, 1.5: serial.STOPBITS_ONE_POINT_FIVE, 2.0: serial.STOPBITS_TWO}
    client = serial.Serial(
        port=config.port, baudrate=config.baudrate, bytesize=config.bytesize,
        parity=parity_map[config.parity], stopbits=stopbits_map[config.stopbits],
        timeout=config.timeout,
    )
    print("Connected.")

    logger = ExcelLogger(
        workbook_path=config.workbook_path, sheet_name=config.sheet_name,
        field_names=[f.name for f in config.fields],
        autosave_every_rows=config.autosave_every_rows,
        autosave_interval_seconds=config.autosave_interval_seconds,
    )

    plotter = LivePlotter(channel_names=[f.name for f in config.fields], window_seconds=args.plot_window, smooth=args.smooth)

    try:
        while True:
            cycle_start = time.perf_counter()
            row_data = poll_once(client, config, logger)

            plot_values = {}
            for f in config.fields:
                val = row_data.get(f.name)
                if val is not None and val != "":
                    plot_values[f.name] = float(val)
            if plot_values:
                plotter.add_point(datetime.now(), plot_values)

            print("[{0}] {1} | {2}".format(
                row_data["timestamp"], row_data["status"],
                ", ".join("{0}={1}".format(f.name, row_data.get(f.name, "")) for f in config.fields)))

            if row_data.get("error"):
                print("  Errors: {0}".format(row_data["error"]))

            if args.once:
                break

            delay = config.poll_interval_seconds - (time.perf_counter() - cycle_start)
            if delay > 0:
                time.sleep(delay)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        logger.close()
        plotter.close()
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
