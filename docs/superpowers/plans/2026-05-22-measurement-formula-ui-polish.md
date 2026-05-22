# Measurement Formula UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add grouped-measurement moment calculations with math-formula display, polish the measurement panel into a more professional instrument-style UI, and add lightweight author/GitHub attribution without breaking the existing acquisition flow.

**Architecture:** Keep the change inside `scripts/serial_logger_with_plot.py`, where grouped measurement state, export logic, and the Tk measurement panel already live. Extend the grouped-result data model with averaged channel values and moment results, render formulas with Matplotlib mathtext embedded into the existing Tk window, and verify the behavior with targeted `unittest` coverage before touching visual layout code.

**Tech Stack:** Python 3, Tkinter/`ttk`, Matplotlib (`TkAgg`, mathtext, `FigureCanvasTkAgg`), `openpyxl`, `unittest`

---

## File Map

- Modify: `scripts/serial_logger_with_plot.py` - add group-average moment calculation helpers, extend measurement result data, render math formulas, restyle the grouped measurement panel, and add footer attribution.
- Modify: `tests/test_serial_logger_with_plot.py` - add failing tests first for moment calculations, formula specs, grouped-result summaries, export columns, and panel footer metadata.
- Reference: `docs/superpowers/specs/2026-05-22-measurement-formula-ui-polish-design.md` - approved design source for formula behavior, UI direction, and attribution rules.

## Task 1: Add group-average moment calculations and export columns

**Files:**
- Modify: `tests/test_serial_logger_with_plot.py`
- Modify: `scripts/serial_logger_with_plot.py`

- [ ] **Step 1: Write the failing helper and export tests**

Append these tests to `tests/test_serial_logger_with_plot.py` inside `GroupedMeasurementHelperTests`:

```python
    def test_finish_measurement_computes_group_average_channels_and_moments(self) -> None:
        state = serial_logger_with_plot.MeasurementSessionState()
        serial_logger_with_plot.start_measurement_group(
            state,
            "1200",
            datetime(2026, 5, 22, 10, 0, 0),
        )
        serial_logger_with_plot.record_measurement_sample(
            state,
            datetime(2026, 5, 22, 10, 0, 0, 100000),
            {"weight_ch1": 1.0, "weight_ch2": 4.0, "weight_ch3": 2.0},
            7.0,
        )
        serial_logger_with_plot.record_measurement_sample(
            state,
            datetime(2026, 5, 22, 10, 0, 0, 200000),
            {"weight_ch1": 3.0, "weight_ch2": 8.0, "weight_ch3": 6.0},
            17.0,
        )

        result = serial_logger_with_plot.finish_measurement_group(
            state,
            "2.50",
            datetime(2026, 5, 22, 10, 0, 1),
        )

        self.assertEqual(result.average_t1, 2.0)
        self.assertEqual(result.average_t2, 6.0)
        self.assertEqual(result.average_t3, 4.0)
        self.assertAlmostEqual(result.moment_y, 0.0)
        self.assertAlmostEqual(result.moment_x, serial_logger_with_plot.math.sqrt(3) * 2.0)
        self.assertAlmostEqual(result.moment_magnitude, serial_logger_with_plot.math.sqrt(12.0))
        self.assertAlmostEqual(result.theta_radians, serial_logger_with_plot.math.pi / 2)
        self.assertAlmostEqual(result.theta_degrees, 90.0)

    def test_build_measurement_export_rows_includes_moment_columns(self) -> None:
        groups = [
            serial_logger_with_plot.MeasurementGroupResult(
                index=1,
                pwm="700",
                start_time=datetime(2026, 5, 22, 10, 1, 0),
                end_time=datetime(2026, 5, 22, 10, 1, 1),
                total_current=1.5,
                average_total_force=8.0,
                average_t1=2.0,
                average_t2=6.0,
                average_t3=4.0,
                moment_y=0.0,
                moment_x=serial_logger_with_plot.math.sqrt(12.0),
                moment_magnitude=serial_logger_with_plot.math.sqrt(12.0),
                theta_radians=serial_logger_with_plot.math.pi / 2,
                theta_degrees=90.0,
                samples=[
                    serial_logger_with_plot.MeasurementSample(
                        timestamp=datetime(2026, 5, 22, 10, 1, 0, 100000),
                        raw_values={
                            "weight_ch1": 1.0,
                            "weight_ch2": 2.0,
                            "weight_ch3": 3.0,
                        },
                        total_force=6.0,
                    )
                ],
            )
        ]

        headers, rows = serial_logger_with_plot.build_measurement_export_rows(groups)

        self.assertEqual(
            headers[:13],
            [
                "序号",
                "PWM",
                "开始时间(北京时间)",
                "结束时间(北京时间)",
                "总电流",
                "合力平均值",
                "T1平均值",
                "T2平均值",
                "T3平均值",
                "M_y",
                "M_x",
                "M",
                "theta(度)",
            ],
        )
        self.assertEqual(rows[0][6], 2.0)
        self.assertEqual(rows[0][7], 6.0)
        self.assertEqual(rows[0][8], 4.0)
        self.assertAlmostEqual(rows[0][12], 90.0)
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `py -m unittest tests.test_serial_logger_with_plot.GroupedMeasurementHelperTests.test_finish_measurement_computes_group_average_channels_and_moments tests.test_serial_logger_with_plot.GroupedMeasurementHelperTests.test_build_measurement_export_rows_includes_moment_columns -v`

Expected: FAIL because `MeasurementGroupResult` does not yet define `average_t1`/`moment_y` fields, `finish_measurement_group()` does not compute those values, and `build_measurement_export_rows()` does not include the new headers.

- [ ] **Step 3: Write the minimal implementation for averaged channels and moments**

In `scripts/serial_logger_with_plot.py`, update the grouped-result dataclass and add helper functions near the existing grouped-measurement helpers:

```python
@dataclass(frozen=True)
class MeasurementGroupResult:
    index: int
    pwm: str
    start_time: datetime
    end_time: datetime
    total_current: float
    average_total_force: float
    average_t1: float
    average_t2: float
    average_t3: float
    moment_y: float
    moment_x: float
    moment_magnitude: float
    theta_radians: float
    theta_degrees: float
    samples: List[MeasurementSample]


