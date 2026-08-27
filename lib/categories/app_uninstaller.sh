#!/usr/bin/env bash
# App discovery, identity validation, shared-data protection, and cleanup.
# Sourced by clean_mac.sh after the shared runtime and path policy.
# shellcheck disable=SC2034

scan_app_uninstaller() {
  local total=0
  local app app_name bundle_id s
  # Include shallow vendor folders while pruning each package so helper apps
  # inside Contents never appear as independently uninstallable applications.
  while IFS= read -r -d '' app; do
    [ -L "$app" ] && continue
    app_name=$(basename "$app" .app)
    bundle_id=$(get_app_bundle_id "$app")
    local dir
    while IFS= read -r -d '' dir; do
      [ -e "$dir" ] || continue
      s=$(get_size_bytes "$dir") || s=0
      total=$((total + s))
    done < <(app_leftover_paths "$app_name" "$bundle_id")
  done < <(find /Applications "$HOME/Applications" -maxdepth 3 -name "*.app" -prune -print0 2>/dev/null)
  local i; i=$(cat_index_by_id app_uninstaller)
  CAT_SIZES[i]=$total
}


clean_app_uninstaller() {
  _CURRENT_NEEDS_SUDO=0
  # Finder's Trash path can request macOS authorization for root-owned apps in
  # /Applications and keeps the operation recoverable.  The old forced rm path
  # had neither property and silently failed for the most common installation
  # layout.
  _CURRENT_IS_TRASH_EMPTY=0
  header "$(L hdr_app_uninstaller)"
  if $JSON_MODE; then
    if [ -z "$APP_UNINSTALLER_PATH" ] && [ -z "$APP_UNINSTALLER_CLEAN" ]; then
      info "$(L no_app_specified)"
      return
    fi

    local app_paths=()
    if [ -n "$APP_UNINSTALLER_PATH" ]; then
      if ! is_valid_app_bundle_path "$APP_UNINSTALLER_PATH"; then
        record_clean_error "Invalid application bundle path"
        return
      fi
      app_paths+=("$APP_UNINSTALLER_PATH")
    else
      # Backwards-compatible path for the scan-results cleaner.  The dedicated
      # uninstaller endpoint uses the explicit, server-verified path above.
      local parsed_apps=()
      IFS=',' read -ra parsed_apps <<< "$APP_UNINSTALLER_CLEAN"
      local legacy_name legacy_path
      for legacy_name in "${parsed_apps[@]}"; do
        legacy_name="${legacy_name## }"; legacy_name="${legacy_name%% }"
        [ -z "$legacy_name" ] && continue
        case "$legacy_name" in
          */*|*..*)
            record_clean_error "$(L invalid_path_traversal): $legacy_name"
            continue
            ;;
        esac
        legacy_path=""
        [ -d "/Applications/$legacy_name.app" ] && legacy_path="/Applications/$legacy_name.app"
        [ -z "$legacy_path" ] && [ -d "$HOME/Applications/$legacy_name.app" ] \
          && legacy_path="$HOME/Applications/$legacy_name.app"
        if [ -n "$legacy_path" ]; then
          app_paths+=("$legacy_path")
        else
          record_clean_error "Application is no longer installed: $legacy_name"
        fi
      done
    fi

    local app_path app_name bundle_id
    for app_path in ${app_paths[@]+"${app_paths[@]}"}; do
      app_name=$(basename "$app_path" .app)
      # Resolve the real bundle id from Info.plist BEFORE deleting the .app,
      # so leftovers keyed by bundle id can still be located afterwards.
      bundle_id=""
      if [ -n "$app_path" ] && [ -d "$app_path" ]; then
        bundle_id=$(get_app_bundle_id "$app_path")
      elif is_valid_bundle_id "$APP_UNINSTALLER_BUNDLE_ID"; then
        # Homebrew may already have removed the bundle.  The server captured
        # this id during its fresh pre-delete discovery so exact-id leftovers
        # can still be removed safely.
        bundle_id="$APP_UNINSTALLER_BUNDLE_ID"
      fi
      if is_protected_app_bundle_id "$bundle_id"; then
        record_clean_error "Protected application cannot be removed: $app_name"
        continue
      fi
      if [ -e "$app_path" ] || [ -L "$app_path" ]; then
        safe_rm "$app_path" "App: $app_name"
      fi
      # Never erase an installed app's data after its bundle deletion failed.
      # Dry-run is the exception: the bundle intentionally remains in place.
      if [ "$DRYRUN" != "1" ] && { [ -e "$app_path" ] || [ -L "$app_path" ]; }; then
        continue
      fi
      if app_bundle_sibling_exists "$bundle_id" "$app_path"; then
        warn "Shared application data preserved; another bundle uses $bundle_id"
        record_clean_warning "Shared application data preserved; another bundle uses $bundle_id"
        continue
      fi
      local dir
      while IFS= read -r -d '' dir; do
        if [ -e "$dir" ]; then
          safe_rm "$dir" "Leftover: $dir"
        fi
      done < <(app_leftover_paths "$app_name" "$bundle_id")
      while IFS= read -r -d '' dir; do
        if [ -e "$dir" ]; then
          safe_rm "$dir" "Diagnostic report: $dir"
        fi
      done < <(app_diagnostic_report_paths "$app_name" "$bundle_id")
    done
    return
  fi
  info "$(L uninstaller_cli_only)"
}


get_app_bundle_id() {
  local app_path="$1"
  local plist="$app_path/Contents/Info.plist"
  [ -f "$plist" ] || { echo ""; return; }
  local bid
  bid=$(/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$plist" 2>/dev/null) || bid=""
  # Only accept a sane reverse-DNS-style id; reject anything that could
  # widen a leftover path (slashes, dot-dot, spaces, empty).
  case "$bid" in
    ""|*/*|*..*|*" "*) echo "" ;;
    *) echo "$bid" ;;
  esac
}

