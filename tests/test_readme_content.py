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

    def test_portable_readme_describes_grouped_measurement_steps(self) -> None:
        portable = Path("README_portable.txt").read_text(encoding="utf-8")

        self.assertIn("PWM 分组测量", portable)
        self.assertIn("开始测量", portable)
        self.assertIn("结束测量", portable)
        self.assertIn("下一组", portable)
        self.assertIn("导出表格", portable)
