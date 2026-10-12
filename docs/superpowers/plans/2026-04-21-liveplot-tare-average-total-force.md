# Live Plot Tare, Second Average, and Total Force Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an in-window manual tare button, switch displayed averages to the previous complete natural second, and draw total force as its own live line in the Modbus live plot.

**Architecture:** Keep the feature localized to `scripts/serial_logger_with_plot.py` by extracting testable pure helper functions for second-bucket statistics, tare offset updates, aligned series storage, and title formatting. Then wire those helpers into `LivePlotter`, add a Matplotlib `Button` for runtime tare, and make a small text-only update in `app_launcher.py` so the launcher explains the new live-plot behavior.

**Tech Stack:** Python 3, tkinter, matplotlib, pyserial, openpyxl, standard-library `unittest`

---

## File Map

- Modify: `scripts/serial_logger_with_plot.py` — add import-safe backend selection, pure helper functions, total-force math, previous-second average logic, manual tare handling, and the Matplotlib tare button.
- Modify: `app_launcher.py` — update the Modbus live-plot hint text to mention runtime tare and total-force display.
- Create: `tests/__init__.py` — make `tests` importable for `python -m unittest`.
- Create: `tests/test_serial_logger_with_plot.py` — cover pure helper functions with TDD-friendly unit tests.

### Task 1: Make the live-plot module testable and add previous-second statistics helpers

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_serial_logger_with_plot.py`
- Modify: `scripts/serial_logger_with_plot.py:1-210`

- [ ] **Step 1: Write the failing test**

Create `tests/__init__.py` with this exact content:

```python
# Tests package for the experiment software.
```

Create `tests/test_serial_logger_with_plot.py` with this exact content:

```python
import importlib
import os
import unittest
from datetime import datetime

os.environ["SERIAL_LOGGER_MPL_BACKEND"] = "Agg"

serial_logger_with_plot = importlib.import_module("scripts.serial_logger_with_plot")


class PreviousSecondAverageTests(unittest.TestCase):
    def test_previous_second_average_uses_only_last_complete_second(self) -> None:
        buckets = {}
        serial_logger_with_plot.record_second_bucket(
            buckets,
            datetime(2026, 4, 21, 12, 0, 4, 100000),
            {
                "weight_ch1": 10.0,
                "weight_ch2": 20.0,
                "weight_ch3": 30.0,
                serial_logger_with_plot.TOTAL_FORCE_NAME: 60.0,
            },
        )
        serial_logger_with_plot.record_second_bucket(
            buckets,
            datetime(2026, 4, 21, 12, 0, 4, 800000),
            {
                "weight_ch1": 14.0,
                "weight_ch2": 24.0,
                "weight_ch3": 34.0,
                serial_logger_with_plot.TOTAL_FORCE_NAME: 72.0,
            },
        )
        serial_logger_with_plot.record_second_bucket(
            buckets,
            datetime(2026, 4, 21, 12, 0, 5, 100000),
            {
                "weight_ch1": 999.0,
                "weight_ch2": 999.0,
                "weight_ch3": 999.0,
                serial_logger_with_plot.TOTAL_FORCE_NAME: 999.0,
            },
        )

        second_ts, averages = serial_logger_with_plot.compute_previous_second_averages(
            buckets,
            datetime(2026, 4, 21, 12, 0, 5, 300000),
        )

        self.assertEqual(second_ts, datetime(2026, 4, 21, 12, 0, 4))
        self.assertEqual(averages["weight_ch1"], 12.0)
        self.assertEqual(averages["weight_ch2"], 22.0)
        self.assertEqual(averages["weight_ch3"], 32.0)
        self.assertEqual(averages[serial_logger_with_plot.TOTAL_FORCE_NAME], 66.0)

    def test_compute_total_force_requires_all_channels(self) -> None:
        total_force = serial_logger_with_plot.compute_total_force(
            {"weight_ch1": 1.0, "weight_ch2": 2.0, "weight_ch3": 3.0},
            ["weight_ch1", "weight_ch2", "weight_ch3"],
        )
        missing_total_force = serial_logger_with_plot.compute_total_force(
            {"weight_ch1": 1.0, "weight_ch2": 2.0},
            ["weight_ch1", "weight_ch2", "weight_ch3"],
        )

        self.assertEqual(total_force, 6.0)
        self.assertIsNone(missing_total_force)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_serial_logger_with_plot.PreviousSecondAverageTests -v`

Expected: FAIL with an import or attribute error mentioning `SERIAL_LOGGER_MPL_BACKEND`, `TOTAL_FORCE_NAME`, `record_second_bucket`, or `compute_previous_second_averages` because those test hooks do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Update the top of `scripts/serial_logger_with_plot.py` so it contains these exact additions and replacements near the import/helper section:

```python
import os
import struct
import sys
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

import matplotlib

