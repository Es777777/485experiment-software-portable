# Launcher UI Polish and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the main launcher into a more complete desktop-software workspace, finish the remaining live-plot UI consistency work, rebuild the portable package, and publish a new GitHub release whose Excel export matches the UI result fields.

**Architecture:** Keep launcher work centered in `app_launcher.py` by extracting palette/copy helpers that are easy to test, then drive the Tk layout from those helpers without changing tool-launching behavior. Keep grouped-measurement behavior in `scripts/serial_logger_with_plot.py`, strengthen export/result consistency with targeted tests, and only after UI/tests are stable update release metadata, rebuild the portable artifact, and publish via `gh` or the previously validated API fallback.

**Tech Stack:** Python 3, Tkinter/`ttk`, Matplotlib/TkAgg, `openpyxl`, PowerShell, `unittest`, GitHub CLI (`gh`)

---

## File Map

- Create: `tests/test_app_launcher.py` - focused regression tests for launcher palette, branding text, status text, and quick-link metadata.
- Modify: `app_launcher.py` - extract launcher UI tokens/copy helpers, restyle the root window into a branded workspace, and preserve existing tool-launching behavior.
- Modify: `scripts/serial_logger_with_plot.py` - finish any remaining result-panel consistency helpers, keep UI/export parity, and polish chart/control-panel status presentation.
- Modify: `tests/test_serial_logger_with_plot.py` - add failing tests for export/UI consistency and any additional live-plot status helpers.
- Modify: `README.md` - update release, screenshots/feature wording, and direct-download metadata for the new UI release.
- Modify: `README_portable.txt` - align operator instructions with the polished launcher and measurement panel.
- Modify: `CHANGELOG.md` - add the new release entry.
- Modify: `build_release.ps1` - bump the release version and keep packaging aligned with the new artifact name.
- Modify: `tests/test_readme_content.py` - update README/CHANGELOG expectations for the new release version and artifact name.
- Modify: `tests/test_release_metadata.py` - update release-script expectations for the new versioned asset.
- Modify: `docs/release-notes/v1.0.1.md` - add the release notes used for the new GitHub release.
- Modify: `docs/project-assets/release-artifacts.md` - record the new portable asset naming.

## Task 1: Add failing regression tests for launcher polish and export consistency

**Files:**
- Create: `tests/test_app_launcher.py`
- Modify: `tests/test_serial_logger_with_plot.py`

- [ ] **Step 1: Write the failing launcher helper tests**

Create `tests/test_app_launcher.py` with these tests:

```python
from pathlib import Path
import unittest

import app_launcher


class LauncherUiHelperTests(unittest.TestCase):
    def test_build_launcher_palette_returns_professional_workspace_colors(self) -> None:
        palette = app_launcher.build_launcher_palette()

        self.assertEqual(palette["shell_background"], "#eef3f8")
        self.assertEqual(palette["panel_background"], "#ffffff")
        self.assertEqual(palette["accent"], "#0f4c81")
        self.assertEqual(palette["accent_soft"], "#dbeafe")
        self.assertEqual(palette["status_ready"], "#0f766e")
        self.assertEqual(palette["status_running"], "#d97706")

    def test_build_launcher_branding_copy_mentions_author_and_github(self) -> None:
        branding = app_launcher.build_launcher_branding_copy()

        self.assertEqual(branding["title"], app_launcher.APP_TITLE)
        self.assertIn("Modbus 采集", branding["subtitle"])
        self.assertIn("Maintained by Chenghang Li", branding["signature"])
        self.assertIn(
            "github.com/Es777777/485experiment-software-portable",
            branding["signature"],
        )

    def test_build_launcher_quick_links_points_to_runtime_folders(self) -> None:
        root = Path(r"C:/demo/project")

        quick_links = app_launcher.build_launcher_quick_links(root)

        self.assertEqual(
            quick_links,
            [
                ("打开 config", root / "config"),
                ("打开 logs", root / "logs"),
                ("打开 videos", root / "videos"),
                ("打开 output", root / "output"),
            ],
        )

    def test_format_launcher_status_badge_returns_expected_copy(self) -> None:
        self.assertEqual(
            app_launcher.format_launcher_status_badge("就绪"),
            "系统状态  |  就绪",
        )
        self.assertEqual(
            app_launcher.format_launcher_status_badge("Modbus 实时曲线 运行中"),
            "系统状态  |  Modbus 实时曲线 运行中",
        )
```

