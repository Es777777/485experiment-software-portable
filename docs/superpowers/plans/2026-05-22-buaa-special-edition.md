# BUAA Special Edition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a separate 北航特供版 portable package that keeps the normal edition unchanged while scaling grouped-measurement `T1/T2/T3` to one third and recomputing all derived moment results from those scaled values.

**Architecture:** Introduce a small runtime edition profile that defaults to the current normal behavior and only applies BUAA scaling when the special package provides a BUAA edition profile file. Keep the scaling logic centralized in `scripts/serial_logger_with_plot.py`, surface the edition label in launcher/live-plot copy, and add a separate packaging script so the standard `v1.0.1` build remains untouched.

**Tech Stack:** Python 3, Tkinter/`ttk`, Matplotlib/TkAgg, `openpyxl`, PowerShell, `unittest`, PyInstaller

---

## File Map

- Create: `config/edition_profile.buaa.json` - BUAA-only runtime profile declaring the edition label and `T1/T2/T3` scaling factor.
- Create: `build_release_buaa.ps1` - separate special-edition packaging script that reuses the standard build flow while producing BUAA-specific names and config.
- Create: `tests/test_buaa_release_metadata.py` - packaging and edition-profile regression tests for the special edition.
- Modify: `scripts/serial_logger_with_plot.py` - load the active edition profile, scale grouped-measurement `T1/T2/T3`, recompute `M_y/M_x/M/theta`, and expose BUAA labeling in result/footnote text.
- Modify: `app_launcher.py` - load the active edition profile and reflect `北航特供版` / `BUAA Edition` in launcher branding copy when the BUAA profile is present.
- Modify: `tests/test_serial_logger_with_plot.py` - add failing tests for scaled `T1/T2/T3`, recomputed moments, export-row behavior, and BUAA edition text.
- Modify: `tests/test_app_launcher.py` - add failing tests for BUAA branding copy.
- Modify: `README_portable.txt` or create a BUAA-specific copy in the package - explain the 1/3 scaling rule for `T1/T2/T3` and derived moment results.

## Task 1: Add failing tests for BUAA scaling behavior and launcher branding

**Files:**
- Create: `tests/test_buaa_release_metadata.py`
- Modify: `tests/test_serial_logger_with_plot.py`
- Modify: `tests/test_app_launcher.py`

- [ ] **Step 1: Write the failing grouped-measurement scaling tests**

Append these tests to `tests/test_serial_logger_with_plot.py` inside `GroupedMeasurementHelperTests` and `GroupedMeasurementDisplayHelperTests`:

```python
    def test_finish_measurement_applies_buaa_scaling_to_t_values_and_moments(self) -> None:
        state = serial_logger_with_plot.MeasurementSessionState()
        serial_logger_with_plot.start_measurement_group(
            state,
            "1200",
            datetime(2026, 5, 22, 12, 0, 0),
        )
        serial_logger_with_plot.record_measurement_sample(
            state,
            datetime(2026, 5, 22, 12, 0, 0, 100000),
            {"weight_ch1": 3.0, "weight_ch2": 9.0, "weight_ch3": 6.0},
            18.0,
        )
        profile = serial_logger_with_plot.EditionProfile(
            edition_key="buaa",
            display_name="北航特供版",
            t_channel_scale=1.0 / 3.0,
            notes="T values scaled for BUAA sensor range",
        )

        result = serial_logger_with_plot.finish_measurement_group(
            state,
            "2.40",
            datetime(2026, 5, 22, 12, 0, 1),
            edition_profile=profile,
        )

        self.assertEqual(result.average_t1, 1.0)
        self.assertEqual(result.average_t2, 3.0)
        self.assertEqual(result.average_t3, 2.0)
        self.assertAlmostEqual(result.moment_y, 0.0)
        self.assertAlmostEqual(result.moment_x, serial_logger_with_plot.math.sqrt(3.0))
        self.assertAlmostEqual(result.theta_degrees, 90.0)

    def test_build_measurement_footer_text_includes_buaa_note_when_profile_enabled(self) -> None:
        profile = serial_logger_with_plot.EditionProfile(
            edition_key="buaa",
            display_name="北航特供版",
            t_channel_scale=1.0 / 3.0,
            notes="T1/T2/T3 and derived moments are scaled by 1/3",
        )

        footer = serial_logger_with_plot.build_measurement_footer_text(profile)

        self.assertIn("北航特供版", footer)
        self.assertIn("1/3", footer)
```

