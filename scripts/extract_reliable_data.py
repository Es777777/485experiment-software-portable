"""Extract reliable force-electric relationship data from experiment logs.

A force-electric relationship is considered reliable when:
1. The first 5 seconds of a stable period are used to compute the baseline average.
2. Subsequent readings stay within 15% of that baseline average.
"""

from __future__ import annotations

import argparse
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np  # type: ignore
from openpyxl import Workbook, load_workbook  # type: ignore
from runtime_paths import get_app_root

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore
    import matplotlib.dates as mdates  # type: ignore
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


STABILITY_WINDOW_SECONDS = 5.0
PERCENTAGE_TOLERANCE = 0.15

OUTPUT_HEADERS = [
    "timestamp",
    "unix_time",
    "weight_ch1",
    "weight_ch2",
    "weight_ch3",
    "voltage",
    "current",
    "stable_segment_id",
    "stable_start_time",
    "stable_duration_seconds",
    "voltage_mean",
    "voltage_std",
    "current_mean",
    "current_std",
    "video_file",
]


def find_latest_video_ocr_excel(logs_dir: Path) -> Path:
    """Find the most recent Excel file containing video OCR data."""
    candidates = [
        p for p in logs_dir.glob("*.xlsx")
        if "_video_ocr" in p.name and not p.name.startswith("~$")
    ]
    if not candidates:
        raise FileNotFoundError(
            "No *_video_ocr.xlsx file found in {0}".format(logs_dir)
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_valid_rows(
    workbook_path: Path,
) -> List[Dict[str, Any]]:
    """Load rows that have both voltage and current values from video OCR."""
    wb = load_workbook(workbook_path, read_only=True)
    ws = wb.active
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]

    col_map: Dict[str, int] = {}
    for idx, h in enumerate(headers):
        if h is not None:
            col_map[str(h)] = idx

    required = ["timestamp", "unix_time", "video_voltage", "video_current"]
    for req in required:
        if req not in col_map:
            raise ValueError("Missing required column: {0}".format(req))

    voltage_col = col_map["video_voltage"]
    current_col = col_map["video_current"]

    weight_cols = {}
    for ch in ("weight_ch1", "weight_ch2", "weight_ch3"):
        if ch in col_map:
            weight_cols[ch] = col_map[ch]

    optional_cols = {}
    for key in ("video_file",):
        if key in col_map:
            optional_cols[key] = col_map[key]

    rows: List[Dict[str, Any]] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        voltage = row[voltage_col]
        current = row[current_col]
        if voltage is None or current is None:
            continue

        ts_val = row[col_map["timestamp"]]
        unix_val = row[col_map["unix_time"]]

        record: Dict[str, Any] = {
            "timestamp": ts_val,
            "unix_time": unix_val,
            "voltage": float(voltage),
            "current": float(current),
        }

        for ch, col_idx in weight_cols.items():
            record[ch] = row[col_idx]

        for key, col_idx in optional_cols.items():
            record[key] = row[col_idx]

        rows.append(record)

    wb.close()
    return rows


