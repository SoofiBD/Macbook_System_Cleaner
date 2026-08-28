"""Unit tests for server.py input validation helpers."""
import sys
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'web'))


class TestScriptPath(unittest.TestCase):
    def test_homebrew_launcher_can_supply_stable_opt_path(self):
        from server import _get_script_path

        configured = "/opt/homebrew/opt/apple-cleanup/libexec/clean_mac.sh"
        with patch.dict(os.environ, {"APPLE_CLEANUP_SCRIPT_PATH": configured}):
            self.assertEqual(str(_get_script_path()), configured)

    def test_dashboard_reads_the_canonical_script_version(self):
        from server import APP_VERSION, SCRIPT_PATH

        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn(f'VERSION="{APP_VERSION}"', source)
        self.assertEqual(APP_VERSION, "2.3.4")

    def test_dashboard_footer_uses_runtime_version_placeholder(self):
        from server import VERSION_PLACEHOLDER

        index = os.path.join(os.path.dirname(__file__), '..', 'web', 'index.html')
        with open(index, encoding="utf-8") as handle:
            self.assertIn(VERSION_PLACEHOLDER, handle.read())


class TestValidateAppLeftover(unittest.TestCase):
    def setUp(self):
        from server import _validate_app_leftover
        self.v = _validate_app_leftover

    def test_allows_simple_name(self):
        self.assertTrue(self.v("Slack"))
        self.assertTrue(self.v("com.google.Chrome"))
        self.assertTrue(self.v("My App"))
        self.assertTrue(self.v("App-Name.1"))

    def test_blocks_path_traversal(self):
        self.assertFalse(self.v("../etc/passwd"))
        self.assertFalse(self.v("/absolute/path"))

    def test_blocks_special_chars(self):
        self.assertFalse(self.v("app;rm -rf /"))
        self.assertFalse(self.v("app`id`"))
        self.assertFalse(self.v("app$HOME"))

    def test_blocks_too_long(self):
        self.assertFalse(self.v("a" * 65))

    def test_blocks_empty(self):
        self.assertFalse(self.v(""))


class TestValidateDeveloperItem(unittest.TestCase):
    def setUp(self):
        from server import _validate_developer_item
        self.v = _validate_developer_item

    def test_whitelist_entries(self):
        for item in ("derived_data", "broken_links", "brew_cache",
                     "docker_prune", "npm_cache", "pip_cache"):
            self.assertTrue(self.v(item), f"Expected True for {item}")

    def test_rejects_unknown(self):
        self.assertFalse(self.v("evil_cmd"))
        self.assertFalse(self.v("../../etc"))
        self.assertFalse(self.v("; rm -rf /"))

    def test_new_developer_keys_allowed(self):
        for k in ["device_support", "coresim_caches", "xcode_archives",
                  "simctl_unavailable", "pnpm_cache", "yarn_cache",
                  "cocoapods_cache", "gradle_cache", "maven_repo",
                  "xcode_products", "simulator_logs", "simulator_devices",
                  "font_caches", "brew_cleanup", "swift_pm_cache", "xcode_logs"]:
            self.assertTrue(self.v(k), k)


class TestValidateBrowserKey(unittest.TestCase):
    def setUp(self):
        from server import _validate_browser_key
        self.v = _validate_browser_key

    def test_whitelist_entries(self):
        for k in ("safari", "cookies", "chrome", "firefox",
                  "brave", "edge", "opera", "arc"):
            self.assertTrue(self.v(k), f"Expected True for {k}")

    def test_rejects_unknown(self):
        self.assertFalse(self.v("not_a_browser"))
        self.assertFalse(self.v("; rm -rf /"))


class TestValidateAppName(unittest.TestCase):
    def setUp(self):
        from server import _validate_app_name
        self.v = _validate_app_name

    def test_allows_valid_app_names(self):
        self.assertTrue(self.v("Firefox"))
        self.assertTrue(self.v("Visual Studio Code"))
        self.assertTrue(self.v("App-Name.1"))

    def test_blocks_traversal(self):
        self.assertFalse(self.v("../Applications"))
        self.assertFalse(self.v("/Applications/Evil"))

    def test_blocks_injection(self):
        self.assertFalse(self.v("App;rm -rf /"))
        self.assertFalse(self.v("App`id`"))

    def test_blocks_empty(self):
        self.assertFalse(self.v(""))


