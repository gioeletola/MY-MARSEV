#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# SOVEREIGN AI OS — Local App Build Script
# Packages the CLI + web server into a portable dist/sovereign/ directory.
#
# Usage:
#   ./scripts/build_local.sh            # standard build
#   ./scripts/build_local.sh --onefile  # single executable (slower start)
#   ./scripts/build_local.sh --clean    # wipe build/ dist/ before build
#
# Requirements:
#   pip install pyinstaller
#   pip install -e ".[dev]"
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ── Parse args ────────────────────────────────────────────────────────────────
ONEFILE=false
CLEAN=false
for arg in "$@"; do
    case "$arg" in
        --onefile) ONEFILE=true ;;
        --clean) CLEAN=true ;;
        *) echo "Unknown arg: $arg" && exit 1 ;;
    esac
done

echo "════════════════════════════════════════"
echo " SOVEREIGN AI OS — Build Script"
echo "════════════════════════════════════════"
echo "Project root: $PROJECT_ROOT"
echo "One-file:     $ONEFILE"
echo "Clean build:  $CLEAN"
echo ""

# ── Clean ─────────────────────────────────────────────────────────────────────
if $CLEAN; then
    echo "[1/5] Cleaning build artifacts..."
    rm -rf build/ dist/
    echo "      ✓ Cleaned"
fi

# ── Dependency check ──────────────────────────────────────────────────────────
echo "[1/5] Checking dependencies..."
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "      Installing PyInstaller..."
    pip install pyinstaller --quiet
fi
echo "      ✓ PyInstaller ready"

# ── Run smoke test ────────────────────────────────────────────────────────────
echo "[2/5] Running smoke test (import check)..."
python -c "import sovereign; print(f'      ✓ sovereign {sovereign.__version__} importable')"

# ── Build ─────────────────────────────────────────────────────────────────────
echo "[3/5] Building with PyInstaller..."
if $ONEFILE; then
    pyinstaller \
        --onefile \
        --name sovereign-cli \
        --hidden-import anthropic \
        --hidden-import fastapi \
        --hidden-import uvicorn \
        --hidden-import structlog \
        --collect-data sovereign \
        --add-data "config:config" \
        --add-data "prompts:prompts" \
        --add-data "sovereign/api/templates:sovereign/api/templates" \
        --add-data "sovereign/skills/data:sovereign/skills/data" \
        main.py
    echo "      ✓ Built: dist/sovereign-cli"
else
    pyinstaller sovereign.spec --clean --noconfirm
    echo "      ✓ Built: dist/sovereign/"
fi

# ── Bundle env example ────────────────────────────────────────────────────────
echo "[4/5] Bundling configuration..."
DIST_DIR="dist/sovereign"
if $ONEFILE; then
    DIST_DIR="dist"
fi

cp .env.example "$DIST_DIR/.env.example" 2>/dev/null || true
mkdir -p "$DIST_DIR/data/memory" "$DIST_DIR/data/ledger"

cat > "$DIST_DIR/START.sh" << 'STARTEOF'
#!/usr/bin/env bash
# Quick-start script for SOVEREIGN AI OS local build
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$DIR/.env" ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo " First run: copy .env.example to .env"
    echo " and set your ANTHROPIC_API_KEY"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    cp "$DIR/.env.example" "$DIR/.env"
    echo "Created .env — edit it before continuing."
    exit 1
fi

export $(grep -v '^#' "$DIR/.env" | xargs)
echo "Starting SOVEREIGN AI OS..."
exec "$DIR/sovereign" "$@"
STARTEOF
chmod +x "$DIST_DIR/START.sh"

echo "      ✓ Config bundle ready"

# ── Summary ───────────────────────────────────────────────────────────────────
echo "[5/5] Build complete!"
echo ""
echo "════════════════════════════════════════"
echo " Output: $DIST_DIR/"
echo ""
echo " Run CLI:    $DIST_DIR/sovereign demo"
echo " Run UI:     $DIST_DIR/sovereign serve --port 8080"
echo " Quick start: $DIST_DIR/START.sh"
echo "════════════════════════════════════════"
