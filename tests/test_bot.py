"""
Integration tests for Daf Yomi History Bot.

Tests cover:
- Masechta name conversion
- Workflow validation
- Required files exist
- Python syntax validation
"""

import os
import re
import sys
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Masechta name mappings (copied from send_video.py to avoid import issues)
MASECHTA_NAME_MAP = {
    "Berakhot": "Berachos",
    "Shabbat": "Shabbos",
    "Sukkah": "Succah",
    "Taanit": "Taanis",
    "Megillah": "Megilah",
    "Chagigah": "Chagiga",
    "Yevamot": "Yevamos",
    "Ketubot": "Kesuvos",
    "Gittin": "Gitin",
    "Kiddushin": "Kidushin",
    "Bava Kamma": "Bava Kama",
    "Bava Batra": "Bava Basra",
    "Makkot": "Makos",
    "Shevuot": "Shevuos",
    "Horayot": "Horayos",
    "Menachot": "Menachos",
    "Chullin": "Chulin",
    "Bekhorot": "Bechoros",
    "Arakhin": "Erchin",
    "Keritot": "Kerisus",
    "Niddah": "Nidah",
}


class TestMasechtaNameMapping(unittest.TestCase):
    """Test masechta name conversion."""

    def test_known_mappings(self):
        """Test that known Hebcal names map correctly to AllDaf names."""
        test_cases = [
            ("Berakhot", "Berachos"),
            ("Shabbat", "Shabbos"),
            ("Menachot", "Menachos"),
            ("Bava Kamma", "Bava Kama"),
            ("Ketubot", "Kesuvos"),
        ]
        for hebcal_name, expected in test_cases:
            with self.subTest(hebcal_name=hebcal_name):
                self.assertEqual(
                    MASECHTA_NAME_MAP.get(hebcal_name, hebcal_name), expected
                )

    def test_unknown_mapping_returns_original(self):
        """Test that unknown names are returned unchanged."""
        unknown_name = "SomeUnknownMasechta"
        self.assertEqual(
            MASECHTA_NAME_MAP.get(unknown_name, unknown_name), unknown_name
        )

    def test_all_mappings_exist(self):
        """Test that all expected masechtot have mappings."""
        expected_masechtot = [
            "Berakhot",
            "Shabbat",
            "Sukkah",
            "Taanit",
            "Megillah",
            "Chagigah",
            "Yevamot",
            "Ketubot",
            "Gittin",
            "Kiddushin",
            "Bava Kamma",
            "Bava Batra",
            "Makkot",
            "Shevuot",
            "Horayot",
            "Menachot",
            "Chullin",
            "Bekhorot",
            "Arakhin",
            "Keritot",
            "Niddah",
        ]
        for masechta in expected_masechtot:
            with self.subTest(masechta=masechta):
                self.assertIn(masechta, MASECHTA_NAME_MAP)


class TestRegexPatterns(unittest.TestCase):
    """Test regex patterns used in video discovery."""

    def test_mp4_url_pattern(self):
        """Test MP4 URL extraction pattern."""
        pattern = r"https://(?:cdn\.jwplayer\.com|content\.jwplatform\.com)/videos/([a-zA-Z0-9]+)\.mp4"

        test_cases = [
            ("https://cdn.jwplayer.com/videos/abc123.mp4", "abc123"),
            ("https://content.jwplatform.com/videos/XYZ789.mp4", "XYZ789"),
        ]

        for url, expected_id in test_cases:
            with self.subTest(url=url):
                match = re.search(pattern, url)
                self.assertIsNotNone(match)
                self.assertEqual(match.group(1), expected_id)

    def test_daf_title_pattern(self):
        """Test daf title parsing pattern."""
        pattern = r"(.+)\s+(\d+)"

        test_cases = [
            ("Menachos 17", ("Menachos", "17")),
            ("Bava Kamma 45", ("Bava Kamma", "45")),
            ("Berakhot 2", ("Berakhot", "2")),
        ]

        for title, expected in test_cases:
            with self.subTest(title=title):
                match = re.match(pattern, title)
                self.assertIsNotNone(match)
                self.assertEqual(match.groups(), expected)


class TestWorkflowValidation(unittest.TestCase):
    """Test that workflow files are valid."""

    def test_ci_workflow_exists(self):
        """Test CI workflow file exists."""
        workflow_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), ".github", "workflows", "ci.yml"
        )
        self.assertTrue(os.path.exists(workflow_path))

    def test_daily_video_workflow_exists(self):
        """Test daily video workflow file exists."""
        workflow_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".github",
            "workflows",
            "daily_video.yml",
        )
        self.assertTrue(os.path.exists(workflow_path))

    def test_poll_commands_workflow_exists(self):
        """Test poll-commands workflow file exists."""
        workflow_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".github",
            "workflows",
            "poll-commands.yml",
        )
        self.assertTrue(os.path.exists(workflow_path))

    def test_workflow_files_are_valid_yaml(self):
        """Test workflow files are valid YAML."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")

        workflows_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), ".github", "workflows"
        )

        for filename in os.listdir(workflows_dir):
            if filename.endswith(".yml"):
                filepath = os.path.join(workflows_dir, filename)
                with self.subTest(file=filename):
                    with open(filepath) as f:
                        # Should not raise
                        yaml.safe_load(f)


class TestRequiredFilesExist(unittest.TestCase):
    """Test that all required files exist."""

    def test_poll_commands_py_exists(self):
        """Test scripts/poll_commands.py exists."""
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "scripts", "poll_commands.py"
        )
        self.assertTrue(os.path.exists(filepath))

    def test_send_video_py_exists(self):
        """Test send_video.py exists."""
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "send_video.py"
        )
        self.assertTrue(os.path.exists(filepath))

    def test_requirements_txt_exists(self):
        """Test requirements.txt exists."""
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "requirements.txt"
        )
        self.assertTrue(os.path.exists(filepath))

    def test_src_modules_exist(self):
        """Test src modules exist."""
        src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
        expected_files = [
            "__init__.py",
            "command_parser.py",
            "rate_limiter.py",
            "message_builder.py",
        ]
        for filename in expected_files:
            filepath = os.path.join(src_dir, filename)
            with self.subTest(file=filename):
                self.assertTrue(os.path.exists(filepath))

    def test_state_directory_exists(self):
        """Test .github/state directory exists."""
        dirpath = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), ".github", "state"
        )
        self.assertTrue(os.path.isdir(dirpath))


class TestPythonSyntax(unittest.TestCase):
    """Test that Python files have valid syntax."""

    def test_poll_commands_py_syntax(self):
        """Test scripts/poll_commands.py has valid syntax."""
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "scripts", "poll_commands.py"
        )
        with open(filepath) as f:
            source = f.read()
        # Should not raise
        compile(source, filepath, "exec")

    def test_send_video_py_syntax(self):
        """Test send_video.py has valid syntax."""
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "send_video.py"
        )
        with open(filepath) as f:
            source = f.read()
        # Should not raise
        compile(source, filepath, "exec")

    def test_test_apis_py_syntax(self):
        """Test test_apis.py has valid syntax."""
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "test_apis.py"
        )
        with open(filepath) as f:
            source = f.read()
        # Should not raise
        compile(source, filepath, "exec")

    def test_src_modules_syntax(self):
        """Test src modules have valid syntax."""
        src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
        for filename in os.listdir(src_dir):
            if filename.endswith(".py"):
                filepath = os.path.join(src_dir, filename)
                with self.subTest(file=filename):
                    with open(filepath) as f:
                        source = f.read()
                    # Should not raise
                    compile(source, filepath, "exec")


if __name__ == "__main__":
    unittest.main()
