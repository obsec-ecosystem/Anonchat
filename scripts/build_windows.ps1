$ErrorActionPreference = "Stop"

pyinstaller --noconfirm --clean --onefile --name anonchat `
  --add-data "anonchat/ui/templates;anonchat/ui/templates" `
  --add-data "anonchat/ui/static;anonchat/ui/static" `
  main.py
