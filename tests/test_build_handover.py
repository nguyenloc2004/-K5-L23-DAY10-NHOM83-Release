import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_handover.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BuildHandoverTest(unittest.TestCase):
    def test_requires_wrong_hash_visual_review_then_builds_rework_and_manifests(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "runs" / "r83"
            delivery = run / "delivery"
            for subdir in ("images", "labels", "masks"):
                (delivery / subdir).mkdir(parents=True)

            names = ("001", "002", "003")
            for name in names:
                (delivery / "images" / f"{name}.jpg").write_bytes(f"image-{name}".encode())
                label_class = "80" if name == "002" else "0"
                (delivery / "labels" / f"{name}.txt").write_text(
                    f"{label_class} 0.5 0.5 0.2 0.2\n", encoding="utf-8"
                )
                (delivery / "masks" / f"{name}.png").write_bytes(f"mask-{name}".encode())

            items = {}
            for name in names:
                items[name] = {
                    "image": f"images/{name}.jpg",
                    "label": f"labels/{name}.txt",
                    "mask": f"masks/{name}.png",
                    "image_sha256": "incorrect" if name == "001" else digest(delivery / "images" / f"{name}.jpg"),
                    "label_sha256": digest(delivery / "labels" / f"{name}.txt"),
                    "mask_sha256": digest(delivery / "masks" / f"{name}.png"),
                }
            manifest_path = delivery / "manifest.json"
            manifest_path.write_text(json.dumps({"items": items}), encoding="utf-8")
            metadata = {
                "items": [
                    {
                        "image": "001", "scene_id": "scene_A", "split": "train",
                        "job_id": "J01", "guideline_version": "v1.3",
                    },
                    {
                        "image": "002", "scene_id": "scene_B", "split": "val",
                        "job_id": "J01", "guideline_version": "v1.2",
                    },
                    {
                        "image": "003", "scene_id": "scene_A", "split": "val",
                        "job_id": "J01", "guideline_version": "v1.2",
                    },
                ]
            }
            metadata_path = delivery / "metadata.json"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            (delivery / "jobs.csv").write_text(
                "job_id,annotator,reviewer,guideline\nJ01,A01,Q01,v1.2\n",
                encoding="utf-8",
            )
            (delivery / "classes.txt").write_text(
                "".join(f"{i} class_{i}\n" for i in range(80)), encoding="utf-8"
            )
            release_id = "lab250_" + hashlib.sha256(
                manifest_path.read_bytes() + metadata_path.read_bytes()
            ).hexdigest()[:12]
            (delivery / "release.json").write_text(
                json.dumps({"release_id": release_id}), encoding="utf-8"
            )
            errors = {
                "errors": [
                    {"type": "wrong_hash", "target": "001"},
                    {"type": "invalid_class", "target": "002"},
                    {"type": "thing_overlap", "target": "003"},
                    {"type": "scene_leak", "target": "scene_A"},
                    {"type": "guideline_mismatch", "target": "001"},
                ]
            }
            (run / "errors.json").write_text(json.dumps(errors), encoding="utf-8")

            command = [sys.executable, str(BUILDER), "--run", str(run)]
            without_review = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(without_review.returncode, 0)
            self.assertIn("--wrong-hash-good", without_review.stderr)

            built = subprocess.run(
                command + ["--wrong-hash-good", "001"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            output = run / "handover" / f"{release_id}_v2"
            self.assertEqual(
                sorted(path.stem for path in (output / "images").glob("*.jpg")),
                ["001", "003"],
            )
            self.assertEqual(
                sorted(path.stem for path in (output / "labels").glob("*.txt")),
                ["001", "003"],
            )
            with (output / "rework_queue.csv").open(encoding="utf-8", newline="") as handle:
                queue = list(csv.DictReader(handle))
            self.assertEqual([row["image"] for row in queue], ["002"])
            with (output / "manifest.csv").open(encoding="utf-8", newline="") as handle:
                manifest_rows = list(csv.DictReader(handle))
            self.assertEqual(len(manifest_rows), 4)
            self.assertTrue(all(len(row["sha256"]) == 64 for row in manifest_rows))
            with (output / "truyvet.csv").open(encoding="utf-8", newline="") as handle:
                trace_rows = list(csv.DictReader(handle))
            self.assertEqual({row["split"] for row in trace_rows}, {"train"})
            self.assertEqual(
                {row["guideline"] for row in trace_rows},
                {"v1.2"},
            )
            self.assertIn("TOTAL", (output / "label_summary.csv").read_text(encoding="utf-8"))
            self.assertIn("wrong_hash", (output / "README.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
