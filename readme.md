# ESP32 Autonomous Delivery Robot (DEV Branch)

> ⚠️ This is the **development / integration branch** (`dev`).
> - `dev` may contain unfinished features or unstable changes.
> - For stable demo/release version, switch to `main`.

---

## Branch Policy

### Main Branches
- ✅ `main`: Stable / demo-ready / release branch (NO direct push)
- ✅ `dev`: Integration branch for team development

### Workflow
1. Developers create a feature branch **from `dev`**
2. Push commits to feature branch
3. Open Pull Request (PR) → merge into `dev`
4. Only when `dev` is stable → PR from `dev` to `main`

### Branch Naming Convention
Use short, module-based prefixes:

#### Frontend
- `fe/<feature>`
  - Example: `fe/map-ui`

#### Backend
- `be/<feature>`
  - Example: `be/order-api`

#### Firmware (ESP32)
- `fw/<feature>`
  - Example: `fw/mqtt-control`

#### Bug Fix
- `fix/<bug>`
  - Example: `fix/backend-timeout`

---

## Project Structure

```

.
├── app/                # Backend (Python)
├── frontend/           # Frontend (Vite / Web UI)
├── data/               # Map / test data
├── robot_simulator.py  # Simulation entry (if used)
└── README.md

````

---

## Quick Start (DEV)

### 1) Backend
```bash
cd app
python -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows

pip install -r requirements.txt
python main.py
````

Backend should run at:

* `http://localhost:8000` (example)

> If port differs, check backend config.

---

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend should run at:

* `http://localhost:5173`

---

## Team Collaboration Rules

### ✅ Do

* Always pull latest `dev` before starting work
* Create a feature branch for each task
* PR into `dev` (NOT `main`)
* Keep PR small (one PR = one feature)

### ❌ Don't

* Do NOT push directly to `main`
* Do NOT mix frontend + backend + firmware changes in one PR
* Do NOT commit `.env` / secrets

---

## Pull Request Checklist

Before creating PR:

* [ ] Code builds successfully
* [ ] Basic manual testing done
* [ ] No secrets committed
* [ ] PR title clearly describes the change

---

## Notes

* The `dev` branch is expected to change frequently.
* Use `main` branch for demo/recording/submission.
