#!/usr/bin/env bash
# QR Text Reader — uninstaller. Removes everything install.sh created.
# Does NOT touch system dnf packages (those are shared with the rest of
# your system and not safe to remove automatically).

set -euo pipefail

INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/qr-text-reader"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/qr-text-reader"

echo "== QR Text Reader — kaldırma =="

rm -f "$BIN_DIR/qr-text-reader"
rm -f "$APPS_DIR/com.example.QRTextReader.desktop"
rm -f "$ICON_DIR/com.example.QRTextReader.svg"
rm -rf "$INSTALL_DIR"

read -r -p "Ayarlar dosyası da silinsin mi? ($CONFIG_DIR) [e/H] " answer
answer="${answer:-H}"
if [[ "$answer" =~ ^([eEyY])$ ]]; then
    rm -rf "$CONFIG_DIR"
fi

command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -f "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" >/dev/null 2>&1 || true

echo "Kaldırıldı."