def compute_group_channel_averages(samples: Sequence[MeasurementSample]) -> Tuple[float, float, float]:
    t1_values = [sample.raw_values["weight_ch1"] for sample in samples if "weight_ch1" in sample.raw_values]
    t2_values = [sample.raw_values["weight_ch2"] for sample in samples if "weight_ch2" in sample.raw_values]
    t3_values = [sample.raw_values["weight_ch3"] for sample in samples if "weight_ch3" in sample.raw_values]
    if not t1_values or not t2_values or not t3_values:
        raise ValueError("当前分组缺少完整的三路力数据，无法计算力矩")
    return (
        sum(t1_values) / len(t1_values),
        sum(t2_values) / len(t2_values),
        sum(t3_values) / len(t3_values),
    )


def compute_moment_metrics(t1: float, t2: float, t3: float) -> Tuple[float, float, float, float, float]:
    moment_y = 0.5 * t1 + 0.5 * t2 - t3
    moment_x = math.sqrt(3) / 2.0 * (t2 - t1)
    moment_magnitude = math.sqrt(moment_x ** 2 + moment_y ** 2)
    theta_radians = math.atan2(moment_x, moment_y)
    theta_degrees = math.degrees(theta_radians)
    return moment_y, moment_x, moment_magnitude, theta_radians, theta_degrees
```

Then update `finish_measurement_group()` and `build_measurement_export_rows()`:

```python
    average_t1, average_t2, average_t3 = compute_group_channel_averages(samples)
    moment_y, moment_x, moment_magnitude, theta_radians, theta_degrees = (
        compute_moment_metrics(average_t1, average_t2, average_t3)
    )
    result = MeasurementGroupResult(
        index=len(state.completed_groups) + 1,
        pwm=state.current_group.pwm,
        start_time=state.current_group.start_time,
        end_time=end_time,
        total_current=total_current,
        average_total_force=sum(sample.total_force for sample in samples) / len(samples),
        average_t1=average_t1,
        average_t2=average_t2,
        average_t3=average_t3,
        moment_y=moment_y,
        moment_x=moment_x,
        moment_magnitude=moment_magnitude,
        theta_radians=theta_radians,
        theta_degrees=theta_degrees,
        samples=samples,
    )
```

```python
    headers = [
        "序号",
        "PWM",
        "开始时间(北京时间)",
        "结束时间(北京时间)",
        "总电流",
        "合力平均值",
        "T1平均值",
        "T2平均值",
        "T3平均值",
        "M_y",
        "M_x",
        "M",
        "theta(度)",
    ]