- [ ] **Step 2: Add the failing export/UI consistency test**

Append this test to `tests/test_serial_logger_with_plot.py` inside `GroupedMeasurementHelperTests`:

```python
    def test_measurement_export_headers_cover_all_ui_result_fields(self) -> None:
        headers, _rows = serial_logger_with_plot.build_measurement_export_rows([])

        for expected in [
            "总电流",
            "合力平均值",
            "T1平均值",
            "T2平均值",
            "T3平均值",
            "M_y",
            "M_x",
            "M",
            "theta(度)",
        ]:
            self.assertIn(expected, headers)
```

- [ ] **Step 3: Run the targeted tests to verify they fail**

Run: `py -m unittest tests.test_app_launcher tests.test_serial_logger_with_plot.GroupedMeasurementHelperTests.test_measurement_export_headers_cover_all_ui_result_fields -v`

Expected: FAIL because `app_launcher.py` does not yet define `build_launcher_palette()`, `build_launcher_branding_copy()`, `build_launcher_quick_links()`, or `format_launcher_status_badge()`.

- [ ] **Step 4: Write the minimal helper implementation**

Add these helpers near the top of `app_launcher.py` after `APP_TITLE`:

```python
def build_launcher_palette() -> dict[str, str]:
    return {
        "shell_background": "#eef3f8",
        "panel_background": "#ffffff",
        "panel_alt": "#f8fbff",
        "accent": "#0f4c81",
        "accent_soft": "#dbeafe",
        "text_primary": "#102a43",
        "text_muted": "#52606d",
        "border": "#d9e2ec",
        "status_ready": "#0f766e",
        "status_running": "#d97706",
    }


def build_launcher_branding_copy() -> dict[str, str]:
    return {
        "title": APP_TITLE,
        "subtitle": "支持 Modbus 采集、实时曲线、原始串口采集、视频回填和后处理。",
        "signature": (
            "Maintained by Chenghang Li  |  "
            "github.com/Es777777/485experiment-software-portable"
        ),
    }


def build_launcher_quick_links(app_root: Path) -> list[tuple[str, Path]]:
    return [
        ("打开 config", app_root / "config"),
        ("打开 logs", app_root / "logs"),
        ("打开 videos", app_root / "videos"),
        ("打开 output", app_root / "output"),
    ]


def format_launcher_status_badge(status: str) -> str:
    return "系统状态  |  {0}".format(status.strip() or "就绪")
```

No production change is needed in `scripts/serial_logger_with_plot.py` for the new export-header test if the current export headers already satisfy it.

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run: `py -m unittest tests.test_app_launcher tests.test_serial_logger_with_plot.GroupedMeasurementHelperTests.test_measurement_export_headers_cover_all_ui_result_fields -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/test_app_launcher.py tests/test_serial_logger_with_plot.py app_launcher.py
git commit -m "test: add launcher polish regression coverage"
```

## Task 2: Restyle the launcher into a branded workspace without breaking tool launching

**Files:**
- Modify: `app_launcher.py`
- Test: `tests/test_app_launcher.py`

- [ ] **Step 1: Write the failing launcher command/status tests**

Append these tests to `tests/test_app_launcher.py`:

