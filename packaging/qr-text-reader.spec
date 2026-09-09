Name:           qr-text-reader
Version:        0.1.0
Release:        1%{?dist}
Summary:        Scan an on-screen QR code and copy its raw text
License:        MIT
URL:            https://example.com/qr-text-reader
BuildArch:      noarch
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  python3-devel
BuildRequires:  python3dist(setuptools)
BuildRequires:  python3dist(wheel)

Requires:       python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       zbar
Requires:       python3dist(pyzbar)
Requires:       python3dist(pillow)
Requires:       xdg-desktop-portal
Requires:       xdg-desktop-portal-gnome

%description
QR Text Reader is a small, offline, secure GTK4/GNOME desktop tool.
It lets you select a QR code shown anywhere on screen, decodes it locally
(no network access, ever), and copies the raw decoded text to the
clipboard. If the QR code is an otpauth:// (2FA setup) URI, it additionally
shows the secret and issuer fields for convenience, without generating any
TOTP codes itself.

%prep
%autosetup -n %{name}-%{version}

%build
%py3_build

%install
%py3_install

mkdir -p %{buildroot}%{_datadir}/applications
install -m 0644 data/com.example.QRTextReader.desktop \
    %{buildroot}%{_datadir}/applications/com.example.QRTextReader.desktop

mkdir -p %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
install -m 0644 data/icons/com.example.QRTextReader.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/com.example.QRTextReader.svg

%files
%license LICENSE
%doc README.md
%{python3_sitelib}/qr_text_reader/
%{python3_sitelib}/qr_text_reader-*.dist-info/
%{_bindir}/qr-text-reader
%{_datadir}/applications/com.example.QRTextReader.desktop
%{_datadir}/icons/hicolor/scalable/apps/com.example.QRTextReader.svg

%changelog
* Wed Sep 09 2026 QR Text Reader contributors <noreply@example.com> - 0.1.0-1
- Initial package.
