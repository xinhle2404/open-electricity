# open-electricity

Fetches Australian National Electricity Market (NEM) data from the
[OpenElectricity API](https://openelectricity.org.au) using its Python SDK,
run on a schedule via GitHub Actions.

## Structure

```
.github/
  workflows/
    fetch-nem-data.yml   # runs src/fetch_nem_data.py hourly
src/
  fetch_nem_data.py      # fetches NEM power data and logs it
requirements.txt
.env                     # local secrets (gitignored)
```

## Prerequisites

- Python 3.12+
- An [OpenElectricity API key](https://openelectricity.org.au)

## Local setup

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Fill in `.env`:

   ```
   OPENELECTRICITY_API_KEY=your-openelectricity-api-key
   ```

3. Run the script:

   ```bash
   python src/fetch_nem_data.py
   ```

## GitHub Actions

The workflow at [.github/workflows/fetch-nem-data.yml](.github/workflows/fetch-nem-data.yml)
runs `src/fetch_nem_data.py` hourly (and on manual dispatch).

Add the API key as a repository secret so the workflow can read it:

```bash
gh secret set OPENELECTRICITY_API_KEY
```

(Settings > Secrets and variables > Actions > New repository secret, if not
using the `gh` CLI.)
