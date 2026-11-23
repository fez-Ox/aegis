#!/usr/bin/env bash
#
# Build the Aegis Flutter app (apps/mobile).
#
# Mirrors what CI/CD does (.github/workflows/ci.yml, cd.yml): fetch packages,
# analyze, test, then build. Fails loudly if the Flutter SDK is missing instead
# of pretending the build succeeded.
#
# Usage:
#   scripts/build_app.sh                 # release APK (default)
#   scripts/build_app.sh --debug         # debug APK
#   scripts/build_app.sh --split         # one APK per ABI (smaller downloads)
#   scripts/build_app.sh --appbundle     # release AAB for Play upload
#   scripts/build_app.sh --web           # web bundle
#   scripts/build_app.sh --no-test       # skip widget tests
#   scripts/build_app.sh --no-analyze    # skip static analysis
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$REPO_ROOT/apps/mobile"

MODE="release"
TARGET="apk"
RUN_ANALYZE=1
RUN_TESTS=1
SPLIT=0

say() { printf '\n==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

usage() {
    awk 'NR == 1 { next } /^set -euo pipefail$/ { exit } { sub(/^# ?/, ""); print }' \
        "${BASH_SOURCE[0]}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --debug)      MODE="debug" ;;
        --release)    MODE="release" ;;
        --web)        TARGET="web" ;;
        --apk)        TARGET="apk" ;;
        --appbundle)  TARGET="appbundle" ;;
        --split)      SPLIT=1 ;;
        --no-analyze) RUN_ANALYZE=0 ;;
        --no-test)    RUN_TESTS=0 ;;
        -h|--help)    usage; exit 0 ;;
        *)            printf 'error: unknown option %s\n\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

if [[ "$TARGET" != "apk" && "$SPLIT" -eq 1 ]]; then
    die "--split only applies to --apk builds"
fi
if [[ "$TARGET" == "appbundle" && "$MODE" == "debug" ]]; then
    die "--appbundle is release-only; drop --debug"
fi

[[ -f "$APP_DIR/pubspec.yaml" ]] || die "no pubspec.yaml at $APP_DIR"

# Flutter is often unpacked outside PATH (e.g. ~/flutter). Use it if found.
find_flutter() {
    local candidate
    if command -v flutter >/dev/null 2>&1; then
        command -v flutter
        return 0
    fi
    for candidate in \
        "${FLUTTER_ROOT:+$FLUTTER_ROOT/bin/flutter}" \
        "$HOME/flutter/bin/flutter" \
        "$HOME/development/flutter/bin/flutter" \
        "$HOME/.local/flutter/bin/flutter" \
        /opt/flutter/bin/flutter \
        /usr/local/flutter/bin/flutter; do
        if [[ -n "$candidate" && -x "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

FLUTTER="$(find_flutter)" || die "Flutter SDK not found on PATH or in the usual places
(~/.flutter, ~/development/flutter, /opt/flutter).
Install it from https://docs.flutter.dev/get-started/install and re-run, or set
FLUTTER_ROOT to an existing SDK. (CI is the only other check.)"
export PATH="$(dirname "$FLUTTER"):$PATH"
say "Using $("$FLUTTER" --version 2>/dev/null | head -1) at $FLUTTER"

if [[ "$TARGET" != "web" ]]; then
    command -v java >/dev/null 2>&1 || die "java not found; an Android build needs JDK 17 on PATH"
    if [[ -z "${ANDROID_HOME:-}" && -z "${ANDROID_SDK_ROOT:-}" && -d "$HOME/Android/Sdk" ]]; then
        export ANDROID_HOME="$HOME/Android/Sdk"
        export ANDROID_SDK_ROOT="$ANDROID_HOME"
    fi
fi

cd "$APP_DIR"

if [[ "$TARGET" != "web" && ! -d android ]]; then
    say "Generating missing Android platform files"
    "$FLUTTER" create --platforms=android --org com.aegis .
fi

say "Fetching packages (flutter pub get)"
"$FLUTTER" pub get

if [[ "$RUN_ANALYZE" -eq 1 ]]; then
    say "Static analysis (flutter analyze)"
    "$FLUTTER" analyze --no-fatal-infos
fi

if [[ "$RUN_TESTS" -eq 1 ]]; then
    say "Widget tests (flutter test)"
    "$FLUTTER" test
fi

if [[ "$TARGET" != "web" ]]; then
    say "Verifying Android network permissions"
    manifest="android/app/src/main/AndroidManifest.xml"
    [[ -f "$manifest" ]] || die "missing $manifest"
    grep -q 'android.permission.INTERNET' "$manifest" \
        || die "INTERNET permission missing from $manifest (the app cannot reach the ask API)"
    grep -q 'usesCleartextTraffic' "$manifest" \
        || die "usesCleartextTraffic missing from $manifest (plain-HTTP dev servers will fail)"
fi

case "$TARGET" in
    web)
        say "Building web bundle ($MODE)"
        "$FLUTTER" build web --"$MODE"
        ARTIFACTS="$APP_DIR/build/web"
        ;;
    appbundle)
        say "Building release App Bundle"
        "$FLUTTER" build appbundle --release
        ARTIFACTS="$APP_DIR/build/app/outputs/bundle/release"
        ;;
    apk)
        if [[ "$SPLIT" -eq 1 ]]; then
            say "Building split APKs ($MODE)"
            "$FLUTTER" build apk --"$MODE" --split-per-abi
        else
            say "Building APK ($MODE)"
            "$FLUTTER" build apk --"$MODE"
        fi
        ARTIFACTS="$APP_DIR/build/app/outputs/flutter-apk"
        ;;
esac

say "Done. Artifacts:"
find "$ARTIFACTS" -maxdepth 1 -type f \( -name '*.apk' -o -name '*.aab' -o -name 'index.html' \) \
    -printf '  %p (%s bytes)\n' | sort

if [[ "$TARGET" == "apk" ]]; then
    cat <<'EOF'

Install on a USB-connected phone:
  adb install -r <apk>
Then point the app at the API, e.g.:
  adb reverse tcp:8000 tcp:8000
EOF
fi
