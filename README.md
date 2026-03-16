# Radio76

This package provides a minimal example of controlling an HF radio using **Hamlib** bindings and displaying real‑time information with the **Textual** UI framework.

**Prerequisites**
- Python 3.10 or newer
- A Hamlib‑compatible radio connected via COM7 (default)

**Installation**
```bash
pip install -e .
```

**Running**
```bash
python -m radio76.main
```

**Notes**
- Turn on FT 710
```
PS C:\Users\beckd\Desktop\hamlib-w32-4.6.5\bin> .\rigctl.exe -m 1049 -r COM7 -s 38400 -vv set_powerstat 1
```
- Turn off FT 710
```
PS C:\Users\beckd\Desktop\hamlib-w32-4.6.5\bin> .\rigctl.exe -m 1049 -r COM7 -s 38400 -vv set_powerstat 0
```
