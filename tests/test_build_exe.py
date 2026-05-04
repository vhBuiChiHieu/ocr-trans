from __future__ import annotations

import unittest

from scripts import build_exe


class BuildExeTests(unittest.TestCase):
    def test_build_command_defaults_to_onedir_and_noupx(self) -> None:
        command = build_exe.build_command(mode="onedir")

        self.assertIn("--onedir", command)
        self.assertNotIn("--onefile", command)
        self.assertIn("--noupx", command)
        self.assertIn("--exclude-module", command)
        self.assertEqual(command[-1], str(build_exe.ROOT / "main.py"))

    def test_build_command_supports_onefile_mode(self) -> None:
        command = build_exe.build_command(mode="onefile")

        self.assertIn("--onefile", command)
        self.assertNotIn("--onedir", command)

    def test_build_command_supports_upx_directory(self) -> None:
        command = build_exe.build_command(mode="onedir", upx=True, upx_dir="C:/tools/upx")

        self.assertNotIn("--noupx", command)
        self.assertIn("--upx-dir", command)
        upx_dir_index = command.index("--upx-dir")
        self.assertEqual(command[upx_dir_index + 1], "C:/tools/upx")

    def test_output_path_matches_mode(self) -> None:
        self.assertEqual(
            build_exe.output_path("onefile"),
            build_exe.DIST / "orc-trans-app.exe",
        )
        self.assertEqual(
            build_exe.output_path("onedir"),
            build_exe.DIST / "orc-trans-app" / "orc-trans-app.exe",
        )


if __name__ == "__main__":
    unittest.main()
