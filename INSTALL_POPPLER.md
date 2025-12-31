# Installing Poppler for OCR CD Extraction

Poppler is required to convert PDF pages to images for OCR processing.

## Quick Install (Windows)

1. **Download Poppler:**
   - Go to: https://github.com/oschwartz10612/poppler-windows/releases
   - Download the latest release (e.g., `Release-XX.XX.X-X.zip`)
   - Extract the ZIP file to a location like `C:\poppler` or `C:\tools\poppler`

2. **Add to PATH (Option A - Recommended):**
   - Open System Properties → Environment Variables
   - Add to User PATH: `C:\poppler\Library\bin` (adjust path as needed)
   - Restart your terminal/PowerShell

3. **Set Environment Variable (Option B - Alternative):**
   - In PowerShell, run:
     ```powershell
     $env:POPPLER_PATH = "C:\poppler\Library\bin"
     ```
   - To make it permanent, add to User Environment Variables:
     - Variable: `POPPLER_PATH`
     - Value: `C:\poppler\Library\bin`

4. **Verify Installation:**
   ```powershell
   pdftoppm -v
   ```
   Should show version information.

## Test After Installation

Once Poppler is installed, test CD extraction:
```powershell
python test_cd_extraction.py
```

Or add CDs to ledger:
```powershell
python add_cds_to_ledger.py
```

