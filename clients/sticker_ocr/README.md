# 💽 Sticker OCR — Disk Sanitization Assistant

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg)](https://microsoft.com/windows)
[![Release](https://img.shields.io/badge/Release-v1.0.1-green.svg)](https://github.com/Ratthabhumi/Sticker_OCR/releases/tag/v1.0.1)
[![OCR Engine](https://img.shields.io/badge/OCR-RapidOCR%20(ONNX)-orange.svg)](https://github.com/RapidAI/RapidOCR)

**Disk Sanitization Assistant** is a desktop application designed to streamline the laptop disk sanitization workflow. It monitors sticker photos of laptop units, automatically extracts the **Serial Number (S/N)** and **Device ID (ID No.)** using **RapidOCR (ONNX Runtime)**, and creates the required destination folder structure `USB:\<SN>(<ID>)\Picture\` on targeted USB drives.

---

## ✨ Key Features

- ⚡ **High-Speed ONNX OCR Engine:** Utilizes RapidOCR for fast, accurate text recognition without external C++ or Heavy AI framework dependencies.
- 💾 **Smart USB Drive Detection & Manual Override:** Automatically detects connected USB Flash Drives and External HDDs, with a live header dropdown selector for manual drive selection when multiple USB devices are connected.
- 🖼️ **Interactive Preview & High-Res Zoom:** Displays an enlarged preview dialog (`860x540`) with full-screen zoom capabilities (`F11` / Double-click) for HD image verification.
- 🧹 **Real-Time Input Sanitization:** Automatically strips illegal OS path characters (`\ / : * ? " < > |`) from S/N and ID inputs in real time to prevent folder creation errors.
- 🔒 **File Lock Race Condition Recovery:** Implements retry loops for image files saved directly from external apps (e.g. LINE PC), featuring a copy-fallback mechanism.
- 🛡️ **Disk Free Space Safety Check:** Verifies available disk space on the target USB drive before initiating folder creation to avoid disk-full errors.
- 📊 **CSV Audit Logging:** Automatically logs daily operational history into CSV audit files located in `Logs/`.
- 🖥️ **Large Display Mode (F11):** High-contrast, large-font fullscreen view for technicians to inspect S/N and ID from a distance.

---

## 📸 Workflow

```mermaid
graph TD
    A["Insert USB Drive"] --> B["Drop sticker image into Sticker/ folder"]
    B --> C["RapidOCR extracts S/N and Device ID"]
    C --> D["Preview Dialog opens for verification"]
    D -->|Click Confirm| E["Create folder USB:\SN(ID)\Picture\"]
    E --> F["Move image to Sticker/Processed/"]
    D -->|Click Skip| G["Move image to Sticker/Failed/"]
```

---

## 🚀 Download & Usage (.exe)

No Python installation required. Download the pre-built standalone package:

1. Download **`FolderCreator.zip`** from [GitHub Releases v1.0.1](https://github.com/Ratthabhumi/Sticker_OCR/releases/tag/v1.0.1).
2. Extract `FolderCreator.zip`.
3. Launch **`FolderCreator.exe`** to start the application.

---

## ⌨️ Shortcut Keys

| Key | Action |
|-----|--------|
| **F11** | Toggle Large Display Mode |
| **ESC** | Close Zoom Dialog / Exit Large Display Mode |

---

## 🛠️ Developer Setup

### Prerequisites
- Windows 10 / 11
- Python 3.10+

### Installation & Execution

```powershell
# Clone repository
git clone https://github.com/Ratthabhumi/Sticker_OCR.git
cd Sticker_OCR

# Setup virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run application
python main.py
```

### Build Executable

```powershell
.\build.bat
```

---

## 📁 Project Structure

```
Sticker_OCR/
├── main.py                   # Main Application Entry Point
├── build.bat                 # Automated PyInstaller & PyArmor Build Script
├── config.json               # Application Configuration
├── requirements.txt          # Dependencies
├── app/
│   ├── config.py             # Configuration Manager
│   ├── constants.py          # App Constants & UI Colors
│   ├── models/               # Data Models (Job, OCRResult, FolderResult)
│   ├── services/             # Core Services (OCR Engine, USB Monitor, File Watcher, Validator)
│   ├── viewmodels/           # MVVM ViewModel State & Logic
│   └── views/                # UI Components (Main Window, Dashboard, History, Settings, Zoom Dialog)
├── Sticker/                  # Input Directory for Images
│   ├── Processed/            # Processed Images
│   └── Failed/               # Failed / Skipped Images
└── Logs/                     # Daily Audit Logs
```

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.
