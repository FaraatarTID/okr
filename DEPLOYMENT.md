# Deployment Guide

## ☁️ Streamlit Cloud Configuration

The application requires specific settings to run correctly on Streamlit Cloud.

### 1. Python Version (CRITICAL)

**Issue:** The default Python 3.13 environment is currently incompatible with the `google-generative-ai` library.
**Fix:** You must set the Python version to **3.11** or **3.10** in your app settings.

**Steps:**

1. Go to your App Dashboard on Streamlit Cloud.
2. Click the three dots (⋮) next to your app and select **Settings**.
3. Under **General**, find "Python version".
4. Select **3.11**.
5. Click **Save**. The app will reboot.

### 2. API Keys (Secrets)

Since `.env` files are not uploaded (for security), you must configure your API key in Streamlit Secrets.

**Steps:**

1. Go to **Settings** > **Secrets** in your App Dashboard.
2. Paste the following configuration:

```toml
GEMINI_API_KEY = "your-google-gemini-api-key-here"
```

3. Click **Save**.

### 3. Data Persistence

**Note:** The app currently uses a local `okr_data.json` file. unique to each running container.

- **Warning:** On Streamlit Cloud, your data will be **reset** when the app reboots or goes to sleep.
- **Recommendation:** specific to this MVP, download your data periodically if needed, or upgrade to a database solution later.
