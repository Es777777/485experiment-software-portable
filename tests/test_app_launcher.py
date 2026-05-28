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


class LauncherCommandTests(unittest.TestCase):
    def test_build_launcher_tab_descriptions_mentions_grouped_measurement(
        self,
    ) -> None:
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


class _FakeVar:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class _FakeLabel:
    def __init__(self) -> None:
        self.configured: dict[str, str] = {}

    def configure(self, **kwargs: str) -> None:
        self.configured.update(kwargs)


class LauncherStatusSyncTests(unittest.TestCase):
    def test_set_status_updates_badge_text_and_color(self) -> None:
        app = app_launcher.ToolLauncherApp.__new__(app_launcher.ToolLauncherApp)
        app.status_var = _FakeVar("就绪")
        app.status_badge_var = _FakeVar("")
        app.status_badge_label = _FakeLabel()

        app._set_status("Modbus 实时曲线 运行中")

        self.assertEqual(app.status_var.get(), "Modbus 实时曲线 运行中")
        self.assertEqual(
            app.status_badge_var.get(),
            "系统状态  |  Modbus 实时曲线 运行中",
        )
        self.assertEqual(
            app.status_badge_label.configured["fg"],
            app_launcher.build_launcher_palette()["status_running"],
        )


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

    def test_build_launcher_branding_copy_keeps_mainline_title_for_standard_profile(
        self,
    ) -> None:
        branding = app_launcher.build_launcher_branding_copy(
            app_launcher.EditionProfile()
        )

        self.assertEqual(branding["title"], app_launcher.APP_TITLE)
        self.assertNotIn("特供版", branding["title"])


if __name__ == "__main__":
    unittest.main()