```

```python
        row = [
            group.index,
            group.pwm,
            group.start_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
            group.end_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
            group.total_current,
            group.average_total_force,
            group.average_t1,
            group.average_t2,
            group.average_t3,
            group.moment_y,
            group.moment_x,
            group.moment_magnitude,
            group.theta_degrees,
        ]
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `py -m unittest tests.test_serial_logger_with_plot.GroupedMeasurementHelperTests.test_finish_measurement_computes_group_average_channels_and_moments tests.test_serial_logger_with_plot.GroupedMeasurementHelperTests.test_build_measurement_export_rows_includes_moment_columns -v`

Expected: PASS.

- [ ] **Step 5: Run the broader grouped-measurement suite**

Run: `py -m unittest tests.test_serial_logger_with_plot.GroupedMeasurementHelperTests tests.test_serial_logger_with_plot.MeasurementWorkbookTests -v`

Expected: PASS, confirming the new result fields did not break workbook creation or the older grouped-measurement helpers.

- [ ] **Step 6: Commit**

```bash
git add tests/test_serial_logger_with_plot.py scripts/serial_logger_with_plot.py
git commit -m "feat: add grouped measurement moment calculations"
```

## Task 2: Add math-formula specs and footer metadata for the polished panel

**Files:**
- Modify: `tests/test_serial_logger_with_plot.py`
- Modify: `scripts/serial_logger_with_plot.py`

- [ ] **Step 1: Write the failing display-helper tests**

Append these tests to `tests/test_serial_logger_with_plot.py` inside a new `GroupedMeasurementDisplayHelperTests` class:

```python
class GroupedMeasurementDisplayHelperTests(unittest.TestCase):
    def test_build_moment_formula_specs_returns_mathtext_expressions(self) -> None:
        result = serial_logger_with_plot.MeasurementGroupResult(
            index=1,
            pwm="1300",
            start_time=datetime(2026, 5, 22, 10, 2, 0),
            end_time=datetime(2026, 5, 22, 10, 2, 1),
            total_current=2.8,
            average_total_force=12.0,
            average_t1=2.0,
            average_t2=6.0,
            average_t3=4.0,
            moment_y=0.0,
            moment_x=serial_logger_with_plot.math.sqrt(12.0),
            moment_magnitude=serial_logger_with_plot.math.sqrt(12.0),
            theta_radians=serial_logger_with_plot.math.pi / 2,
            theta_degrees=90.0,
            samples=[],
        )

        specs = serial_logger_with_plot.build_moment_formula_specs(result)

        self.assertEqual([spec.key for spec in specs], ["M_y", "M_x", "M", "theta"])
        self.assertIn(r"\\frac{1}{2}T_1", specs[0].expression)
        self.assertIn(r"\\frac{\\sqrt{3}}{2}", specs[1].expression)
        self.assertIn(r"\\sqrt{M_x^2 + M_y^2}", specs[2].expression)
        self.assertIn(r"\\theta = \\operatorname{atan2}(M_x, M_y)", specs[3].expression)
        self.assertEqual(specs[3].value_text, "90.00°")

    def test_build_measurement_footer_text_includes_author_and_github(self) -> None:
        footer = serial_logger_with_plot.build_measurement_footer_text()

        self.assertIn("Maintained by Chenghang Li", footer)
        self.assertIn("github.com/Es777777/485experiment-software-portable", footer)
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `py -m unittest tests.test_serial_logger_with_plot.GroupedMeasurementDisplayHelperTests -v`

Expected: FAIL because neither `build_moment_formula_specs()` nor `build_measurement_footer_text()` exists.

- [ ] **Step 3: Write the minimal display-helper implementation**

In `scripts/serial_logger_with_plot.py`, add a lightweight dataclass plus helper functions after the grouped-measurement export helpers:

```python
@dataclass(frozen=True)
class FormulaDisplaySpec:
    key: str
    expression: str
    value_text: str


def build_moment_formula_specs(result: MeasurementGroupResult) -> List[FormulaDisplaySpec]:
    return [
        FormulaDisplaySpec(
            key="M_y",
            expression=r"$M_y = \\frac{1}{2}T_1 + \\frac{1}{2}T_2 - T_3$",
            value_text="{0:.3f}".format(result.moment_y),
        ),
        FormulaDisplaySpec(
            key="M_x",
            expression=r"$M_x = \\frac{\\sqrt{3}}{2}(T_2 - T_1)$",
            value_text="{0:.3f}".format(result.moment_x),
        ),
        FormulaDisplaySpec(
            key="M",
            expression=r"$M = \\sqrt{M_x^2 + M_y^2}$",
            value_text="{0:.3f}".format(result.moment_magnitude),
        ),
        FormulaDisplaySpec(
            key="theta",
            expression=r"$\\theta = \\operatorname{atan2}(M_x, M_y)$",
            value_text="{0:.2f}°".format(result.theta_degrees),
        ),
    ]


