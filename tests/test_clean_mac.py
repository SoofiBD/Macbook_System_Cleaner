# tests/test_clean_mac.py
import json
import os
import plistlib
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "clean_mac.sh"


def test_cli_reports_current_release_version():
    result = subprocess.run(
        ["bash", str(SCRIPT), "--version"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "2.1.0"


def run_scan(home: Path) -> dict:
    """clean_mac.sh --scan-json'u izole bir HOME ile çalıştır, JSON döndür."""
    env = dict(os.environ, HOME=str(home))
    out = subprocess.run(
        ["bash", str(SCRIPT), "--scan-json"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def run_category_scan(home: Path, category_id: str):
    env = dict(os.environ, HOME=str(home))
    result = subprocess.run(
        ["bash", str(SCRIPT), "--scan-category-json", category_id],
        env=env, capture_output=True, text=True, timeout=60,
    )
    return result, json.loads(result.stdout)


def make_dir_with_bytes(path: Path, kb: int) -> None:
    """path altında ~kb kilobayt veri oluştur."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "blob.bin").write_bytes(b"x" * (kb * 1024))


def test_scan_json_has_required_keys(tmp_path):
    data = run_scan(tmp_path)
    assert data["success"] is True
    assert "scan" in data
    assert "total_bytes" in data
    assert data["plan_version"] == 1
    # Her kategori size_bytes alanı taşımalı
    for cat_id, info in data["scan"].items():
        assert "size_bytes" in info, cat_id
        assert info["recovery"] in {"trash", "permanent", "mixed"}, cat_id


def test_single_category_scan_uses_stable_id_protocol(tmp_path):
    make_dir_with_bytes(tmp_path / "Library/Caches/com.example.app", kb=8)
    result, data = run_category_scan(tmp_path, "user_cache")
    assert result.returncode == 0, result.stderr
    assert data["success"] is True
    assert data["plan_version"] == 1
    assert data["id"] == "user_cache"
    assert data["category"]["size_bytes"] >= 8 * 1024
    assert data["category"]["risk"] == "safe"


def test_single_category_scan_rejects_unknown_id(tmp_path):
    result, data = run_category_scan(tmp_path, "../../etc")
    assert result.returncode != 0
    assert data == {"success": False, "error": "unknown category id: ../../etc"}


def test_scan_json_includes_risk_per_category(tmp_path):
    data = run_scan(tmp_path)
    assert data["scan"]["browser_full"]["risk"] == "danger"
    assert data["scan"]["user_cache"]["risk"] == "safe"


def test_app_uninstaller_excluded_from_total(tmp_path):
    # app_uninstaller (in_total=0) yalnız bir alt-öğe üretebilir ama
    # total_bytes'a EKLENMEMELİ. Burada user_cache'e 2MB koyup
    # toplamın yalnızca onu içerdiğini doğruluyoruz.
    make_dir_with_bytes(tmp_path / "Library/Caches/com.example.app", kb=2048)
    data = run_scan(tmp_path)
    # app_uninstaller bytes'ı varsa bile total'a dahil olmamalı
    summed_in_total = sum(
        info["size_bytes"] for cid, info in data["scan"].items()
        if cid != "app_uninstaller"
    )
    assert data["total_bytes"] == summed_in_total


def test_app_leftovers_excludes_browser_dirs(tmp_path):
    # Chrome profili Application Support/Google altında; app_leftovers'a
    # sayılmamalı (browser_full sahibi).
    make_dir_with_bytes(
        tmp_path / "Library/Application Support/Google/Chrome", kb=4096)
    make_dir_with_bytes(
        tmp_path / "Library/Application Support/SomeApp", kb=1024)
    data = run_scan(tmp_path)
    leftovers = data["scan"]["app_leftovers"]["size_bytes"]
    # Yalnızca SomeApp (~1MB) sayılmalı, Google (~4MB) değil
    assert leftovers < 3 * 1024 * 1024, leftovers


def test_hardlinks_not_double_counted(tmp_path):
    import os as _os
    logs = tmp_path / "Library/Logs"
    logs.mkdir(parents=True)
    (logs / "a").mkdir()
    (logs / "b").mkdir()
    big = logs / "a" / "big.bin"
    big.write_bytes(b"y" * (5 * 1024 * 1024))  # 5MB
    _os.link(big, logs / "b" / "big_link.bin")  # aynı inode, kardeş dizinde
    data = run_scan(tmp_path)
    logs_size = data["scan"]["logs"]["size_bytes"]
    # Hardlink tek sayılmalı → ~5MB, 10MB değil
    assert logs_size < 8 * 1024 * 1024, logs_size


def run_clean(home, cats: str) -> dict:
    env = dict(os.environ, HOME=str(home))
    out = subprocess.run(
        ["bash", str(SCRIPT), "--clean-json", cats],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_clean_json_reports_real_and_estimated(tmp_path):
    # logs kategorisi (id index 4) — boş HOME'da silinecek bir şey yok.
    data = run_clean(tmp_path, "4")
    assert "freed_bytes" in data       # gerçek (df farkı)
    assert "estimated_bytes" in data   # du tahmini
    assert "freed_source" in data      # "df" veya "estimated"
    assert data["freed_bytes"] >= 0    # negatif kıstırılmış


def test_dry_run_previews_without_deleting(tmp_path):
    # user_cache (index 1) holds a 2MB blob; dry-run must report it as an
    # estimate but leave the file untouched on disk.
    blob = tmp_path / "Library/Caches/com.example.app/blob.bin"
    make_dir_with_bytes(blob.parent, kb=2048)
    env = dict(os.environ, HOME=str(tmp_path), APPLE_CLEANUP_DRYRUN="1")
    out = subprocess.run(
        ["bash", str(SCRIPT), "--clean-json", "1"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert data["dry_run"] is True
    assert data["estimated_bytes"] > 0
    # File must still exist — nothing was actually removed.
    assert blob.exists(), "dry-run must not delete files"


def _write_mutation_probe(path: Path, tool: str, marker: Path) -> None:
    script = f'''#!/bin/sh
case "$*" in
  "system prune -a -f --volumes"|"cleanup -s"|\
  "simctl delete unavailable"|"simctl shutdown all"|"simctl erase all")
    printf '%s\\n' {json.dumps(tool)} >> {json.dumps(str(marker))}
    ;;
esac
case "{tool}:$*" in
  "brew:--cache") printf '%s\\n' {json.dumps(str(path.parent / "brew-cache"))} ;;
esac
exit 0
'''
    path.write_text(script)
    path.chmod(0o755)


def test_developer_owner_commands_obey_dry_run(tmp_path):
    marker = tmp_path / "mutations.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("docker", "brew", "xcrun"):
        _write_mutation_probe(bin_dir / tool, tool, marker)

    env = dict(
        os.environ,
        HOME=str(tmp_path),
        PATH=f"{bin_dir}:{os.environ.get('PATH', '')}",
        APPLE_CLEANUP_DRYRUN="1",
    )
    out = subprocess.run(
        ["bash", str(SCRIPT), "--clean-json", "6", "--developer-sub",
         "docker_prune,brew_cleanup,simctl_unavailable,simulator_devices"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert data["dry_run"] is True
    assert not marker.exists(), "dry-run invoked a mutating owner command"


def test_force_rm_requires_explicit_isolated_test_mode(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), APPLE_CLEANUP_FORCE_RM="1")
    out = subprocess.run(
        ["bash", "-c", f'source "{SCRIPT}" --__noop; _should_force_rm 0 0'],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert out.returncode != 0, "FORCE_RM alone must not enable permanent deletion"

    env["APPLE_CLEANUP_TEST_MODE"] = "1"
    out = subprocess.run(
        ["bash", "-c", f'source "{SCRIPT}" --__noop; _should_force_rm 0 0'],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert out.returncode == 0, out.stderr


def _validate_path(home: Path, path: str, mode="leaf", category=""):
    env = dict(os.environ, HOME=str(home), APPLE_CLEANUP_NO_OPLOG="1")
    command = (
        f'source "{SCRIPT}" --__noop; '
        f'_CURRENT_CATEGORY={json.dumps(category)}; '
        f'_validate_removal_path {json.dumps(path)} {json.dumps(mode)}'
    )
    return subprocess.run(
        ["bash", "-c", command], env=env,
        capture_output=True, text=True, timeout=10,
    )


def test_removal_validator_rejects_critical_and_malformed_paths(tmp_path):
    for path in (
        "relative/path",
        "/",
        str(tmp_path),
        str(tmp_path / "Downloads"),
        str(tmp_path / "Library/../Downloads/file"),
        str(tmp_path / "Library/Caches/bad\nname"),
        "/Library/Preferences/com.example.plist",
    ):
        result = _validate_path(tmp_path, path)
        assert result.returncode != 0, path


def test_removal_validator_rejects_ancestor_symlink_scope_escape(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    victim = outside / "victim"
    victim.mkdir()
    link = tmp_path / "Library/Caches/escape"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside, target_is_directory=True)

    escaped = link / "victim"
    result = _validate_path(tmp_path, str(escaped))
    assert result.returncode != 0
    assert victim.exists()


def test_removal_validator_allows_ordinary_home_leaf(tmp_path):
    victim = tmp_path / "Library/Caches/com.example.app"
    victim.mkdir(parents=True)
    result = _validate_path(tmp_path, str(victim))
    assert result.returncode == 0, result.stderr


def test_downloads_leaf_is_allowed_only_for_installer_category(tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    installer = downloads / "Tool.dmg"
    installer.write_bytes(b"x")
    blocked = _validate_path(tmp_path, str(installer), category="user_cache")
    assert blocked.returncode != 0
    allowed = _validate_path(
        tmp_path, str(installer), category="installer_artifacts")
    assert allowed.returncode == 0, allowed.stderr


def test_removal_validator_rejects_symlinked_contents_root(tmp_path):
    target = tmp_path / "Library/Caches/real"
    target.mkdir(parents=True)
    link = tmp_path / "Library/Caches/link"
    link.symlink_to(target, target_is_directory=True)
    result = _validate_path(tmp_path, str(link), mode="contents")
    assert result.returncode != 0


def _project_identity(home: Path, artifact: Path) -> str:
    env = dict(os.environ, HOME=str(home), APPLE_CLEANUP_NO_OPLOG="1")
    out = subprocess.run(
        ["bash", "-c",
         f'source "{SCRIPT}" --__noop; '
         f'_project_artifact_identity {json.dumps(str(artifact))}'],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def test_project_artifact_identity_rejects_replaced_target(tmp_path):
    project = tmp_path / "Projects/app"
    artifact = project / "node_modules"
    artifact.mkdir(parents=True)
    (project / "package.json").write_text("{}")
    (artifact / "old.txt").write_text("old")
    identity = _project_identity(tmp_path, artifact)

    artifact.rename(project / "node_modules.old")
    artifact.mkdir()
    (artifact / "new.txt").write_text("new")

    env = dict(os.environ, HOME=str(tmp_path), APPLE_CLEANUP_NO_OPLOG="1")
    command = f'''
source "{SCRIPT}" --__noop
scan_all() {{ :; }}
PROJECT_ARTIFACT_CLEAN={json.dumps(str(artifact))}
PROJECT_ARTIFACT_IDENTITIES={json.dumps(identity)}
do_clean_json 17
'''
    out = subprocess.run(
        ["bash", "-c", command], env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert data["success"] is False
    assert artifact.exists()
    assert (artifact / "new.txt").exists()


def test_project_artifact_identity_allows_unchanged_target(tmp_path):
    project = tmp_path / "Projects/app"
    artifact = project / "node_modules"
    artifact.mkdir(parents=True)
    (project / "package.json").write_text("{}")
    (artifact / "payload").write_text("data")
    identity = _project_identity(tmp_path, artifact)

    env = dict(os.environ, HOME=str(tmp_path), APPLE_CLEANUP_NO_OPLOG="1")
    trash = tmp_path / ".Trash"
    command = f'''
source "{SCRIPT}" --__noop
scan_all() {{ :; }}
_trash_item() {{ mkdir -p {json.dumps(str(trash))}; mv "$1" {json.dumps(str(trash))}/artifact; echo {json.dumps(str(trash))}/artifact; }}
PROJECT_ARTIFACT_CLEAN={json.dumps(str(artifact))}
PROJECT_ARTIFACT_IDENTITIES={json.dumps(identity)}
do_clean_json 17
'''
    out = subprocess.run(
        ["bash", "-c", command], env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert data["success"] is True, data
    assert not artifact.exists()
    assert (trash / "artifact/payload").exists()


def test_live_guard_skips_cache_with_open_files(tmp_path):
    target = tmp_path / "Library/Caches/com.example.LiveApp"
    target.mkdir(parents=True)
    payload = target / "state.sqlite"
    payload.write_text("database")
    env = dict(os.environ, HOME=str(tmp_path), APPLE_CLEANUP_NO_OPLOG="1")
    command = f'''
source "{SCRIPT}" --__noop
_path_owner_is_running() {{ return 1; }}
_path_has_open_files() {{ return 0; }}
safe_rm_contents {json.dumps(str(target))} "Live cache"
printf '\\nWARNINGS=%s\\n' "${{#CLEAN_WARNINGS[@]}}"
'''
    out = subprocess.run(
        ["bash", "-c", command], env=env,
        capture_output=True, text=True, timeout=10,
    )
    assert out.returncode == 0, out.stderr
    assert payload.exists()
    assert "WARNINGS=1" in out.stdout


def test_live_guard_fails_closed_for_database_when_lsof_unavailable(tmp_path):
    target = tmp_path / "Library/Caches/com.example.DatabaseApp"
    target.mkdir(parents=True)
    payload = target / "state.db-wal"
    payload.write_text("wal")
    env = dict(os.environ, HOME=str(tmp_path), APPLE_CLEANUP_NO_OPLOG="1")
    command = f'''
source "{SCRIPT}" --__noop
_path_owner_is_running() {{ return 1; }}
_path_has_open_files() {{ return 2; }}
safe_rm_contents {json.dumps(str(target))} "Database cache"
'''
    out = subprocess.run(
        ["bash", "-c", command], env=env,
        capture_output=True, text=True, timeout=10,
    )
    assert out.returncode == 0, out.stderr
    assert payload.exists()


def test_live_guard_allows_closed_cache(tmp_path):
    target = tmp_path / "Library/Caches/com.example.ClosedApp"
    target.mkdir(parents=True)
    payload = target / "cache.bin"
    payload.write_text("cache")
    trash = tmp_path / ".Trash"
    env = dict(os.environ, HOME=str(tmp_path), APPLE_CLEANUP_NO_OPLOG="1")
    command = f'''
source "{SCRIPT}" --__noop
_path_owner_is_running() {{ return 1; }}
_path_has_open_files() {{ return 1; }}
_trash_item() {{ mkdir -p {json.dumps(str(trash))}; mv "$1" {json.dumps(str(trash))}/item; echo {json.dumps(str(trash))}/item; }}
safe_rm_contents {json.dumps(str(target))} "Closed cache"
'''
    out = subprocess.run(
        ["bash", "-c", command], env=env,
        capture_output=True, text=True, timeout=10,
    )
    assert out.returncode == 0, out.stderr
    assert not payload.exists()
    assert (trash / "item").exists()


def test_clean_json_reports_dry_run_flag(tmp_path):
    data = run_clean(tmp_path, "4")  # normal run
    assert data["dry_run"] is False


def test_exclusion_list_protects_path(tmp_path):
    caches = tmp_path / "Library/Caches"
    keep = caches / "keep.app"
    drop = caches / "drop.app"
    make_dir_with_bytes(keep, kb=512)
    make_dir_with_bytes(drop, kb=512)
    env = dict(os.environ, HOME=str(tmp_path), APPLE_CLEANUP_FORCE_RM="1",
               APPLE_CLEANUP_TEST_MODE="1",
               APPLE_CLEANUP_EXCLUDE=str(keep))
    out = subprocess.run(
        ["bash", str(SCRIPT), "--clean-json", "1"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    # clean_user_cache clears each cache dir's contents; the excluded dir's
    # payload must survive while the non-excluded one is removed.
    assert (keep / "blob.bin").exists(), "excluded path must survive cleaning"
    assert not (drop / "blob.bin").exists(), "non-excluded path should be removed"


def test_app_uninstaller_unknown_app_is_safe(tmp_path):
    # An app not present in /Applications resolves to an empty bundle id.
    # The cleaner must NEVER fall back to deleting whole Library subdirs
    # (e.g. ~/Library/Containers) when the bundle id is empty.
    keep = tmp_path / "Library/Containers/keepme"
    keep.mkdir(parents=True)
    (keep / "data").write_bytes(b"x" * 1024)
    env = dict(os.environ, HOME=str(tmp_path), APPLE_CLEANUP_FORCE_RM="1",
               APPLE_CLEANUP_TEST_MODE="1")
    out = subprocess.run(
        ["bash", str(SCRIPT), "--clean-json", "11",
         "--app-uninstaller-sub", "ZzNoSuchApp"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    assert (tmp_path / "Library/Containers/keepme/data").exists(), \
        "empty bundle id must not delete Library subdirectories"


def _write_fake_app(path: Path, bundle_id="com.example.FancyApp") -> None:
    contents = path / "Contents"
    contents.mkdir(parents=True)
    with (contents / "Info.plist").open("wb") as handle:
        plistlib.dump({
            "CFBundleIdentifier": bundle_id,
            "CFBundleName": path.stem,
            "CFBundleShortVersionString": "1.0",
        }, handle)


def _run_explicit_uninstall(home: Path, app: Path, bundle_id: str, trash_ok: bool):
    env = dict(os.environ, HOME=str(home), APPLE_CLEANUP_NO_OPLOG="1")
    if trash_ok:
        trash_impl = (
            '_trash_item() { local d="$HOME/.Trash/$(basename "$1").$$.$RANDOM"; '
            'mkdir -p "$HOME/.Trash"; mv "$1" "$d"; echo "$d"; }'
        )
    else:
        trash_impl = '_trash_item() { return 1; }'
    command = (
        f'source "{SCRIPT}" --__noop; {trash_impl}; '
        f'APP_UNINSTALLER_PATH={json.dumps(str(app))}; '
        f'APP_UNINSTALLER_BUNDLE_ID={json.dumps(bundle_id)}; '
        'do_clean_json 11'
    )
    out = subprocess.run(
        ["bash", "-c", command], env=env, capture_output=True,
        text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_explicit_uninstaller_trashes_app_and_exact_leftovers(tmp_path):
    bundle_id = "com.example.FancyApp"
    app = tmp_path / "Applications/My, Fancy App.app"
    _write_fake_app(app, bundle_id)
    leftovers = [
        tmp_path / "Library/Application Support/My, Fancy App",
        tmp_path / f"Library/Caches/{bundle_id}",
        tmp_path / f"Library/WebKit/{bundle_id}",
        tmp_path / f"Library/Application Scripts/{bundle_id}",
        tmp_path / f"Library/Preferences/ByHost/{bundle_id}.A1B2C3.plist",
        tmp_path / f"Library/LaunchAgents/{bundle_id}.helper.plist",
        tmp_path / f"Library/Saved Application State/{bundle_id}.session.savedState",
    ]
    for path in leftovers:
        make_dir_with_bytes(path, kb=1)
    crash_report = tmp_path / "Library/Logs/DiagnosticReports/My, Fancy App_2026-08-27.crash"
    crash_report.parent.mkdir(parents=True, exist_ok=True)
    crash_report.write_bytes(b"x" * 1024)

    data = _run_explicit_uninstall(tmp_path, app, bundle_id, trash_ok=True)

    assert data["success"] is True, data
    assert not app.exists()
    assert all(not path.exists() for path in leftovers)
    assert not crash_report.exists()
    assert data["items_cleaned"] == 2 + len(leftovers)


def test_uninstaller_reports_permission_failure_and_preserves_data(tmp_path):
    bundle_id = "com.example.BlockedApp"
    app = tmp_path / "Applications/Blocked App.app"
    _write_fake_app(app, bundle_id)
    leftover = tmp_path / "Library/Application Support/Blocked App"
    make_dir_with_bytes(leftover, kb=1)

    data = _run_explicit_uninstall(tmp_path, app, bundle_id, trash_ok=False)

    assert data["success"] is False
    assert data["details"][0]["category"] == "app_uninstaller"
    assert data["details"][0]["status"] == "error"
    assert data["errors"]
    assert app.exists(), "failed bundle removal must be reported"
    assert leftover.exists(), "live app data must remain after bundle failure"


def test_uninstaller_preserves_shared_data_when_bundle_sibling_exists(tmp_path):
    bundle_id = "com.example.SharedApp"
    app = tmp_path / "Applications/Primary.app"
    sibling = tmp_path / "Applications/Secondary.app"
    _write_fake_app(app, bundle_id)
    _write_fake_app(sibling, bundle_id)
    shared = tmp_path / f"Library/Caches/{bundle_id}"
    make_dir_with_bytes(shared, kb=1)

    data = _run_explicit_uninstall(tmp_path, app, bundle_id, trash_ok=True)

    assert data["success"] is True, data
    assert not app.exists()
    assert sibling.exists()
    assert shared.exists(), "data shared by a surviving bundle must be preserved"
    assert data["details"][0]["status"] == "partial"


def test_all_apple_bundle_ids_are_protected(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path))
    for bundle_id in ("com.apple.Safari", "com.apple.UnknownFutureApp"):
        out = subprocess.run(
            ["bash", "-c", f'source "{SCRIPT}" --__noop; '
             f'is_protected_app_bundle_id {json.dumps(bundle_id)}'],
            env=env, capture_output=True, text=True, timeout=10,
        )
        assert out.returncode == 0, bundle_id


def test_developer_subitems_include_new_caches(tmp_path):
    # Gradle cache fixture → developer subitems içinde gradle_cache görünmeli
    make_dir_with_bytes(tmp_path / ".gradle/caches/modules", kb=2048)
    data = run_scan(tmp_path)
    subs = data["scan"]["developer"].get("subitems", [])
    ids = {s["id"] for s in subs}
    assert "gradle_cache" in ids, ids
    g = next(s for s in subs if s["id"] == "gradle_cache")
    assert g["risk"] == "caution"
    assert g["size_bytes"] > 0


def test_new_system_categories_present(tmp_path):
    data = run_scan(tmp_path)
    for cid in ["diagnostic_reports", "quicklook_cache",
                "saved_app_state", "other_trash"]:
        assert cid in data["scan"], cid


def test_thin_snapshots_json_shape(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), APPLE_CLEANUP_DRYRUN="1")
    out = subprocess.run(
        ["bash", str(SCRIPT), "--thin-snapshots-json"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert "success" in data
    assert "snapshots_before" in data


def test_scan_json_includes_in_total_per_category(tmp_path):
    # Her kategori bir boolean in_total bayrağı taşımalı; client toplamı
    # yalnız in_total=true kategorilerden hesaplar (çift sayımı önler).
    data = run_scan(tmp_path)
    for cat_id, info in data["scan"].items():
        assert "in_total" in info, cat_id
        assert isinstance(info["in_total"], bool), cat_id
    # app_uninstaller, app_leftovers ile çakıştığı için total dışı olmalı.
    assert data["scan"]["app_uninstaller"]["in_total"] is False


def test_total_bytes_equals_in_total_sum(tmp_path):
    data = run_scan(tmp_path)
    expected = sum(
        info.get("size_bytes", 0)
        for info in data["scan"].values()
        if info.get("in_total")
    )
    assert data["total_bytes"] == expected


def _source_eval(expr: str) -> str:
    """Source clean_mac.sh (main is guarded) and echo a shell expression."""
    out = subprocess.run(
        ["bash", "-c", f'source "{SCRIPT}" >/dev/null 2>&1; {expr}'],
        capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def test_safe_clean_ids_map_to_expected_numbers():
    # The quick-clean set is keyed by stable category ids. This locks the
    # id→display-number mapping so reordering CATEGORIES is caught instead of
    # silently changing what gets cleaned (frontend index ↔ backend order).
    nums = _source_eval('cat_nums_by_ids "${SAFE_CLEAN_IDS[@]}"').split()
    assert nums == ["1", "2", "4", "5", "7", "8"], nums


def test_category_registry_order_is_stable():
    # Canonical CAT_IDS order. If this changes, frontend script.js CATEGORIES
    # indices and any hardcoded numbers must be revisited together.
    expected = [
        "user_cache", "system_cache", "app_leftovers", "logs", "temp_files",
        "developer", "trash", "browser_cache", "browser_full", "ios_backups",
        "app_uninstaller", "mail_downloads", "diagnostic_reports",
        "quicklook_cache", "saved_app_state", "other_trash", "project_artifacts",
        "installer_artifacts",
    ]
    ids = _source_eval('printf "%s\\n" "${CAT_IDS[@]}"').splitlines()
    assert ids == expected, ids


def test_installer_artifacts_are_explicit_identity_bound_candidates(tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    installer = downloads / "Example.dmg"
    installer.write_bytes(b"x" * (11 * 1024 * 1024))

    result, data = run_category_scan(tmp_path, "installer_artifacts")
    assert result.returncode == 0, result.stderr
    category = data["category"]
    assert category["in_total"] is False
    assert category["risk"] == "caution"
    assert len(category["subitems"]) == 1
    item = category["subitems"][0]
    assert item["id"] == str(installer)
    assert item["is_orphaned"] is False
    assert len(item["identity"].split(":")) == 4


def test_installer_artifact_dry_run_requires_unchanged_identity(tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    installer = downloads / "Example.pkg"
    installer.write_bytes(b"x" * (11 * 1024 * 1024))
    _, scan = run_category_scan(tmp_path, "installer_artifacts")
    item = scan["category"]["subitems"][0]

    env = dict(os.environ, HOME=str(tmp_path), APPLE_CLEANUP_DRYRUN="1")
    ok = subprocess.run([
        "bash", str(SCRIPT), "--installer-artifact-sub", item["id"],
        "--installer-artifact-identities", item["identity"],
        "--clean-ids-json", "installer_artifacts",
    ], env=env, capture_output=True, text=True, timeout=60)
    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout)["estimated_bytes"] >= 11 * 1024 * 1024
    assert installer.exists(), "dry-run must not move the installer"

    installer.write_bytes(b"changed")
    changed = subprocess.run([
        "bash", str(SCRIPT), "--installer-artifact-sub", item["id"],
        "--installer-artifact-identities", item["identity"],
        "--clean-ids-json", "installer_artifacts",
    ], env=env, capture_output=True, text=True, timeout=60)
    payload = json.loads(changed.stdout)
    assert payload["success"] is False
    assert "changed scan identity" in payload["errors"][0]["message"]


def test_clean_ids_json_uses_stable_category_ids(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), APPLE_CLEANUP_DRYRUN="1")
    out = subprocess.run(
        ["bash", str(SCRIPT), "--clean-ids-json", "user_cache,logs"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert [entry["category"] for entry in data["details"]] == [
        "user_cache", "logs",
    ]


def test_clean_ids_json_rejects_unknown_id(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path))
    out = subprocess.run(
        ["bash", str(SCRIPT), "--clean-ids-json", "user_cache,not-a-category"],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert out.returncode != 0
    assert json.loads(out.stdout)["success"] is False


def test_remove_user_data_moves_state_and_schedule_to_trash(tmp_path):
    state = tmp_path / ".cache/apple-cleanup"
    state.mkdir(parents=True)
    (state / "usage_history.json").write_text("[]")
    agent = tmp_path / "Library/LaunchAgents/com.cleanmac.weeklycleanup.plist"
    agent.parent.mkdir(parents=True)
    agent.write_text("plist")
    trash = tmp_path / ".Trash"
    trash.mkdir()
    env = dict(os.environ, HOME=str(tmp_path), APPLE_CLEANUP_NO_OPLOG="1")
    command = f'''
source "{SCRIPT}" --__noop
confirm() {{ return 0; }}
launchctl() {{ return 0; }}
do_remove_user_data
'''
    out = subprocess.run(
        ["bash", "-c", command], env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert out.returncode == 0, out.stderr
    assert not state.exists()
    assert not agent.exists()
    assert any(path.name.startswith("apple-cleanup") for path in trash.iterdir())
    assert any(path.name.startswith("com.cleanmac.weeklycleanup.plist")
               for path in trash.iterdir())


def test_derived_data_summary_handles_empty_rows(tmp_path):
    # Under set -eo pipefail, derived_data_project_summary must not exit 1
    # when DerivedData has no projects > 1MB.
    env = dict(os.environ, HOME=str(tmp_path))
    dd = tmp_path / "Library/Developer/Xcode/DerivedData"
    dd.mkdir(parents=True)
    out = subprocess.run(
        ["bash", "-c", f'set -eo pipefail; source "{SCRIPT}"; derived_data_project_summary'],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert out.returncode == 0, out.stderr


def test_safe_rm_contents_handles_trash_failure(tmp_path):
    # Mock _trash_item to return 1; safe_rm_contents must not exit 1 under set -e.
    env = dict(os.environ, HOME=str(tmp_path))
    target = tmp_path / "cache_dir"
    target.mkdir()
    (target / "file.txt").write_text("data")
    cmd = (
        f'set -eo pipefail; source "{SCRIPT}"; '
        '_trash_item() { return 1; }; '
        'safe_rm_contents "' + str(target) + '" "Test"'
    )
    out = subprocess.run(
        ["bash", "-c", cmd],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert out.returncode == 0, out.stderr


def test_partial_direct_cleanup_reports_english_warning_and_keeps_success(tmp_path):
    target = tmp_path / "temp"
    target.mkdir()
    removable = target / "removable.bin"
    blocked = target / "blocked.bin"
    removable.write_bytes(b"x" * 4096)
    blocked.write_bytes(b"y" * 4096)

    env = dict(os.environ, HOME=str(tmp_path), APPLE_CLEANUP_FORCE_RM="1",
               APPLE_CLEANUP_TEST_MODE="1")
    command = f'''
source "{SCRIPT}" --__noop
scan_all() {{ :; }}
rm() {{
  local arg
  for arg in "$@"; do
    case "$arg" in *blocked.bin) return 1 ;; esac
  done
  command rm "$@"
}}
clean_temp_files() {{
  _CURRENT_NEEDS_SUDO=0
  _CURRENT_IS_TRASH_EMPTY=1
  safe_rm_contents {json.dumps(str(target))} "User Temp"
  _CURRENT_IS_TRASH_EMPTY=0
}}
do_clean_json 5
'''
    out = subprocess.run(
        ["bash", "-c", command], env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)

    assert data["success"] is True
    assert data["details"][0]["status"] == "partial"
    assert data["errors"] == []
    assert data["warnings"] == [{
        "category": "temp_files",
        "message": "User Temp: some active or protected files were skipped",
    }]
    assert data["estimated_bytes"] > 0
    assert not removable.exists()
    assert blocked.exists()
