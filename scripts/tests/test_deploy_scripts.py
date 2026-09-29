"""Exercise deployment ordering and image identity without a live cluster."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
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
        shutil.copy(REPO / "Makefile", self.root / "Makefile")
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

    def test_smoke_starts_forwards_before_http_requests(self):
        result = subprocess.run(["make", "-n", "smoke"], cwd=self.root,
                                env=self.env, capture_output=True, text=True, check=True)
        self.assertLess(result.stdout.index("port-forward.sh"),
                        result.stdout.index("scripts/smoke.sh"))

    def test_stale_pid_file_does_not_stop_unrelated_process(self):
        process = subprocess.Popen(["sleep", "60"])
        self.addCleanup(process.wait)
        self.addCleanup(process.terminate)
        pid_file = self.root / "stale.pid"
        pid_file.write_text(f"{process.pid} 0\n")
        subprocess.run(["bash", "-c", 'source "$1"; stop_process "$2"', "_",
                        str(self.root / "scripts/lib.sh"), str(pid_file)], check=True)
        self.assertIsNone(process.poll())
        self.assertFalse(pid_file.exists())

    def test_live_forward_is_replaced_and_stopped(self):
        tool = self.bin / "kubectl"
        tool.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(60)\n")
        pid_file = self.root / "forward.pid"
        source = str(self.root / "scripts/lib.sh")
        command = 'source "$1"; start_port_forward aggregator svc/app 8080:8080 "$2"'
        def start():
            subprocess.run(["bash", "-c", command, "_", source, str(pid_file)],
                           env=self.env, check=True)
            return int(pid_file.read_text().split()[0])
        def live(pid):
            path = Path(f"/proc/{pid}/stat")
            return path.exists() and path.read_text().split()[2] != "Z"
        first = start()
        try:
            time.sleep(0.05)
            second = start()
            self.assertNotEqual(first, second)
            self.assertFalse(live(first))
            self.assertTrue(live(second))
        finally:
            subprocess.run(["bash", "-c", 'source "$1"; stop_process "$2"', "_",
                            source, str(pid_file)], check=True)
        self.assertFalse(live(second))

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