```python
class LauncherCommandTests(unittest.TestCase):
    def test_build_launcher_tab_descriptions_mentions_grouped_measurement(self) -> None:
        descriptions = app_launcher.build_launcher_tab_descriptions()

        self.assertIn("Modbus 采集", descriptions)
        self.assertIn("PWM 分组测量", descriptions["Modbus 采集"])
        self.assertIn("视频回填", descriptions)

    def test_build_launcher_status_badge_palette_maps_running_state(self) -> None:
        palette = app_launcher.build_launcher_palette()

        self.assertEqual(
            app_launcher.pick_launcher_status_color("就绪", palette),
            palette["status_ready"],
        )
        self.assertEqual(
            app_launcher.pick_launcher_status_color("Modbus 实时曲线 运行中", palette),
            palette["status_running"],
        )
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `py -m unittest tests.test_app_launcher.LauncherCommandTests -v`

Expected: FAIL because `build_launcher_tab_descriptions()` and `pick_launcher_status_color()` do not yet exist.

- [ ] **Step 3: Implement the launcher workspace helpers and refactor `_build_ui()`**

Add these helpers to `app_launcher.py`:

```python
def build_launcher_tab_descriptions() -> dict[str, str]:
    return {
        "Modbus 采集": "适用于标准 Modbus 轮询与实时曲线采集，支持 PWM 分组测量、总电流录入与 Excel 导出。",
        "原始串口采集": "直接记录原始串口数据，适合底层调试与对照采集。",
        "视频回填": "把视频表计识别结果补写到 Excel，便于后续对齐与分析。",
        "可靠数据与曲线": "提取稳定数据并输出图表，用于报告与复盘。",
    }


def pick_launcher_status_color(status: str, palette: dict[str, str]) -> str:
    return palette["status_running"] if "运行中" in status else palette["status_ready"]
```

Then refactor `_build_ui()` so it uses a branded shell, hero header, quick-link strip, descriptive tab intro, and a more explicit status bar. Use the existing methods for launching tools; only change presentation. The new top section should look like this:

```python
        palette = build_launcher_palette()
        branding = build_launcher_branding_copy()
        self.root.configure(bg=palette["shell_background"])

        outer = tk.Frame(self.root, bg=palette["shell_background"], padx=18, pady=18)
        outer.pack(fill="both", expand=True)

        hero = tk.Frame(
            outer,
            bg=palette["panel_background"],
            bd=1,
            relief="solid",
            highlightbackground=palette["border"],
            highlightthickness=1,
            padx=20,
            pady=18,
        )
        hero.pack(fill="x")
        tk.Label(
            hero,
            text=branding["title"],
            bg=palette["panel_background"],
            fg=palette["text_primary"],
            font=("Microsoft YaHei UI", 22, "bold"),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            hero,
            text=branding["subtitle"],
            bg=palette["panel_background"],
            fg=palette["text_muted"],
            anchor="w",
            justify="left",
        ).pack(anchor="w", pady=(6, 0))
        tk.Label(
            hero,
            text=branding["signature"],
            bg=palette["panel_background"],
            fg=palette["accent"],
            anchor="w",
            cursor="hand2",
        ).pack(anchor="w", pady=(8, 0))
```

Create quick links from `build_launcher_quick_links(self.app_root)` instead of the current inline tuple loop, and replace the status row with a card-style bar:

```python
        status_bar = tk.Frame(
            outer,
            bg=palette["panel_background"],
            bd=1,
            relief="solid",
            highlightbackground=palette["border"],
            highlightthickness=1,
            padx=14,
            pady=10,
        )
        status_bar.pack(fill="x", pady=(12, 0))
        self.status_badge_var = tk.StringVar(
            value=format_launcher_status_badge(self.status_var.get())
        )
        self.status_badge_label = tk.Label(
            status_bar,
            textvariable=self.status_badge_var,
            bg=palette["accent_soft"],
            fg=pick_launcher_status_color(self.status_var.get(), palette),
            font=("Microsoft YaHei UI", 10, "bold"),
            padx=12,
            pady=6,
        )
        self.status_badge_label.pack(side="left")
```

Also add a helper to keep the badge in sync when status changes:

```python
    def _set_status(self, value: str) -> None:
        self.status_var.set(value)
        if hasattr(self, "status_badge_var"):
            self.status_badge_var.set(format_launcher_status_badge(value))
        if hasattr(self, "status_badge_label"):
            palette = build_launcher_palette()
            self.status_badge_label.configure(
                fg=pick_launcher_status_color(value, palette)
            )
