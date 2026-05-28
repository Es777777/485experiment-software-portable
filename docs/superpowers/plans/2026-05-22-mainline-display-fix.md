# Mainline Display Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the mainline normal edition so launcher and live-plot windows no longer have text overlap/compression issues, then rebuild the normal portable package and publish the corrected code and release artifact.

**Architecture:** Keep the current visual language, but introduce small layout-helper functions and elastic layout rules instead of adding more UI features. Make the launcher and grouped-measurement panel responsive through explicit wrap widths, grid weights, split rows, and figure sizing, prove the changes with focused `unittest` coverage, then bump the normal release to `v1.0.2`, rebuild the portable artifact, and publish it through GitHub.

**Tech Stack:** Python 3, Tkinter/`ttk`, Matplotlib/TkAgg, PowerShell, `unittest`, GitHub CLI (`gh`)

---

## File Map

- Modify: `app_launcher.py` - add launcher layout helpers, split crowded rows, make long copy/path fields wrap or stretch correctly, and keep launcher behavior unchanged.
- Modify: `scripts/serial_logger_with_plot.py` - split grouped-measurement input/actions into separate rows, constrain and wrap long labels, and resize the formula/results/history sections for stable display.
- Modify: `tests/test_app_launcher.py` - add failing tests for launcher layout helper values and status/header copy widths.
- Modify: `tests/test_serial_logger_with_plot.py` - add failing tests for grouped-measurement layout helper values and adaptive display behavior.
- Modify: `build_release.ps1` - bump the normal release version to `v1.0.2` and keep the artifact name aligned.
- Modify: `README.md` - update version, download filename, and release notes summary.
- Modify: `README_portable.txt` - mention the display-fix improvements if the operator-facing text references the old crowded UI.
- Modify: `CHANGELOG.md` - add a `v1.0.2` entry for the mainline display fix.
- Modify: `docs/release-notes/v1.0.2.md` - release note body for the fixed normal edition.
- Modify: `docs/project-assets/release-artifacts.md` - record the `v1.0.2` normal package name.
- Modify: `tests/test_readme_content.py` and `tests/test_release_metadata.py` - expect `v1.0.2` metadata.

## Task 1: Add failing regression tests for launcher display layout

**Files:**
- Modify: `tests/test_app_launcher.py`
- Modify: `app_launcher.py`

- [ ] **Step 1: Write the failing launcher layout tests**

Append these tests to `tests/test_app_launcher.py`:

```python
class LauncherLayoutHelperTests(unittest.TestCase):
    def test_build_launcher_layout_metrics_define_wrap_lengths(self) -> None:
        metrics = app_launcher.build_launcher_layout_metrics()

        self.assertEqual(metrics["hero_subtitle_wrap"], 820)
        self.assertEqual(metrics["workspace_intro_wrap"], 820)
        self.assertEqual(metrics["tab_intro_wrap"], 760)
        self.assertEqual(metrics["status_message_wrap"], 560)

    def test_normalize_launcher_path_display_shortens_long_paths(self) -> None:
        displayed = app_launcher.normalize_launcher_path_display(
            r"C:/very/long/project/path/with/many/segments/config/logger_config.json",
            max_length=42,
        )

        self.assertLessEqual(len(displayed), 42)
        self.assertIn("...", displayed)

    def test_build_launcher_branding_copy_keeps_mainline_title_for_standard_profile(self) -> None:
        branding = app_launcher.build_launcher_branding_copy(app_launcher.EditionProfile())

        self.assertEqual(branding["title"], app_launcher.APP_TITLE)
        self.assertNotIn("特供版", branding["title"])
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `py -m unittest tests.test_app_launcher.LauncherLayoutHelperTests -v`

Expected: FAIL because `build_launcher_layout_metrics()` and `normalize_launcher_path_display()` do not exist yet.

- [ ] **Step 3: Implement the minimal launcher helper functions**

Add these helpers near the existing launcher palette/copy helpers in `app_launcher.py`:

```python
def build_launcher_layout_metrics() -> dict[str, int]:
    return {
        "hero_subtitle_wrap": 820,
        "workspace_intro_wrap": 820,
        "tab_intro_wrap": 760,
        "status_message_wrap": 560,
        "path_entry_width": 64,
    }


