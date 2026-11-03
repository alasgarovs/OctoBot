# OctoBot - WhatsApp Automation Made Easy

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green.svg)
![neonize](https://img.shields.io/badge/WhatsApp-neonize-teal.svg)
![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)

</div>

## ✨ What is OctoBot?

OctoBot is a **WhatsApp messaging automation tool** with a clean, modern desktop interface, built with Python and PyQt6. It connects directly to WhatsApp through the [neonize](https://github.com/krypton-byte/neonize) websocket protocol — no browser, no Selenium, no WhatsApp Web UIAutomation. Send personalized bulk messages to your contacts straight from your Excel spreadsheets.

### 🎯 Key Features

* 📊 **Excel Integration** - Import contacts and export results from/to Excel files
* 🤖 **Bulk Messaging** - Send campaigns with delivery stats and automatic retries
* 📝 **Message Templates** - Save multiple templates; exactly one active at a time
* 🖥️ **Native Windows Executable** - No Python required: download, extract, run
* 📶 **QR Pairing** - Link a device like you would in WhatsApp, then it just works
* ✅ **Number Validation** - Check whether numbers are on WhatsApp before sending
* 🎨 **Modern GUI** - Clean, intuitive interface built with PyQt6
* 🌍 **Multi-language Support** - Available in English, Russian, and Azerbaijani

## 📸 Preview

<div align="center">   <img width="600" height="400" alt="OctoBot Interface" src="https://github.com/user-attachments/assets/8871f01c-2e00-4418-ba37-c6756fbb133b" /> </div>

## 🚀 Getting Started

### For End Users

Download the latest build from the [releases page](https://github.com/alasgarovs/OctoBot/releases), extract the zip, and run `OctoBot.exe`. That's it — no Python installation needed.

### For Developers

```console
# Clone the repository
git clone https://github.com/alasgarovs/OctoBot.git
cd OctoBot

# Create a virtual environment and install dependencies
python -m venv .venv
.venv/bin/pip install -r requirements.txt    # Windows: .venv\Scripts\pip

# Launch the application
.venv/bin/python src/app.py                  # Windows: .venv\Scripts\python
```

## 📦 Building the Executable

The executable must be built **on Windows** (PyInstaller cannot cross-compile):

```console
pip install -r requirements.txt
pyinstaller --noconfirm --clean --upx-dir="C:\Tools\upx-5.3.0-win64" OctoBot.spec
# -> dist\OctoBot\OctoBot.exe   (onedir build)
```

## 🛠️ Development Commands

```console
# Update translation files with new strings
make update-translations

# Compile all translation files (.ts → .qm)
make compile-translations

# Regenerate icons/favicon.ico from the in-app logo
make favicon
```

## 🌐 Language Support

OctoBot speaks your language:

| Language         | Status   | Code     |
| ------------------ | ---------- | ---------- |
| 🇬🇧 English     | Default  | `en` |
| 🇷🇺 Russian     | Complete | `ru` |
| 🇦🇿 Azerbaijani | Complete | `az` |

## 🤝 Contributing

Contributions are welcome! Feel free to:

* 🐛 Report bugs
* 💡 Suggest new features
* 🔧 Submit pull requests
* 📖 Improve documentation

## ⚠️ Disclaimer

OctoBot connects over an **unofficial WhatsApp protocol** — aggressive or unsolicited messaging can get the linked account banned. This tool is intended for legitimate communication purposes only. Please ensure you:

* Have consent from recipients before sending messages
* Comply with WhatsApp's Terms of Service
* Follow local regulations regarding automated messaging
* Use responsibly and ethically — you are responsible for your account

## 📝 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](https://github.com/alasgarovs/OctoBot/blob/main/LICENSE) file for details.

---

<div align="center">

⭐ Star us on GitHub if you find this project helpful!

</div>
