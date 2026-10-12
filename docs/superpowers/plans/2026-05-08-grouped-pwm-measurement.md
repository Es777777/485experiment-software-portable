# Grouped PWM Measurement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an in-window grouped PWM measurement workflow that records PWM, start/end Beijing timestamps, manual total current, interval average total force, and exports all completed groups to a dated Excel file.

**Architecture:** Keep the feature centered in `scripts/serial_logger_with_plot.py` by introducing small pure helpers for grouped measurement state, sample capture, average calculation, and export row generation, then wire those helpers into `LivePlotter` and a compact control panel inside the existing live plot window. Preserve the current launcher entry in `app_launcher.py`, and export a single worksheet whose first columns show per-group summaries and whose later columns expand raw sample data per group.

**Tech Stack:** Python 3, tkinter, matplotlib, pyserial, openpyxl, standard-library `unittest`

---

## File Map

- Modify: `scripts/serial_logger_with_plot.py` - add grouped-measurement dataclasses, lifecycle helpers, UI controls, interval sample capture, and workbook export.
- Modify: `tests/test_serial_logger_with_plot.py` - add failing tests first for group lifecycle, interval averaging, reset behavior, export headers, and dated filenames.
- Modify: `app_launcher.py` - update the live-plot hint text so the launcher mentions PWM grouping, manual total current entry, and export.

### Task 1: Add grouped-measurement helper types and pure functions

**Files:**
- Modify: `tests/test_serial_logger_with_plot.py`
- Modify: `scripts/serial_logger_with_plot.py`

- [ ] **Step 1: Write the failing test**

Append these tests above `if __name__ == "__main__":` in `tests/test_serial_logger_with_plot.py`:

```python
class GroupedMeasurementHelperTests(unittest.TestCase):
    def test_finish_measurement_uses_only_recorded_group_samples(self) -> None:
        state = serial_logger_with_plot.MeasurementSessionState()
        start_time = datetime(2026, 5, 8, 15, 0, 0, 100000)
        end_time = datetime(2026, 5, 8, 15, 0, 1, 400000)

        serial_logger_with_plot.start_measurement_group(state, "1200", start_time)
        serial_logger_with_plot.record_measurement_sample(
            state,
            datetime(2026, 5, 8, 15, 0, 0, 200000),
            {"weight_ch1": 1.0, "weight_ch2": 2.0, "weight_ch3": 3.0},
            6.0,
        )
        serial_logger_with_plot.record_measurement_sample(
            state,
            datetime(2026, 5, 8, 15, 0, 1, 100000),
            {"weight_ch1": 2.0, "weight_ch2": 3.0, "weight_ch3": 4.0},
            9.0,
        )

        group = serial_logger_with_plot.finish_measurement_group(state, "3.25", end_time)

        self.assertEqual(group.pwm, "1200")
        self.assertEqual(group.start_time, start_time)
        self.assertEqual(group.end_time, end_time)
        self.assertEqual(group.total_current, 3.25)
        self.assertEqual(group.average_total_force, 7.5)
        self.assertEqual(len(group.samples), 2)
        self.assertEqual(len(state.completed_groups), 1)

    def test_finish_measurement_requires_total_force_samples(self) -> None:
        state = serial_logger_with_plot.MeasurementSessionState()
        serial_logger_with_plot.start_measurement_group(
            state,
            "800",
            datetime(2026, 5, 8, 15, 1, 0),
        )

        with self.assertRaisesRegex(ValueError, "No valid total force samples"):
            serial_logger_with_plot.finish_measurement_group(
                state,
                "1.20",
                datetime(2026, 5, 8, 15, 1, 1),
            )

    def test_reset_for_next_group_keeps_completed_results(self) -> None:
        state = serial_logger_with_plot.MeasurementSessionState(
            completed_groups=[
                serial_logger_with_plot.MeasurementGroupResult(
                    index=1,
                    pwm="600",
                    start_time=datetime(2026, 5, 8, 15, 2, 0),
                    end_time=datetime(2026, 5, 8, 15, 2, 1),
                    total_current=0.8,
                    average_total_force=5.5,
                    samples=[],
                )
            ]
        )
        serial_logger_with_plot.start_measurement_group(
            state,
            "900",
            datetime(2026, 5, 8, 15, 2, 2),
        )

        serial_logger_with_plot.reset_for_next_group(state)

        self.assertEqual(len(state.completed_groups), 1)
        self.assertIsNone(state.current_group)

    def test_build_measurement_export_rows_expands_summary_and_raw_columns(self) -> None:
        groups = [
            serial_logger_with_plot.MeasurementGroupResult(
                index=1,
                pwm="700",
                start_time=datetime(2026, 5, 8, 15, 3, 0),
                end_time=datetime(2026, 5, 8, 15, 3, 2),
                total_current=1.5,
                average_total_force=8.0,
                samples=[
                    serial_logger_with_plot.MeasurementSample(
                        timestamp=datetime(2026, 5, 8, 15, 3, 0, 100000),
                        raw_values={"weight_ch1": 1.0, "weight_ch2": 2.0, "weight_ch3": 3.0},
                        total_force=6.0,
                    ),
                    serial_logger_with_plot.MeasurementSample(
                        timestamp=datetime(2026, 5, 8, 15, 3, 1, 100000),
                        raw_values={"weight_ch1": 2.0, "weight_ch2": 3.0, "weight_ch3": 4.0},
                        total_force=9.0,
                    ),
                ],
            )
        ]

        headers, rows = serial_logger_with_plot.build_measurement_export_rows(groups)

        self.assertEqual(
            headers[:6],
            ["序号", "PWM", "开始时间(北京时间)", "结束时间(北京时间)", "总电流", "合力平均值"],
        )
        self.assertIn("原始时间戳_1", headers)
        self.assertIn("原始合力_2", headers)
        self.assertIn("原始ch1_1", headers)
        self.assertEqual(rows[0][0], 1)
        self.assertEqual(rows[0][1], "700")

    def test_build_measurement_export_path_contains_datetime(self) -> None:
        export_path = serial_logger_with_plot.build_measurement_export_path(
            Path("C:/temp/output"),
            datetime(2026, 5, 8, 15, 4, 5),
        )

        self.assertEqual(export_path.name, "measurement_results_20260508_150405.xlsx")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_serial_logger_with_plot.GroupedMeasurementHelperTests -v`