- [ ] **Step 2: Write the failing launcher branding test**

Append this test to `tests/test_app_launcher.py`:

```python
    def test_build_launcher_branding_copy_uses_buaa_edition_label(self) -> None:
        profile = app_launcher.EditionProfile(
            edition_key="buaa",
            display_name="北航特供版",
            t_channel_scale=1.0 / 3.0,
            notes="T values scaled for BUAA sensor range",
        )

        branding = app_launcher.build_launcher_branding_copy(profile)

        self.assertIn("北航特供版", branding["title"])
        self.assertIn("1/3", branding["subtitle"])
```

- [ ] **Step 3: Write the failing BUAA packaging tests**

Create `tests/test_buaa_release_metadata.py` with:

```python
from pathlib import Path
import json
import unittest


class BuaaReleaseMetadataTests(unittest.TestCase):
    def test_buaa_build_script_uses_special_artifact_name(self) -> None:
        script = Path("build_release_buaa.ps1").read_text(encoding="utf-8")

        self.assertIn('$releaseVersion = "v1.0.1"', script)
        self.assertIn("485experiment-software-portable-buaa", script)
        self.assertIn("实验软件_北航特供版", script)
        self.assertIn("edition_profile.buaa.json", script)

    def test_buaa_edition_profile_declares_one_third_scale(self) -> None:
        profile = json.loads(
            Path("config/edition_profile.buaa.json").read_text(encoding="utf-8")
        )

        self.assertEqual(profile["edition_key"], "buaa")
        self.assertEqual(profile["display_name"], "北航特供版")
        self.assertAlmostEqual(profile["t_channel_scale"], 1.0 / 3.0)
```

- [ ] **Step 4: Run the targeted tests to verify they fail**

Run: `py -m unittest tests.test_serial_logger_with_plot.GroupedMeasurementHelperTests.test_finish_measurement_applies_buaa_scaling_to_t_values_and_moments tests.test_serial_logger_with_plot.GroupedMeasurementDisplayHelperTests.test_build_measurement_footer_text_includes_buaa_note_when_profile_enabled tests.test_app_launcher tests.test_buaa_release_metadata -v`

Expected: FAIL because `EditionProfile`, BUAA-aware helpers, `build_release_buaa.ps1`, and `config/edition_profile.buaa.json` do not exist yet.

- [ ] **Step 5: Commit**

```bash
git add tests/test_serial_logger_with_plot.py tests/test_app_launcher.py tests/test_buaa_release_metadata.py
git commit -m "test: add BUAA special edition coverage"
```

## Task 2: Implement the runtime edition profile and BUAA scaling logic

**Files:**
- Modify: `scripts/serial_logger_with_plot.py`
- Modify: `app_launcher.py`
- Create: `config/edition_profile.buaa.json`

- [ ] **Step 1: Add the minimal edition-profile implementation**

In `scripts/serial_logger_with_plot.py`, add an edition dataclass and loader near the grouped-measurement helpers:

```python
@dataclass(frozen=True)
class EditionProfile:
    edition_key: str = "standard"
    display_name: str = "标准版"
    t_channel_scale: float = 1.0
    notes: str = ""


def load_edition_profile(config_dir: Path) -> EditionProfile:
    profile_path = config_dir / "edition_profile.json"
    if not profile_path.exists():
        return EditionProfile()
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    return EditionProfile(
        edition_key=payload.get("edition_key", "standard"),
        display_name=payload.get("display_name", "标准版"),
        t_channel_scale=float(payload.get("t_channel_scale", 1.0)),
        notes=payload.get("notes", ""),
    )
```

Create `config/edition_profile.buaa.json`:

```json
{
  "edition_key": "buaa",
  "display_name": "北航特供版",
  "t_channel_scale": 0.3333333333333333,
  "notes": "T1/T2/T3 and derived moments are scaled by 1/3 for the BUAA sensor range."
}
```