def build_measurement_footer_text() -> str:
    return (
        "485 Experiment Software  |  "
        "Maintained by Chenghang Li  |  "
        "github.com/Es777777/485experiment-software-portable"
    )
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `py -m unittest tests.test_serial_logger_with_plot.GroupedMeasurementDisplayHelperTests -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_serial_logger_with_plot.py scripts/serial_logger_with_plot.py
git commit -m "feat: add measurement formula display metadata"
```

## Task 3: Update the Tk measurement panel to show formulas, values, and polished attribution

**Files:**
- Modify: `tests/test_serial_logger_with_plot.py`
- Modify: `scripts/serial_logger_with_plot.py`

- [ ] **Step 1: Write the failing LivePlotter UI-state tests**

Append these tests to `tests/test_serial_logger_with_plot.py` inside `LivePlotterGroupedMeasurementTests`:

```python
    def test_finish_measurement_updates_formula_values_and_footer(self) -> None:
        plotter = serial_logger_with_plot.LivePlotter(
            ["weight_ch1", "weight_ch2", "weight_ch3"],
            window_seconds=60,
            smooth=False,
        )
        plotter.tare_done = True

        try:
            plotter.measurement_pwm_var.set("1300")
            plotter.start_measurement()
            plotter.add_point(
                datetime(2026, 5, 22, 10, 3, 0, 100000),
                {"weight_ch1": 1.0, "weight_ch2": 4.0, "weight_ch3": 2.0},
            )
            plotter.add_point(
                datetime(2026, 5, 22, 10, 3, 0, 200000),
                {"weight_ch1": 3.0, "weight_ch2": 8.0, "weight_ch3": 6.0},
            )
            plotter.measurement_current_var.set("2.80")
            plotter.finish_measurement()

            self.assertIn("平均合力=12.000", plotter.measurement_summary_var.get())
            self.assertEqual(plotter.measurement_formula_value_vars["M_y"].get(), "0.000")
            self.assertEqual(plotter.measurement_formula_value_vars["theta"].get(), "90.00°")
            self.assertIn("Maintained by Chenghang Li", plotter.measurement_footer_var.get())
        finally:
            plotter.close()

    def test_prepare_next_group_clears_formula_values_but_keeps_history(self) -> None:
        plotter = serial_logger_with_plot.LivePlotter(
            ["weight_ch1", "weight_ch2", "weight_ch3"],
            window_seconds=60,
            smooth=False,
        )
        plotter.tare_done = True

        try:
            plotter.measurement_state.completed_groups.append(
                serial_logger_with_plot.MeasurementGroupResult(
                    index=1,
                    pwm="1200",
                    start_time=datetime(2026, 5, 22, 10, 4, 0),
                    end_time=datetime(2026, 5, 22, 10, 4, 1),
                    total_current=2.3,
                    average_total_force=9.5,
                    average_t1=2.0,
                    average_t2=4.0,
                    average_t3=3.0,
                    moment_y=0.0,
                    moment_x=serial_logger_with_plot.math.sqrt(3),
                    moment_magnitude=serial_logger_with_plot.math.sqrt(3),
                    theta_radians=serial_logger_with_plot.math.pi / 2,
                    theta_degrees=90.0,
                    samples=[],
                )
            )
            plotter._refresh_measurement_history()
            plotter._apply_measurement_result(None)

            plotter.prepare_next_group()

            self.assertEqual(plotter.measurement_formula_value_vars["M"].get(), "--")
            self.assertEqual(plotter.measurement_formula_value_vars["theta"].get(), "--")
            self.assertIn("1200", plotter.measurement_history_var.get())
        finally:
            plotter.close()
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `py -m unittest tests.test_serial_logger_with_plot.LivePlotterGroupedMeasurementTests.test_finish_measurement_updates_formula_values_and_footer tests.test_serial_logger_with_plot.LivePlotterGroupedMeasurementTests.test_prepare_next_group_clears_formula_values_but_keeps_history -v`

Expected: FAIL because `LivePlotter` does not yet define `measurement_formula_value_vars`, `measurement_footer_var`, or `_apply_measurement_result()`.

- [ ] **Step 3: Implement the minimal LivePlotter state and panel rendering**

In `scripts/serial_logger_with_plot.py`, first add the extra imports near the Matplotlib section:

```python
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
```

Then extend `LivePlotter.__init__()` and `_rebind_measurement_vars()` with formula/value/footer variables:

```python
        self.measurement_formula_value_vars: Dict[str, Any] = {
            "M_y": SimpleStringVar("--"),
            "M_x": SimpleStringVar("--"),
            "M": SimpleStringVar("--"),
            "theta": SimpleStringVar("--"),
        }
        self.measurement_footer_var = SimpleStringVar(build_measurement_footer_text())
        self.measurement_formula_figure: Optional[Figure] = None
        self.measurement_formula_canvas: Any = None
        self.measurement_formula_axes: List[Any] = []