Expected: FAIL with attribute errors mentioning `MeasurementSessionState`, `start_measurement_group`, `finish_measurement_group`, `build_measurement_export_rows`, or `build_measurement_export_path`.

- [ ] **Step 3: Write minimal implementation**

Add these definitions to `scripts/serial_logger_with_plot.py` below `TOTAL_FORCE_NAME = "total_force"`:

```python
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
    completed_groups: List[MeasurementGroupResult] | None = None
    current_group: Optional[ActiveMeasurementGroup] = None

    def __post_init__(self) -> None:
        if self.completed_groups is None:
            self.completed_groups = []
```

Add these helper functions below `format_previous_second_title(...)`:

```python
def start_measurement_group(state: MeasurementSessionState, pwm: str, start_time: datetime) -> ActiveMeasurementGroup:
    cleaned_pwm = pwm.strip()
    if not cleaned_pwm:
        raise ValueError("PWM is required")
    if state.current_group is not None:
        raise ValueError("Measurement already in progress")
    current_group = ActiveMeasurementGroup(pwm=cleaned_pwm, start_time=start_time, samples=[])
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
        MeasurementSample(timestamp=timestamp, raw_values=dict(raw_values), total_force=float(total_force))
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
        average_total_force=sum(sample.total_force for sample in samples) / len(samples),
        samples=samples,
    )
    state.completed_groups.append(result)
    state.current_group = None
    return result


def reset_for_next_group(state: MeasurementSessionState) -> None:
    state.current_group = None


def build_measurement_export_path(output_dir: Path, now: datetime) -> Path:
    return output_dir / "measurement_results_{0}.xlsx".format(now.strftime("%Y%m%d_%H%M%S"))


def build_measurement_export_rows(groups: Sequence[MeasurementGroupResult]) -> Tuple[List[str], List[List[Any]]]:
    max_samples = max((len(group.samples) for group in groups), default=0)
    headers = ["序号", "PWM", "开始时间(北京时间)", "结束时间(北京时间)", "总电流", "合力平均值"]
    for index in range(1, max_samples + 1):
        headers.extend([
            "原始时间戳_{0}".format(index),
            "原始合力_{0}".format(index),
            "原始ch1_{0}".format(index),
            "原始ch2_{0}".format(index),
            "原始ch3_{0}".format(index),
        ])

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
            row.extend([
                sample.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f"),
                sample.total_force,
                sample.raw_values.get("weight_ch1", ""),
                sample.raw_values.get("weight_ch2", ""),
                sample.raw_values.get("weight_ch3", ""),
            ])
        for _ in range(len(group.samples), max_samples):
            row.extend(["", "", "", "", ""])
        rows.append(row)
    return headers, rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m unittest tests.test_serial_logger_with_plot.GroupedMeasurementHelperTests -v`
