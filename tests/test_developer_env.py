"""Offline integration tests using real temporary Git repositories."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "make-developer-env.py"
spec = importlib.util.spec_from_file_location("developer_env", SCRIPT)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def git(path, *args):
    return subprocess.check_output(
        ["git", "-C", str(path), *args], text=True, stderr=subprocess.PIPE
    ).strip()


def repository(path):
    path.mkdir(parents=True)
    git(path, "init")
    git(path, "config", "commit.gpgsign", "false")
    git(path, "config", "core.hooksPath", str(path / "no-hooks"))
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.invalid")
    (path / "pyproject.toml").write_text("# fixture\n", encoding="utf-8")
    (path / "uv.lock").write_text("# fixture lock\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-m", "Fixture")


class DeveloperEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="developer env ")
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name).resolve()
        self.root = self.parent / "lighthouse"
        repository(self.root)
        self.origins = {}
        for name in setup.REPOSITORIES:
            origin = self.parent / "origins" / name
            repository(origin)
            (origin / name).mkdir()
            (origin / name / "__init__.py").write_text("", encoding="utf-8")
            git(origin, "add", ".")
            git(origin, "commit", "-m", "Package")
            self.origins[name] = str(origin)
        self.sources = patch.dict(setup.REPOSITORIES, self.origins, clear=True)
        self.sources.start()
        self.addCleanup(self.sources.stop)

    def test_clone_repeat_preserves_dirty_checkout_and_metadata(self):
        setup.setup(self.root)
        sibling = self.parent / "activitysim"
        git(sibling, "checkout", "-b", "local-work")
        (sibling / "pyproject.toml").write_text("# local edit\n", encoding="utf-8")
        before = {
            p: p.read_bytes()
            for p in [
                self.root / "pyproject.toml",
                self.root / "uv.lock",
                self.root / "uv-local",
            ]
        }
        setup.setup(self.root)
        self.assertEqual(git(sibling, "branch", "--show-current"), "local-work")
        self.assertEqual((sibling / "pyproject.toml").read_text(), "# local edit\n")
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)
        exclude = self.root / ".git" / "info" / "exclude"
        self.assertEqual(exclude.read_text().splitlines().count("/uv-local"), 1)
        self.assertEqual(git(self.root, "check-ignore", "uv-local"), "uv-local")
        self.assertEqual(git(self.root, "status", "--porcelain"), "")

    def test_invalid_existing_sibling_is_preserved(self):
        sibling = self.parent / "activitysim"
        sibling.mkdir()
        marker = sibling / "keep.txt"
        marker.write_text("keep")
        with self.assertRaises(ValueError):
            setup.setup(self.root)
        self.assertEqual(marker.read_text(), "keep")
        self.assertFalse((self.parent / "sharrow").exists())
        self.assertFalse((self.root / "uv-local").exists())

    def test_unrelated_runner_is_preserved(self):
        runner = self.root / "uv-local"
        runner.write_text("my own program\n")
        with self.assertRaises(ValueError):
            setup.setup(self.root)
        self.assertEqual(runner.read_text(), "my own program\n")
        self.assertFalse((self.parent / "activitysim").exists())

    def test_worktree_exclusion(self):
        tree = self.parent / "worktree"
        git(self.root, "worktree", "add", "-b", "worktree-test", str(tree))
        setup.setup(tree)
        self.assertEqual(git(tree, "check-ignore", "uv-local"), "uv-local")
        self.assertEqual(git(tree, "status", "--porcelain"), "")

    def test_runner_forwards_arguments_environment_and_exit_code(self):
        setup.setup(self.root)
        loader = SourceFileLoader("runner", str(self.root / "uv-local"))
        runner_spec = importlib.util.spec_from_loader("runner", loader)
        runner = importlib.util.module_from_spec(runner_spec)
        runner.__file__ = str(self.root / "uv-local")
        loader.exec_module(runner)
        args = [runner.__file__, "python", "script with spaces.py", "a&b", "--flag"]
        with (
            patch.object(sys, "argv", args),
            patch.object(runner.shutil, "which", return_value="uv"),
            patch.object(runner.subprocess, "call", return_value=7) as call,
            patch.dict(os.environ, {"PYTHONPATH": "existing path"}),
        ):
            self.assertEqual(runner.main(), 7)
        command = call.call_args.args[0]
        self.assertEqual(command[command.index("--") + 1 :], args[1:])
        self.assertEqual(command.count("--with-editable"), 2)
        self.assertIn("--locked", command)
        self.assertEqual(call.call_args.kwargs["cwd"], self.root)
        expected = os.pathsep.join(
            [
                str(self.parent / "activitysim"),
                str(self.parent / "sharrow"),
                "existing path",
            ]
        )
        self.assertEqual(call.call_args.kwargs["env"]["PYTHONPATH"], expected)

    def test_runner_usage(self):
        setup.setup(self.root)
        result = subprocess.run(
            [sys.executable, str(self.root / "uv-local")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stderr)


if __name__ == "__main__":
    unittest.main()