```

```python
        self.measurement_footer_var = self._make_string_var(self.measurement_footer_var.get())
        self.measurement_formula_value_vars = {
            key: self._make_string_var(var.get())
            for key, var in self.measurement_formula_value_vars.items()
        }
```

Add helpers to apply a completed result into the UI and clear it for the next group:

```python
    def _apply_measurement_result(self, result: Optional[MeasurementGroupResult]) -> None:
        if result is None:
            for key in self.measurement_formula_value_vars:
                self.measurement_formula_value_vars[key].set("--")
            self._render_formula_specs([])
            return

        for spec in build_moment_formula_specs(result):
            self.measurement_formula_value_vars[spec.key].set(spec.value_text)
        self._render_formula_specs(build_moment_formula_specs(result))

    def _render_formula_specs(self, specs: Sequence[FormulaDisplaySpec]) -> None:
        if self.measurement_formula_figure is None:
            return
        axes = self.measurement_formula_axes
        for axis in axes:
            axis.clear()
            axis.set_axis_off()
        for axis, spec in zip(axes, specs):
            axis.text(0.02, 0.68, spec.expression, fontsize=13)
            axis.text(0.04, 0.18, "= {0}".format(spec.value_text), fontsize=11, color="#0f4c81")
        if self.measurement_formula_canvas is not None:
            self.measurement_formula_canvas.draw_idle()
```

Refactor `_build_measurement_panel()` so it creates separate frames for inputs, actions, results, history, and footer. Use `ttk.Frame`/`ttk.LabelFrame` widgets, a dedicated formula host, and a footer label:

```python
        panel = ttk.LabelFrame(window, text="分组测量", padding=10)
        panel.pack(side="bottom", fill="x", padx=10, pady=8)

        top_row = ttk.Frame(panel)
        top_row.grid(row=0, column=0, sticky="ew")
        action_row = ttk.Frame(panel)
        action_row.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        result_box = ttk.LabelFrame(panel, text="结果区", padding=8)
        result_box.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        history_box = ttk.LabelFrame(panel, text="历史区", padding=8)
        history_box.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        footer_label = ttk.Label(panel, textvariable=self.measurement_footer_var, anchor="w")
        footer_label.grid(row=4, column=0, sticky="ew", pady=(8, 0))
```

Create the formula figure inside `result_box`:

```python
        self.measurement_formula_figure = Figure(figsize=(6.4, 2.8), dpi=100)
        self.measurement_formula_axes = [
            self.measurement_formula_figure.add_subplot(2, 2, index + 1)
            for index in range(4)
        ]
        for axis in self.measurement_formula_axes:
            axis.set_axis_off()
        self.measurement_formula_canvas = FigureCanvasTkAgg(
            self.measurement_formula_figure,
            master=result_box,
        )
        self.measurement_formula_canvas.get_tk_widget().grid(
            row=1,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(8, 0),
        )
```

Finally, update the workflow methods to apply the richer result state:

```python
        self.measurement_summary_var.set(
            "已完成组数: {0} | 最近一组 PWM={1} | 平均合力={2:.3f}".format(
                len(self.measurement_state.completed_groups),
                result.pwm,
                result.average_total_force,
            )
        )
        self._apply_measurement_result(result)
        self.measurement_footer_var.set(build_measurement_footer_text())
```

```python
        self.measurement_summary_var.set(
            "已完成组数: {0}".format(len(self.measurement_state.completed_groups))
        )
        self._apply_measurement_result(None)
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `py -m unittest tests.test_serial_logger_with_plot.LivePlotterGroupedMeasurementTests.test_finish_measurement_updates_formula_values_and_footer tests.test_serial_logger_with_plot.LivePlotterGroupedMeasurementTests.test_prepare_next_group_clears_formula_values_but_keeps_history -v`

