# OKR Tracker 🚀

A high-performance Streamlit application for managing Objectives and Key Results (OKRs), featuring multi-user support, specialized roles, and AI-driven strategic analysis.

## 🌟 Key Features

- **Multi-User & Role-Based Access**: Secure authentication with `bcrypt` support.
  - **Admin**: Full system control, user management, and aggregated "God View" of all OKRs.
  - **Manager**: Team-level visibility and strategic planning for direct reports.
  - **Member**: Execution-focused with task management and personal time tracking.
- **Simplified 4-Level Hierarchy**:
  - `Goal` (with ♟️ Strategy Tags) → `Objective` → `Key Result` (with ⚡ Initiative Tags) → `Task` (with ⏱️ Timer)
- **Visual Intelligence**:
  - **🗺️ Interactive Mind Map**: Dynamic tree visualization of the entire OKR hierarchy using `streamlit-agraph`.
  - **📊 Strategic Dashboards**: High-level heatmaps, confidence trends, and progress metrics.
- **Accountability & Tracking**:
  - **✍️ Creator Tags**: Automated tracking and display of who created every item.
  - **👤 Owner Tags**: Dedicated responsibility assignment for top-level goals.
- **AI Strategic Analysis**: Integration with Google Gemini for critical gap analysis, performance scoring, and automated task proposals.
- **Global Readiness**: Full support for **RTL (Right-to-Left)** layouts and Persian typography via the **Vazirmatn** font.
- **Professional Reporting**: Generate formatted Daily and Weekly work reports with one-click **PDF Export**.

## 🛠️ Installation & Prerequisites

1.  **Clone the Repo**:

    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Install System Dependencies**:

    - **wkhtmltopdf**: Required for PDF generation. [Download here](https://wkhtmltopdf.org/downloads.html) and ensure it's in your system PATH.

3.  **Install Python Dependencies**:

    ```bash
    pip install -r streamlit_app/requirements.txt
    ```

4.  **Configure Secrets**:
    Create `.streamlit/secrets.toml` and add your `GEMINI_API_KEY`.

5.  **Run the Application**:
    ```bash
    streamlit run streamlit_app/app.py
    ```
    _Default credentials: `admin` / `admin`._

## 🔒 Permission & Ownership Model

| Feature                       | Admin | Manager | Member |
| :---------------------------- | :---: | :-----: | :----: |
| **Manage Users & Cycles**     |  ✅   |   ❌    |   ❌   |
| **Cross-Team Visibility**     |  ✅   |   ❌    |   ❌   |
| **Team Performance View**     |  ✅   |   ✅    |   ❌   |
| **Define Strategy (Goal/KR)** |  ✅   |   ✅    |   ❌   |
| **Create Tasks**              |  ✅   |   ✅    |   ✅   |
| **Time Tracking / Timer**     |  ❌   |   ❌    |   ✅   |

> [!IMPORTANT] > **Edit/Delete Rights**: To maintain data integrity, only the **Owner** (creator) of an item can modify its title, description, or delete it. Admins and Managers have read-only access to member OKRs.

## 📂 Architecture & Data

- **Frontend**: Streamlit + Vanilla CSS + Google Fonts (Vazirmatn).
- **Security**: Password hashing via `bcrypt`.
- **Database**: SQLModel (SQLite) for user entities and cycle metadata.
- **Storage**: User-specific JSON files with optional **Google Sheets Cloud Sync** for enterprise-grade persistence.
- **Intelligence**: Google Gemini AI (Pro/Flash) for strategic evaluation.

---

_Built for excellence in strategic alignment and execution tracking._
