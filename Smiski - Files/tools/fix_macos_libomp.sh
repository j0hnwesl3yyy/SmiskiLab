#!/usr/bin/env bash
# LightGBM/XGBoost wheels on macOS look for Homebrew's libomp. If it is missing, reuse the copy that ships
# inside scikit-learn's wheel and point both libraries at it (changes only the local .venv).
# Preferred alternative when you have Homebrew access:  brew install libomp
set -euo pipefail
VENV="${1:-.venv}"
SP=$(ls -d "$VENV"/lib/python*/site-packages)
SRC="$SP/sklearn/.dylibs/libomp.dylib"
[ -f "$SRC" ] || { echo "sklearn libomp not found at $SRC"; exit 1; }
for pair in "lightgbm/lib/lib_lightgbm.dylib" "xgboost/lib/libxgboost.dylib"; do
  LIB="$SP/$pair"; DIR=$(dirname "$LIB")
  cp "$SRC" "$DIR/libomp.dylib"
  install_name_tool -add_rpath @loader_path "$LIB" 2>/dev/null || true   # already present on re-run
  codesign --force --sign - "$LIB" >/dev/null 2>&1
  echo "patched $pair"
done
