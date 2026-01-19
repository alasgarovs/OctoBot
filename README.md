# OctoBot - WhatsApp Bot

<div align="center">
  <img src="icons/octopus.png" alt="Logo" width="200"/>
</div>

## Overview

This project is a **WhatsApp Messaging Bot** developed using **Python**, **PyQt6** and **Selenium**. The bot is designed to extract phone numbers from Excel file and send automated messages to each contact via WhatsApp Web.

## Demo

<img width="600" height="400" alt="screenshot-01" src="https://github.com/user-attachments/assets/8871f01c-2e00-4418-ba37-c6756fbb133b" />

## Installation

### For end users

- Just download pre-built packages (coming soon)

### For developers

```console
# Clone the repository
git clone https://github.com/alasgarovs/OctoBot.git
cd OctoBot

# Install requirements
pip install -r requirements.txt

# Run app.py
python src/app.py

# Update all .ts files with new/changed strings from app.py
make update-translations

# Compile all .ts → .qm
make compile-translations

# Clean compiled .qm files
make clean
```

## Languages

OctoBot supports multiple interface languages:

- 🇬🇧 **English** - default
- 🇷🇺 **Russian** - full translation
- 🇦🇿 **Azerbaijani** - full translation

### Project status update

We are continuously working on building and enhancing features to improve functionality and user experience.
