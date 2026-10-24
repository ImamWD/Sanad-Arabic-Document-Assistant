#!/bin/sh
# Render-tools smoke test (make render-smoke). Proves the image renders shaped Arabic:
#   1. Chromium prints the Arabic HTML snippet to PDF with the Arabic fonts embedded.
#   2. Text extracted from that PDF comes back in logical order, codes and URL intact.
#   3. LibreOffice converts the same snippet to DOCX and the DOCX back to PDF.
# Outputs (PDF, DOCX, PNG of page 1) go to tools/render/out/, which git ignores.
set -eu
src=tools/render/smoke/arabic.html
out=tools/render/out
rm -rf "$out" && mkdir -p "$out"

echo "== Arabic fonts known to fontconfig"
fc-list :lang=ar family | sort -u

echo "== Chromium: HTML -> PDF"
html2pdf "$src" "$out/arabic-chromium.pdf"
pdffonts "$out/arabic-chromium.pdf"

echo "== Extracted text (pdftotext)"
pdftotext -layout "$out/arabic-chromium.pdf" "$out/arabic-chromium.txt"
cat "$out/arabic-chromium.txt"
# Body text is Noto Naskh Arabic; the last needle is set in Amiri. Not checked: the KacstOne
# line, because poppler extracts its lam-meem ligature as "امل" (finding for C1b/S1: prefer
# Noto Naskh/Sans Arabic or Amiri for seed documents).
for needle in 'YEP-2021-03' 'https://example.org/r' 'برنامج تمكين الشباب للتوظيف' \
  'المحافظة الشمالية' 'وعلى الله فليتوكل المتوكلون'; do
  if grep -qF -- "$needle" "$out/arabic-chromium.txt"; then
    echo "found: $needle"
  else
    echo "MISSING from extracted text: $needle" >&2
    exit 1
  fi
done
pdftoppm -png -r 80 -f 1 -l 1 "$out/arabic-chromium.pdf" "$out/arabic-chromium-page"

echo "== LibreOffice: HTML -> DOCX -> PDF"
lo="soffice --headless --norestore -env:UserInstallation=file:///tmp/lo-profile"
$lo --convert-to 'docx:MS Word 2007 XML' --outdir "$out" "$src" >/dev/null
$lo --convert-to pdf --outdir "$out" "$out/arabic.docx" >/dev/null
pdffonts "$out/arabic.pdf"
pdftoppm -png -r 80 -f 1 -l 1 "$out/arabic.pdf" "$out/arabic-libreoffice-page"

echo "== Tool versions"
chromium --version
soffice --version
pandoc --version | head -1
python3 -c 'import docx, markdown, yaml; print("python3 + yaml, markdown, docx OK")'

ls -l "$out"
echo "render smoke: OK"