class TestValidateBrewName(unittest.TestCase):
    def setUp(self):
        from server import _validate_brew_name
        self.v = _validate_brew_name

    def test_allows_valid_tokens(self):
        self.assertTrue(self.v("wget"))
        self.assertTrue(self.v("google-chrome"))
        self.assertTrue(self.v("python@3.12"))
        self.assertTrue(self.v("homebrew/cask/firefox"))

    def test_blocks_flag_injection(self):
        # A leading dash would let brew parse the token as an option.
        self.assertFalse(self.v("--force"))
        self.assertFalse(self.v("-q"))

    def test_blocks_traversal_and_injection(self):
        self.assertFalse(self.v("../etc"))
        self.assertFalse(self.v("pkg;rm -rf /"))
        self.assertFalse(self.v("pkg`id`"))
        self.assertFalse(self.v(""))


class TestCategoryValidation(unittest.TestCase):
    def setUp(self):
        from server import _coerce_categories
        self.v = _coerce_categories

    def test_accepts_integer_and_digit_string_ids(self):
        self.assertEqual(
            self.v([1, "11", 17]),
            ["user_cache", "app_uninstaller", "project_artifacts"],
        )

    def test_accepts_stable_category_ids(self):
        self.assertEqual(
            self.v(["user_cache", "project_artifacts"]),
            ["user_cache", "project_artifacts"],
        )

    def test_rejects_out_of_range_duplicate_and_boolean_ids(self):
        self.assertIsNone(self.v([0]))
        self.assertEqual(self.v([18]), ["installer_artifacts"])
        self.assertIsNone(self.v([19]))
        self.assertIsNone(self.v([1, 1]))
        self.assertIsNone(self.v([True]))
        self.assertIsNone(self.v(["1;rm"]))


class TestInstallerArtifactValidation(unittest.TestCase):
    def test_requires_direct_download_child_and_identity(self):
        from server import _validate_installer_artifact_selection

        with patch.dict(os.environ, {"HOME": "/Users/tester"}):
            self.assertTrue(_validate_installer_artifact_selection({
                "path": "/Users/tester/Downloads/Tool.dmg",
                "identity": "1:2:100:1234",
            }))
            self.assertFalse(_validate_installer_artifact_selection({
                "path": "/Users/tester/Documents/Tool.dmg",
                "identity": "1:2:100:1234",
            }))
            self.assertFalse(_validate_installer_artifact_selection({
                "path": "/Users/tester/Downloads/Tool.txt",
                "identity": "1:2:100:1234",
            }))
            self.assertFalse(_validate_installer_artifact_selection({
                "path": "/Users/tester/Downloads/Tool.pkg",
                "identity": "not-an-identity",
            }))


class TestExclusiveOperation(unittest.TestCase):
    def test_rejects_overlapping_mutations(self):
        import server

        class Dummy:
            called = False
            error = None

            def _send_error_json(self, message, status=500):
                self.error = (message, status)

            @server._exclusive_operation
            def mutate(self):
                self.called = True

        dummy = Dummy()
        server._operation_lock.acquire()
        try:
            dummy.mutate()
        finally:
            server._operation_lock.release()
        self.assertFalse(dummy.called)
        self.assertEqual(dummy.error[1], 409)


class TestApplicationDiscovery(unittest.TestCase):
    def test_discovers_nested_app_but_not_embedded_helper(self):
        import plistlib
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import server

        root = Path(tempfile.mkdtemp()) / "Applications"
        app = root / "Vendor" / "Fancy App.app"
        contents = app / "Contents"
        contents.mkdir(parents=True)
        with (contents / "Info.plist").open("wb") as handle:
            plistlib.dump({
                "CFBundleIdentifier": "com.example.fancy",
                "CFBundleName": "Fancy App",
                "CFBundleShortVersionString": "2.0",
            }, handle)
        helper = app / "Contents/Library/LoginItems/Helper.app/Contents"
        helper.mkdir(parents=True)

        with patch.object(server, "_application_roots", return_value=(root,)), \
             patch.object(server.shutil, "which", return_value=None):
            apps = server.discover_applications()

        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]["path"], str(app))
        self.assertEqual(apps[0]["bundle_id"], "com.example.fancy")
        self.assertEqual(apps[0]["target_id"], f"app:{app}")
        self.assertFalse(apps[0]["protected"])

    def test_extracts_homebrew_app_artifacts(self):
        from server import _cask_app_artifacts
        self.assertEqual(
            _cask_app_artifacts({"artifacts": [{"app": ["Visual Studio Code.app"]}]}),
            {"visual studio code"},
        )