```

Replace direct `self.status_var.set(...)` calls in `_poll_log_queue()` and `_start_tool()` with `_set_status(...)`.

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `py -m unittest tests.test_app_launcher -v`

Expected: PASS.

- [ ] **Step 5: Manual launcher smoke-check**

Run: `py app_launcher.py`

Expected: the launcher opens with a branded header, clearer quick-link strip, more intentional tab workspace, and a visible status badge while all existing start/stop controls still work.

- [ ] **Step 6: Commit**

```bash
git add app_launcher.py tests/test_app_launcher.py
git commit -m "feat: polish launcher workspace"
```

## Task 3: Finish live-plot UI consistency and keep Excel export aligned with UI fields

**Files:**
- Modify: `scripts/serial_logger_with_plot.py`
- Modify: `tests/test_serial_logger_with_plot.py`

- [ ] **Step 1: Write the failing live-plot helper tests**

Append these tests to `tests/test_serial_logger_with_plot.py` inside `GroupedMeasurementDisplayHelperTests`:

```python
    def test_build_measurement_context_text_covers_running_done_and_export_states(self) -> None:
        result = serial_logger_with_plot.MeasurementGroupResult(
            index=2,
            pwm="1500",
            start_time=datetime(2026, 5, 22, 11, 0, 0),
            end_time=datetime(2026, 5, 22, 11, 0, 1),
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

        self.assertIn(
            "当前组 PWM=1500",
            serial_logger_with_plot.build_measurement_context_text(1, "测量中", current_pwm="1500"),
        )
        self.assertIn(
            "最近完成 #2",
            serial_logger_with_plot.build_measurement_context_text(2, "已完成", latest_result=result),
        )
        self.assertIn(
            "demo.xlsx",
            serial_logger_with_plot.build_measurement_context_text(2, "已导出", export_name="demo.xlsx"),
        )

    def test_build_measurement_metric_values_matches_export_visible_fields(self) -> None:
        result = serial_logger_with_plot.MeasurementGroupResult(
            index=1,
            pwm="800",
            start_time=datetime(2026, 5, 22, 11, 1, 0),
            end_time=datetime(2026, 5, 22, 11, 1, 1),
            total_current=1.25,
            average_total_force=5.5,
            average_t1=1.0,
            average_t2=2.0,
            average_t3=2.5,
            moment_y=0.0,
            moment_x=0.0,
            moment_magnitude=0.0,
            theta_radians=0.0,
            theta_degrees=0.0,
            samples=[],
        )

        metric_values = serial_logger_with_plot.build_measurement_metric_values(result)

        self.assertEqual(metric_values["average_total_force"], "5.500")
        self.assertEqual(metric_values["T1"], "1.000")
        self.assertEqual(metric_values["T2"], "2.000")
        self.assertEqual(metric_values["T3"], "2.500")
        self.assertEqual(metric_values["total_current"], "1.250 A")
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `py -m unittest tests.test_serial_logger_with_plot.GroupedMeasurementDisplayHelperTests.test_build_measurement_context_text_covers_running_done_and_export_states tests.test_serial_logger_with_plot.GroupedMeasurementDisplayHelperTests.test_build_measurement_metric_values_matches_export_visible_fields -v`

Expected: FAIL if the context helper and metric helper are missing or incomplete.

- [ ] **Step 3: Implement the live-plot helper/UI refinements**

In `scripts/serial_logger_with_plot.py`, make sure these helpers exist and are used by the panel state updates:

```python
def build_measurement_metric_values(
    result: Optional[MeasurementGroupResult],
) -> Dict[str, str]:
    if result is None:
        return {
            "average_total_force": "--",
            "T1": "--",
            "T2": "--",
            "T3": "--",
            "total_current": "--",
        }
    return {
        "average_total_force": "{0:.3f}".format(result.average_total_force),
        "T1": "{0:.3f}".format(result.average_t1),
        "T2": "{0:.3f}".format(result.average_t2),
        "T3": "{0:.3f}".format(result.average_t3),
        "total_current": "{0:.3f} A".format(result.total_current),
    }
```

```python
def build_measurement_context_text(
    completed_count: int,
    status: str,
    current_pwm: str = "",
    latest_result: Optional[MeasurementGroupResult] = None,
    export_name: str = "",
) -> str:
    if export_name:
        return "已完成组数={0} | 已导出 {1} | 可继续检查结果或开始新一轮测量".format(
            completed_count,
            export_name,
        )
    if status == "测量中":
        return "当前组 PWM={0} | 正在采样，等待稳定后结束测量并录入总电流".format(
            current_pwm or "--"
        )
    if latest_result is not None and status == "已完成":
        return (
            "最近完成 #{0} | T1/T2/T3={1:.3f}/{2:.3f}/{3:.3f} | 可继续下一组或导出"
        ).format(
            latest_result.index,
            latest_result.average_t1,
            latest_result.average_t2,
            latest_result.average_t3,
        )
    return "已完成组数={0} | 请输入下一组 PWM，或检查历史后导出".format(
        completed_count
    )
```

Make sure `LivePlotter` stores `measurement_context_var`, renders it between the hint line and the metric cards, and updates it from `start_measurement()`, `finish_measurement()`, `prepare_next_group()`, and `export_measurements()`.

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `py -m unittest tests.test_serial_logger_with_plot.GroupedMeasurementDisplayHelperTests tests.test_serial_logger_with_plot.LivePlotterGroupedMeasurementTests -v`

Expected: PASS.

- [ ] **Step 5: Run the full measurement-related suite**

Run: `py -m unittest tests.test_serial_logger_with_plot -v`

Expected: PASS, with no `Agg` backend warning and no identical-`xlim` warning.

- [ ] **Step 6: Commit**

```bash
git add scripts/serial_logger_with_plot.py tests/test_serial_logger_with_plot.py
git commit -m "feat: refine grouped measurement presentation"
```

## Task 4: Update docs and release metadata for the new portable version

**Files:**
- Modify: `build_release.ps1`
- Modify: `README.md`
- Modify: `README_portable.txt`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_readme_content.py`
- Modify: `tests/test_release_metadata.py`
- Modify: `docs/release-notes/v1.0.1.md`
- Modify: `docs/project-assets/release-artifacts.md`

- [ ] **Step 1: Write the failing docs/release tests**

Update `tests/test_release_metadata.py` and `tests/test_readme_content.py` to expect the next patch release:

```python
        self.assertIn('$releaseVersion = "v1.0.1"', script)
```

```python
        self.assertIn("v1.0.1", readme)
        self.assertIn("485experiment-software-portable-v1.0.1-", readme)
```

```python
        self.assertIn("## v1.0.1", changelog)
        self.assertIn("主窗口 UI", changelog)
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `py -m unittest tests.test_readme_content tests.test_release_metadata -v`

Expected: FAIL because the repository still references `v1.0.0`.

- [ ] **Step 3: Write the minimal docs and metadata implementation**

Update `build_release.ps1` to bump the version:

```powershell
$releaseVersion = "v1.0.1"
```

Update `CHANGELOG.md` to add a new top entry like:

```markdown
## v1.0.1 - 2026-05-22

- polish the launcher into a more complete desktop workspace with clearer status, quick links, and stronger action hierarchy
- refine the grouped measurement panel so UI cards, formulas, context hints, and Excel export columns stay aligned
- rebuild the portable package and publish a refreshed release asset
```

Create `docs/release-notes/v1.0.1.md` with:

```markdown
# v1.0.1 Release Notes

## Summary

- polish the launcher UI into a more complete desktop-software workspace
- refine grouped measurement presentation and keep Excel export aligned with visible result fields
- rebuild the portable package for the refreshed release

## Included updates

- branded launcher header, quick-link strip, and clearer status presentation
- grouped measurement result cards, math formulas, context hints, and export consistency
- entrypoint and plotting warning fixes retained in the portable build
```

Update `README.md`, `README_portable.txt`, and `docs/project-assets/release-artifacts.md` so they reference `v1.0.1` and the new zip naming pattern.

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `py -m unittest tests.test_readme_content tests.test_release_metadata -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add build_release.ps1 README.md README_portable.txt CHANGELOG.md tests/test_readme_content.py tests/test_release_metadata.py docs/release-notes/v1.0.1.md docs/project-assets/release-artifacts.md
git commit -m "docs: prepare v1.0.1 release metadata"
```

## Task 5: Rebuild the portable package and verify the artifact locally

**Files:**
- Modify: generated output under `dist/`
- Verify: desktop portable folder generated from the release script output

- [ ] **Step 1: Run the release build**

Run: `powershell -ExecutionPolicy Bypass -File "C:\Users\asd\OneDrive\Desktop\实验软件 - 副本\.worktrees\grouped-pwm-measurement\build_release.ps1"`

Expected: success output showing the portable release folder path and the `485experiment-software-portable-v1.0.1-<date>.zip` path.

- [ ] **Step 2: Verify the built artifact and launcher entrypoint**

Run: `py scripts/serial_logger_with_plot.py --help`

Expected: the help text prints successfully from the repo root.

- [ ] **Step 3: Verify the full automated suite after the build**

Run: `py -m unittest tests.test_app_launcher tests.test_serial_logger_with_plot tests.test_readme_content tests.test_release_metadata -v`

Expected: PASS.

- [ ] **Step 4: Copy the rebuilt portable folder to the Desktop delivery location**

Run: `powershell -Command "Copy-Item -Path 'C:\Users\asd\OneDrive\Desktop\实验软件 - 副本\.worktrees\grouped-pwm-measurement\dist\实验软件' -Destination 'C:\Users\asd\OneDrive\Desktop\实验软件_便携版_20260522' -Recurse -Force"`

Expected: the refreshed portable folder exists on the desktop with updated launcher and live-plot UI.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "build: refresh portable release package"
```

## Task 6: Sync GitHub and publish the new release

**Files:**
- Verify: remote branch, PR, and GitHub release state

- [ ] **Step 1: Check branch state before publishing**

Run these commands:

```bash
git status --short
git branch --show-current
git remote -v
```

Expected: only intended tracked changes are present and the branch is still `feature/grouped-pwm-measurement`.

- [ ] **Step 2: Push the branch**

Run: `git push -u origin feature/grouped-pwm-measurement`

Expected: branch pushes successfully.

If `git push` fails with the known network problem, fall back to the previously validated GitHub API/`gh` workflow instead of stopping. Use `gh api` to upload the content-equivalent tree and move the remote ref.

- [ ] **Step 3: Update or create the GitHub release**

Run:

```bash
gh release create v1.0.1 "dist/485experiment-software-portable-v1.0.1-<date>.zip" --title "v1.0.1" --notes-file "docs/release-notes/v1.0.1.md"
```

If the tag already exists, use:

```bash
gh release upload v1.0.1 "dist/485experiment-software-portable-v1.0.1-<date>.zip" --clobber
gh release edit v1.0.1 --title "v1.0.1" --notes-file "docs/release-notes/v1.0.1.md"
```

- [ ] **Step 4: Verify the published release**

Run: `gh release view v1.0.1`

Expected: the release exists and lists the refreshed `485experiment-software-portable-v1.0.1-<date>.zip` asset.

- [ ] **Step 5: Verify the PR/branch content if needed**

Run: `gh pr view 2`

Expected: the existing PR still points to the updated branch, or if the release work went to a new branch the new PR URL is available.

- [ ] **Step 6: Commit any final release-note or metadata adjustments**

```bash
git add README.md README_portable.txt CHANGELOG.md docs/release-notes/v1.0.1.md docs/project-assets/release-artifacts.md
git commit -m "release: publish v1.0.1"
```
