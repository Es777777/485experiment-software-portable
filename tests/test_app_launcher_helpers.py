import unittest

import app_launcher


class LauncherHelperTests(unittest.TestCase):
    def test_child_process_environment_forces_utf8_output(self) -> None:
        env = app_launcher.build_child_process_environment({"PATH": "demo"})

        self.assertEqual(env["PATH"], "demo")
        self.assertEqual(env["PYTHONUTF8"], "1")
        self.assertEqual(env["PYTHONIOENCODING"], "utf-8")

    def test_select_preferred_port_keeps_detected_config_port(self) -> None:
        self.assertEqual(
            app_launcher.select_preferred_port(["COM4", "COM3"], "com3"),
            "COM3",
        )

    def test_select_preferred_port_uses_first_detected_when_config_missing(self) -> None:
        self.assertEqual(
            app_launcher.select_preferred_port(["COM7", "COM8"], "COM3"),
            "COM7",
        )

    def test_select_preferred_port_keeps_config_when_nothing_detected(self) -> None:
        self.assertEqual(
            app_launcher.select_preferred_port([], "COM3"),
            "COM3",
        )


if __name__ == "__main__":
    unittest.main()
