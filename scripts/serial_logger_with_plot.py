"""Real-time serial data logger with live force-time plot.

Reads Modbus RTU data from serial port, writes to Excel, and plots force in real-time.
Single script, no conflicts.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import time
import tkinter as tk
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

import matplotlib

matplotlib.use(os.environ.get("SERIAL_LOGGER_MPL_BACKEND", "TkAgg"))
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

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
    "uint16": 1,
    "int16": 1,
    "uint32": 2,
    "int32": 2,
    "float32": 2,
}

MODBUS_EXCEPTION_CODES = {
    1: "Illegal function",
    2: "Illegal data address",
    3: "Illegal data value",
    4: "Slave device failure",
    5: "Acknowledge",
    6: "Slave device busy",
    8: "Memory parity error",
    10: "Gateway path unavailable",
    11: "Gateway target failed to respond",
}

TOTAL_FORCE_NAME = "total_force"


@dataclass(frozen=True)
class MeasurementSample:
    timestamp: datetime
    raw_values: Dict[str, float]
    total_force: float


@dataclass(frozen=True)
class MeasurementGroupResult:
    index: int
    pwm: str
    start_time: datetime
    end_time: datetime
    total_current: float
    average_total_force: float
    samples: List[MeasurementSample]


@dataclass
class ActiveMeasurementGroup:
    pwm: str
    start_time: datetime
    samples: List[MeasurementSample]


@dataclass
class MeasurementSessionState:
    completed_groups: List[MeasurementGroupResult] = field(default_factory=list)
    current_group: Optional[ActiveMeasurementGroup] = None


class SimpleStringVar:
    def __init__(self, value: str = "") -> None:
        self._value = value

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


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
    workbook_path = Path(
        workbook_path_str.replace(
            "{start_time}", datetime.now().strftime("%Y%m%d_%H%M%S")
        )
    )
    if not workbook_path.is_absolute():
        workbook_path = project_root / workbook_path

    fields = [
        FieldConfig(
            name=str(f["name"]),
            function_code=int(f["function_code"]),
            address=int(f["address"]),
            data_type=str(f["data_type"]).lower(),
            scale=float(f.get("scale", 1.0)),
            offset=float(f.get("offset", 0.0)),
            precision=int(f["precision"]) if f.get("precision") is not None else None,
            byte_order=str(f.get("byte_order", "big")).lower(),
            word_order=str(f.get("word_order", "big")).lower(),
        )
        for f in payload.get("fields", [])
    ]

    return AppConfig(
        port=str(payload["port"]),
        baudrate=int(payload.get("baudrate", 115200)),
        bytesize=int(payload.get("bytesize", 8)),
        parity=str(payload.get("parity", "N")).upper(),
        stopbits=float(payload.get("stopbits", 1)),
        timeout=float(payload.get("timeout", 1.0)),
        slave_id=int(payload.get("slave_id", 1)),
        poll_interval_seconds=float(payload.get("poll_interval_seconds", 0.1)),
        inter_request_delay_seconds=float(
            payload.get("inter_request_delay_seconds", 0.0)
        ),
        retries=int(payload.get("retries", 1)),
        workbook_path=workbook_path,
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


def build_request(
    slave_id: int, function_code: int, address: int, quantity: int
) -> bytes:
    return append_crc(struct.pack(">BBHH", slave_id, function_code, address, quantity))


def read_registers(
    client, slave_id: int, function_code: int, address: int, quantity: int
) -> Tuple[List[int], bytes]:
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
    registers = [
        int.from_bytes(data_bytes[i : i + 2], byteorder="big")
        for i in range(0, len(data_bytes), 2)
    ]
    return registers, response


def read_with_retries(
    client, config: AppConfig, function_code: int, address: int, quantity: int
) -> Tuple[List[int], bytes]:
    last_err = None
    for _ in range(config.retries + 1):
        try:
            return read_registers(
                client, config.slave_id, function_code, address, quantity
            )
        except Exception as e:
            last_err = e
            time.sleep(0.2)
    raise last_err  # type: ignore


def registers_to_bytes(
    registers: Sequence[int], byte_order: str, word_order: str
) -> bytes:
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


def floor_to_second(ts: datetime) -> datetime:
    return ts.replace(microsecond=0)


def previous_complete_second(ts: datetime) -> datetime:
    return floor_to_second(ts) - timedelta(seconds=1)


def compute_total_force(
    values: Dict[str, float],
    channel_names: Sequence[str],
) -> Optional[float]:
    if any(name not in values for name in channel_names):
        return None
    return sum(values[name] for name in channel_names)


def record_second_bucket(
    buckets: Dict[datetime, Dict[str, List[float]]],
    ts: datetime,
    values: Dict[str, Optional[float]],
) -> None:
    second_key = floor_to_second(ts)
    for name, value in values.items():
        if value is None:
            continue
        bucket = buckets.setdefault(second_key, {})
        bucket.setdefault(name, []).append(value)


def compute_previous_second_averages(
    buckets: Dict[datetime, Dict[str, List[float]]],
    now: datetime,
) -> Tuple[Optional[datetime], Dict[str, float]]:
    second_key = previous_complete_second(now)
    bucket = buckets.get(second_key)
    if not bucket:
        return None, {}

    averages: Dict[str, float] = {}
    for name, samples in bucket.items():
        if samples:
            averages[name] = sum(samples) / len(samples)
    if not averages:
        return None, {}
    return second_key, averages


def build_manual_tare_offsets(
    last_raw_values: Dict[str, float],
    channel_names: Sequence[str],
) -> Dict[str, float]:
    return {
        name: last_raw_values[name] for name in channel_names if name in last_raw_values
    }


def prepare_plot_sample(
    raw_values: Dict[str, float],
    offsets: Dict[str, float],
    channel_names: Sequence[str],
) -> Dict[str, Optional[float]]:
    sample: Dict[str, Optional[float]] = {}
    zeroed_values: Dict[str, float] = {}

    for name in channel_names:
        if name in raw_values:
            zeroed = raw_values[name] - offsets.get(name, 0.0)
            sample[name] = zeroed
            zeroed_values[name] = zeroed
        else:
            sample[name] = None

    sample[TOTAL_FORCE_NAME] = compute_total_force(zeroed_values, channel_names)
    return sample


def append_series_snapshot(
    history: Dict[str, List[float]],
    series_names: Sequence[str],
    sample: Dict[str, Optional[float]],
) -> None:
    for name in series_names:
        value = sample.get(name)
        series = history.setdefault(name, [])
        series.append(float("nan") if value is None else value)


def format_previous_second_title(
    second_ts: Optional[datetime],
    averages: Dict[str, float],
    series_names: Sequence[str],
    tare_message: Optional[str],
) -> str:
    parts: List[str] = []
    if tare_message:
        parts.append(tare_message)

    if second_ts is None or not averages:
        parts.append("等待上一秒统计")
        return " | ".join(parts)

    parts.append("上一秒均值 {0}".format(second_ts.strftime("%H:%M:%S")))
    for name in series_names:
        if name in averages:
            parts.append("{0}={1:.2f}".format(name, averages[name]))
    return " | ".join(parts)


def start_measurement_group(
    state: MeasurementSessionState,
    pwm: str,
    start_time: datetime,
) -> ActiveMeasurementGroup:
    cleaned_pwm = pwm.strip()
    if not cleaned_pwm:
        raise ValueError("PWM is required")
    if state.current_group is not None:
        raise ValueError("Measurement already in progress")
    current_group = ActiveMeasurementGroup(
        pwm=cleaned_pwm, start_time=start_time, samples=[]
    )
    state.current_group = current_group
    return current_group


def record_measurement_sample(
    state: MeasurementSessionState,
    timestamp: datetime,
    raw_values: Dict[str, float],
    total_force: Optional[float],
) -> None:
    if state.current_group is None or total_force is None:
        return
    state.current_group.samples.append(
        MeasurementSample(
            timestamp=timestamp,
            raw_values=dict(raw_values),
            total_force=float(total_force),
        )
    )


def finish_measurement_group(
    state: MeasurementSessionState,
    total_current_text: str,
    end_time: datetime,
) -> MeasurementGroupResult:
    if state.current_group is None:
        raise ValueError("Measurement has not started")
    total_current = float(total_current_text.strip())
    samples = list(state.current_group.samples)
    if not samples:
        raise ValueError("No valid total force samples")
    result = MeasurementGroupResult(
        index=len(state.completed_groups) + 1,
        pwm=state.current_group.pwm,
        start_time=state.current_group.start_time,
        end_time=end_time,
        total_current=total_current,
        average_total_force=sum(sample.total_force for sample in samples)
        / len(samples),
        samples=samples,
    )
    state.completed_groups.append(result)
    state.current_group = None
    return result


def reset_for_next_group(state: MeasurementSessionState) -> None:
    state.current_group = None


def build_measurement_export_path(output_dir: Path, now: datetime) -> Path:
    return output_dir / "measurement_results_{0}.xlsx".format(
        now.strftime("%Y%m%d_%H%M%S")
    )


def build_measurement_export_rows(
    groups: Sequence[MeasurementGroupResult],
) -> Tuple[List[str], List[List[Any]]]:
    max_samples = max((len(group.samples) for group in groups), default=0)
    headers = [
        "序号",
        "PWM",
        "开始时间(北京时间)",
        "结束时间(北京时间)",
        "总电流",
        "合力平均值",
    ]
    for index in range(1, max_samples + 1):
        headers.extend(
            [
                "原始时间戳_{0}".format(index),
                "原始合力_{0}".format(index),
                "原始ch1_{0}".format(index),
                "原始ch2_{0}".format(index),
                "原始ch3_{0}".format(index),
            ]
        )

    rows: List[List[Any]] = []
    for group in groups:
        row: List[Any] = [
            group.index,
            group.pwm,
            group.start_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
            group.end_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
            group.total_current,
            group.average_total_force,
        ]
        for sample in group.samples:
            row.extend(
                [
                    sample.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f"),
                    sample.total_force,
                    sample.raw_values.get("weight_ch1", ""),
                    sample.raw_values.get("weight_ch2", ""),
                    sample.raw_values.get("weight_ch3", ""),
                ]
            )
        for _ in range(len(group.samples), max_samples):
            row.extend(["", "", "", "", ""])
        rows.append(row)
    return headers, rows


def write_measurement_workbook(
    output_path: Path, groups: Sequence[MeasurementGroupResult]
) -> None:
    assert Workbook is not None
    headers, rows = build_measurement_export_rows(groups)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "measurements"
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)
    worksheet.freeze_panes = "A2"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    workbook.close()


class ExcelLogger:
    def __init__(
        self,
        workbook_path: Path,
        sheet_name: str,
        field_names: Sequence[str],
        autosave_every_rows: int,
        autosave_interval_seconds: float,
    ) -> None:
        self.workbook_path = workbook_path
        self.sheet_name = sheet_name
        self.autosave_every_rows = autosave_every_rows
        self.autosave_interval_seconds = autosave_interval_seconds
        self.pending_rows: List[List[Any]] = []
        self.expected_headers = [
            "timestamp",
            "unix_time",
            "port",
            "baudrate",
            "slave_id",
            "status",
            "error",
            "raw_frames",
        ] + list(field_names)
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
            last_col = (
                get_column_letter(len(self.headers)) if get_column_letter else "H"
            )
            ws.auto_filter.ref = "A1:{0}{1}".format(last_col, max(ws.max_row, 1))
        tmp = self.workbook_path.with_name(
            "{0}.tmp{1}".format(self.workbook_path.stem, self.workbook_path.suffix)
        )
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
        if (
            self.unsaved_rows >= self.autosave_every_rows
            or time.monotonic() - self.last_save_monotonic
            >= self.autosave_interval_seconds
        ):
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
            print(
                "  [Saved {0} rows to {1}]".format(
                    len(self.pending_rows), self.workbook_path.name
                )
            )
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

    def __init__(
        self,
        channel_names: List[str],
        window_seconds: int = 60,
        smooth: bool = False,
        calc_window: int = 10,
        tare_seconds: float = 2.0,
    ) -> None:
        self.channel_names = channel_names
        self.total_force_name = TOTAL_FORCE_NAME
        self.plot_series_names = list(channel_names) + [self.total_force_name]
        self.window_seconds = window_seconds
        self.calc_window = calc_window
        self.smooth = smooth
        self.tare_seconds = tare_seconds
        self.offsets: Dict[str, float] = {name: 0.0 for name in channel_names}
        self.tare_done = False
        self.tare_start: Optional[datetime] = None
        self.tare_buffer: Dict[str, List[float]] = {name: [] for name in channel_names}
        self.last_raw_values: Dict[str, float] = {}
        self.last_tare_message: Optional[str] = None
        self.last_tare_message_until: float = 0.0
        self.second_buckets: Dict[datetime, Dict[str, List[float]]] = {}
        self.last_sample_ts: Optional[datetime] = None
        self.measurement_state = MeasurementSessionState()
        self.measurement_output_dir = get_app_root() / "output"
        self.all_times: List[datetime] = []
        self.all_values: Dict[str, List[float]] = {
            name: [] for name in self.plot_series_names
        }
        self.raw_lines: Dict[str, Any] = {}
        self.smooth_lines: Dict[str, Any] = {}
        self.avg_lines: Dict[str, Any] = {}

        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        plt.subplots_adjust(top=0.86)

        for i, name in enumerate(self.plot_series_names):
            color = self.COLORS[i % len(self.COLORS)]
            (raw_line,) = self.ax.plot(
                [], [], color=color, linewidth=0.8, alpha=0.3, markersize=2
            )
            self.raw_lines[name] = raw_line
            (smooth_line,) = self.ax.plot(
                [], [], color=color, linewidth=2.0, label=name
            )
            self.smooth_lines[name] = smooth_line
            (avg_line,) = self.ax.plot(
                [],
                [],
                color=color,
                linestyle="--",
                linewidth=1.2,
                label="Avg {0}".format(name),
            )
            self.avg_lines[name] = avg_line

        self.button_ax = self.fig.add_axes([0.84, 0.9, 0.12, 0.06])
        self.tare_button = Button(self.button_ax, "去皮")
        self.tare_button.on_clicked(self.request_manual_tare)

        self.ax.set_title("Taring... ({0:.1f}s remaining)".format(tare_seconds))
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Force (g)")
        self.ax.grid(True, alpha=0.3)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        self.ax.legend(loc="upper right", fontsize=8)
        self.fig.autofmt_xdate()
        plt.ion()
        plt.show(block=False)
        self.measurement_status_var = self._make_string_var("未开始")
        self.measurement_pwm_var = self._make_string_var("")
        self.measurement_current_var = self._make_string_var("")
        self.measurement_summary_var = self._make_string_var("已完成组数: 0")
        self.measurement_history_var = self._make_string_var("暂无已完成组")
        self._build_measurement_panel()

    def _make_string_var(self, value: str) -> Any:
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            return SimpleStringVar(value)
        return tk.StringVar(master=root, value=value)

    def _build_measurement_panel(self) -> None:
        manager = getattr(self.fig.canvas, "manager", None)
        window = getattr(manager, "window", None)
        if window is None:
            return

        panel = ttk.LabelFrame(window, text="分组测量", padding=8)
        panel.pack(side="bottom", fill="x")

        ttk.Label(panel, text="PWM").grid(
            row=0, column=0, padx=(0, 6), pady=4, sticky="w"
        )
        ttk.Entry(panel, textvariable=self.measurement_pwm_var, width=12).grid(
            row=0, column=1, pady=4, sticky="w"
        )
        ttk.Label(panel, text="总电流").grid(
            row=0, column=2, padx=(12, 6), pady=4, sticky="w"
        )
        ttk.Entry(panel, textvariable=self.measurement_current_var, width=12).grid(
            row=0, column=3, pady=4, sticky="w"
        )

        ttk.Button(panel, text="开始测量", command=self.start_measurement).grid(
            row=0, column=4, padx=(12, 4), pady=4
        )
        ttk.Button(panel, text="结束测量", command=self.finish_measurement).grid(
            row=0, column=5, padx=4, pady=4
        )
        ttk.Button(panel, text="下一组", command=self.prepare_next_group).grid(
            row=0, column=6, padx=4, pady=4
        )
        ttk.Button(panel, text="导出表格", command=self.export_measurements).grid(
            row=0, column=7, padx=4, pady=4
        )

        ttk.Label(panel, textvariable=self.measurement_status_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )
        ttk.Label(panel, textvariable=self.measurement_summary_var).grid(
            row=1, column=2, columnspan=6, sticky="w", pady=(4, 0)
        )
        ttk.Label(
            panel,
            textvariable=self.measurement_history_var,
            justify="left",
            anchor="w",
        ).grid(row=2, column=0, columnspan=8, sticky="ew", pady=(6, 0))

    def _refresh_measurement_history(self) -> None:
        if not self.measurement_state.completed_groups:
            self.measurement_history_var.set("暂无已完成组")
            return

        lines = []
        for group in self.measurement_state.completed_groups:
            lines.append(
                "#{0} PWM={1} 开始={2} 结束={3} 总电流={4:.3f} 平均合力={5:.3f}".format(
                    group.index,
                    group.pwm,
                    group.start_time.strftime("%H:%M:%S"),
                    group.end_time.strftime("%H:%M:%S"),
                    group.total_current,
                    group.average_total_force,
                )
            )
        self.measurement_history_var.set("\n".join(lines))

    def _set_tare_message(self, message: str) -> None:
        self.last_tare_message = message
        self.last_tare_message_until = time.monotonic() + 2.0

    def _active_tare_message(self) -> Optional[str]:
        if time.monotonic() <= self.last_tare_message_until:
            return self.last_tare_message
        return None

    def request_manual_tare(self, _event: object | None = None) -> None:
        if not self.last_raw_values:
            self._set_tare_message("去皮失败：暂无有效数据")
            return

        if self.last_sample_ts is not None:
            self.second_buckets.pop(floor_to_second(self.last_sample_ts), None)

        self.offsets.update(
            build_manual_tare_offsets(self.last_raw_values, self.channel_names)
        )
        self.tare_done = True
        self.tare_start = None
        self.tare_buffer = {name: [] for name in self.channel_names}
        self._set_tare_message("已去皮 {0}".format(datetime.now().strftime("%H:%M:%S")))

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
            self._set_tare_message("启动去皮完成")
            return True
        return False

    def _prune_history(self, ts: datetime) -> None:
        cutoff = ts.timestamp() - self.window_seconds
        while self.all_times and self.all_times[0].timestamp() < cutoff:
            self.all_times.pop(0)
            for name in self.plot_series_names:
                if self.all_values[name]:
                    self.all_values[name].pop(0)

        oldest_bucket = floor_to_second(ts) - timedelta(seconds=self.window_seconds + 2)
        for bucket_ts in list(self.second_buckets):
            if bucket_ts < oldest_bucket:
                del self.second_buckets[bucket_ts]

    def add_point(self, ts: datetime, values: Dict[str, float]) -> None:
        self.last_raw_values = dict(values)
        self.last_sample_ts = ts

        if not self.tare_done:
            self._tare(ts, values)
            return

        sample = prepare_plot_sample(values, self.offsets, self.channel_names)
        record_measurement_sample(
            self.measurement_state,
            ts,
            dict(values),
            sample.get(self.total_force_name),
        )

        self.all_times.append(ts)
        append_series_snapshot(self.all_values, self.plot_series_names, sample)
        record_second_bucket(self.second_buckets, ts, sample)
        self._prune_history(ts)
        self._update()

    def _build_smoothed_values(self, values: List[float]) -> List[float]:
        if not HAS_NUMPY or len(values) <= 3 or any(math.isnan(v) for v in values):
            return values
        win = max(3, len(values) // 30)
        kernel = np.ones(win) / win
        padded = np.pad(values, (win // 2, win // 2), mode="edge")
        return list(np.convolve(padded, kernel, mode="valid")[: len(values)])

    def _update(self) -> None:
        if not self.all_times:
            return

        now = self.all_times[-1]
        second_ts, averages = compute_previous_second_averages(self.second_buckets, now)

        for name in self.plot_series_names:
            vals = self.all_values.get(name, [])
            if not vals:
                continue

            self.raw_lines[name].set_data(self.all_times, vals)

            if self.smooth:
                smoothed = self._build_smoothed_values(vals)
                self.smooth_lines[name].set_data(self.all_times, smoothed)
            else:
                self.smooth_lines[name].set_data(self.all_times, vals)

            if name in averages:
                avg_vals = [averages[name]] * len(self.all_times)
                self.avg_lines[name].set_data(self.all_times, avg_vals)
            else:
                self.avg_lines[name].set_data([], [])

        self.ax.relim()
        self.ax.autoscale_view()
        self.ax.set_xlim([self.all_times[0], self.all_times[-1]])
        self.ax.set_title(
            format_previous_second_title(
                second_ts,
                averages,
                self.plot_series_names,
                self._active_tare_message(),
            )
        )
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def start_measurement(self) -> None:
        try:
            start_measurement_group(
                self.measurement_state,
                self.measurement_pwm_var.get(),
                datetime.now(),
            )
        except ValueError as exc:
            messagebox.showerror("开始测量失败", str(exc))
            return
        self.measurement_status_var.set("测量中")
        self.measurement_summary_var.set(
            "已完成组数: {0} | 当前 PWM={1}".format(
                len(self.measurement_state.completed_groups),
                self.measurement_pwm_var.get().strip(),
            )
        )

    def finish_measurement(self) -> None:
        try:
            result = finish_measurement_group(
                self.measurement_state,
                self.measurement_current_var.get(),
                datetime.now(),
            )
        except ValueError as exc:
            messagebox.showerror("结束测量失败", str(exc))
            return
        self.measurement_status_var.set("已完成")
        self.measurement_summary_var.set(
            "已完成组数: {0} | 最近一组 PWM={1} | 平均合力={2:.3f}".format(
                len(self.measurement_state.completed_groups),
                result.pwm,
                result.average_total_force,
            )
        )
        self._refresh_measurement_history()

    def prepare_next_group(self) -> None:
        if self.measurement_state.current_group is not None:
            messagebox.showerror("下一组失败", "当前组尚未结束")
            return
        reset_for_next_group(self.measurement_state)
        self.measurement_pwm_var.set("")
        self.measurement_current_var.set("")
        self.measurement_status_var.set("未开始")
        self.measurement_summary_var.set(
            "已完成组数: {0}".format(len(self.measurement_state.completed_groups))
        )
        self._refresh_measurement_history()

    def export_measurements(self) -> Path:
        if not self.measurement_state.completed_groups:
            messagebox.showerror("导出失败", "没有可导出的测量组")
            raise ValueError("No completed measurement groups")
        output_path = build_measurement_export_path(
            self.measurement_output_dir, datetime.now()
        )
        write_measurement_workbook(output_path, self.measurement_state.completed_groups)
        self.measurement_summary_var.set("已导出: {0}".format(output_path.name))
        self._refresh_measurement_history()
        return output_path

    def close(self) -> None:
        plt.close(self.fig)


def poll_once(client, config: AppConfig, logger: ExcelLogger) -> Dict[str, Any]:
    timestamp = datetime.now()
    row_data: Dict[str, Any] = {
        "timestamp": timestamp.strftime(config.timestamp_format),
        "unix_time": round(time.time(), 3),
        "port": config.port,
        "baudrate": config.baudrate,
        "slave_id": config.slave_id,
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
                field_regs = registers[offset : offset + f.register_count]
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
    parser = argparse.ArgumentParser(
        description="Serial data logger with live force-time plot."
    )
    parser.add_argument(
        "--config", default="config/logger_config.json", help="Config file path."
    )
    parser.add_argument(
        "--port", help="Override serial port from config, for example COM4."
    )
    parser.add_argument(
        "--plot-window", type=int, default=60, help="Plot time window in seconds."
    )
    parser.add_argument(
        "--smooth", action="store_true", help="Apply smoothing to plot."
    )
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
    parity_map = {
        "N": serial.PARITY_NONE,
        "E": serial.PARITY_EVEN,
        "O": serial.PARITY_ODD,
    }
    stopbits_map = {
        1.0: serial.STOPBITS_ONE,
        1.5: serial.STOPBITS_ONE_POINT_FIVE,
        2.0: serial.STOPBITS_TWO,
    }
    client = serial.Serial(
        port=config.port,
        baudrate=config.baudrate,
        bytesize=config.bytesize,
        parity=parity_map[config.parity],
        stopbits=stopbits_map[config.stopbits],
        timeout=config.timeout,
    )
    print("Connected.")

    logger = ExcelLogger(
        workbook_path=config.workbook_path,
        sheet_name=config.sheet_name,
        field_names=[f.name for f in config.fields],
        autosave_every_rows=config.autosave_every_rows,
        autosave_interval_seconds=config.autosave_interval_seconds,
    )

    plotter = LivePlotter(
        channel_names=[f.name for f in config.fields],
        window_seconds=args.plot_window,
        smooth=args.smooth,
    )

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

            print(
                "[{0}] {1} | {2}".format(
                    row_data["timestamp"],
                    row_data["status"],
                    ", ".join(
                        "{0}={1}".format(f.name, row_data.get(f.name, ""))
                        for f in config.fields
                    ),
                )
            )

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