- [ ] **Step 2: Make grouped-measurement results use the edition profile**

Update `compute_group_channel_averages()` and `finish_measurement_group()` in `scripts/serial_logger_with_plot.py` so the special edition applies scaling before building `MeasurementGroupResult`:

```python
def compute_group_channel_averages(
    samples: Sequence[MeasurementSample],
    edition_profile: EditionProfile | None = None,
) -> Tuple[float, float, float]:
    profile = edition_profile or EditionProfile()
    ...
    return (
        sum(cast(List[float], t1_values)) / len(samples) * profile.t_channel_scale,
        sum(cast(List[float], t2_values)) / len(samples) * profile.t_channel_scale,
        sum(cast(List[float], t3_values)) / len(samples) * profile.t_channel_scale,
    )
```

```python
def finish_measurement_group(
    state: MeasurementSessionState,
    total_current_text: str,
    end_time: datetime,
    edition_profile: EditionProfile | None = None,
) -> MeasurementGroupResult:
    ...
    average_t1, average_t2, average_t3 = compute_group_channel_averages(
        samples,
        edition_profile=edition_profile,
    )
```

Update `build_measurement_footer_text()` so BUAA profiles include the edition label and scaling note:

```python
def build_measurement_footer_text(profile: EditionProfile | None = None) -> str:
    active = profile or EditionProfile()
    suffix = ""
    if active.edition_key == "buaa":
        suffix = "  |  北航特供版：T1/T2/T3 与由其推导的力矩结果按 1/3 换算"
    return (
        "485 Experiment Software  |  "
        "Maintained by Chenghang Li  |  "
        "github.com/Es777777/485experiment-software-portable"
        + suffix
    )
```

- [ ] **Step 3: Thread the edition profile into launcher and live-plot UI**

In `app_launcher.py`, add a matching `EditionProfile` dataclass and a `load_edition_profile()` helper, then make `build_launcher_branding_copy()` accept an optional profile:

```python
def build_launcher_branding_copy(
    profile: EditionProfile | None = None,
) -> dict[str, str]:
    active = profile or EditionProfile()
    title = APP_TITLE if active.edition_key == "standard" else f"{APP_TITLE} - {active.display_name}"
    subtitle = "支持 Modbus 采集、实时曲线、原始串口采集、视频回填和后处理。"
    if active.edition_key == "buaa":
        subtitle += " 北航特供版会将 T1/T2/T3 及其推导力矩结果按 1/3 口径显示。"
    return {
        "title": title,
        "subtitle": subtitle,
        "signature": (...),
    }
```

Store the loaded profile in both launcher and live-plot runtime objects and pass it into:

- `build_launcher_branding_copy(self.edition_profile)`
- `finish_measurement_group(..., edition_profile=self.edition_profile)`
- `build_measurement_footer_text(self.edition_profile)`

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `py -m unittest tests.test_serial_logger_with_plot.GroupedMeasurementHelperTests.test_finish_measurement_applies_buaa_scaling_to_t_values_and_moments tests.test_serial_logger_with_plot.GroupedMeasurementDisplayHelperTests.test_build_measurement_footer_text_includes_buaa_note_when_profile_enabled tests.test_app_launcher tests.test_buaa_release_metadata -v`

Expected: PASS.

- [ ] **Step 5: Run the broader suites**

Run: `py -m unittest tests.test_app_launcher tests.test_serial_logger_with_plot -v`

Expected: PASS, confirming the standard edition still behaves the same and the new BUAA-aware logic only activates with a profile file.

- [ ] **Step 6: Commit**

```bash
git add app_launcher.py scripts/serial_logger_with_plot.py config/edition_profile.buaa.json tests/test_app_launcher.py tests/test_serial_logger_with_plot.py tests/test_buaa_release_metadata.py
git commit -m "feat: add BUAA special edition scaling"
```

## Task 3: Add a separate BUAA packaging flow and validate the artifact naming

**Files:**
- Create: `build_release_buaa.ps1`
- Modify: `README_portable.txt` or package-time generated BUAA readme copy
- Modify: `tests/test_buaa_release_metadata.py`

