# OKR Tracker

A comprehensive Streamlit application for managing Objectives and Key Results (OKRs), tracking time, and leveraging AI for strategic analysis.

## 🚀 Features

- **Hierarchical OKR Management**: Structure your work from top-level Goals down to actionable Tasks.
  - _Hierarchy_: Goal 🏁 → Strategy ♟️ → Objective 🎯 → Key Result 📊 → Initiative ⚡ → Task 📋
- **Interactive Visualization**: Explore your OKR structure using an interactive Mind Map.
- **Time Tracking**: Built-in focus timer for tasks with work logging and summary reporting.
- **AI Strategic Analysis**: Integrated with Google Gemini AI to analyze Key Results, scoring them on Efficiency and Effectiveness, and proposing missing tasks.
- **Reporting**: Generate Daily and Weekly work reports with PDF export functionality.
- **Cloud Sync**: Optional synchronization with Google Sheets for data persistence across sessions.
- **RTL Support**: Full support for Right-to-Left languages and layouts.

## 🛠️ Installation

1.  **Clone the repository**:

    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Install Dependencies**:
    Ensure you have Python installed (3.10+ recommended).
    ```bash
    pip install -r streamlit_app/requirements.txt
    ```
    _Note: `pdfkit` may require `wkhtmltopdf` to be installed on your system for PDF generation._

## ⚙️ Configuration

This application uses Streamlit secrets for configuration. Create a file at `.streamlit/secrets.toml` in the project root.

### 1. Gemini AI (Required for AI Analysis)

```toml
GEMINI_API_KEY = "your_google_gemini_api_key"
```

### 2. Google Sheets Sync (Optional)

To enable cloud sync, you need a Google Service Account.

```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "..."
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

## ▶️ Running the App

Run the application using Streamlit:

```bash
streamlit run streamlit_app/app.py
```

## 📖 User Guide

### Navigation

- **Home Dashboard**: View your root Goals.
- **Drill Down**: Click on any item to view its children. Use the "Navigation" pills at the top to jump back to higher levels.
- **Mind Map**: Click the "🗺️ Mind Map" button to visualize the entire tree structure starting from the current node.

### Managing Items

- **Add Item**: Use the "Add [Type]" button to create new items.
- **Inspector**: Click the "Inspect / Edit" button on any item to:
  - Rename or change description.
  - Update progress manually (for leaf nodes).
  - **Track Time**: For Tasks, start/stop the timer or view work history.
  - **Run AI Analysis**: For Key Results, trigger a Gemini analysis to get feedback and task suggestions.

### Reporting

- Click "📊 Reports" in the sidebar (or main menu) to access the reporting dialog.
- Select "Daily" or "Weekly" views.
- Export the data to formatted PDF reports.

## 📂 Data Storage

- **Local Mode**: Data is saved to `okr_data.json` (or user-specific json files) in the `streamlit_app` directory by default.
- **Cloud Mode**: If Google Sheets credentials are configured, data will verify and sync with the connected Google Sheet.
