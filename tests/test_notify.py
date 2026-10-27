import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notify import build, clean, detect_format, first_sentences, mask, render, sequence  # noqa: E402

ESC = chr(27)
BEL = chr(7)
DONE = {"assistant_response": "Fixed the bug. Tests pass. More text."}


class NotifyTest(unittest.TestCase):
    def test_complete_names_the_folder_and_the_start_of_the_reply(self):
        self.assertEqual(
            build("complete", DONE, {}, "/work/my-app"),
            {"title": "Hermes · my-app", "body": "Task complete: Fixed the bug. Tests pass."},
        )

    def test_permission_and_question_bodies(self):
        perm = build("permission", {"command": "npm test"}, {}, "C:\\src\\app\\")
        self.assertEqual(perm["title"], "Hermes · app")
        self.assertEqual(perm["body"], "Permission needed: npm test")
        q = build("question", {"kind": "clarify", "prompt": "Which one?"}, {}, "/w/x")
        self.assertEqual(q["body"], "Question: Which one?")
        self.assertIsNone(build("nonsense", {}, {}, "/w/x"))

    def test_details_off_shows_the_event_alone(self):
        env = {"TERMINAL_NOTIFY_DETAILS": "false"}
        self.assertEqual(build("complete", DONE, env, "/w/x")["body"], "Task complete")
        self.assertEqual(build("permission", {"command": "make deploy"}, env, "/w/x")["body"], "Permission needed")
        self.assertEqual(build("question", {"kind": "clarify", "prompt": "Q?"}, env, "/w/x")["body"], "Question waiting")

    def test_secrets_are_masked(self):
        self.assertEqual(mask("key sk-abcdefghijkl here"), "key *** here")
        self.assertEqual(mask("token=hunter2abc"), "token=***")
        self.assertEqual(mask("https://user:pw@example.com/x"), "***example.com/x")
        perm = build("permission", {"command": "curl -H 'Authorization: Bearer abcdefghijklmnop'"}, {}, "/w/x")
        self.assertNotIn("abcdefghijklmnop", perm["body"])

    def test_control_characters_cannot_break_out_of_the_sequence(self):
        n = build("complete", {"assistant_response": "Done" + BEL + ESC + "]52;c;AAAA" + BEL + " now" + chr(0x9C) + "."}, {}, "/w/x")
        self.assertFalse(any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in n["body"]))

    def test_code_is_left_out_of_the_reply(self):
        self.assertEqual(first_sentences("Did `make all` ok.\n```\nx\n```\nNext one.", 2), "Did ok. Next one.")
        self.assertEqual(clean(None), "")

    def test_terminal_detection(self):
        self.assertEqual(detect_format({"AGENT_TERMINAL_SESSION_ID": "s1", "WT_SESSION": "x"}), "osc777")
        self.assertEqual(detect_format({"KITTY_WINDOW_ID": "1"}), "osc99")
        self.assertEqual(detect_format({"TERM_PROGRAM": "ghostty"}), "osc777")
        self.assertEqual(detect_format({"TERM_PROGRAM": "WarpTerminal"}), "osc777")
        self.assertEqual(detect_format({"TERM": "rxvt-unicode-256color"}), "osc777")
        self.assertEqual(detect_format({"WT_SESSION": "x"}), "osc9")
        self.assertEqual(detect_format({"TERM_PROGRAM": "iTerm.app"}), "osc9")
        self.assertEqual(detect_format({"TERM_PROGRAM": "WezTerm"}), "osc9")
        self.assertEqual(detect_format({"TERM_PROGRAM": "Apple_Terminal"}), "bell")
        self.assertEqual(detect_format({}), "osc9")

    def test_sequences(self):
        self.assertEqual(sequence("osc777", "T;x", "a;b"), ESC + "]777;notify;T,x;a,b" + BEL)
        self.assertEqual(sequence("osc9", "T", "b"), ESC + "]9;T: b" + BEL)
        self.assertEqual(sequence("osc9", "4", "x"), ESC + "]9;· 4: x" + BEL)
        self.assertEqual(sequence("osc9", " -1 x", "y"), ESC + "]9;·  -1 x: y" + BEL)
        self.assertEqual(
            sequence("all", "T", "b"),
            ESC + "]9;T: b" + BEL + ESC + "]99;;T: b" + ESC + "\\" + ESC + "]777;notify;T;b" + BEL,
        )
        self.assertEqual(sequence("osc99", "T", "a;b"), ESC + "]99;;T: a,b" + ESC + "\\")
        self.assertEqual(sequence("bell", "T", "b"), BEL)

    def test_format_option_overrides_detection_off_and_bad_values(self):
        self.assertTrue(render("complete", DONE, {"WT_SESSION": "x", "TERMINAL_NOTIFY_FORMAT": "osc777"}, "/w").startswith(ESC + "]777;"))
        self.assertIsNone(render("complete", DONE, {"TERMINAL_NOTIFY_FORMAT": "off"}, "/w"))
        self.assertTrue(render("complete", DONE, {"WT_SESSION": "x", "TERMINAL_NOTIFY_FORMAT": "nonsense"}, "/w").startswith(ESC + "]9;"))
        self.assertEqual(render("complete", DONE, {"TERMINAL_NOTIFY_FORMAT": "bell"}, "/w"), BEL)

    def test_render_matches_the_claude_code_plugin(self):
        self.assertEqual(
            render("complete", DONE, {"WT_SESSION": "x"}, "/work/my-app"),
            ESC + "]9;Hermes · my-app: Task complete: Fixed the bug. Tests pass." + BEL,
        )


if __name__ == "__main__":
    unittest.main()
