# 🧹 Data Cleanliness Checker
# [LINK](https://datarate-asvfzjemivjbxuep9sjfsk.streamlit.app/)

A **Streamlit** web app for instantly auditing and cleaning CSV datasets — from local files or directly from **Google Drive**.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📂 Local Upload | Upload `.csv` or `.zip` files directly from your machine |
| 🌐 Google Drive | Browse Drive folders and load CSV files with one click |
| 🗂️ Dataset Overview | Row/column counts, data types, null %, memory usage |
| ❓ Missing Values | Visual bar chart + detailed missing-values table per column |
| 👥 Duplicates | Detect and preview duplicate rows |
| 📄 Full Report | Generate an interactive HTML report via `ydata-profiling` |
| ✨ Quick Clean | Remove duplicates & fill missing values, then download cleaned CSV |

---

## 🖥️ Screenshots

> Load a CSV → get instant data quality insights across 5 analysis tabs.

---

## 🚀 Getting Started

### Prerequisites

- Python **3.10+**
- A Google account (only needed for Drive integration)

---

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/DataRate.git
cd DataRate
```

---

### 2. Set Up Virtual Environment

```powershell
# Create a fresh venv (make sure NO other venv is active first)
python -m venv .venv

# Activate it (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate it (Windows CMD)
.venv\Scripts\activate.bat
```

> ⚠️ **Important:** Never create a `.venv` while another project's venv is already active — it will inherit the wrong Python path and break.

---

### 3. Install Dependencies

```powershell
.venv\Scripts\pip.exe install -r requirements.txt
```

Or after activating the venv:

```powershell
pip install -r requirements.txt
```

---

### 4. Run the App

```powershell
.venv\Scripts\streamlit.exe run app.py
```

Or after activating the venv:

```powershell
streamlit run app.py
```

The app will open at **http://localhost:8501** in your browser.

---

## 🌐 Google Drive Setup (Optional)

To enable the Google Drive browser, follow these one-time steps:

### Step 1 — Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Navigate to **APIs & Services → Library**
4. Search for and enable the **Google Drive API**

### Step 2 — Create OAuth 2.0 Credentials

1. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
2. Set **Application type** to **Desktop App**
3. On the **OAuth consent screen**, choose **User Data**
4. Add the scope: `https://www.googleapis.com/auth/drive.readonly`

### Step 3 — Download & Place Credentials

1. Download the `client_secrets.json` file
2. Place it in the **project root** (same folder as `app.py`)
3. Make sure the deployed environment also has access to that file; otherwise Google Drive login will fail with a missing-file error.

```
DataRate/
├── app.py
├── client_secrets.json   ← place here
├── requirements.txt
└── ...
```

### First Run (OAuth Consent)

On first launch, clicking **"Connect to Google Drive"** in the sidebar will:
- Open a browser window for OAuth consent
- Cache credentials to `mycreds.txt` for all future runs (no browser pop-up again)

---

## 📁 Project Structure

```
DataRate/
├── app.py                        # Main Streamlit application
├── requirements.txt              # Python dependencies
├── client_secrets.json           # Google OAuth credentials (not committed)
├── mycreds.txt                   # Cached OAuth token (auto-generated, not committed)
├── src/
│   ├── sources/
│   │   ├── local_source.py       # Local file upload handler
│   │   └── drive_source.py       # Google Drive browser & loader
│   └── ui/
│       └── dataset_selector.py   # Active dataset selector widget
```

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `streamlit >= 1.42` | Web UI framework |
| `pandas >= 2.2` | Data loading & analysis |
| `plotly >= 5.20` | Interactive charts |
| `ydata-profiling >= 4.9` | Full HTML profiling report |
| `pydrive2 >= 1.19` | Google Drive OAuth & file access |
| `google-auth >= 2.29` | Google authentication |
| `google-auth-oauthlib >= 1.2` | OAuth2 flow |
| `openpyxl >= 3.1` | Excel file support |

---

## 🔒 Security Notes

- `client_secrets.json` and `mycreds.txt` contain sensitive credentials — **do not commit them to Git**.
- Add them to your `.gitignore`:

```
client_secrets.json
mycreds.txt
```

---

## 🛠️ Troubleshooting

### `Fatal error in launcher: Unable to create process`
Your `.venv` was created while another project's venv was active. Fix:
```powershell
Remove-Item -Recurse -Force .venv
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
```

### `streamlit: command not found`
Use the full path to the venv's streamlit:
```powershell
.venv\Scripts\streamlit.exe run app.py
```

### Google Drive auth fails
- Make sure `client_secrets.json` is in the project root
- Ensure the **Google Drive API** is enabled in your Cloud project
- Check that your Google account is added as a test user in the OAuth consent screen
- If the error says `client_secrets.json is missing`, the app cannot find the OAuth file in the deployed or local working directory.

---

## 📄 License

MIT License — feel free to use and modify.