def normalize_launcher_path_display(path_text: str, max_length: int = 64) -> str:
    text = str(path_text)
    if len(text) <= max_length:
        return text
    keep = max_length - 3
    head = keep // 2
    tail = keep - head
    return text[:head] + "..." + text[-tail:]
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `py -m unittest tests.test_app_launcher.LauncherLayoutHelperTests -v`

Expected: PASS.

- [ ] **Step 5: Refactor launcher layout to use the helper values**

Update `app_launcher.py` so the brand/subtitle labels and status message use explicit wrapping and the config/path widgets can stretch:

```python
        metrics = build_launcher_layout_metrics()
        ...
        tk.Label(
            hero,
            text=branding["subtitle"],
            ...,
            wraplength=metrics["hero_subtitle_wrap"],
        ).pack(anchor="w", pady=(6, 0), fill="x")
```

```python
        tk.Label(
            workspace_shell,
            text="按页切换采集、回填与后处理任务；关键操作入口和串口选择放在每个页签顶部。",
            ...,
            wraplength=metrics["workspace_intro_wrap"],
        ).pack(anchor="w", pady=(4, 10), fill="x")
```

```python
        ttk.Label(
            parent,
            text=descriptions.get(title, ""),
            wraplength=build_launcher_layout_metrics()["tab_intro_wrap"],
            justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 10))
```

```python
        tk.Label(
            status_bar,
            text="运行日志会在下方持续刷新，启动器会阻止多个任务同时运行。",
            ...,
            wraplength=metrics["status_message_wrap"],
            justify="left",
        ).pack(side="left", padx=(12, 0), fill="x", expand=True)
```

Also make the main tab grids stretchable where long paths/config entries live by adding `parent.grid_columnconfigure(1, weight=1)` or equivalent inside the tab builders.

- [ ] **Step 6: Run the full launcher test file**

Run: `py -m unittest tests.test_app_launcher -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app_launcher.py tests/test_app_launcher.py
git commit -m "fix: stabilize launcher text layout"
```

## Task 2: Add failing regression tests for grouped-measurement layout and fix the adaptive panel

**Files:**
- Modify: `tests/test_serial_logger_with_plot.py`
- Modify: `scripts/serial_logger_with_plot.py`

- [ ] **Step 1: Write the failing grouped-measurement layout tests**

Append these tests to `tests/test_serial_logger_with_plot.py` inside `GroupedMeasurementDisplayHelperTests`:

```python
    def test_build_measurement_layout_metrics_sets_wrap_and_figure_sizes(self) -> None:
        metrics = serial_logger_with_plot.build_measurement_layout_metrics()

        self.assertEqual(metrics["hint_wrap"], 720)
        self.assertEqual(metrics["context_wrap"], 720)
        self.assertEqual(metrics["footer_wrap"], 720)
        self.assertEqual(metrics["formula_figure_size"], (6.4, 2.6))

    def test_split_measurement_actions_breaks_controls_into_two_rows(self) -> None:
        rows = serial_logger_with_plot.split_measurement_actions(
            ["开始测量", "结束测量", "下一组", "导出表格"]
        )

        self.assertEqual(rows, [["开始测量", "结束测量"], ["下一组", "导出表格"]])
```

Append this test inside `LivePlotterGroupedMeasurementTests`:

```python
    def test_measurement_footer_text_wraps_for_long_buaa_copy(self) -> None:
        profile = serial_logger_with_plot.EditionProfile(
            edition_key="buaa",
            display_name="北航特供版",
            t_channel_scale=1.0 / 3.0,
            notes="scaled",
        )

        footer = serial_logger_with_plot.build_measurement_footer_text(profile)

        self.assertIn("北航特供版", footer)
        self.assertIn("1/3", footer)
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `py -m unittest tests.test_serial_logger_with_plot.GroupedMeasurementDisplayHelperTests.test_build_measurement_layout_metrics_sets_wrap_and_figure_sizes tests.test_serial_logger_with_plot.GroupedMeasurementDisplayHelperTests.test_split_measurement_actions_breaks_controls_into_two_rows -v`

Expected: FAIL because `build_measurement_layout_metrics()` and `split_measurement_actions()` do not exist yet.

- [ ] **Step 3: Implement the minimal measurement layout helpers**

Add these helpers near the existing grouped-measurement display helpers in `scripts/serial_logger_with_plot.py`:

```python
def build_measurement_layout_metrics() -> Dict[str, Any]:
    return {
        "hint_wrap": 720,
        "context_wrap": 720,
        "footer_wrap": 720,
        "formula_figure_size": (6.4, 2.6),
    }


