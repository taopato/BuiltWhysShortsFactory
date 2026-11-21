"""The new pilot must reject generic/still-image storyboards before rendering."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation" / "pilots_3d"))
from story_contract import validate_story  # noqa: E402


class StoryContractTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / "automation" / "pilots_3d" / "lock_storyboard_v5.json"
        self.story = json.loads(path.read_text(encoding="utf-8"))

    def test_lock_storyboard_passes(self):
        self.assertEqual(validate_story(self.story), [])

    def test_seatbelt_storyboard_passes(self):
        path = ROOT / "automation" / "pilots_3d" / "seatbelt_storyboard_v1.json"
        story = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(validate_story(story), [])

    def test_thermostat_storyboard_passes(self):
        path = ROOT / "automation" / "pilots_3d" / "thermostat_storyboard_v1.json"
        story = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(validate_story(story), [])

    def test_rejects_unrelated_or_static_visual_beats(self):
        for beat in self.story["beats"]:
            beat["visible_action"] = "camera pans over a still image"
        self.assertTrue(any("distinct visual actions" in e for e in validate_story(self.story)))

    def test_rejects_missing_sources_and_long_static_beat(self):
        self.story["fact_sources"] = []
        self.story["beats"][0]["end"] = 8
        errors = validate_story(self.story)
        self.assertTrue(any("fact source" in e for e in errors))
        self.assertTrue(any("five seconds" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
