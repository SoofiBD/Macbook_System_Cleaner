#!/usr/bin/env bash
# Trash-first mutation executor and dry-run gateway.
# Sourced by clean_mac.sh after shared formatting/log helpers are initialized.
# shellcheck disable=SC2034

_trash_item() {
  local path="$1"
  # -L keeps broken symlinks (target gone, -e is false) in scope.
  [ -e "$path" ] || [ -L "$path" ] || return 0

  local base expected expected_was_free=false
  base=$(basename "$path")
  expected="$HOME/.Trash/$base"
  if [ ! -e "$expected" ] && [ ! -L "$expected" ]; then
    expected_was_free=true
  fi

  # Tier 1: AppleScript (native Finder trash with undo support).
  # Only run if not running in a mocked test environment ($HOME in /tmp or /var)
  if [[ "$HOME" != /private/var/* && "$HOME" != /var/* && "$HOME" != /tmp/* && "${APPLE_CLEANUP_FORCE_MANUAL_TRASH:-0}" != "1" ]]; then
    if osascript -e 'on run argv' \
                 -e 'set theItem to (POSIX file (item 1 of argv)) as alias' \
                 -e 'tell application "Finder" to delete theItem' \
                 -e 'end run' "$path" >/dev/null 2>&1; then
      if $expected_was_free && { [ -e "$expected" ] || [ -L "$expected" ]; }; then
        echo "$expected"
      elif [ ! -e "$path" ]; then
        echo "$expected"
      fi
      return 0
    fi
  fi

  # Tier 2: Manual mv to ~/.Trash with collision-safe naming
  [ -L "$HOME/.Trash" ] && return 1
  if [ ! -d "$HOME/.Trash" ]; then
    mkdir -m 700 "$HOME/.Trash" 2>/dev/null || return 1
  fi
  [ -O "$HOME/.Trash" ] || return 1
  local dest
  dest="$HOME/.Trash/$base"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    # Append timestamp + pid + random so collisions within the same second
    # (two identically-named items) don't overwrite each other.
    dest="$HOME/.Trash/${base}.$(date +%s).$$.${RANDOM}"
    while [ -e "$dest" ] || [ -L "$dest" ]; do
      dest="$HOME/.Trash/${base}.$(date +%s).$$.${RANDOM}"
    done
  fi
  if mv "$path" "$dest" 2>/dev/null; then
    echo "$dest"
    return 0
  fi
  return 1
}

# Determine if we should use rm -rf or trash-first for a given context
# Arguments: needs_sudo_flag (0 or 1), is_trash_empty (0 or 1)
_should_force_rm() {
  local needs_sudo="${1:-0}"
  local is_trash_empty="${2:-0}"
  # Force RM conditions:
  #   1. Explicit test bypass in an isolated temporary HOME
  #   2. Category requires sudo (system paths)
  #   3. We are emptying the trash itself
  if [ "$FORCE_RM" = "1" ] && [ "$TEST_MODE" = "1" ]; then
    case "$HOME" in
      /tmp/*|/private/tmp/*|/private/var/folders/*) return 0 ;;
    esac
  fi
  [ "$needs_sudo" -eq 1 ] && return 0
  [ "$is_trash_empty" -eq 1 ] && return 0
  return 1
}

# Run a non-file mutating command under the same dry-run contract as safe_rm.
# Arguments: success translation key, failure translation key, command argv...
run_mutating_action() {
  local success_key="$1"
  local failure_key="$2"
  shift 2

  if [ "$DRYRUN" = "1" ]; then
    success "$(L "$success_key") — $(L would_run)"
    TOTAL_ITEMS=$((TOTAL_ITEMS + 1))
    return 0
  fi

  if "$@" >/dev/null 2>&1; then
    success "$(L "$success_key")"
    TOTAL_ITEMS=$((TOTAL_ITEMS + 1))
    return 0
  fi

  warn "$(L "$failure_key")"
  record_clean_warning "$(L "$failure_key")"
  return 1
}

_simctl_erase_all() {
  xcrun simctl shutdown all >/dev/null 2>&1 || true
  xcrun simctl erase all
}

# The path policy is a separately testable core module. It is sourced here so
# the executor below cannot be used without its fail-closed validation layer.
# shellcheck source=lib/core/path_policy.sh
source "$SCRIPT_DIR/lib/core/path_policy.sh"

# Context variable: set by clean functions to indicate sudo context
_CURRENT_NEEDS_SUDO=0
_CURRENT_IS_TRASH_EMPTY=0
# Category key for the item currently being cleaned (set by run_clean); used to
# tag operation-log records. Empty when cleanup runs outside a category loop.
_CURRENT_CATEGORY=""

_removal_identity_matches() {
  local kind="$1" path="$2" expected="$3" actual=""
  case "$kind" in
    project_artifact)
      actual=$(_project_artifact_identity "$path" 2>/dev/null || true)
      ;;
    installer_artifact)
      actual=$(_installer_artifact_identity "$path" 2>/dev/null || true)
      ;;
    *) return 1 ;;
  esac
  [ -n "$actual" ] && [ "$actual" = "$expected" ]
}

safe_rm() {
  local path="$1"
  local label="${2:-$1}"
  local expected_identity="${3:-}"
  local identity_kind="${4:-project_artifact}"
  local invalid_identity_msg
  if [ "$identity_kind" = "installer_artifact" ]; then
    invalid_identity_msg=$(L invalid_installer_artifact)
  else
    invalid_identity_msg=$(L invalid_artifact)
  fi
  [ -z "$path" ] && {
    err "$(L empty_path): $label"
    record_clean_error "$(L empty_path): $label"
    return 0
  }
  if _is_excluded "$path"; then
    info "$(L excluded): $label"
    return 0
  fi
  # -L keeps broken symlinks (target gone, -e is false) in scope.
  [ -e "$path" ] || [ -L "$path" ] || return 0
  _validate_removal_path "$path" leaf "$label" || return 0
  _guard_live_path "$path" "$label" || return 0
  if [ -n "$expected_identity" ] && \
     ! _removal_identity_matches "$identity_kind" "$path" "$expected_identity"; then
    warn "$invalid_identity_msg: $path"
    record_clean_error "$invalid_identity_msg: identity changed: $path"
    return 0
  fi
  local sz_b; sz_b=$(get_size_bytes "$path")
  local sz_h; sz_h=$(format_bytes "$sz_b")

  if [ "$DRYRUN" = "1" ]; then
    success "$label: ${BOLD}${sz_h}${NC} $(L would_remove)"
    TOTAL_FREED=$((TOTAL_FREED + sz_b))
    TOTAL_ITEMS=$((TOTAL_ITEMS + 1))
    return 0
  fi

  if _should_force_rm "$_CURRENT_NEEDS_SUDO" "$_CURRENT_IS_TRASH_EMPTY"; then
    if [ -n "$expected_identity" ] && \
       ! _removal_identity_matches "$identity_kind" "$path" "$expected_identity"; then
      warn "$invalid_identity_msg: $path"
      record_clean_error "$invalid_identity_msg: identity changed: $path"
      return 0
    fi
    # Direct rm -rf (sudo paths, trash emptying, or CI mode)
    if $SUDO_AVAILABLE && [ "$_CURRENT_NEEDS_SUDO" -eq 1 ]; then
      if sudo rm -rf "$path" 2>/dev/null; then
        success "$label: ${BOLD}${sz_h}${NC} $(L deleted)"
        TOTAL_FREED=$((TOTAL_FREED + sz_b))
        TOTAL_ITEMS=$((TOTAL_ITEMS + 1))
        oplog_record "delete" "$sz_b" "$path" "" "$_CURRENT_CATEGORY"
      else
        err "$label $(L delete_failed)"
        record_clean_error "$label $(L delete_failed)"
      fi
    else
      if rm -rf "$path" 2>/dev/null; then
        success "$label: ${BOLD}${sz_h}${NC} $(L deleted)"
        TOTAL_FREED=$((TOTAL_FREED + sz_b))
        TOTAL_ITEMS=$((TOTAL_ITEMS + 1))
        oplog_record "delete" "$sz_b" "$path" "" "$_CURRENT_CATEGORY"
      else
        err "$label $(L delete_failed)"
        record_clean_error "$label $(L delete_failed)"
      fi
    fi
  else
    # Trash-first (user files, non-sudo)
    if [ -n "$expected_identity" ] && \
       ! _removal_identity_matches "$identity_kind" "$path" "$expected_identity"; then
      warn "$invalid_identity_msg: $path"
      record_clean_error "$invalid_identity_msg: identity changed: $path"
      return 0
    fi
    local _td; _td="$(_trash_item "$path" || true)"
    if [ -n "$_td" ] || [ ! -e "$path" ]; then
      success "$label: ${BOLD}${sz_h}${NC} $(L trashed)"
      TOTAL_FREED=$((TOTAL_FREED + sz_b))
      TOTAL_ITEMS=$((TOTAL_ITEMS + 1))
      oplog_record "trash" "$sz_b" "$path" "$_td" "$_CURRENT_CATEGORY"
    else
      err "$label $(L delete_failed)"
      record_clean_error "$label $(L delete_failed)"
    fi
  fi
}

safe_rm_contents() {
  local path="$1"
  local label="${2:-$1}"
  [ -z "$path" ] && {
    record_clean_error "$(L empty_path): $label"
    return 0
  }
  [ -d "$path" ] || return 0
  _validate_removal_path "$path" contents "$label" || return 0
  _guard_live_path "$path" "$label" || return 0
  # Exclusion-aware mode: when the user defined protected paths, delete each
  # child individually (via safe_rm, which honors excludes + dry-run) so a
  # protected item inside the directory is never swept away by a bulk rm.
  if [ -n "$EXCLUDE_RAW" ]; then
    local child
    while IFS= read -r -d '' child; do
      safe_rm "$child" "$child"
    done < <(find "$path" -maxdepth 1 -mindepth 1 -print0 2>/dev/null)
    return 0
  fi
  local sz_b; sz_b=$(get_dir_size_bytes "$path")
  [ "$sz_b" -le 0 ] 2>/dev/null && return 0
  local sz_h; sz_h=$(format_bytes "$sz_b")

  if [ "$DRYRUN" = "1" ]; then
    success "$label: ${BOLD}${sz_h}${NC} $(L would_remove)"
    TOTAL_FREED=$((TOTAL_FREED + sz_b))
    TOTAL_ITEMS=$((TOTAL_ITEMS + 1))
    return 0
  fi

  if _should_force_rm "$_CURRENT_NEEDS_SUDO" "$_CURRENT_IS_TRASH_EMPTY"; then
    # Delete children independently. macOS may keep a few live service files
    # open or recreate them during cleanup; one such item must not turn all
    # successfully removed siblings into a category-wide failure.
    local removed_any=false
    local delete_failed=false
    local removed_bytes=0
    local child child_sz
    while IFS= read -r -d '' child; do
      if ! _validate_removal_path "$child" leaf "$label"; then
        delete_failed=true
        continue
      fi
      child_sz=$(get_size_bytes "$child")
      local child_removed=false
      if $SUDO_AVAILABLE && [ "$_CURRENT_NEEDS_SUDO" -eq 1 ]; then
        sudo rm -rf "$child" 2>/dev/null && child_removed=true
      else
        rm -rf "$child" 2>/dev/null && child_removed=true
      fi
      # A live service can race the command and remove the path first. Treat a
      # path that is now absent as successfully cleaned regardless of rm's code.
      if $child_removed || { [ ! -e "$child" ] && [ ! -L "$child" ]; }; then
        removed_any=true
        removed_bytes=$((removed_bytes + child_sz))
        oplog_record "delete" "$child_sz" "$child" "" "$_CURRENT_CATEGORY"
      else
        delete_failed=true
      fi
    done < <(find "$path" -maxdepth 1 -mindepth 1 -print0 2>/dev/null)

    if $removed_any; then
      local removed_h; removed_h=$(format_bytes "$removed_bytes")
      success "$label: ${BOLD}${removed_h}${NC} $(L deleted)"
      TOTAL_FREED=$((TOTAL_FREED + removed_bytes))
      TOTAL_ITEMS=$((TOTAL_ITEMS + 1))
    fi
    if $delete_failed; then
      if $removed_any; then
        warn "$label: $(L partial_skipped)"
        record_clean_warning "$label: $(L partial_skipped)"
      else
        err "$label $(L delete_failed)"
        record_clean_error "$label $(L delete_failed)"
      fi
    fi
  else
    # Trash-first: move each child item to trash individually
    local trashed_any=false
    local trash_failed=false
    local trashed_bytes=0
    local child _td
    while IFS= read -r -d '' child; do
      if ! _validate_removal_path "$child" leaf "$label"; then
        trash_failed=true
        continue
      fi
      # Capture size BEFORE trashing; afterwards the child is gone and any size
      # read returns 0. Use get_size_bytes so files (not just dirs) are measured.
      local child_sz; child_sz=$(get_size_bytes "$child")
      _td="$(_trash_item "$child" || true)"
      if [ -n "$_td" ] || [ ! -e "$child" ]; then
        trashed_any=true
        trashed_bytes=$((trashed_bytes + child_sz))
        oplog_record "trash" "$child_sz" "$child" "$_td" "$_CURRENT_CATEGORY"
      else
        trash_failed=true
      fi
    done < <(find "$path" -maxdepth 1 -mindepth 1 -print0 2>/dev/null)
    if $trashed_any; then
      local trashed_h; trashed_h=$(format_bytes "$trashed_bytes")
      success "$label: ${BOLD}${trashed_h}${NC} $(L trashed)"
      TOTAL_FREED=$((TOTAL_FREED + trashed_bytes))
      TOTAL_ITEMS=$((TOTAL_ITEMS + 1))
    fi
    if $trash_failed; then
      if $trashed_any; then
        warn "$label: $(L partial_skipped)"
        record_clean_warning "$label: $(L partial_skipped)"
      else
        err "$label $(L delete_failed)"
        record_clean_error "$label $(L delete_failed)"
      fi
    fi
  fi
}

# ─── Sudo Check ─────────────────────────────────────────────────────────────
