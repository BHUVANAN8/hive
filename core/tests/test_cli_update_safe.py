import argparse
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from framework.runner.cli import cmd_update

class TestCliUpdateSafe(unittest.TestCase):
    def setUp(self):
        self.args = argparse.Namespace(no_stash=False)

    @patch("framework.runner.cli.subprocess.run")
    @patch("framework.runner.cli.Path")
    def test_cmd_update_dirty_tree_success(self, mock_path, mock_run):
        # Setup mocks
        mock_root = MagicMock(spec=Path)
        (mock_root / ".git").is_dir.return_value = True
        mock_path.__file__ = "/root/file.py"
        mock_path.resolve.return_value.parents = [mock_root]
        
        # Define mock side effects for subprocess outcomes
        def run_side_effect(cmd, **kwargs):
            m = MagicMock()
            if cmd == ["git", "status", "--porcelain"]:
                m.stdout = " M modified_file.py"
            elif cmd == ["git", "stash", "--include-untracked"]:
                m.stdout = "Saved working directory and index state..."
            elif cmd == ["git", "pull", "origin", "main"]:
                m.stdout = "Already up to date."
            elif cmd == ["uv", "sync"]:
                m.stdout = "All dependencies are synced."
            elif cmd == ["git", "stash", "pop"]:
                m.stdout = "Dropped refs/stash@{0}"
            else:
                m.stdout = ""
            m.returncode = 0
            return m

        mock_run.side_effect = run_side_effect

        # Execute
        result = cmd_update(self.args)

        # Verify
        self.assertEqual(result, 0)
        # Check that stash and pop were called
        # The key is to check if these commands were called with the right base cmd
        stash_called = any(call.args[0] == ["git", "stash", "--include-untracked"] for call in mock_run.call_args_list)
        pop_called = any(call.args[0] == ["git", "stash", "pop"] for call in mock_run.call_args_list)
        
        self.assertTrue(stash_called, "git stash was not called")
        self.assertTrue(pop_called, "git stash pop was not called")

    @patch("framework.runner.cli.subprocess.run")
    @patch("framework.runner.cli.Path")
    def test_cmd_update_clean_tree_success(self, mock_path, mock_run):
        # Setup mocks
        mock_root = MagicMock(spec=Path)
        (mock_root / ".git").is_dir.return_value = True
        mock_path.resolve.return_value.parents = [mock_root]
        
        def run_side_effect(cmd, **kwargs):
            m = MagicMock()
            if cmd == ["git", "status", "--porcelain"]:
                m.stdout = "" # Clean
            m.returncode = 0
            return m

        mock_run.side_effect = run_side_effect

        # Execute
        result = cmd_update(self.args)

        # Verify
        self.assertEqual(result, 0)
        # Stash should NOT be called
        for call in mock_run.call_args_list:
            cmd = call[0][0]
            self.assertNotEqual(cmd, ["git", "stash", "--include-untracked"])
            self.assertNotEqual(cmd, ["git", "stash", "pop"])

    @patch("framework.runner.cli.subprocess.run")
    @patch("framework.runner.cli.Path")
    def test_cmd_update_pop_conflict(self, mock_path, mock_run):
        # Setup mocks
        mock_root = MagicMock(spec=Path)
        (mock_root / ".git").is_dir.return_value = True
        mock_path.resolve.return_value.parents = [mock_root]
        
        def run_side_effect(cmd, **kwargs):
            m = MagicMock()
            if cmd == ["git", "status", "--porcelain"]:
                m.stdout = " M file.py"
            elif cmd == ["git", "stash", "pop"]:
                # Simulate conflict
                raise subprocess.CalledProcessError(1, cmd, stderr="Merge conflict in file.py")
            m.returncode = 0
            return m

        mock_run.side_effect = run_side_effect

        # Execute
        with patch("builtins.print") as mock_print:
            result = cmd_update(self.args)

        # Verify
        self.assertEqual(result, 1)
        # Check for recovery message
        printed_text = "".join([call.args[0] for call in mock_print.call_args_list])
        self.assertIn("CONFLICT DETECTED", printed_text)
        self.assertIn("git stash list", printed_text)
        self.assertIn("git stash pop", printed_text)

if __name__ == "__main__":
    unittest.main()