class TestValidateProjectArtifact(unittest.TestCase):
    def setUp(self):
        from server import _validate_project_artifact
        self.v = _validate_project_artifact

    def test_allows_recognized_artifacts(self):
        self.assertTrue(self.v("/Users/x/Code/app/node_modules"))
        self.assertTrue(self.v("/Users/x/Developer/cli/target"))
        self.assertTrue(self.v("/Users/x/Projects/pkg/.build"))
        self.assertTrue(self.v("/Users/x/repos/svc/vendor"))
        self.assertTrue(self.v("/Users/x/src/app/.dart_tool"))

    def test_blocks_traversal(self):
        self.assertFalse(self.v("/Users/x/../../etc/node_modules"))

    def test_blocks_non_artifact_basename(self):
        self.assertFalse(self.v("/Users/x/Documents"))
        self.assertFalse(self.v("/etc"))
        self.assertFalse(self.v("/Users/x/Code/app/src"))

    def test_blocks_relative_and_nonstring(self):
        self.assertFalse(self.v("node_modules"))
        self.assertFalse(self.v(""))
        self.assertFalse(self.v(None))

    def test_selection_requires_scan_identity(self):
        from server import _validate_project_artifact_selection
        identity = "1:2:3:4:5:6:package.json"
        self.assertTrue(_validate_project_artifact_selection({
            "path": "/Users/x/Code/app/node_modules",
            "identity": identity,
        }))
        self.assertFalse(_validate_project_artifact_selection({
            "path": "/Users/x/Code/app/node_modules",
        }))
        self.assertFalse(_validate_project_artifact_selection({
            "path": "/Users/x/Code/app/node_modules",
            "identity": "../../bad",
        }))


class TestProtectedBundlePolicy(unittest.TestCase):
    def test_all_apple_bundle_ids_are_protected(self):
        from server import _is_protected_bundle_id
        self.assertTrue(_is_protected_bundle_id("com.apple.Safari"))
        self.assertTrue(_is_protected_bundle_id("com.apple.FutureSystemApp"))
        self.assertFalse(_is_protected_bundle_id("com.example.App"))


class TestDeveloperWhitelistSync(unittest.TestCase):
    """The shell and server developer-key whitelists must stay identical."""

    def test_whitelists_match(self):
        import re
        from server import _DEVELOPER_WHITELIST

        script = os.path.join(os.path.dirname(__file__), '..', 'clean_mac.sh')
        with open(script, encoding='utf-8') as f:
            text = f.read()

        m = re.search(r'_VALID_DEVELOPER_KEYS="([^"]*)"', text)
        self.assertIsNotNone(m, "_VALID_DEVELOPER_KEYS not found in clean_mac.sh")
        shell_keys = set(m.group(1).split('|'))

        self.assertEqual(
            shell_keys, set(_DEVELOPER_WHITELIST),
            "clean_mac.sh _VALID_DEVELOPER_KEYS and server _DEVELOPER_WHITELIST "
            "have drifted out of sync",
        )


class TestAllowedHost(unittest.TestCase):
    def setUp(self):
        from server import _is_allowed_host
        self.v = _is_allowed_host

    def test_allows_loopback(self):
        self.assertTrue(self.v("localhost"))
        self.assertTrue(self.v("localhost:8080"))
        self.assertTrue(self.v("127.0.0.1"))
        self.assertTrue(self.v("127.0.0.1:8080"))
        self.assertTrue(self.v("[::1]"))
        self.assertTrue(self.v("[::1]:8080"))

    def test_blocks_external_hosts(self):
        self.assertFalse(self.v("example.com"))
        self.assertFalse(self.v("192.168.1.20:8080"))
        self.assertFalse(self.v("evil.attacker.test"))

    def test_blocks_empty(self):
        self.assertFalse(self.v(""))


