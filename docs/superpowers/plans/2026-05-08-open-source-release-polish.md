# Open Source Release Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the grouped PWM measurement branch into a polished open-source release with a Chinese-first repository homepage, portable usage guide, reproducible release zip, GitHub PR, and GitHub Release download entry.

**Architecture:** Keep the software feature code stable and focus this plan on the delivery layer: rewrite top-level docs for end users, upgrade the existing PowerShell release script so it outputs a complete portable folder plus a versioned zip, then publish the branch through GitHub PR and Release metadata. Reuse the already-tested `feature/grouped-pwm-measurement` branch, verify existing tests and packaging still pass after doc/script changes, and avoid risky GUI refactors beyond light wording polish.

**Tech Stack:** Markdown, PowerShell, Python 3, PyInstaller, Git, GitHub CLI (`gh`)

---

## File Map

- Modify: `README.md` - replace the current script-oriented landing page with a Chinese-first project homepage for users and contributors.
- Modify: `README_portable.txt` - turn the portable note into a complete field-operator guide for grouped PWM measurement and export.
- Modify: `build_release.ps1` - generate a release-ready portable folder and versioned zip artifact.
- Create: `docs/release-notes/v1.0.0.md` - Chinese release notes used for GitHub Release body.
- Create: `docs/project-assets/release-artifacts.md` - short internal note documenting zip name, folder name, and release structure.

### Task 1: Rewrite the repository homepage with a user-facing structure

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

Add this test file as `tests/test_readme_content.py`:

```python
from pathlib import Path
import unittest


class ReadmeContentTests(unittest.TestCase):
    def test_readme_includes_release_and_grouped_measurement_sections(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("# 485 实验软件便携版", readme)
        self.assertIn("## 功能亮点", readme)
        self.assertIn("## 便携版下载", readme)
        self.assertIn("## PWM 分组测量流程", readme)
        self.assertIn("## 从源码运行", readme)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_readme_content -v`
Expected: FAIL because the current `README.md` is still the old English script document and does not contain the new Chinese sections.

- [ ] **Step 3: Write minimal implementation**

Replace `README.md` with a Chinese-first homepage containing these exact top-level headings in this order:

```markdown
# 485 实验软件便携版

## 功能亮点

## 适用场景

## 快速开始

## 便携版下载

## PWM 分组测量流程

## 输出文件说明

## 目录结构

## 从源码运行

## 常见问题

## 更新说明
```

Populate each section with project-specific content from the current codebase:

- In `功能亮点`, describe Modbus 采集, 实时曲线, 手动去皮, PWM 分组测量, Excel 导出, 视频回填.
- In `便携版下载`, reference GitHub Releases and say the latest packaged zip will be attached there.
- In `PWM 分组测量流程`, describe: input PWM -> start -> observe stability -> input total current -> finish -> next group -> export.
- In `从源码运行`, keep a short developer section using `py -m pip install -r requirements.txt` and `py -m PyInstaller -y app_launcher.spec`.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m unittest tests.test_readme_content -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_readme_content.py
git commit -m "docs: rewrite project homepage"
```

### Task 2: Upgrade the portable usage guide for experiment operators

**Files:**
- Modify: `README_portable.txt`
- Modify: `tests/test_readme_content.py`

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_readme_content.py`:

```python
    def test_portable_readme_describes_grouped_measurement_steps(self) -> None:
        portable = Path("README_portable.txt").read_text(encoding="utf-8")

        self.assertIn("PWM 分组测量", portable)
        self.assertIn("开始测量", portable)
        self.assertIn("结束测量", portable)
        self.assertIn("下一组", portable)
        self.assertIn("导出表格", portable)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_readme_content -v`
Expected: FAIL because `README_portable.txt` does not yet mention the grouped measurement workflow in detail.

- [ ] **Step 3: Write minimal implementation**

Rewrite `README_portable.txt` into a Chinese operator guide with these sections:

```text
实验软件便携版使用说明

一、启动方式
二、采集前准备
三、PWM 分组测量流程
四、导出结果表
五、目录说明
六、常见问题
```

In `三、PWM 分组测量流程`, include these numbered actions exactly in spirit:

1. 输入 PWM
2. 点击“开始测量”
3. 人工判断曲线稳定
4. 输入总电流
5. 点击“结束测量”
6. 查看历史记录
7. 点击“下一组”继续
8. 最后点击“导出表格”

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m unittest tests.test_readme_content -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README_portable.txt tests/test_readme_content.py
git commit -m "docs: expand portable usage guide"
```

### Task 3: Produce a release-ready zip artifact from the PowerShell build script

**Files:**
- Modify: `build_release.ps1`
- Create: `docs/project-assets/release-artifacts.md`

- [ ] **Step 1: Write the failing test**

Create `tests/test_release_metadata.py` with this content:

```python
from pathlib import Path
import unittest