matplotlib.use(os.environ.get("SERIAL_LOGGER_MPL_BACKEND", "TkAgg"))
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
```

Add this constant directly under `MODBUS_EXCEPTION_CODES`:

```python
TOTAL_FORCE_NAME = "total_force"
```

Add these helper functions directly under `decode_value()`:

```python
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
    bucket = buckets.setdefault(second_key, {})
    for name, value in values.items():
        if value is None:
            continue
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m unittest tests.test_serial_logger_with_plot.PreviousSecondAverageTests -v`

Expected:

```text
test_compute_total_force_requires_all_channels ... ok
test_previous_second_average_uses_only_last_complete_second ... ok
```

- [ ] **Step 5: Commit**

```bash
git add tests/__init__.py tests/test_serial_logger_with_plot.py scripts/serial_logger_with_plot.py
git commit -m "feat: add live plot second-average helpers"
```

### Task 2: Add testable tare and aligned-series helpers

**Files:**
- Modify: `tests/test_serial_logger_with_plot.py`
- Modify: `scripts/serial_logger_with_plot.py:180-320`

- [ ] **Step 1: Write the failing test**

Append these test cases to `tests/test_serial_logger_with_plot.py` immediately above the `if __name__ == "__main__":` block:

```python

class TareAndSamplePreparationTests(unittest.TestCase):
    def test_build_manual_tare_offsets_uses_latest_raw_values(self) -> None:
        offsets = serial_logger_with_plot.build_manual_tare_offsets(
            {"weight_ch1": 101.0, "weight_ch2": 202.0, "weight_ch3": 303.0},
            ["weight_ch1", "weight_ch2", "weight_ch3"],
        )

        self.assertEqual(
            offsets,
            {"weight_ch1": 101.0, "weight_ch2": 202.0, "weight_ch3": 303.0},
        )

    def test_prepare_plot_sample_applies_offsets_and_adds_total_force(self) -> None:
        sample = serial_logger_with_plot.prepare_plot_sample(
            {"weight_ch1": 110.0, "weight_ch2": 215.0, "weight_ch3": 320.0},
            {"weight_ch1": 100.0, "weight_ch2": 200.0, "weight_ch3": 300.0},
            ["weight_ch1", "weight_ch2", "weight_ch3"],
        )

        self.assertEqual(sample["weight_ch1"], 10.0)
        self.assertEqual(sample["weight_ch2"], 15.0)
        self.assertEqual(sample["weight_ch3"], 20.0)
        self.assertEqual(sample[serial_logger_with_plot.TOTAL_FORCE_NAME], 45.0)

    def test_append_series_snapshot_fills_missing_values_with_nan(self) -> None:
        history = {
            "weight_ch1": [],
            "weight_ch2": [],
            "weight_ch3": [],
            serial_logger_with_plot.TOTAL_FORCE_NAME: [],
        }

        serial_logger_with_plot.append_series_snapshot(
            history,
            [
                "weight_ch1",
                "weight_ch2",
                "weight_ch3",
                serial_logger_with_plot.TOTAL_FORCE_NAME,
            ],
            {"weight_ch1": 1.0, "weight_ch2": 2.0},
        )

        self.assertEqual(history["weight_ch1"][0], 1.0)
        self.assertEqual(history["weight_ch2"][0], 2.0)
        self.assertTrue(serial_logger_with_plot.math.isnan(history["weight_ch3"][0]))
        self.assertTrue(serial_logger_with_plot.math.isnan(history[serial_logger_with_plot.TOTAL_FORCE_NAME][0]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_serial_logger_with_plot.TareAndSamplePreparationTests -v`

Expected: FAIL with attribute errors for `build_manual_tare_offsets`, `prepare_plot_sample`, or `append_series_snapshot`.

- [ ] **Step 3: Write minimal implementation**

Add these helper functions directly under `compute_previous_second_averages()` in `scripts/serial_logger_with_plot.py`:

```python
def build_manual_tare_offsets(
    last_raw_values: Dict[str, float],
    channel_names: Sequence[str],
) -> Dict[str, float]:
    return {
        name: last_raw_values[name]
        for name in channel_names
        if name in last_raw_values
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
        history[name].append(float("nan") if value is None else value)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m unittest tests.test_serial_logger_with_plot.TareAndSamplePreparationTests -v`

Expected:

```text
test_append_series_snapshot_fills_missing_values_with_nan ... ok
test_build_manual_tare_offsets_uses_latest_raw_values ... ok
test_prepare_plot_sample_applies_offsets_and_adds_total_force ... ok
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_serial_logger_with_plot.py scripts/serial_logger_with_plot.py
git commit -m "feat: add live plot tare helpers"
```

### Task 3: Add title formatting tests, integrate helpers into `LivePlotter`, and wire the tare button

**Files:**
- Modify: `tests/test_serial_logger_with_plot.py`
- Modify: `scripts/serial_logger_with_plot.py:299-456`
- Modify: `app_launcher.py:175-186`

- [ ] **Step 1: Write the failing test**

Append this test class to `tests/test_serial_logger_with_plot.py` immediately above the `if __name__ == "__main__":` block:

```python

class TitleFormattingTests(unittest.TestCase):
    def test_format_previous_second_title_includes_second_force_and_tare_message(self) -> None:
        title = serial_logger_with_plot.format_previous_second_title(
            datetime(2026, 4, 21, 12, 0, 4),
            {
                "weight_ch1": 1.0,
                "weight_ch2": 2.0,
                "weight_ch3": 3.0,
                serial_logger_with_plot.TOTAL_FORCE_NAME: 6.0,
            },
            [
                "weight_ch1",
                "weight_ch2",
                "weight_ch3",
                serial_logger_with_plot.TOTAL_FORCE_NAME,
            ],
            "已去皮 12:00:05",
        )

        self.assertIn("已去皮 12:00:05", title)
        self.assertIn("上一秒均值 12:00:04", title)
        self.assertIn("weight_ch1=1.00", title)
        self.assertIn("total_force=6.00", title)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_serial_logger_with_plot.TitleFormattingTests -v`

Expected: FAIL with an attribute error for `format_previous_second_title`.

- [ ] **Step 3: Write minimal implementation**

Add this helper directly under `append_series_snapshot()` in `scripts/serial_logger_with_plot.py`:

```python
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
```

Replace the current `LivePlotter` class in `scripts/serial_logger_with_plot.py` with this version:

```python
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
        self.all_times: List[datetime] = []
        self.all_values: Dict[str, List[float]] = {name: [] for name in self.plot_series_names}
        self.raw_lines: Dict[str, Any] = {}
        self.smooth_lines: Dict[str, Any] = {}
        self.avg_lines: Dict[str, Any] = {}

        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        plt.subplots_adjust(top=0.86)

        for i, name in enumerate(self.plot_series_names):
            color = self.COLORS[i % len(self.COLORS)]
            raw_line, = self.ax.plot([], [], color=color, linewidth=0.8, alpha=0.3, markersize=2)
            self.raw_lines[name] = raw_line
            smooth_line, = self.ax.plot([], [], color=color, linewidth=2.0, label=name)
            self.smooth_lines[name] = smooth_line
            avg_line, = self.ax.plot([], [], color=color, linestyle="--", linewidth=1.2, label="Avg {0}".format(name))
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

        self.offsets.update(build_manual_tare_offsets(self.last_raw_values, self.channel_names))
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

        if not self.tare_done:
            self._tare(ts, values)
            return

        sample = prepare_plot_sample(values, self.offsets, self.channel_names)

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
        return list(np.convolve(padded, kernel, mode="valid")[:len(values)])

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

    def close(self) -> None:
        plt.close(self.fig)
```

Update the Modbus help text in `app_launcher.py` so the label at the end of `_build_modbus_tab()` becomes:

```python
        ttk.Label(parent, text="“开始实时曲线采集”会打开独立曲线窗口，支持测定过程中手动去皮，并显示合力曲线与上一秒平均值。").grid(
            row=4,
            column=1,
            sticky="w",
            pady=(0, 10),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m unittest tests.test_serial_logger_with_plot.TitleFormattingTests -v`

Expected:

```text
test_format_previous_second_title_includes_second_force_and_tare_message ... ok
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_serial_logger_with_plot.py scripts/serial_logger_with_plot.py app_launcher.py
git commit -m "feat: add live plot tare button and total force line"
```

### Task 4: Run the regression and smoke-verification loop

**Files:**
- Modify: `scripts/serial_logger_with_plot.py` if any test or smoke-run fixes are required
- Modify: `app_launcher.py` if the launcher text or live-plot launch flow needs a final correction
- Test: `tests/test_serial_logger_with_plot.py`

- [ ] **Step 1: Run the full targeted unit suite**

Run: `py -m unittest tests.test_serial_logger_with_plot -v`

Expected: all helper tests pass, including previous-second averages, tare helper behavior, aligned history handling, and title formatting.

- [ ] **Step 2: Run a syntax smoke check on the touched files**

Run: `py -m py_compile scripts/serial_logger_with_plot.py app_launcher.py tests/test_serial_logger_with_plot.py`

Expected: no output.

- [ ] **Step 3: Manually smoke test the launcher and live plot**

Run: `py app_launcher.py`

Verify all of the following manually:

```text
1. Open “Modbus 采集”.
2. Confirm the hint text now mentions hand tare, total-force curve, and previous-second average.
3. Start “开始实时曲线采集”.
4. In the plot window, confirm a visible “去皮” button exists.
5. Click “去皮” during measurement and confirm only subsequent samples re-zero.
6. Confirm the title updates at most once per second for averages.
7. Confirm the legend includes total_force and the total-force line is drawn.
```

- [ ] **Step 4: Fix anything found and re-run the same checks**

If the smoke test exposes issues, make only the minimum code changes needed, then re-run:

```bash
py -m unittest tests.test_serial_logger_with_plot -v
py -m py_compile scripts/serial_logger_with_plot.py app_launcher.py tests/test_serial_logger_with_plot.py
```

Expected: both commands succeed before moving on.

- [ ] **Step 5: Commit**

```bash
git add tests/test_serial_logger_with_plot.py scripts/serial_logger_with_plot.py app_launcher.py
git commit -m "test: verify live plot tare and total force workflow"
```
