# Repository Map

Canonical repo root:

```text
/Users/jakenaor/Documents/Coding Stuff/Space/Exoplanet-Transit-Finder
```

## Directory Tree

```text
.
├── .git/
├── Exoplaned data parsing tool/
│   ├── main.py
│   └── requirements.txt
├── LICENSE
└── docs/
    ├── README.md
    ├── CURRENT_STATE.md
    └── REPO_MAP.md
```

## Tracked Contents

- `Exoplaned data parsing tool/main.py`
  - Single-file localhost web app.
  - Serves the HTML/CSS/JavaScript UI with Python `http.server`.
  - Parses uploaded CSVs with `Time`/`Flux` columns.
  - Detects transit candidates, estimates period, computes chi-squared p-values, plots views, supports manual box edits, detection controls, and exports.

- `Exoplaned data parsing tool/requirements.txt`
  - Python dependencies: `numpy`, `scipy`, `astropy`.

- `LICENSE`
  - Repository license.

- `docs/README.md`
  - Canonical documentation index.

- `docs/CURRENT_STATE.md`
  - Narrative state and implementation notes for future sessions.

- `docs/REPO_MAP.md`
  - This file. Canonical filesystem map.

## Runtime

From the app directory:

```bash
cd "/Users/jakenaor/Documents/Coding Stuff/Space/Exoplanet-Transit-Finder/Exoplaned data parsing tool"
python3 main.py
```

Default URL:

```text
http://127.0.0.1:8000
```

The server tries ports `8000` through `8010` if the default port is occupied.