class ReleaseMetadataTests(unittest.TestCase):
    def test_build_release_script_defines_versioned_zip_name(self) -> None:
        script = Path("build_release.ps1").read_text(encoding="utf-8")

        self.assertIn("$releaseVersion = \"v1.0.0\"", script)
        self.assertIn("485experiment-software-portable", script)
        self.assertIn("Compress-Archive", script)

    def test_release_artifact_note_exists(self) -> None:
        note = Path("docs/project-assets/release-artifacts.md").read_text(encoding="utf-8")

        self.assertIn("485experiment-software-portable-v1.0.0", note)
        self.assertIn("Release 附件", note)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_release_metadata -v`
Expected: FAIL because the current script does not define a versioned zip artifact and the artifact note file does not exist.

- [ ] **Step 3: Write minimal implementation**

Update `build_release.ps1` with these behaviors:

- Add `$releaseVersion = "v1.0.0"`
- Add `$releaseDate = Get-Date -Format "yyyyMMdd"`
- Add `$zipName = "485experiment-software-portable-$releaseVersion-$releaseDate.zip"`
- After copying `config` and `README.txt`, create the zip with:

```powershell
$zipPath = Join-Path $distRoot $zipName
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}
Compress-Archive -Path (Join-Path $appDist.FullName '*') -DestinationPath $zipPath
Write-Host "Portable release zip created at: $zipPath"
```

Create `docs/project-assets/release-artifacts.md` with a short note documenting:

- the release version `v1.0.0`
- the expected zip naming convention
- the fact that Release attachments come from `dist/`

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m unittest tests.test_release_metadata -v`
Expected: PASS.

- [ ] **Step 5: Run the release build script**

Run: `powershell -ExecutionPolicy Bypass -File .\build_release.ps1`
Expected: script completes successfully, creates a portable folder under `dist/`, and creates a `485experiment-software-portable-v1.0.0-<date>.zip` file in `dist/`.

- [ ] **Step 6: Commit**

```bash
git add build_release.ps1 docs/project-assets/release-artifacts.md tests/test_release_metadata.py
git commit -m "build: package release zip artifact"
```

### Task 4: Prepare release notes, create PR, and publish the first GitHub Release

**Files:**
- Create: `docs/release-notes/v1.0.0.md`

- [ ] **Step 1: Write the release notes file**

Create `docs/release-notes/v1.0.0.md` with this exact structure:

```markdown
# v1.0.0 首个便携版发布

## 本次更新
- 新增 PWM 分组测量流程
- 支持记录开始/结束时间与总电流
- 支持导出带日期文件名的结果表
- 支持在实时窗口查看已完成组历史
- 补齐便携版目录与中文说明

## 下载说明
- 请在 Release 页面下载便携版压缩包
- 解压后直接运行 `实验软件.exe`

## 使用提醒
- 首次使用前请检查 `config/` 中的串口与寄存器配置
- 导出的实验结果会保存在 `output/` 目录
```

- [ ] **Step 2: Verify existing tests and packaging still pass**

Run: `py -m unittest tests.test_serial_logger_with_plot tests.test_readme_content tests.test_release_metadata -v`
Expected: PASS.

Run: `powershell -ExecutionPolicy Bypass -File .\build_release.ps1`
Expected: PASS and refresh the zip artifact in `dist/`.

- [ ] **Step 3: Create the Pull Request**

Run:

```bash
gh pr create --base main --head feature/grouped-pwm-measurement --title "feat: add grouped measurement release polish" --body "$(cat <<'EOF'
## Summary
- polish the grouped PWM measurement branch for public delivery
- rewrite the repository homepage and portable usage guide in Chinese
- generate a release-ready portable zip artifact and release notes

## Test Plan
- [x] py -m unittest tests.test_serial_logger_with_plot tests.test_readme_content tests.test_release_metadata -v
- [x] powershell -ExecutionPolicy Bypass -File .\build_release.ps1
EOF
)"
```

Expected: GitHub returns a PR URL.

- [ ] **Step 4: Create the GitHub Release**

Run the two commands below, replacing `<DATE>` with the date embedded in the generated zip filename:

```bash
gh release create v1.0.0 "dist/485experiment-software-portable-v1.0.0-<DATE>.zip" --title "v1.0.0 首个便携版发布" --notes-file "docs/release-notes/v1.0.0.md"
gh release view v1.0.0
```

Expected: the release is created and `gh release view v1.0.0` shows the uploaded zip asset.

- [ ] **Step 5: Commit documentation-only leftovers if needed**

If `docs/release-notes/v1.0.0.md` or other tracked files are still uncommitted after release preparation, run:

```bash
git add docs/release-notes/v1.0.0.md
git commit -m "docs: add v1.0.0 release notes"
git push
```

If no tracked changes remain, skip this step.