def parse_timestamp(value: Any) -> Optional[datetime]:
    """Parse timestamp from various formats."""
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S.%f",
        "%Y/%m/%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def find_stable_segments(
    rows: List[Dict[str, Any]],
    stability_seconds: float = STABILITY_WINDOW_SECONDS,
    percentage_tol: float = PERCENTAGE_TOLERANCE,
) -> List[List[Dict[str, Any]]]:
    """Find stable segments using baseline-average + percentage tolerance.

    Algorithm:
    1. Group consecutive readings into candidate segments (voltage+current
       must not change abruptly between adjacent readings).
    2. For each candidate >= stability_seconds:
       - Compute baseline average from the first `stability_seconds`.
       - Mark readings as reliable if they stay within `percentage_tol`
         of the baseline average (for both voltage and current).
    """
    if not rows:
        return []

    timestamped: List[Tuple[datetime, Dict[str, Any]]] = []
    for row in rows:
        ts = parse_timestamp(row["timestamp"])
        if ts is not None:
            timestamped.append((ts, row))

    if not timestamped:
        return []

    timestamped.sort(key=lambda x: x[0])

    step_v_tol = 1.0
    step_c_tol = 1.0

    candidates: List[List[Tuple[datetime, Dict[str, Any]]]] = []
    current: List[Tuple[datetime, Dict[str, Any]]] = [timestamped[0]]

    for i in range(1, len(timestamped)):
        prev_v = current[-1][1]["voltage"]
        prev_c = current[-1][1]["current"]
        curr_v = timestamped[i][1]["voltage"]
        curr_c = timestamped[i][1]["current"]

        if abs(curr_v - prev_v) <= step_v_tol and abs(curr_c - prev_c) <= step_c_tol:
            current.append(timestamped[i])
        else:
            if len(current) > 1:
                candidates.append(current)
            current = [timestamped[i]]

    if len(current) > 1:
        candidates.append(current)

    reliable_segments: List[List[Dict[str, Any]]] = []

    for candidate in candidates:
        start_time = candidate[0][0]
        baseline_end = start_time + timedelta(seconds=stability_seconds)

        baseline_rows = [
            item for item in candidate if item[0] <= baseline_end
        ]

        if not baseline_rows or len(baseline_rows) < 2:
            continue

        baseline_v_mean = sum(r[1]["voltage"] for r in baseline_rows) / len(baseline_rows)
        baseline_c_mean = sum(r[1]["current"] for r in baseline_rows) / len(baseline_rows)

        if baseline_v_mean == 0 and baseline_c_mean == 0:
            continue

        v_threshold = max(abs(baseline_v_mean) * percentage_tol, 0.1)
        c_threshold = max(abs(baseline_c_mean) * percentage_tol, 0.05)

        reliable: List[Dict[str, Any]] = []
        for _, row in candidate:
            v_ok = abs(row["voltage"] - baseline_v_mean) <= v_threshold
            c_ok = abs(row["current"] - baseline_c_mean) <= c_threshold
            if v_ok and c_ok:
                reliable.append(row)

        if len(reliable) >= 2:
            first_ts = parse_timestamp(reliable[0]["timestamp"])
            last_ts = parse_timestamp(reliable[-1]["timestamp"])
            if first_ts and last_ts and (last_ts - first_ts).total_seconds() >= stability_seconds:
                reliable_segments.append(reliable)

    return reliable_segments