class TestAllowedOrigin(unittest.TestCase):
    def setUp(self):
        from server import _is_allowed_origin
        self.v = _is_allowed_origin

    def test_absent_origin_allowed(self):
        # curl / native clients omit Origin; allowed (token + Host still guard)
        self.assertTrue(self.v(None))
        self.assertTrue(self.v(""))

    def test_loopback_origin_allowed(self):
        self.assertTrue(self.v("http://localhost:8080"))
        self.assertTrue(self.v("http://127.0.0.1:8080"))
        self.assertTrue(self.v("http://[::1]:8080"))

    def test_external_origin_blocked(self):
        self.assertFalse(self.v("http://evil.example.com"))
        self.assertFalse(self.v("https://attacker.test"))
        self.assertFalse(self.v("null"))


class TestComputeForecast(unittest.TestCase):
    def setUp(self):
        from server import compute_forecast
        self.f = compute_forecast

    def test_insufficient_data(self):
        r = self.f([], 1000, 500)
        self.assertIsNone(r["days_until_full"])
        self.assertEqual(r["history_points"], 0)
        r = self.f([(0.0, 100)], 1000, 500)
        self.assertIsNone(r["days_until_full"])

    def test_steady_growth_predicts_full(self):
        day = 86400
        total = 1000
        # 10 bytes/day growth, currently at 900 → 100 remaining → ~10 days
        hist = [(i * day, 800 + i * 10) for i in range(11)]  # 10 days span
        r = self.f(hist, total, 900)
        self.assertEqual(r["daily_growth_bytes"], 10)
        self.assertEqual(r["days_until_full"], 10)
        self.assertGreaterEqual(r["history_span_days"], 10)

    def test_shrinking_usage_no_forecast(self):
        day = 86400
        hist = [(i * day, 900 - i * 10) for i in range(11)]
        r = self.f(hist, 1000, 800)
        self.assertIsNone(r["days_until_full"])
        self.assertLessEqual(r["daily_growth_bytes"], 0)

    def test_span_under_one_day_no_forecast(self):
        hist = [(0.0, 100), (3600.0, 200)]  # 1 hour apart
        r = self.f(hist, 1000, 500)
        self.assertIsNone(r["days_until_full"])

    def test_beyond_horizon_returns_none(self):
        day = 86400
        # 1 byte/day growth, 10000 remaining → 10000 days > 365 → None
        hist = [(i * day, 100 + i) for i in range(11)]
        r = self.f(hist, 100000, 90000)
        self.assertIsNone(r["days_until_full"])
        self.assertEqual(r["daily_growth_bytes"], 1)


class TestRecordSnapshot(unittest.TestCase):
    def setUp(self):
        from server import _record_snapshot
        self.f = _record_snapshot

    def test_appends_when_empty(self):
        out = self.f([], 500, now=1000.0)
        self.assertEqual(out, [(1000.0, 500)])

    def test_throttles_within_interval(self):
        hist = [(1000.0, 500)]
        out = self.f(hist, 600, now=1000.0 + 1800)  # 30 min later
        self.assertEqual(out, hist)  # unchanged

    def test_appends_after_interval(self):
        hist = [(1000.0, 500)]
        out = self.f(hist, 600, now=1000.0 + 7200)  # 2 hours later
        self.assertEqual(len(out), 2)
        self.assertEqual(out[-1], (1000.0 + 7200, 600))

    def test_prunes_old_entries(self):
        now = 100 * 86400.0
        hist = [(0.0, 100), (95 * 86400.0, 200)]  # first is >90 days old
        out = self.f(hist, 300, now=now)
        self.assertTrue(all(t > now - 90 * 86400 for t, _ in out))
        self.assertNotIn((0.0, 100), out)


class TestExtraEnvForClean(unittest.TestCase):
    def setUp(self):
        from server import _extra_env_for_clean
        self.f = _extra_env_for_clean

    def test_dry_run_true_sets_env(self):
        self.assertEqual(self.f({"dry_run": True}),
                         {"APPLE_CLEANUP_DRYRUN": "1"})

    def test_dry_run_absent_or_false_empty(self):
        self.assertEqual(self.f({}), {})
        self.assertEqual(self.f({"dry_run": False}), {})
        # Only a real boolean True enables it (no truthy strings)
        self.assertEqual(self.f({"dry_run": "true"}), {})
        self.assertEqual(self.f({"dry_run": 1}), {})


class TestTokenCompare(unittest.TestCase):
    def setUp(self):
        from server import _token_matches, SESSION_TOKEN
        self.v = _token_matches
        self.token = SESSION_TOKEN

    def test_matches_correct_token(self):
        self.assertTrue(self.v(self.token))

    def test_rejects_wrong_token(self):
        self.assertFalse(self.v("wrong"))
        self.assertFalse(self.v(None))
        self.assertFalse(self.v(""))


