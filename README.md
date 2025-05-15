# 🤖 ProjectBuddy – Smart Project Onboarding Bot

**ProjectBuddy** is an intelligent onboarding assistant designed to simplify and streamline the onboarding experience for both new joiners and mentors. It automates task generation from onboarding documents, understands user roles, and creates a guided, interactive onboarding journey tailored to each project.

---

## 🚀 What Does ProjectBuddy Do?

### ✅ Identifies User Role
- Detects if the user is a **mentor** or a **new joiner** and adapts its behavior accordingly.

### 📁 Understands Project Context
- Asks for the project name to fetch the correct onboarding materials and tasks.

### 📋 Automated Task Generation
- Parses uploaded onboarding documents using **LLMs (Large Language Models)** to generate relevant onboarding tasks.

### 🗂 Centralised Document Management
- Allows mentors to upload onboarding material following predefined templates in one place.

### 👥 Acts as a Virtual Buddy
- Interactively guides new joiners through their onboarding steps like a helpful teammate.

### ♻️ Reusable & Scalable
- Supports reusable templates across different projects and teams to save time and ensure consistency.

### ⚙️ Reduces Manual Work
- Automates repetitive onboarding steps to improve productivity for both mentors and new joiners.

---

## 🎯 Benefits & Value Proposition

### For New Joiners
- **📌 Clear Starting Point**: Instantly receive a personalised onboarding checklist generated from your project’s documentation.
- **🧠 Role & Project Awareness**: ProjectBuddy adapts based on your role and team.
- **🔗 Git Task Integration**: All tasks are automatically created in GitHub/GitLab.
- **⏰ Always-Available Buddy**: Ask questions and navigate onboarding at your own pace.
- **⚡ Faster Ramp-Up**: Contribute to the project more quickly with less confusion.

### For Buddies / Mentors
- **📤 Centralised Doc Upload**: Manage onboarding documents and templates easily per project.
- **♻️ Reusable Templates**: Save time and ensure consistency across new joiners.
- **🤖 Automated Git Task Creation**: Let ProjectBuddy parse documents and generate Git issues.
- **🧹 Smart Delegation**: Automate repetitive onboarding while focusing on meaningful mentorship.
- **📈 Consistent Experience**: Ensure every new joiner has a high-quality onboarding experience, regardless of buddy availability.

---

## 📦 Installation

### 1. Clone the Repository
```bash
git clone https://github.ibm.com/Code-Your-Skills/project-buddy-d3b0884f.git
cd projectbuddy
```

### 2. Clone the Repository
```bash
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## 🧪 Getting Started
```bash
chainlit run app.py
```

## 📁 Project Structure
```text
projectbuddy/
│
├── app/                        # Entry point (e.g., Chainlit)
├── ibm_cloud/                  # Logic to upload and fetch docs to ibm cloud
├── task_handler/               # Onboarding task creator
├── rag_model/                  # Logic to create vectore and answer questions
│
├── Project_Onboarding.xlsm     # Sample document
├── onboarding_template.xlsx    # Onbaording template
├── requirements.txt            # Project dependencies
├── README.md                   # This file
```

## 💡 Tech Stack
- Python 3.10+

- FAISS (vector DB for smart retrieval)

- MongoDB (for session and document tracking)

- Chainlit (interactive conversational UI)

- GitHub/GitLab API (task creation)