def split_measurement_actions(labels: Sequence[str]) -> List[List[str]]:
    items = list(labels)
    midpoint = max(1, len(items) // 2)
    return [items[:midpoint], items[midpoint:]]
```

- [ ] **Step 4: Refactor the grouped-measurement panel to use elastic layout**

In `scripts/serial_logger_with_plot.py`, use the helper values to split the action buttons into two rows, wrap long text, and reduce horizontal crowding:

```python
        metrics = build_measurement_layout_metrics()
        panel.grid_columnconfigure(0, weight=1)
        header_row.grid_columnconfigure(0, weight=1)
        header_row.grid_columnconfigure(1, weight=1)
```

```python
        input_box = tk.LabelFrame(...)
        input_box.grid(row=0, column=0, sticky="ew")
        action_box = tk.LabelFrame(...)
        action_box.grid(row=1, column=0, sticky="ew", pady=(8, 0))
```

```python
        action_rows = split_measurement_actions(["开始测量", "结束测量", "下一组", "导出表格"])
```

```python
        hint_label = tk.Label(..., wraplength=metrics["hint_wrap"], justify="left")
        context_label = tk.Label(..., wraplength=metrics["context_wrap"], justify="left")
        self.measurement_footer_label = tk.Label(..., wraplength=metrics["footer_wrap"], justify="left")
        self.measurement_formula_figure = Figure(figsize=metrics["formula_figure_size"], dpi=100, ...)
```

Also make `result_box`, `history_box`, and `metric_row` columns stretch with `grid_columnconfigure()` so the cards and formula canvas can shrink gracefully.

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run: `py -m unittest tests.test_serial_logger_with_plot.GroupedMeasurementDisplayHelperTests tests.test_serial_logger_with_plot.LivePlotterGroupedMeasurementTests -v`

Expected: PASS.

- [ ] **Step 6: Run the full live-plot test file**

Run: `py -m unittest tests.test_serial_logger_with_plot -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/serial_logger_with_plot.py tests/test_serial_logger_with_plot.py
git commit -m "fix: improve grouped measurement layout"
```

## Task 3: Bump the normal edition to v1.0.2 and update release/docs metadata

**Files:**
- Modify: `build_release.ps1`
- Modify: `README.md`
- Modify: `README_portable.txt`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_readme_content.py`
- Modify: `tests/test_release_metadata.py`
- Modify: `docs/release-notes/v1.0.2.md`
- Modify: `docs/project-assets/release-artifacts.md`

- [ ] **Step 1: Write the failing docs/release tests**

Update `tests/test_release_metadata.py` and `tests/test_readme_content.py` to expect `v1.0.2`:

```python
        self.assertIn('$releaseVersion = "v1.0.2"', script)
```

```python
        self.assertIn("v1.0.2", readme)
        self.assertIn("485experiment-software-portable-v1.0.2-20260522.zip", readme)
```

```python
        self.assertIn("## v1.0.2", changelog)
        self.assertIn("显示问题修复", changelog)
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `py -m unittest tests.test_readme_content tests.test_release_metadata -v`

Expected: FAIL because the repo still references `v1.0.1`.

- [ ] **Step 3: Update the release metadata and docs**

Modify `build_release.ps1`:

```powershell
$releaseVersion = "v1.0.2"
```

Add a new top changelog entry:

```markdown
## v1.0.2

- 修复主窗口与实时曲线窗口中的文字堆叠、挤压和布局不稳定问题
- 调整分组测量区输入、按钮、结果卡片、公式区和历史区布局，使其在常见桌面缩放下更稳定
- 重新打包普通版便携包并同步发布修复后的 release
```

Create `docs/release-notes/v1.0.2.md`:

```markdown
# v1.0.2 Release Notes

## Summary

- fix text overlap and compressed layout problems in the normal edition launcher and live-plot window
- stabilize grouped measurement presentation without changing the normal-edition calculation logic
- rebuild and republish the corrected portable package
```

Update `README.md`, `README_portable.txt`, and `docs/project-assets/release-artifacts.md` so they reference `v1.0.2` and the new zip filename.

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `py -m unittest tests.test_readme_content tests.test_release_metadata -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add build_release.ps1 README.md README_portable.txt CHANGELOG.md tests/test_readme_content.py tests/test_release_metadata.py docs/release-notes/v1.0.2.md docs/project-assets/release-artifacts.md
git commit -m "docs: prepare v1.0.2 display fix release"
```

## Task 4: Rebuild the normal portable package and publish the corrected release

**Files:**
- Verify/generated: `dist/485experiment-software-portable-v1.0.2-20260522.zip`
- Verify/generated: desktop portable folder

- [ ] **Step 1: Run the normal release build**

Run: `powershell -ExecutionPolicy Bypass -File "C:\Users\asd\OneDrive\Desktop\实验软件 - 副本\.worktrees\grouped-pwm-measurement\build_release.ps1"`

Expected: success output with `485experiment-software-portable-v1.0.2-20260522.zip`.

- [ ] **Step 2: Run the final automated suite**

Run: `py -m unittest tests.test_app_launcher tests.test_serial_logger_with_plot tests.test_readme_content tests.test_release_metadata -v`

Expected: PASS.

- [ ] **Step 3: Copy the rebuilt normal portable folder to the desktop delivery location**

Run: `powershell -Command "Copy-Item -Path 'C:\Users\asd\OneDrive\Desktop\实验软件 - 副本\.worktrees\grouped-pwm-measurement\dist\实验软件' -Destination 'C:\Users\asd\OneDrive\Desktop\实验软件_便携版_20260522_mainline_fix' -Recurse -Force"`

Expected: the updated normal-edition desktop folder exists.

- [ ] **Step 4: Publish the corrected release**

Run: `gh release create v1.0.2 "dist/485experiment-software-portable-v1.0.2-20260522.zip" --target feature/launcher-ui-v1.0.1 --title "v1.0.2" --notes-file "docs/release-notes/v1.0.2.md"`

If the tag already exists, use:

```bash
gh release upload v1.0.2 "dist/485experiment-software-portable-v1.0.2-20260522.zip" --clobber
gh release edit v1.0.2 --title "v1.0.2" --notes-file "docs/release-notes/v1.0.2.md"
```

- [ ] **Step 5: Publish the code changes**

Run: `git push -u origin HEAD:refs/heads/feature/mainline-display-fix-v1.0.2`

If Git transport fails again, reuse the validated `gh api` tree/commit/ref workflow instead of forcing the old branch.

- [ ] **Step 6: Create the PR**

Run: `gh pr create --base main --head feature/mainline-display-fix-v1.0.2 --title "fix: resolve mainline display layout issues" --body-file "docs/release-notes/v1.0.2.md"`

- [ ] **Step 7: Verify the published release and PR**

Run:

```bash
gh release view v1.0.2
gh pr view --web
```

Expected: the release lists the new `v1.0.2` asset and the PR points at the updated branch.
