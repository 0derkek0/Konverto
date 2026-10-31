# Konverto im Microsoft Store veröffentlichen

Das Paket wird als **MSIX** hochgeladen. Microsoft signiert es beim Einreichen selbst, du brauchst also
**kein eigenes Code-Signing-Zertifikat**.

## 1. Partner-Center-Konto

1. Auf <https://partner.microsoft.com/dashboard> mit deinem Microsoft-Konto anmelden.
2. Als **Einzelentwickler** (Individual) registrieren. Die aktuellen Bedingungen und Kosten zeigt Partner Center bei der Anmeldung an.

## 2. App-Namen reservieren

**Apps und Spiele → Neues Produkt → MSIX- oder PWA-App** und den Namen **Konverto** reservieren.
Ist der Name schon vergeben, nimm z. B. „Konverto – Datei-Konverter“. Den Namen dann auch in
`packaging/store_config.json` bei `display_name` eintragen.

## 3. Produktidentität eintragen

In Partner Center: **Produktverwaltung → Produktidentität**. Dort stehen drei Werte. Diese kopierst du in
`packaging/store_config.json`:

| Partner Center | store_config.json |
|---|---|
| `Package/Identity/Name` (z. B. `12345DerKeK.Konverto`) | `identity_name` |
| `Package/Identity/Publisher` (z. B. `CN=A1B2C3D4-…`) | `publisher` |
| `Package/Properties/PublisherDisplayName` (z. B. `DerKeK`) | `publisher_display_name` |

Die Werte müssen exakt stimmen, sonst lehnt der Upload das Paket ab.

## 4. Paket bauen

Doppelklick auf **`build_store.bat`** erzeugt `dist\Konverto_1.0.0.0_x64.msix`.

Für jedes Update in `konverto/__init__.py` die `APP_VERSION` erhöhen (z. B. `1.0.1`) und neu bauen.
Der Store akzeptiert keine Version, die gleich hoch oder niedriger als die vorherige ist.

### Lokal testen (optional)

Bei aktiviertem Entwicklermodus in Windows:

```powershell
Add-AppxPackage -Register "$env:TEMP\konverto_build\msix_layout\AppxManifest.xml"
```

Danach steht Konverto im Startmenü. Zum Entfernen:
`Get-AppxPackage *Konverto* | Remove-AppxPackage`

Für eine Prüfung wie im Store-Review: **Windows App Certification Kit** (im Windows SDK enthalten,
Startmenü → „Windows App Cert Kit“, braucht Admin-Rechte) und dort die `.msix` prüfen.

## 5. Einreichung ausfüllen

**Preise und Verfügbarkeit:** Kostenlos (oder Preis nach Wahl), Märkte z. B. alle.

**Eigenschaften:**
- Kategorie: *Hilfsprogramme & Tools* (Utilities & tools)
- Datenschutzerklärung: Konverto sammelt keine Daten und geht nicht ins Internet. Eine URL ist dann meist
  nicht Pflicht. Hast du eine eigene Seite (z. B. GitHub), kannst du den Text unten dort hinstellen.

**Altersfreigabe:** Fragebogen ausfüllen. Keine Gewalt, kein Chat, kein Online-Inhalt, also ergibt sich „3+“.

**Pakete:** die `.msix` aus `dist\` hochladen.

**Einreichungsoptionen → Eingeschränkte Funktionen:** Partner Center fragt nach einer Begründung für `runFullTrust`:

> Konverto ist eine klassische Win32-Desktopanwendung (Python/Qt), die als MSIX verpackt ist. runFullTrust wird
> benötigt, um die App als Desktop-Prozess zu starten und Dateien, die der Nutzer auswählt, lokal mit FFmpeg
> umzuwandeln. Die App greift nicht auf das Netzwerk zu.

**Store-Eintrag (Deutsch):**

- **Beschreibung:**

  > Konverto wandelt Dateien direkt auf deinem PC um, ohne Upload und ohne Konto.
  >
  > Einfach Dateien oder ganze Ordner ins Fenster ziehen, Zielformat wählen, fertig. Es werden nur die
  > Einstellungen angezeigt, die zu deinen Dateien passen.
  >
  > • Video: MP4, MKV, MOV, AVI, WEBM, GIF – oder nur den Ton als MP3 speichern
  > • Audio: MP3, WAV, FLAC, AAC, M4A, OGG, OPUS, WMA
  > • Bilder: JPG, PNG, WEBP, AVIF, HEIC (iPhone), BMP, TIFF, ICO, GIF
  > • PDF: Seiten als Bilder, Text, Word – oder mehrere Bilder/Dokumente zu einer PDF zusammenfügen
  > • Dokumente: Word, Markdown, Text und HTML zu PDF
  > • Tabellen: CSV, Excel (XLSX) und JSON untereinander
  >
  > Viele Dateien gleichzeitig, Qualität und Größe einstellbar, Ausgabe neben dem Original oder in einem
  > eigenen Ordner.

- **Kurzbeschreibung:** Video, Audio, Bilder, PDFs und Dokumente lokal umwandeln – schnell und ohne Upload.
- **Features (je eine Zeile):** Drag & Drop für Dateien und Ordner · Über 40 Formate · Video zu MP3 ·
  HEIC zu JPG · Bilder zu PDF zusammenfügen · Arbeitet komplett offline
- **Screenshots:** die vier Bilder aus `packaging/store_screenshots/` (1366×768)
- **Suchbegriffe:** konverter, mp4 zu mp3, png zu jpg, pdf, heic, video konvertieren, audio

### Datenschutzerklärung (Vorlage)

> Konverto verarbeitet alle Dateien ausschließlich lokal auf deinem Gerät. Die App sammelt keine
> personenbezogenen Daten, sendet keine Daten an Server und enthält keine Werbung oder Tracking.

## 6. Lizenzen

Konverto ist Open Source unter der **AGPL-3.0**. Der Quellcode liegt auf
<https://github.com/0derkek0/Konverto>. Das ist nötig, weil PyMuPDF (AGPL-3.0) und FFmpeg (GPL-3.0)
mitgeliefert werden. Die App verlinkt den Quellcode unten rechts („Quellcode“) und zeigt die Lizenzen an.

Im Store-Eintrag zusätzlich angeben:

- **Website / Support-Kontakt:** `https://github.com/0derkek0/Konverto` (Support z. B. über GitHub Issues)
- Am Ende der Beschreibung: *„Konverto ist Open Source (AGPL-3.0): github.com/0derkek0/Konverto“*

Bei jedem Store-Update auch den passenden Code auf GitHub pushen, damit Quellcode und App zusammenpassen.