Expected: all five grouped-measurement helper tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_serial_logger_with_plot.py scripts/serial_logger_with_plot.py
git commit -m "feat: add grouped measurement helpers"
```

### Task 2: Wire grouped sampling into `LivePlotter`

**Files:**
- Modify: `tests/test_serial_logger_with_plot.py`
- Modify: `scripts/serial_logger_with_plot.py`

- [ ] **Step 1: Write the failing test**

Append this test above `if __name__ == "__main__":` in `tests/test_serial_logger_with_plot.py`:

```python
class LivePlotterGroupedMeasurementTests(unittest.TestCase):
    def test_live_plotter_records_samples_only_while_group_is_active(self) -> None:
        plotter = serial_logger_with_plot.LivePlotter(
            ["weight_ch1", "weight_ch2", "weight_ch3"],
            window_seconds=60,
            smooth=False,
        )
        plotter.tare_done = True

        try:
            plotter.add_point(
                datetime(2026, 5, 8, 15, 5, 0),
                {"weight_ch1": 1.0, "weight_ch2": 2.0, "weight_ch3": 3.0},
            )
            self.assertEqual(len(plotter.measurement_state.completed_groups), 0)

            serial_logger_with_plot.start_measurement_group(
                plotter.measurement_state,
                "1100",
                datetime(2026, 5, 8, 15, 5, 0, 100000),
            )
            plotter.add_point(
                datetime(2026, 5, 8, 15, 5, 0, 200000),
                {"weight_ch1": 2.0, "weight_ch2": 3.0, "weight_ch3": 4.0},
            )
            plotter.add_point(
                datetime(2026, 5, 8, 15, 5, 0, 300000),
                {"weight_ch1": 3.0, "weight_ch2": 4.0, "weight_ch3": 5.0},
            )

            result = serial_logger_with_plot.finish_measurement_group(
                plotter.measurement_state,
                "2.40",
                datetime(2026, 5, 8, 15, 5, 1),
            )

            self.assertEqual(result.average_total_force, 10.5)
            self.assertEqual(len(result.samples), 2)
        finally:
            plotter.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_serial_logger_with_plot.LivePlotterGroupedMeasurementTests -v`
Expected: FAIL because `LivePlotter` does not yet expose `measurement_state` or feed total-force samples into it.

- [ ] **Step 3: Write minimal implementation**

Update `LivePlotter.__init__` in `scripts/serial_logger_with_plot.py` to add this state after `self.last_sample_ts`:

```python
self.measurement_state = MeasurementSessionState()
```

Update `LivePlotter.add_point(...)` so right after `sample = prepare_plot_sample(values, self.offsets, self.channel_names)` it records the raw interval sample:

```python
record_measurement_sample(
    self.measurement_state,
    ts,
    dict(values),
    sample.get(self.total_force_name),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m unittest tests.test_serial_logger_with_plot.LivePlotterGroupedMeasurementTests -v`
Expected: the grouped-sampling test passes.

- [ ] **Step 5: Commit**

```bash
git add tests/test_serial_logger_with_plot.py scripts/serial_logger_with_plot.py
git commit -m "feat: record grouped live plot samples"
```

### Task 3: Add live-window controls, export workbook writing, launcher text, and final verification

**Files:**
- Modify: `tests/test_serial_logger_with_plot.py`
- Modify: `scripts/serial_logger_with_plot.py`
- Modify: `app_launcher.py`

- [ ] **Step 1: Write the failing test**

Append this test above `if __name__ == "__main__":` in `tests/test_serial_logger_with_plot.py`:

```python
class MeasurementWorkbookTests(unittest.TestCase):
    def test_write_measurement_workbook_creates_expected_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "measurement_results_20260508_150405.xlsx"
            groups = [
                serial_logger_with_plot.MeasurementGroupResult(
                    index=1,
                    pwm="500",
                    start_time=datetime(2026, 5, 8, 16, 0, 0),
                    end_time=datetime(2026, 5, 8, 16, 0, 1),
                    total_current=0.75,
                    average_total_force=4.5,
                    samples=[
                        serial_logger_with_plot.MeasurementSample(
                            timestamp=datetime(2026, 5, 8, 16, 0, 0, 100000),
                            raw_values={"weight_ch1": 1.0, "weight_ch2": 1.5, "weight_ch3": 2.0},
                            total_force=4.5,
                        )
                    ],
                )
            ]

            serial_logger_with_plot.write_measurement_workbook(output_path, groups)

            workbook = serial_logger_with_plot.load_workbook(output_path)
            worksheet = workbook.active
            headers = [cell.value for cell in worksheet[1]]
            workbook.close()

            self.assertEqual(headers[:6], ["序号", "PWM", "开始时间(北京时间)", "结束时间(北京时间)", "总电流", "合力平均值"])
            self.assertIn("原始时间戳_1", headers)
            self.assertEqual(worksheet.max_row, 2)
```

Also add `import tempfile` near the top of `tests/test_serial_logger_with_plot.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_serial_logger_with_plot.MeasurementWorkbookTests -v`
Expected: FAIL because `write_measurement_workbook(...)` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add this helper below `build_measurement_export_rows(...)` in `scripts/serial_logger_with_plot.py`:

```python
def write_measurement_workbook(output_path: Path, groups: Sequence[MeasurementGroupResult]) -> None:
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
```

Then update `LivePlotter.__init__` to add a small `tkinter` control panel anchored to the figure manager window with these widgets and callbacks:

```python
self.measurement_status_var = tk.StringVar(value="未开始")
self.measurement_pwm_var = tk.StringVar(value="")
self.measurement_current_var = tk.StringVar(value="")
self.measurement_summary_var = tk.StringVar(value="已完成组数: 0")
```

Create buttons wired to methods with these exact names:

```python
def start_measurement(self) -> None:
    start_measurement_group(self.measurement_state, self.measurement_pwm_var.get(), datetime.now())
    self.measurement_status_var.set("测量中")


def finish_measurement(self) -> None:
    result = finish_measurement_group(self.measurement_state, self.measurement_current_var.get(), datetime.now())
    self.measurement_status_var.set("已完成")
    self.measurement_summary_var.set("已完成组数: {0} | 最近一组 PWM={1} | 平均合力={2:.3f}".format(
        len(self.measurement_state.completed_groups),
        result.pwm,
        result.average_total_force,
    ))


def prepare_next_group(self) -> None:
    if self.measurement_state.current_group is not None:
        raise ValueError("Current group is still active")
    reset_for_next_group(self.measurement_state)
    self.measurement_pwm_var.set("")
    self.measurement_current_var.set("")
    self.measurement_status_var.set("未开始")


def export_measurements(self) -> Path:
    if not self.measurement_state.completed_groups:
        raise ValueError("No completed measurement groups")
    output_path = build_measurement_export_path(get_app_root() / "output", datetime.now())
    write_measurement_workbook(output_path, self.measurement_state.completed_groups)
    self.measurement_summary_var.set("已导出: {0}".format(output_path.name))
    return output_path
```

Update the Modbus live-plot hint in `app_launcher.py` to this text:

```python
ttk.Label(parent, text="“开始实时曲线采集”会打开独立曲线窗口，支持测定过程中手动去皮、PWM 分组测量、总电流录入、合力平均值统计和表格导出。")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m unittest tests.test_serial_logger_with_plot.MeasurementWorkbookTests -v`
Expected: the workbook-export test passes.

- [ ] **Step 5: Run the focused and full verification**

Run: `py -m unittest tests.test_serial_logger_with_plot -v`
Expected: all tests in `tests/test_serial_logger_with_plot.py` pass.

Run: `py -m PyInstaller app_launcher.spec`
Expected: build completes successfully and refreshes `dist/实验软件/实验软件.exe`.

- [ ] **Step 6: Commit**

```bash
git add tests/test_serial_logger_with_plot.py scripts/serial_logger_with_plot.py app_launcher.py
git commit -m "feat: add grouped pwm measurement workflow"
```

- [ ] **Step 7: Push and package**

```bash
git push origin main
```

Then copy the fresh packaged output from `dist/实验软件/` into a new dated desktop folder such as `C:/Users/asd/OneDrive/Desktop/实验软件_便携版_20260508/` and verify the new folder contains `实验软件.exe`, `config/`, `logs/`, `output/`, `videos/`, and the updated readme.
