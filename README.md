# Expense Tracker Lite 💰

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)
![Chart.js](https://img.shields.io/badge/Chart.js-FF6384?style=for-the-badge&logo=chartdotjs&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)

A modern, responsive personal finance and expense tracking web application featuring interactive charts, monthly budget monitoring, recurring expense automation, savings goals, and report exports.

<!-- Once deployed, replace the link below with your live URL -->
**[🌐 Live Demo](https://github.com/GarimaVerma45/EXPENSE-TRACKER)** • **[Report Bug](https://github.com/GarimaVerma45/EXPENSE-TRACKER/issues)** • **[Request Feature](https://github.com/GarimaVerma45/EXPENSE-TRACKER/issues)**

</div>

---

## ✨ Features

- 📊 **Interactive Analytics Dashboard**:
  - Breakdown by category with toggleable chart types: **Donut**, **Pie**, and **Polar Area**.
  - Daily spending trends with toggleable **Bar** and **Line** charts.
  - Interactive slice filtering with one-click filter toggle and persistent chart type preferences.
- 🎯 **Monthly Budget Tracking**:
  - Set monthly spending budgets with real-time visual progress bars, over-budget warnings, and daily allowance calculators.
- 🔄 **Recurring Expenses**:
  - Automatically track recurring bills, subscriptions, and regular monthly payments.
- 🏆 **Savings Goals**:
  - Create financial goals with target deadlines, visual progress percentages, deposit logs, and completion milestones.
- 📑 **Export Reports**:
  - Export filtered expense logs directly as **CSV** or professional styled **PDF** summaries (powered by ReportLab).
- 🔐 **User Authentication & Security**:
  - Multi-user authentication powered by Flask-Login and secure password hashing (`werkzeug.security`).
  - Account profile management and password recovery via customizable security questions.
- 🌓 **Modern Dark / Light Theme**:
  - Sleek modern UI built with Tailwind CSS, supporting dark and light modes with seamless local storage persistence.

---

## 🛠️ Tech Stack

- **Backend**: Python 3, Flask, Flask-SQLAlchemy, Flask-Login, ReportLab
- **Database**: SQLite (SQLAlchemy ORM)
- **Frontend**: HTML5, Tailwind CSS, Vanilla JavaScript
- **Charts**: Chart.js 4.x
- **Production Server**: Gunicorn

---

## 📁 Project Structure

```text
EXPENSE-TRACKER/
├── app.py                  # Core Flask app, models, API endpoints & business logic
├── requirements.txt        # Python dependencies
├── Procfile                # Gunicorn deployment config for cloud hosts
├── .gitignore              # Files excluded from git (DB, cache, venv)
├── templates/              # Jinja2 HTML templates styled with Tailwind CSS
│   ├── base.html           # Main layout, navbar, theme switch & shortcuts
│   ├── index.html          # Interactive dashboard & chart analytics
│   ├── budget.html         # Monthly budget tracking
│   ├── recurring.html      # Recurring bills & subscriptions
│   ├── savings.html        # Savings goals & progress
│   ├── profile.html        # User account & password management
│   ├── login.html          # User authentication login
│   ├── signup.html         # User registration
│   ├── forgot_password.html# Security question password recovery
│   ├── reset_password.html # New password form
│   └── edit.html           # Expense editing
└── README.md               # Project documentation
```

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/GarimaVerma45/EXPENSE-TRACKER.git
cd EXPENSE-TRACKER
```

### 2. Set up a virtual environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the application
```bash
python app.py
```

The application will be live locally at: **http://127.0.0.1:5000**

---

## ☁️ Deployment

This project is pre-configured for one-click deployment on platforms like **[Render](https://render.com/)**, **Railway**, or **PythonAnywhere**:

1. Push your repository to GitHub.
2. Log in to [Render](https://render.com/) and create a new **Web Service**.
3. Connect your repository: `GarimaVerma45/EXPENSE-TRACKER`.
4. Configure settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app` (auto-detected via `Procfile`)
5. Click **Deploy Web Service**!

---

## 👤 Author

- **Garima Verma** - [@GarimaVerma45](https://github.com/GarimaVerma45)

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).
