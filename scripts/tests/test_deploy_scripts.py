"""Exercise deployment ordering and image identity without a live cluster."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
FAKE_TOOL = r"""#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["COMMAND_TRACE"], "a") as trace:
    trace.write(json.dumps([name, *args]) + "\n")
if name == "helm" and args[0] == "diff":
    sys.exit(2)
if name == "kubectl" and "--for=create" in args:
    sys.exit(int(os.environ.get("CREATE_FAILS", "0")))
if name == "kubectl" and "create" in args:
    print("{}")
"""


class DeployScripts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / "app").mkdir()
        for name in ("lib.sh", "openbao-up.sh", "app-up.sh", "image-tag.sh"):
            shutil.copy(REPO / "scripts" / name, self.root / "scripts" / name)
        shutil.copy(REPO / "versions.env", self.root / "versions.env")
        shutil.copytree(REPO / "deploy/openbao", self.root / "deploy/openbao")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("helm", "kubectl"):
            tool = self.bin / name
            tool.write_text(FAKE_TOOL)
            tool.chmod(0o755)
        self.trace = self.root / "commands.jsonl"
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        COMMAND_TRACE=str(self.trace), IMAGE_TAG="test")

    def run_script(self, name, check=True):
        return subprocess.run(["bash", str(self.root / "scripts" / name)],
                              env=self.env, capture_output=True, text=True, check=check)

    def commands(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()]

    def test_openbao_waits_for_creation_before_readiness(self):
        self.run_script("openbao-up.sh")
        waits = [c for c in self.commands() if c[0] == "kubectl" and "wait" in c]
        self.assertEqual(len(waits), 2)
        self.assertIn("--for=create", waits[0])
        self.assertIn("--for=condition=Ready", waits[1])
        self.assertTrue(all("pod/openbao-0" in c for c in waits))

    def test_failed_creation_stops_deployment(self):
        self.env["CREATE_FAILS"] = "1"
        result = self.run_script("openbao-up.sh", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any("--for=condition=Ready" in c for c in self.commands()))

    def test_app_waits_for_rollout_after_install(self):
        self.run_script("app-up.sh")
        commands = self.commands()
        self.assertEqual(commands[-1], ["kubectl", "-n", "aggregator", "rollout",
                         "status", "deployment/integration-aggregator", "--timeout=300s"])
        self.assertTrue(any(c[:3] == ["helm", "upgrade", "--install"] for c in commands))

    def test_image_tag_ignores_generated_files_but_tracks_source(self):
        source = self.root / "app/main.py"
        source.write_text("print('hello')\n")
        before = self.run_script("image-tag.sh").stdout
        for name in ("__pycache__/main.pyc", "src/__pycache__/module.pyc",
                     ".pytest_cache/state", ".venv/site-packages/pkg.py",
                     "coverage.xml", ".coverage", "tests/test_main.py"):
            path = self.root / "app" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("generated data")
        self.assertEqual(before, self.run_script("image-tag.sh").stdout)
        source.write_text("print('changed')\n")
        self.assertNotEqual(before, self.run_script("image-tag.sh").stdout)


if __name__ == "__main__":
    unittest.main()
