from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from automation.originality import assess_job, cosine_similarity


class OriginalityTests(unittest.TestCase):
    def test_similarity_detects_near_duplicate_scripts(self) -> None:
        left = "Train wheels use a conical tread so the axle steers itself through a curve."
        right = "A conical tread lets train wheels steer their axle through railway curves."
        self.assertGreater(cosine_similarity(left, right), 0.55)

    def test_complete_original_package_passes(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            manifest = Path(folder) / "manifest.json"
            assets = [
                {"type": "stock_video", "pexels_id": index, "source_url": f"https://pexels.test/{index}",
                 "license": "Pexels License", "commercial_use": True}
                for index in range(1, 7)
            ] + [
                {"type": "procedural_diagram", "source_url": f"local://diagram-{index}.png",
                 "license": "Project-generated original diagram", "commercial_use": True}
                for index in range(2)
            ]
            manifest.write_text(json.dumps({
                "fact_sources": [{"url": "https://source.test/a"}, {"url": "https://source.test/b"}],
                "assets": assets,
            }), encoding="utf-8")
            connection = sqlite3.connect(":memory:")
            connection.row_factory = sqlite3.Row
            connection.execute("""CREATE TABLE jobs(id TEXT,topic TEXT,title TEXT,script TEXT,
                               manifest_path TEXT,status TEXT,parent_job_id TEXT)""")
            script = " ".join(f"engineeringword{index}" for index in range(80))
            report = assess_job(connection, {"id": "new", "topic": "unique mechanism", "title": "Unique",
                                                     "script": script, "manifest_path": str(manifest),
                                                     "parent_job_id": ""})
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["score"], 100)

    def test_hybrid_package_accepts_three_stock_and_four_original_animations(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            manifest = Path(folder) / "manifest.json"
            assets = [
                {"type": "stock_video", "pexels_id": index, "source_url": f"https://pexels.test/{index}",
                 "license": "Pexels License", "commercial_use": True}
                for index in range(1, 4)
            ] + [
                {"type": "procedural_animation", "source_url": f"local://animation-{index}.mp4",
                 "license": "Project-generated original animation", "commercial_use": True}
                for index in range(4)
            ]
            manifest.write_text(json.dumps({
                "hybrid_template": "bridge-expansion-joint",
                "fact_sources": [{"url": "https://source.test/a"}, {"url": "https://source.test/b"}],
                "assets": assets,
            }), encoding="utf-8")
            connection = sqlite3.connect(":memory:")
            connection.row_factory = sqlite3.Row
            connection.execute("""CREATE TABLE jobs(id TEXT,topic TEXT,title TEXT,script TEXT,
                               manifest_path TEXT,status TEXT,parent_job_id TEXT)""")
            script = " ".join(f"mechanismword{index}" for index in range(80))
            report = assess_job(connection, {
                "id": "hybrid", "topic": "unique bridge mechanism", "title": "Unique Bridge",
                "script": script, "manifest_path": str(manifest), "parent_job_id": "",
            })
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["score"], 100)


if __name__ == "__main__":
    unittest.main()