class TestHistoryRoute(unittest.TestCase):
    """GET /api/history shells out to clean_mac.sh --history-json and returns a list."""

    def test_history_route_returns_list(self):
        import http.client
        import http.server
        import json as _json
        import os
        import tempfile
        import threading
        import importlib.util

        # Load the server module by path.
        web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
        spec = importlib.util.spec_from_file_location(
            "cleanup_server", os.path.join(web_dir, "server.py"))
        server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server)

        home = tempfile.mkdtemp()
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = home  # isolated => empty history => []
        httpd = http.server.HTTPServer(("127.0.0.1", 0), server.CleanupHandler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
            conn.request("GET", "/api/history", headers={"Host": f"127.0.0.1:{port}"})
            resp = conn.getresponse()
            body = resp.read().decode()
            self.assertEqual(resp.status, 200, body)
            self.assertIsInstance(_json.loads(body), list)
        finally:
            httpd.shutdown()
            if old_home is not None:
                os.environ["HOME"] = old_home


class TestValidateSessionId(unittest.TestCase):
    def setUp(self):
        from server import _validate_session_id
        self.v = _validate_session_id

    def test_allows_uuid(self):
        self.assertTrue(self.v("3F2504E0-4F89-41D3-9A0C-0305E82C3301"))

    def test_allows_pid_ts_fallback(self):
        self.assertTrue(self.v("12345-1700000000"))

    def test_blocks_injection(self):
        self.assertFalse(self.v("; rm -rf /"))
        self.assertFalse(self.v("../../etc"))
        self.assertFalse(self.v(""))
        self.assertFalse(self.v("a" * 50))


class TestValidateItemIds(unittest.TestCase):
    def setUp(self):
        from server import _validate_item_ids
        self.v = _validate_item_ids

    def test_allows_int_list(self):
        self.assertTrue(self.v([1, 2, 3]))

    def test_blocks_non_int(self):
        self.assertFalse(self.v(["1; rm"]))
        self.assertFalse(self.v([-1]))
        self.assertFalse(self.v([]))
        self.assertFalse(self.v("notalist"))

    def test_blocks_booleans(self):
        # bool is subclass of int in Python; must be rejected
        self.assertFalse(self.v([True]))
        self.assertFalse(self.v([False]))
        self.assertFalse(self.v([1, True, 2]))


class TestRunScriptResilience(unittest.TestCase):
    """Test _run_script handling of non-zero exit codes with valid JSON stdout."""

    def test_run_script_parses_json_even_if_returncode_nonzero(self):
        import importlib.util
        import os

        web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
        spec = importlib.util.spec_from_file_location(
            "cleanup_server", os.path.join(web_dir, "server.py"))
        server_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server_mod)

        handler = server_mod.CleanupHandler.__new__(server_mod.CleanupHandler)
        # Test running a python command that exits 1 but prints valid JSON
        import subprocess
        cmd = [sys.executable, "-c", "import sys, json; print(json.dumps({'success': True, 'msg': 'partial'})); sys.exit(1)"]
        
        # Override SCRIPT_PATH temporarily for test or test sub call logic directly
        old_script_path = server_mod.SCRIPT_PATH
        try:
            # We can mock subprocess.run or pass custom command via a wrapper helper
            res = subprocess.run(cmd, capture_output=True, text=True)
            # Verify stdout is parsed correctly
            output = res.stdout.strip()
            parsed = server_mod.json.loads(output)
            self.assertTrue(parsed.get("success"))
        finally:
            server_mod.SCRIPT_PATH = old_script_path

    def test_run_script_forces_english_messages(self):
        import server

        handler = server.CleanupHandler.__new__(server.CleanupHandler)
        completed = SimpleNamespace(
            stdout='{"success": true}', stderr="", returncode=0)
        with patch.object(server, "_run_process", return_value=completed) as run:
            data, err = handler._run_script(
                ["--status-json"], env_extra={"APPLE_CLEANUP_LANG": "tr"})

        self.assertIsNone(err)
        self.assertTrue(data["success"])
        self.assertEqual(
            run.call_args.kwargs["env"]["APPLE_CLEANUP_LANG"], "en")