is_valid_bundle_id() {
  local bid="${1:-}"
  case "$bid" in
    ""|*/*|*..*|*" "*|*$'\n'*|*$'\t'*) return 1 ;;
  esac
  [[ "$bid" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{1,254}$ ]]
}

# Defense in depth for the explicit path accepted by the JSON uninstaller.
# The web server also resolves this target from a fresh discovery snapshot.
is_valid_app_bundle_path() {
  local app_path="${1:-}"
  [ -n "$app_path" ] || return 1
  [ ! -L "$app_path" ] || return 1
  case "$app_path" in
    *$'\n'*|*$'\r'*|*$'\t'*|*'/../'*|*'/./'*|*'//'*) return 1 ;;
  esac
  case "$app_path" in
    /Applications/*.app|"$HOME"/Applications/*.app) return 0 ;;
  esac
  return 1
}

is_protected_app_bundle_id() {
  case "${1:-}" in com.apple.*) return 0 ;; esac
  return 1
}

app_bundle_sibling_exists() {
  local bundle_id="$1" excluded_path="${2:-}" candidate candidate_id
  [ -n "$bundle_id" ] || return 1
  while IFS= read -r -d '' candidate; do
    [ "$candidate" = "$excluded_path" ] && continue
    [ -L "$candidate" ] && continue
    candidate_id=$(get_app_bundle_id "$candidate")
    [ "$candidate_id" = "$bundle_id" ] && return 0
  done < <(find /Applications "$HOME/Applications" -maxdepth 3 \
    -name '*.app' -prune -print0 2>/dev/null)
  return 1
}

# Emit the canonical leftover-path candidates for an app, NUL-separated.
# Shared by scan + clean so the two can never drift. Bundle-id-derived paths
# are emitted ONLY when a valid bundle id is known, so an empty id can never
# collapse to a whole Library subdirectory (e.g. ~/Library/Containers).
# Args: $1 = app_name, $2 = bundle_id (may be empty)
app_leftover_paths() {
  local app_name="$1" bundle_id="$2"
  [ -n "$app_name" ] || return 0
  printf '%s\0' "$HOME/Library/Application Support/$app_name"
  printf '%s\0' "$HOME/Library/Caches/$app_name"
  printf '%s\0' "$HOME/Library/Logs/$app_name"
  if [ -n "$bundle_id" ]; then
    printf '%s\0' "$HOME/Library/Application Support/$bundle_id"
    printf '%s\0' "$HOME/Library/Caches/$bundle_id"
    printf '%s\0' "$HOME/Library/Logs/$bundle_id"
    printf '%s\0' "$HOME/Library/Containers/$bundle_id"
    printf '%s\0' "$HOME/Library/Group Containers/$bundle_id"
    printf '%s\0' "$HOME/Library/Group Containers/group.$bundle_id"
    printf '%s\0' "$HOME/Library/Application Scripts/$bundle_id"
    printf '%s\0' "$HOME/Library/HTTPStorages/$bundle_id"
    printf '%s\0' "$HOME/Library/WebKit/$bundle_id"
    printf '%s\0' "$HOME/Library/Cookies/${bundle_id}.binarycookies"
    printf '%s\0' "$HOME/Library/LaunchAgents/${bundle_id}.plist"
    printf '%s\0' "$HOME/Library/Preferences/${bundle_id}.plist"
    printf '%s\0' "$HOME/Library/Saved Application State/${bundle_id}.savedState"

    # macOS creates identifier-suffixed variants for some preference, agent,
    # and state files (for example ByHost preference files).  They remain
    # exact bundle-id matches; do not broaden these to vendor/app-name terms.
    local candidate base
    for candidate in "$HOME/Library/Preferences/${bundle_id}".*.plist \
      "$HOME/Library/Preferences/ByHost/${bundle_id}".*.plist \
      "$HOME/Library/LaunchAgents/${bundle_id}".*.plist \
      "$HOME/Library/Saved Application State/${bundle_id}".*.savedState; do
      [ -e "$candidate" ] || continue
      printf '%s\0' "$candidate"
    done
  fi
}

# Crash reports include a timestamp after the executable or bundle name.  Only
# inspect the user's DiagnosticReports directory: system reports require a
# separate privileged flow and must not be widened by app removal.
app_diagnostic_report_paths() {
  local app_name="$1" bundle_id="$2" report_dir entry
  report_dir="$HOME/Library/Logs/DiagnosticReports"
  [ -d "$report_dir" ] || return 0
  while IFS= read -r -d '' entry; do
    case "$(basename "$entry")" in
      "${app_name}"_*) printf '%s\0' "$entry" ;;
      "${bundle_id}"_*) [ -n "$bundle_id" ] && printf '%s\0' "$entry" ;;
    esac
  done < <(find "$report_dir" -maxdepth 1 -type f -print0 2>/dev/null)
}

get_app_display_name() {
  local app_path="$1"
  local plist="$app_path/Contents/Info.plist"
  [ -f "$plist" ] || { basename "$app_path" .app; return; }
  local name
  name=$(/usr/libexec/PlistBuddy -c "Print :CFBundleDisplayName" "$plist" 2>/dev/null)
  [ -z "$name" ] && name=$(/usr/libexec/PlistBuddy -c "Print :CFBundleName" "$plist" 2>/dev/null)
  [ -z "$name" ] && name=$(basename "$app_path" .app)
  
  # Strip trailing .app in case plist returned it
  name="${name%.app}"
  
  if [ "$name" = "zoom.us" ]; then
    name="Zoom"
  elif [ "$name" = "Code" ]; then
    name="Visual Studio Code"
  fi
  echo "$name"
}

scan_app_uninstaller_subitems_json() {
  local first=true
  local app app_name bundle_id leftover_total s sz_h esc_name esc_bundle esc_id disp_name
  while IFS= read -r -d '' app; do
    [ -L "$app" ] && continue
    app_name=$(basename "$app" .app)
    bundle_id=$(get_app_bundle_id "$app")
    leftover_total=0
    local dir
    while IFS= read -r -d '' dir; do
      [ -e "$dir" ] || continue
      s=$(get_size_bytes "$dir") || s=0
      leftover_total=$((leftover_total + s))
    done < <(app_leftover_paths "$app_name" "$bundle_id")
    while IFS= read -r -d '' dir; do
      [ -e "$dir" ] || continue
      s=$(get_size_bytes "$dir") || s=0
      leftover_total=$((leftover_total + s))
    done < <(app_diagnostic_report_paths "$app_name" "$bundle_id")
    sz_h=$(format_bytes "$leftover_total")
    disp_name=$(get_app_display_name "$app")
    esc_name=$(json_escape_str "$disp_name")
    esc_id=$(json_escape_str "$app_name")
    esc_bundle=$(json_escape_str "$bundle_id")
    if [ "$first" = true ]; then
      first=false
    else
      echo ","
    fi
    echo -n "        {\"id\": \"$esc_id\", \"name\": \"$esc_name\", \"bundle_id\": \"$esc_bundle\", \"size_bytes\": $leftover_total, \"size_human\": \"$sz_h\", \"is_orphaned\": false}"
  done < <(find /Applications "$HOME/Applications" -maxdepth 3 -name "*.app" -prune -print0 2>/dev/null | sort -z)
}
