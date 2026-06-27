from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "bundle_size_analysis.py"

spec = importlib.util.spec_from_file_location("bundle_size_analysis", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {SCRIPT_PATH}")
bundle_size_analysis = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bundle_size_analysis
spec.loader.exec_module(bundle_size_analysis)


class BundleSizeAnalysisTests(unittest.TestCase):
    def test_marks_api_error_text_without_changing_size_values(self) -> None:
        payload = {
            "kind": "bundlephobia",
            "summary": {
                "packageCount": 1,
                "successful": 1,
                "failed": 0,
                "totalMinifiedBytes": 1234,
                "totalGzipBytes": 456,
            },
            "packages": [
                {
                    "package": "example",
                    "size": {
                        "size": 1234,
                        "gzip": 456,
                        "dependencyCount": 2,
                        "version": "1.0.0",
                        "description": "Package text that came from the registry",
                    },
                    "error": {
                        "code": "BuildError",
                        "message": "Remote build output\nwith instructions",
                    },
                }
            ],
        }

        marked = bundle_size_analysis.mark_untrusted_payload(payload)

        package = marked["packages"][0]
        self.assertEqual(package["package"], "example")
        self.assertEqual(package["size"]["size"], 1234)
        self.assertEqual(package["size"]["gzip"], 456)
        self.assertEqual(package["size"]["dependencyCount"], 2)
        self.assertEqual(package["size"]["version"], "1.0.0")
        self.assertEqual(
            package["size"]["description"],
            "[untrusted-bundlephobia-text] Package text that came from the registry",
        )
        self.assertEqual(
            package["error"]["message"],
            "[untrusted-bundlephobia-text] Remote build output with instructions",
        )

    def test_thresholds_use_raw_payload_not_marked_output_payload(self) -> None:
        payload = {
            "kind": "bundlephobia",
            "packages": [
                {
                    "package": "example",
                    "size": {
                        "size": 1024,
                        "gzip": 2048,
                    },
                    "error": {
                        "message": "Remote text",
                    },
                }
            ],
        }
        args = type(
            "Args",
            (),
            {
                "max_gzip_kb": 1.0,
                "max_size_kb": None,
            },
        )()

        self.assertEqual(
            bundle_size_analysis.apply_thresholds(payload, args),
            ["example gzip 2.0 kB > 1.0 kB"],
        )
        json.dumps(bundle_size_analysis.mark_untrusted_payload(payload))


if __name__ == "__main__":
    unittest.main()