def compute_segment_stats(
    segment: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute statistical summary for a stable segment."""
    voltages = [r["voltage"] for r in segment]
    currents = [r["current"] for r in segment]

    n = len(voltages)
    v_mean = sum(voltages) / n
    c_mean = sum(currents) / n
    v_std = (sum((v - v_mean) ** 2 for v in voltages) / n) ** 0.5
    c_std = (sum((c - c_mean) ** 2 for c in currents) / n) ** 0.5

    first_ts = parse_timestamp(segment[0]["timestamp"])
    last_ts = parse_timestamp(segment[-1]["timestamp"])
    duration = (last_ts - first_ts).total_seconds() if first_ts and last_ts else 0.0

    return {
        "voltage_mean": round(v_mean, 4),
        "voltage_std": round(v_std, 4),
        "current_mean": round(c_mean, 4),
        "current_std": round(c_std, 4),
        "stable_start_time": segment[0]["timestamp"],
        "stable_duration_seconds": round(duration, 2),
    }


def write_reliable_excel(
    segments: List[List[Dict[str, Any]]],
    output_path: Path,
) -> int:
    """Write reliable data segments to a new Excel workbook."""
    wb = Workbook()
    ws = wb.active
    if ws is not None:
        ws.title = "reliable_data"

        for col_idx, header in enumerate(OUTPUT_HEADERS, start=1):
            ws.cell(row=1, column=col_idx, value=header)

    total_rows = 0
    for seg_idx, segment in enumerate(segments, start=1):
        stats = compute_segment_stats(segment)
        for row_data in segment:
            row_values = {
                "timestamp": row_data.get("timestamp", ""),
                "unix_time": row_data.get("unix_time", ""),
                "weight_ch1": row_data.get("weight_ch1", ""),
                "weight_ch2": row_data.get("weight_ch2", ""),
                "weight_ch3": row_data.get("weight_ch3", ""),
                "voltage": row_data["voltage"],
                "current": row_data["current"],
                "stable_segment_id": seg_idx,
                "stable_start_time": stats["stable_start_time"],
                "stable_duration_seconds": stats["stable_duration_seconds"],
                "voltage_mean": stats["voltage_mean"],
                "voltage_std": stats["voltage_std"],
                "current_mean": stats["current_mean"],
                "current_std": stats["current_std"],
                "video_file": row_data.get("video_file", ""),
            }

            if ws is not None:
                for col_idx, header in enumerate(OUTPUT_HEADERS, start=1):
                    ws.cell(row=total_rows + 2, column=col_idx, value=row_values[header])
            total_rows += 1

    if ws is not None:
        ws.auto_filter.ref = "A1:{0}{1}".format(
            _col_letter(len(OUTPUT_HEADERS)), total_rows + 1
        )
        ws.freeze_panes = "A2"

        for col_idx, header in enumerate(OUTPUT_HEADERS, start=1):
            width = max(14, min(len(str(header)) + 4, 30))
            ws.column_dimensions[_col_letter(col_idx)].width = width

    output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = output_path.with_name(
        "{0}.tmp{1}".format(output_path.stem, output_path.suffix)
    )
    try:
        wb.save(temp_path)
        if output_path.exists():
            try:
                os.replace(temp_path, output_path)
            except PermissionError:
                fallback = output_path.with_name(
                    "{0}_{1}{2}".format(
                        output_path.stem,
                        datetime.now().strftime("%H%M%S"),
                        output_path.suffix,
                    )
                )
                shutil.move(str(temp_path), str(fallback))
                output_path = fallback
                print("Warning: original file was locked, saved as: {0}".format(fallback))
        else:
            os.replace(temp_path, output_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise
    finally:
        wb.close()
    return total_rows


def _col_letter(col_num: int) -> str:
    """Convert column number to Excel column letter."""
    letters = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _prepare_plot_data(
    segments: List[List[Dict[str, Any]]],
) -> Tuple[List[datetime], List[float], List[float], List[int]]:
    """Flatten segments into time-series arrays for plotting."""
    times: List[datetime] = []
    forces: List[float] = []
    powers: List[float] = []
    seg_ids: List[int] = []

    for seg_idx, segment in enumerate(segments, start=1):
        for row in segment:
            ts = parse_timestamp(row["timestamp"])
            if ts is not None:
                times.append(ts)
                weight = row.get("weight_ch1", 0) or 0
                forces.append(float(weight))
                powers.append(row["voltage"] * row["current"])
                seg_ids.append(seg_idx)

    return times, forces, powers, seg_ids


def _moving_average(data: List[float], window: int) -> List[float]:
    """Simple moving average smoothing."""
    if window <= 1:
        return list(data)
    kernel = np.ones(window) / window
    padded = np.pad(data, (window // 2, window // 2), mode="edge")
    smoothed = np.convolve(padded, kernel, mode="valid")
    return list(smoothed[:len(data)])


def _plot_force_electric_curve(
    times: List[datetime],
    forces: List[float],
    powers: List[float],
    seg_ids: List[int],
    output_dir: Path,
    smoothed: bool = False,
) -> Path:
    """Plot force vs electric power curve, raw or smoothed."""
    suffix = "_smoothed" if smoothed else "_raw"
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    seg_colors = plt.cm.tab10(np.linspace(0, 1, max(len(set(seg_ids)), 1)))
    unique_segs = sorted(set(seg_ids))

    if smoothed:
        window = max(5, len(forces) // 100)
        forces_plot = _moving_average(forces, window)
        powers_plot = _moving_average(powers, window)
    else:
        forces_plot = forces
        powers_plot = powers

    for seg_id in unique_segs:
        mask = [i for i, s in enumerate(seg_ids) if s == seg_id]
        color = seg_colors[seg_id - 1] if seg_id <= len(seg_colors) else seg_colors[0]
        seg_times = [times[i] for i in mask]
        seg_forces = [forces_plot[i] for i in mask]
        seg_powers = [powers_plot[i] for i in mask]

        ax1.plot(seg_times, seg_forces, ".", color=color, markersize=3,
                 label="Seg {0}".format(seg_id))
        ax2.plot(seg_times, seg_powers, ".", color=color, markersize=3)
        ax3.plot(seg_times, seg_powers, ".", color=color, markersize=3)

    ax1.set_ylabel("Force (g)")
    ax1.set_title("Force vs Time ({0})".format("Smoothed" if smoothed else "Raw"))
    ax1.legend(loc="upper right", fontsize=7)
    ax1.grid(True, alpha=0.3)

    ax2.set_ylabel("Power (V*A)")
    ax2.set_title("Electric Power vs Time ({0})".format("Smoothed" if smoothed else "Raw"))
    ax2.grid(True, alpha=0.3)

    ax3.set_xlabel("Time")
    ax3.set_ylabel("Power vs Force")
    ax3.grid(True, alpha=0.3)

    for seg_id in unique_segs:
        mask = [i for i, s in enumerate(seg_ids) if s == seg_id]
        color = seg_colors[seg_id - 1] if seg_id <= len(seg_colors) else seg_colors[0]
        seg_forces = [forces_plot[i] for i in mask]
        seg_powers = [powers_plot[i] for i in mask]
        ax3.plot(seg_forces, seg_powers, ".", color=color, markersize=3,
                 label="Seg {0}".format(seg_id))
    ax3.legend(loc="upper right", fontsize=7)

    fig.autofmt_xdate()
    plt.tight_layout()

    filename = "force_electric_curve{0}.png".format(suffix)
    output_path = output_dir / filename
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract reliable force-electric relationship data "
        "from experiment logs. Reliability is determined by voltage and "
        "current stability over a configurable time window."
    )
    parser.add_argument(
        "--input",
        help="Path to the *_video_ocr.xlsx file. "
        "Default: latest file in logs/",
    )
    parser.add_argument(
        "--output",
        help="Output Excel path. Default: output/reliable_data_<timestamp>.xlsx",
    )
    parser.add_argument(
        "--stability-seconds",
        type=float,
        default=STABILITY_WINDOW_SECONDS,
        help="Baseline window duration in seconds. Default: {0}".format(
            STABILITY_WINDOW_SECONDS
        ),
    )
    parser.add_argument(
        "--percentage-tolerance",
        type=float,
        default=PERCENTAGE_TOLERANCE,
        help="Max deviation from baseline average (fraction). Default: {0}".format(
            PERCENTAGE_TOLERANCE
        ),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    base_dir = get_app_root()
    logs_dir = base_dir / "logs"

    if args.input:
        input_path = Path(args.input).resolve()
    else:
        input_path = find_latest_video_ocr_excel(logs_dir)

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_dir = base_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / "reliable_data_{0}.xlsx".format(ts)

    print("Input: {0}".format(input_path))
    print("Output: {0}".format(output_path))

    rows = load_valid_rows(input_path)
    print("Valid rows loaded: {0}".format(len(rows)))

    segments = find_stable_segments(
        rows,
        stability_seconds=args.stability_seconds,
        percentage_tol=args.percentage_tolerance,
    )
    print("Stable segments found: {0}".format(len(segments)))

    total_rows = write_reliable_excel(segments, output_path)
    print("Reliable rows written: {0}".format(total_rows))
    print("Saved to: {0}".format(output_path))

    for idx, segment in enumerate(segments, start=1):
        stats = compute_segment_stats(segment)
        print(
            "  Segment {0}: {1} rows, V={2}+/-{3}, I={4}+/-{5}, duration={6}s".format(
                idx,
                len(segment),
                stats["voltage_mean"],
                stats["voltage_std"],
                stats["current_mean"],
                stats["current_std"],
                stats["stable_duration_seconds"],
            )
        )

    if HAS_MPL and segments:
        plot_dir = base_dir / "output"
        times, forces, powers, seg_ids = _prepare_plot_data(segments)

        raw_path = _plot_force_electric_curve(
            times, forces, powers, seg_ids, plot_dir, smoothed=False
        )
        print("Raw curve saved: {0}".format(raw_path))

        smoothed_path = _plot_force_electric_curve(
            times, forces, powers, seg_ids, plot_dir, smoothed=True
        )
        print("Smoothed curve saved: {0}".format(smoothed_path))
    elif not HAS_MPL:
        print("matplotlib not installed; skipping curve plots. Install: py -m pip install matplotlib")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