Expected: PASS.

- [ ] **Step 5: Run the full measurement test file**

Run: `py -m unittest tests.test_serial_logger_with_plot -v`

Expected: PASS, including the old grouped-measurement tests and the new formula/display coverage.

- [ ] **Step 6: Commit**

```bash
git add tests/test_serial_logger_with_plot.py scripts/serial_logger_with_plot.py
git commit -m "feat: polish grouped measurement panel"
```

## Task 4: Add low-risk theme polish and verify the final user-facing behavior

**Files:**
- Modify: `tests/test_serial_logger_with_plot.py`
- Modify: `scripts/serial_logger_with_plot.py`

- [ ] **Step 1: Write the failing theme-state tests**

Append these tests to `tests/test_serial_logger_with_plot.py` inside `LivePlotterGroupedMeasurementTests`:

```python
    def test_measurement_theme_palette_matches_instrument_console_mix(self) -> None:
        palette = serial_logger_with_plot.build_measurement_theme_palette()

        self.assertEqual(palette["panel_background"], "#f4f7fb")
        self.assertEqual(palette["card_background"], "#ffffff")
        self.assertEqual(palette["accent"], "#0f4c81")
        self.assertEqual(palette["status_active"], "#d97706")
        self.assertEqual(palette["status_done"], "#0f766e")
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `py -m unittest tests.test_serial_logger_with_plot.LivePlotterGroupedMeasurementTests.test_measurement_theme_palette_matches_instrument_console_mix -v`

Expected: FAIL because `build_measurement_theme_palette()` does not exist.

- [ ] **Step 3: Implement the minimal theme helper and connect it to panel styling**

In `scripts/serial_logger_with_plot.py`, add a palette helper near the display helpers:

```python
def build_measurement_theme_palette() -> Dict[str, str]:
    return {
        "panel_background": "#f4f7fb",
        "card_background": "#ffffff",
        "accent": "#0f4c81",
        "status_active": "#d97706",
        "status_done": "#0f766e",
        "text_primary": "#102a43",
        "text_muted": "#52606d",
        "border": "#d9e2ec",
    }
```

Inside `_build_measurement_panel()`, use that palette for the embedded formula figure and its canvas widget so the polished panel actually matches the tested colors:

```python
        palette = build_measurement_theme_palette()
        self.measurement_formula_figure.patch.set_facecolor(palette["card_background"])
        for axis in self.measurement_formula_axes:
            axis.set_facecolor(palette["card_background"])
        canvas_widget = self.measurement_formula_canvas.get_tk_widget()
        canvas_widget.configure(
            background=palette["card_background"],
            highlightbackground=palette["border"],
            highlightthickness=1,
        )
```

Also use the status colors when updating the summary and footer text blocks:

```python
        self.measurement_status_label = ttk.Label(panel, textvariable=self.measurement_status_var)
        self.measurement_summary_label = ttk.Label(result_box, textvariable=self.measurement_summary_var)
```

```python
        if self.measurement_status_var.get() == "测量中":
            self.measurement_status_label.configure(foreground=palette["status_active"])
        elif self.measurement_status_var.get() == "已完成":
            self.measurement_status_label.configure(foreground=palette["status_done"])
        else:
            self.measurement_status_label.configure(foreground=palette["text_primary"])
```

- [ ] **Step 4: Run the targeted test to verify it passes**

Run: `py -m unittest tests.test_serial_logger_with_plot.LivePlotterGroupedMeasurementTests.test_measurement_theme_palette_matches_instrument_console_mix -v`

Expected: PASS.

- [ ] **Step 5: Run the final verification set**

Run: `py -m unittest tests.test_serial_logger_with_plot tests.test_readme_content tests.test_release_metadata -v`

Expected: PASS for all tests, with the grouped-measurement panel changes remaining compatible with the recent docs/release checks.

- [ ] **Step 6: Manual smoke-check the live window**

Run: `py scripts/serial_logger_with_plot.py --config config/logger_config.json --once`

Expected: the script starts successfully in the current environment, and when run without `--once` in a GUI-capable session the grouped measurement area shows separate input/action/result/history/footer sections and math formulas render as formatted expressions rather than plain inline text.

- [ ] **Step 7: Commit**

```bash
git add tests/test_serial_logger_with_plot.py scripts/serial_logger_with_plot.py
git commit -m "style: refine measurement result presentation"
```
