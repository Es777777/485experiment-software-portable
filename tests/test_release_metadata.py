from pathlib import Path
import unittest


class ReleaseMetadataTests(unittest.TestCase):
    def test_build_release_script_defines_versioned_zip_name(self) -> None:
        script = Path("build_release.ps1").read_text(encoding="utf-8")

        self.assertIn('$releaseVersion = "v1.0.0"', script)
        self.assertIn("485experiment-software-portable", script)
        self.assertIn("Compress-Archive", script)

    def test_release_artifact_note_exists(self) -> None:
        note = Path("docs/project-assets/release-artifacts.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("485experiment-software-portable-v1.0.0", note)
        self.assertIn("Release 附件", note)
