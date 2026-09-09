#!/usr/bin/env bash
# QR Text Reader — Fedora GNOME/Wayland installer.
#
# What this does:
#   1. Checks (and optionally installs, with your confirmation) the required
#      dnf system packages.
#   2. Builds a Python virtualenv with --system-site-packages under
#      ~/.local/share/qr-text-reader/venv (so it can see the system
#      PyGObject/GTK4 bindings, which pip cannot install on its own).
#   3. Installs this project into that venv.
#   4. Symlinks the launcher into ~/.local/bin so `qr-text-reader` works
#      from any terminal (as long as ~/.local/bin is on your PATH, which is
#      the Fedora/GNOME default).
#   5. Installs the .desktop entry and app icon so it shows up in the
#      GNOME Activities/App Grid.
#
# This script only touches your user's home directory (~/.local, ~/.config)
# except for the optional `sudo dnf install` step, which it asks about
# explicitly before running.
#
# Safe to re-run: it's idempotent.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/qr-text-reader"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
DESKTOP_FILE_NAME="com.example.QRTextReader.desktop"
ICON_FILE_NAME="com.example.QRTextReader.svg"

REQUIRED_DNF_PACKAGES=(
    python3
    python3-pip
    python3-gobject
    gtk4
    libadwaita
    zbar
    xdg-desktop-portal
    xdg-desktop-portal-gnome
)

echo "== QR Text Reader — Fedora kurulumu =="
echo "Proje dizini: $PROJECT_DIR"
echo

# ---------------------------------------------------------------------------
# 1. System dependencies
# ---------------------------------------------------------------------------
echo "-> Sistem bağımlılıkları kontrol ediliyor..."
missing_packages=()
for pkg in "${REQUIRED_DNF_PACKAGES[@]}"; do
    if ! rpm -q "$pkg" >/dev/null 2>&1; then
        missing_packages+=("$pkg")
    fi
done

if [ "${#missing_packages[@]}" -gt 0 ]; then
    echo "   Eksik paketler: ${missing_packages[*]}"
    read -r -p "   'sudo dnf install -y ${missing_packages[*]}' çalıştırılsın mı? [E/h] " answer
    answer="${answer:-E}"
    if [[ "$answer" =~ ^([eEyY])$ ]]; then
        sudo dnf install -y "${missing_packages[@]}"
    else
        echo "   Uyarı: eksik paketlerle kurulum devam ediyor, uygulama çalışmayabilir."
    fi
else
    echo "   Tüm sistem paketleri zaten kurulu."
fi
echo

# ---------------------------------------------------------------------------
# 2. Virtualenv with access to system GTK4/PyGObject bindings
# ---------------------------------------------------------------------------
echo "-> Sanal ortam hazırlanıyor: $VENV_DIR"
mkdir -p "$INSTALL_DIR"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv --system-site-packages "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet

echo "-> Uygulama kuruluyor..."
pip install "$PROJECT_DIR" --quiet
deactivate
echo

# ---------------------------------------------------------------------------
# 3. Launcher on PATH
# ---------------------------------------------------------------------------
echo "-> Komut satırı launcher'ı bağlanıyor: $BIN_DIR/qr-text-reader"
mkdir -p "$BIN_DIR"
ln -sf "$VENV_DIR/bin/qr-text-reader" "$BIN_DIR/qr-text-reader"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "   UYARI: $BIN_DIR PATH içinde görünmüyor."
    echo "   Şunu ~/.bashrc dosyanıza ekleyip terminali yeniden başlatın:"
    echo "     export PATH=\"$BIN_DIR:\$PATH\""
fi
echo

# ---------------------------------------------------------------------------
# 4. Desktop entry + icon
# ---------------------------------------------------------------------------
echo "-> Masaüstü entegrasyonu kuruluyor..."
mkdir -p "$APPS_DIR" "$ICON_DIR"

sed "s|^Exec=.*|Exec=$BIN_DIR/qr-text-reader|" \
    "$PROJECT_DIR/data/$DESKTOP_FILE_NAME" > "$APPS_DIR/$DESKTOP_FILE_NAME"

cp "$PROJECT_DIR/data/icons/$ICON_FILE_NAME" "$ICON_DIR/$ICON_FILE_NAME"

command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -f "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" >/dev/null 2>&1 || true

echo
echo "== Kurulum tamamlandı =="
echo "GNOME uygulama menüsünde 'QR Text Reader' olarak görünecek."
echo "Terminalden çalıştırmak için (yeni bir terminal açıp): qr-text-reader"
echo "Kaldırmak için: ./uninstall.sh"
