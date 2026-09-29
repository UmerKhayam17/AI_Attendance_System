# AI Attendance System

Face recognition powered attendance system using Django, InsightFace, and React.

## Architecture

```
React Frontend (Vite)  →  Django REST API  →  PostgreSQL
                              ↓
                        InsightFace (ArcFace)
                              ↓
                     Webcam / CCTV Recognition
```

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Backend runs at **http://127.0.0.1:8000**

### 2. Frontend (Development)

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:5173** with API proxy to Django.

### 3. Production (single server)

```bash
cd frontend && npm run build
cd ../backend && python manage.py runserver
```

Open **http://127.0.0.1:8000** — Django serves the React app.

## Frontend Pages

| Page | Route | Description |
|------|-------|-------------|
| Dashboard | `/` | Live stats, department breakdown, recent activity |
| Employees | `/employees` | Register, edit, search, filter, delete |
| Face Enrollment | `/enrollment` | Webcam capture + train embeddings |
| Live Monitor | `/monitor` | Real-time recognition + auto attendance |
| Attendance | `/attendance` | Records with filters + manual entry |
| Reports | `/reports` | Daily present/late/absent report |

## Workflow

1. **Register employee** → Employees page
2. **Enroll face** → Capture 5+ images → Train embeddings
3. **Start monitor** → Automatic check-in / check-out
4. **View reports** → Dashboard & Reports pages

## API Base

All APIs: `/api/`

- `POST /api/employees/` — Register
- `POST /api/recognition/enroll/{id}/capture/` — Capture face
- `POST /api/recognition/enroll/{id}/train/` — Train embeddings
- `POST /api/recognition/identify/` — Recognize face
- `GET /api/attendance/records/` — List attendance
- `GET /api/dashboard/summary/` — Dashboard stats

## Database

PostgreSQL database: `AIAttendance` (configure in `backend/config/settings.py`)

## Requirements

- Python 3.11+
- Node.js 18+
- PostgreSQL
- Webcam (for enrollment & monitoring)
