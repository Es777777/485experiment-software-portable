from pathlib import Path
import json
import unittest


class BuaaReleaseMetadataTests(unittest.TestCase):
    def test_buaa_build_script_uses_special_artifact_name(self) -> None:
        script = Path("build_release_buaa.ps1").read_text(encoding="utf-8")

        self.assertIn('$releaseVersion = "v1.0.1"', script)
        self.assertIn("485experiment-software-portable-buaa", script)
        self.assertIn("edition_profile.json", script)
        self.assertIn("edition_profile.buaa.json", script)

    def test_buaa_edition_profile_declares_one_third_scale(self) -> None:
        profile = json.loads(
            Path("config/edition_profile.buaa.json").read_text(encoding="utf-8")
        )

        self.assertEqual(profile["edition_key"], "buaa")
        self.assertEqual(profile["display_name"], "北航特供版")
        self.assertAlmostEqual(profile["t_channel_scale"], 1.0 / 3.0)


if __name__ == "__main__":
    unittest.main()
