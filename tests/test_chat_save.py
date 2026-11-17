import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MOD_PATH = Path(__file__).resolve().parent.parent / "bin" / "chat-save.py"
spec = importlib.util.spec_from_file_location("chat_save", MOD_PATH)
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)


class TestChatSave(unittest.TestCase):
    def test_start_dir_first_entry_wins(self):
        entries = [
            {"type": "user", "cwd": "/home/user/work/project/my-app"},
            {"type": "assistant", "cwd": "/home/user/other"},
        ]
        self.assertEqual(cs._start_dir(entries, Path("/tmp")), Path("/home/user/work/project/my-app"))

    def test_start_dir_fallback_when_no_cwd(self):
        entries = [{"type": "user", "message": {"content": "hi"}}]
        self.assertEqual(cs._start_dir(entries, Path("/tmp/fallback")), Path("/tmp/fallback"))

    def test_folder_documents_not_doubled(self):
        start = Path.home() / "Documents" / "stepbooks"
        self.assertEqual(cs._folder(None, start), Path.home() / "Documents" / "stepbooks" / "conversations")

    def test_folder_drops_project_segment(self):
        start = Path.home() / "work" / "project" / "my-app"
        self.assertEqual(cs._folder(None, start), Path.home() / "Documents" / "work" / "my-app" / "conversations")

    def test_claude_render_and_anon(self):
        entries = [
            {"type": "custom-title", "customTitle": "Refactor Auth"},
            {
                "type": "user",
                "cwd": "/home/user/work",
                "message": {"content": "<system-reminder>ignore</system-reminder>Hello Claude"},
            },
            {
                "type": "assistant",
                "message": {
                    "model": "claude-sonnet-4-5",
                    "content": [
                        {"type": "tool_use", "name": "Read", "input": {"file_path": "/home/user/work/app.py"}},
                        {"type": "text", "text": "Done reading."},
                    ],
                },
            },
        ]
        session = "11111111-2222-3333-4444-555555555555"
        title = cs._title(entries, session)
        self.assertEqual(title, "refactor-auth")

        rendered = cs._render(entries, title, session, Path("/fallback"), anon=False, agent="claude")
        self.assertIn("Conversation: refactor-auth", rendered)
        self.assertIn("Agent: claude (sonnet-4-5)", rendered)
        self.assertIn("Directory: /home/user/work", rendered)
        self.assertIn(f"Session: {session}", rendered)
        self.assertIn("❯ Hello Claude", rendered)
        self.assertIn("⏺ Read(/home/user/work/app.py)", rendered)
        self.assertIn("⏺ Done reading.", rendered)

        rendered_anon = cs._render(entries, title, session, Path("/fallback"), anon=True, agent="claude")
        self.assertNotIn("Agent:", rendered_anon)
        self.assertNotIn("Directory:", rendered_anon)
        self.assertNotIn("Session:", rendered_anon)
        self.assertNotIn("Host:", rendered_anon)

    def test_antigravity_adapter_title_start_dir_and_render(self):
        home = Path.home()
        entries = [
            {
                "step_index": 0,
                "source": "USER_EXPLICIT",
                "type": "USER_INPUT",
                "content": (
                    "<USER_REQUEST>\n"
                    "Unpark TOOL-CSAVE-AGY and add Antigravity support\n"
                    "</USER_REQUEST>\n"
                    "<ADDITIONAL_METADATA>\n2026-11-18\n</ADDITIONAL_METADATA>"
                ),
            },
            {
                "step_index": 1,
                "source": "MODEL",
                "type": "PLANNER_RESPONSE",
                "model": "gemini-4-argon-medium",
                "tool_calls": [
                    {
                        "name": "read_file",
                        "args": {"Path": f"{home}/work/projects/my-tool/bin/my-tool.py"},
                    }
                ],
                "content": "I have inspected the tool.",
            },
            {
                "step_index": 2,
                "source": "MODEL",
                "type": "GENERIC",
                "content": "raw tool output should be skipped",
            },
        ]
        session = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        self.assertEqual(cs._detect_agent(entries), "antigravity")
        self.assertEqual(
            cs._title_antigravity(entries, session),
            "unpark-tool-csave-agy-and-add-antigravity-support",
        )
        self.assertEqual(
            cs._title_antigravity(entries, session, title_override="Custom Title"),
            "custom-title",
        )
        self.assertEqual(
            cs._start_dir_antigravity(entries, Path("/tmp")),
            home / "work" / "projects" / "my-tool",
        )

        rendered = cs._render(entries, "custom-title", session, Path("/tmp"), anon=False, agent="antigravity")
        self.assertIn("Agent: antigravity (gemini-4-argon-medium)", rendered)
        self.assertIn(f"Directory: {home}/work/projects/my-tool", rendered)
        self.assertIn("❯ Unpark TOOL-CSAVE-AGY and add Antigravity support", rendered)
        self.assertIn(f"⏺ read_file({home}/work/projects/my-tool/bin/my-tool.py)", rendered)
        self.assertIn("⏺ I have inspected the tool.", rendered)
        self.assertNotIn("raw tool output should be skipped", rendered)

    def test_find_transcript_antigravity(self):
        session = "ebfeca39-a20c-4de1-877f-0aa4a3332959"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            log_dir = tmp_path / "antigravity-cli" / "brain" / session / ".system_generated" / "logs"
            log_dir.mkdir(parents=True)
            tf = log_dir / "transcript_full.jsonl"
            tf.write_text(json.dumps({"type": "USER_INPUT", "content": "<USER_REQUEST>hi</USER_REQUEST>"}) + "\n")
            with mock.patch.object(cs, "PROJECTS_DIR", tmp_path / "no-claude"), mock.patch.object(
                cs, "GEMINI_DIR", tmp_path
            ):
                found, agent = cs._find_transcript(session)
                self.assertEqual(found, tf)
                self.assertEqual(agent, "antigravity")


if __name__ == "__main__":
    unittest.main()