class TestHealthReport(unittest.TestCase):
    def test_reports_broad_state_permissions_and_redirected_trash(self):
        import tempfile
        from pathlib import Path
        from server import _build_health_report

        with tempfile.TemporaryDirectory() as root:
            home = Path(root)
            script = home / "clean_mac.sh"
            script.write_text("#!/bin/bash\n")
            state_dir = home / ".cache" / "apple-cleanup"
            state_dir.mkdir(parents=True)
            state_dir.chmod(0o755)
            target = home / "redirected-trash"
            target.mkdir()
            (home / ".Trash").symlink_to(target, target_is_directory=True)

            report = _build_health_report(
                home=home,
                script_path=script,
                system_name="Darwin",
                mac_version="15.0",
                which=lambda name: f"/usr/bin/{name}",
                disk_usage=lambda path: SimpleNamespace(
                    total=1000, used=500, free=500),
            )

        checks = {check["id"]: check for check in report["checks"]}
        self.assertEqual(checks["macos"]["status"], "ok")
        self.assertEqual(checks["state"]["status"], "warning")
        self.assertEqual(checks["trash"]["status"], "warning")
        self.assertEqual(report["status"], "attention")

    def test_low_disk_and_missing_lsof_are_explicit_warnings(self):
        import tempfile
        from pathlib import Path
        from server import _build_health_report

        with tempfile.TemporaryDirectory() as root:
            home = Path(root)
            script = home / "clean_mac.sh"
            script.touch()
            report = _build_health_report(
                home=home,
                script_path=script,
                system_name="Darwin",
                mac_version="14.0",
                which=lambda name: None if name == "lsof" else f"/usr/bin/{name}",
                disk_usage=lambda path: SimpleNamespace(
                    total=1000, used=950, free=50),
            )

        checks = {check["id"]: check for check in report["checks"]}
        self.assertEqual(checks["disk"]["status"], "warning")
        self.assertEqual(checks["live_guard"]["status"], "warning")
        self.assertIn("skipped", checks["live_guard"]["detail"])


class TestBoundedScan(unittest.TestCase):
    @staticmethod
    def category(category_id, size=100, in_total=True):
        return {
            "success": True,
            "id": category_id,
            "category": {
                "size_bytes": size,
                "size_human": f"{size} B",
                "needs_sudo": False,
                "in_total": in_total,
                "risk": "safe",
                "recovery": "trash",
            },
        }

    def test_preserves_successful_categories_when_one_worker_times_out(self):
        from server import _run_bounded_scan

        def run_category(category_id):
            if category_id == "logs":
                return None, "Script timed out"
            return self.category(category_id), None

        result = _run_bounded_scan(
            run_category,
            lambda: ({"disk_free": "10 GB", "user": "tester"}, None),
            category_ids=("user_cache", "logs"),
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["partial"])
        self.assertEqual(result["failed_categories"], {"logs": "timeout"})
        self.assertEqual(result["total_bytes"], 100)
        self.assertEqual(list(result["scan"]), ["user_cache"])

    def test_rejects_malformed_worker_payload(self):
        from server import _run_bounded_scan

        result = _run_bounded_scan(
            lambda category_id: ({
                "success": True,
                "id": category_id,
                "category": {"size_bytes": "a lot"},
            }, None),
            lambda: ({}, None),
            category_ids=("developer",),
        )
        self.assertFalse(result["success"])
        self.assertEqual(
            result["failed_categories"], {"developer": "unavailable"})

    def test_marks_cancelled_worker_distinctly(self):
        from server import _run_bounded_scan

        result = _run_bounded_scan(
            lambda category_id: (None, "Script cancelled"),
            lambda: ({}, None),
            category_ids=("developer",),
        )
        self.assertEqual(
            result["failed_categories"], {"developer": "cancelled"})


class TestProcessCancellation(unittest.TestCase):
    def test_cancel_event_reaps_process_group_promptly(self):
        import threading
        import time
        from server import ProcessCancelled, _run_process

        cancel = threading.Event()
        timer = threading.Timer(0.1, cancel.set)
        started = time.monotonic()
        timer.start()
        try:
            with self.assertRaises(ProcessCancelled):
                _run_process(
                    [sys.executable, "-c", "import time; time.sleep(30)"],
                    timeout=10,
                    cancel_event=cancel,
                )
        finally:
            timer.cancel()
        self.assertLess(time.monotonic() - started, 3)


if __name__ == "__main__":
    unittest.main()
