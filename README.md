# Expense Tracker Lite 💰

A modern, responsive personal expense tracking and financial management web application built with **Python (Flask)**, **SQLite**, **Tailwind CSS**, and **Chart.js**.

---

## ✨ Features

- 📊 **Interactive Analytics Dashboard**:
  - Breakdown by category with toggleable chart types: **Donut**, **Pie**, and **Polar Area**.
  - Daily spending trends with toggleable **Bar** and **Line** charts.
  - Interactive slice filtering and persistent chart type preferences.
- 🎯 **Budget Tracking**:
  - Set monthly spending budgets with real-time visual progress bars and status indicators.
- 🔄 **Recurring Expenses**:
  - Automatically manage recurring bills, subscriptions, and regular expenses.
- 🏆 **Savings Goals**:
  - Track financial goals with progress percentage, deposit records, and target completion alerts.
- 📑 **Export Reports**:
  - Export filtered expense logs directly as **CSV** or styled **PDF** summaries (powered by ReportLab).
- 🔐 **User Authentication & Security**:
  - Multi-user support with secure password hashing (`werkzeug.security`).
  - Account profile management and password reset via security questions.
- 🌓 **Modern Dark / Light Theme**:
  - Sleek modern UI built with Tailwind CSS, supporting dark and light themes with preference persistence.

---

## 🛠️ Tech Stack

- **Backend**: Python 3, Flask, Flask-SQLAlchemy, Flask-Login, ReportLab
- **Database**: SQLite (SQLAlchemy ORM)
- **Frontend**: HTML5, Tailwind CSS, Vanilla JavaScript
- **Charts**: Chart.js 4.x

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
```

### 2. Set up virtual environment
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

The app will be available at: **http://127.0.0.1:5000**

---

## 📄 License
This project is open source and available under the [MIT License](LICENSE).
