# Data Cleanliness Checker Web App — Project Planner

**Version:** 1.0 (based on chat conversation)  
**Date:** April 2026  
**Goal:** Build a simple, fast web app where users can upload CSV files (or a ZIP folder) **or browse Google Drive folders**, select any dataset, and instantly get a full **data cleanliness report** with quick cleaning options and downloadable cleaned files.

---

## 1. Project Overview

- **App Name:** Data Cleanliness Checker
- **Core Purpose:** Upload / browse → select CSV → analyze cleanliness (integrity + clarity) → view results → quick clean → download fixed file.
- **Target Users:** Data analysts, engineers, students, or anyone working with messy CSV data.
- **MVP Scope:** Local upload + Google Drive folder browser + cleanliness checks + quick clean + download.

---

## 2. Key Features

### Must-Have (MVP)
- **Data Sources**
  - Local upload: single CSV or ZIP (folder of CSVs)
  - Google Drive integration with **folder browsing**
    - Start at "My Drive"
    - Navigate subfolders
    - Back button + folder history
    - Display folders + CSV files only
    - One-click load selected CSV

- **Dataset Selection**
  - Dropdown of all loaded files (local + Drive)
  - Shows shape (rows × columns)

- **Cleanliness Analysis (Tabs)**
  1. **Overview** — rows, columns, missing %, duplicates, memory
  2. **Missing Values** — % total + bar chart per column
  3. **Duplicates** — count + preview of duplicate rows
  4. **Full Report** — ydata-profiling interactive HTML report

- **Quick Clean Actions**
  - Remove duplicates
  - Fill missing values (median for numeric, mode for others)
  - Download cleaned CSV

- **UI/UX**
  - Clean, wide layout with Streamlit
  - Sidebar for source selection
  - Real-time metrics with `st.metric`
  - Plotly charts
  - Session state persistence during session

### Nice-to-Have (Future)
- Excel / JSON / Parquet support
- Upload cleaned file back to current Google Drive folder
- Breadcrumbs navigation
- User accounts & report history
- Service account for production deployment

---

## 3. Tech Stack (Precise)

| Layer          | Technology                          | Version (Recommended) | Reason |
|----------------|-------------------------------------|-----------------------|--------|
| **Framework**  | **Streamlit**                       | 1.42+                 | Pure Python, fastest way to build interactive data apps |
| **Data**       | **Pandas**                          | 2.2+                  | Core data loading & cleaning |
| **Visualization** | **Plotly Express**               | Latest                | Interactive charts |
| **Profiling**  | **ydata-profiling**                 | Latest                | Beautiful automated HTML reports |
| **Google Drive** | **PyDrive2**                      | Latest                | OAuth + folder browsing + file download |
| **Auth**       | Google OAuth2 (`LocalWebserverAuth`) | -                     | Simple local development flow |
| **File Handling** | Python `zipfile`, `io`, `pathlib` | Built-in              | ZIP + in-memory CSV handling |
| **State**      | Streamlit Session State             | Built-in              | Folder history + loaded dataframes |

**No frontend framework needed** (Streamlit handles React under the hood).

---

## 4. Project Structure
