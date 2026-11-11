"""Folder choice of chat-save (TOOL-CSAVE-STARTDIR): pure functions only, writes nothing."""

import importlib.util
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "bin" / "chat-save.py"
_spec = importlib.util.spec_from_file_location("chat_save", _SRC)
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)

HOME = Path.home()
DOCS = HOME / "Documents"


def folder_for(entries, cwd, dest=None):
    # same order as cmd_run: transcript start folder first, --cwd only as fallback
    return cs._folder(dest, cs._start_dir(entries, Path(cwd)))


class FolderTest(unittest.TestCase):
    def test_start_home_ignores_cwd_under_documents(self):
        # the bug: chat started in ~, skill passed --cwd ~/Documents/stepbooks
        got = folder_for([{"cwd": str(HOME)}], DOCS / "stepbooks")
        self.assertEqual(got, DOCS / "conversations")

    def test_start_under_documents_not_doubled(self):
        got = folder_for([{"cwd": str(DOCS / "stepbooks")}], HOME)
        self.assertEqual(got, DOCS / "stepbooks" / "conversations")

    def test_start_documents_root(self):
        self.assertEqual(folder_for([{"cwd": str(DOCS)}], HOME), DOCS / "conversations")

    def test_no_cwd_in_transcript_falls_back_to_cwd(self):
        got = folder_for([{"type": "user"}], HOME / "work")
        self.assertEqual(got, DOCS / "work" / "conversations")

    def test_project_segment_dropped(self):
        got = folder_for([{"cwd": str(HOME / "work" / "project" / "my-app")}], HOME)
        self.assertEqual(got, DOCS / "work" / "my-app" / "conversations")

    def test_dest_wins(self):
        got = folder_for([{"cwd": str(HOME)}], HOME, dest="~/Documents/archive")
        self.assertEqual(got, DOCS / "archive" / "conversations")


if __name__ == "__main__":
    unittest.main()