- [ ] **Step 1: Write the minimal BUAA packaging script**

Create `build_release_buaa.ps1` based on the standard script, but with BUAA-specific names and profile copy:

```powershell
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildRoot = Join-Path $projectRoot "build"
$distRoot = Join-Path $projectRoot "dist"
$releaseVersion = "v1.0.1"
$releaseDate = Get-Date -Format "yyyyMMdd"
$zipName = "485experiment-software-portable-buaa-$releaseVersion-$releaseDate.zip"

Set-Location $projectRoot
py -3 -m pip install -r requirements.txt
py -3 -m pip install pyinstaller
py -3 -m PyInstaller .\app_launcher.spec --noconfirm

$appDist = Join-Path $distRoot "实验软件"
$buaaDist = Join-Path $distRoot "实验软件_北航特供版"
if (Test-Path $buaaDist) { Remove-Item $buaaDist -Recurse -Force }
Copy-Item -Path $appDist -Destination $buaaDist -Recurse -Force
Copy-Item -Path (Join-Path $projectRoot "config\edition_profile.buaa.json") -Destination (Join-Path $buaaDist "config\edition_profile.json") -Force
Copy-Item -Path (Join-Path $projectRoot "README_portable.txt") -Destination (Join-Path $buaaDist "README.txt") -Force

$zipPath = Join-Path $distRoot $zipName
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $buaaDist '*') -DestinationPath $zipPath
Write-Host "BUAA portable release zip created at: $zipPath"
```

- [ ] **Step 2: Add a BUAA note to the packaged README text**

Update `README_portable.txt` with a short paragraph that can safely appear in the special edition package:

```text
北航特供版说明

- 本版本会将 T1/T2/T3 以及由其推导的 M_y、M_x、M、theta 统一按 1/3 系数换算。
- 总电流、平均合力和原始采样列保持原始口径不变。
```

Keep the wording neutral enough that it is still understandable if copied into the BUAA package only.

- [ ] **Step 3: Run the packaging metadata tests**

Run: `py -m unittest tests.test_buaa_release_metadata -v`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add build_release_buaa.ps1 README_portable.txt tests/test_buaa_release_metadata.py
git commit -m "build: add BUAA special edition package"
```

## Task 4: Build the BUAA portable package and verify the result locally

**Files:**
- Modify: generated output under `dist/`
- Verify: desktop BUAA portable folder

- [ ] **Step 1: Run the BUAA build script**

Run: `powershell -ExecutionPolicy Bypass -File "C:\Users\asd\OneDrive\Desktop\实验软件 - 副本\.worktrees\grouped-pwm-measurement\build_release_buaa.ps1"`

Expected: success output showing a BUAA folder under `dist\实验软件_北航特供版` and a zip named `485experiment-software-portable-buaa-v1.0.1-<date>.zip`.

- [ ] **Step 2: Run the full verification suite after the BUAA build**

Run: `py -m unittest tests.test_app_launcher tests.test_serial_logger_with_plot tests.test_buaa_release_metadata -v`

Expected: PASS.

- [ ] **Step 3: Copy the BUAA package to the desktop delivery folder**

Run: `powershell -Command "Copy-Item -Path 'C:\Users\asd\OneDrive\Desktop\实验软件 - 副本\.worktrees\grouped-pwm-measurement\dist\实验软件_北航特供版' -Destination 'C:\Users\asd\OneDrive\Desktop\实验软件_北航特供版_20260522' -Recurse -Force"`

Expected: a new desktop directory `实验软件_北航特供版_20260522` exists.

- [ ] **Step 4: Verify the packaged BUAA profile file is present**

Run: `powershell -Command "Get-Content 'C:\Users\asd\OneDrive\Desktop\实验软件_北航特供版_20260522\config\edition_profile.json'"`

Expected: JSON content with `"edition_key": "buaa"` and `"t_channel_scale": 0.3333333333333333`.

- [ ] **Step 5: Commit**

```bash
git add config/edition_profile.buaa.json build_release_buaa.ps1 README_portable.txt tests/test_buaa_release_metadata.py
git commit -m "build: package BUAA special edition"
```
