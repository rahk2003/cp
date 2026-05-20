# 🛰️ NaftScan — Oil Spill Detection & Risk Analysis

**نَفط سكان** — نظام ذكاء اصطناعي ثنائي اللغة لرصد التسرّبات النفطية وتحليل المخاطر البيئية من صور الأقمار الصناعية.

A bilingual (AR/EN) frontend for satellite-based oil spill detection.
Wired to the **Rana FastAPI backend** (PostgreSQL + DeepLab + RAG + Smart Chat Router).

---

## ✨ Features

- **🏠 Home** — Live stats from the backend, latest detections strip.
- **🗺️ Interactive Map** — Leaflet map with risk-coded markers from `/api/spills`.
- **📤 Analyze Image** — Drag-drop upload that POSTs to `/api/analyze-image`.
- **💬 AI Chatbot** — Wired to the Smart Router at `/api/chat` (DB / RAG / Response Guide).
- **📄 Reports** — Lists `/api/reports`, generates new ones via `/api/generate-report`, opens HTML via `/api/reports/:id`.
- **ℹ️ About** — Pipeline diagram & technical stack.

Bilingual (AR/EN) with automatic RTL.

---

## 🚀 Quick Start (Frontend Only)

```bash
cd oil-spill-app
npm install
npm run dev
# Open http://localhost:5173
```

The dev server proxies all `/api/*` requests to `http://127.0.0.1:8000`
(configured in `vite.config.ts`).

---

## 🔌 Running with the Backend

### 1. Start the backend

```bash
cd backend-rana-clean
python3.11 -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # edit CSV_PATH / DB_* values
uvicorn main:app --reload --port 8000
```

Verify:
- http://localhost:8000/ → JSON health
- http://localhost:8000/docs → Swagger UI

> ⚠️ The backend's `.env` ships with macOS paths (`/Users/rana/...`).
> On Windows, edit `CSV_PATH` and `CP_PATH` to your local equivalents
> (e.g. `C:\Users\jojoo\Desktop\oil-spill-project\backend-rana-clean\data\...`),
> otherwise the CSV auto-import and the RAG endpoints will fail.

### 2. Start the frontend in a second terminal

```bash
cd oil-spill-app
npm run dev
```

Open **http://localhost:5173**.

---

## 🔧 Backend Endpoints Consumed

| Page | Endpoint | Method |
|---|---|---|
| Home, Map, Chatbot, Reports | `/api/spills?risk=&limit=` | `GET` |
| Map (single) | `/api/spills/:id` | `GET` |
| Analyze | `/api/analyze-image` | `POST` multipart |
| Chatbot | `/api/chat` | `POST` JSON |
| Reports list | `/api/reports` | `GET` |
| Reports HTML | `/api/reports/:id` | `GET` HTML |
| Generate | `/api/generate-report` | `POST` JSON |

All wrapped in **`src/lib/api.ts`** with TypeScript types.

---

## ⚙️ Configuration

By default the frontend uses the Vite proxy (no setup needed in dev).

For a deployed build, set the backend URL in `.env.local`:

```env
VITE_API_BASE_URL=https://your-backend.example.com
```

---

## 🛠️ Tech Stack

| Layer | Tech |
|---|---|
| Framework | React 18 + TypeScript 5.6 + Vite 5 |
| Styling | Tailwind CSS 3.4 (custom navy/teal/ocean palette) |
| UI primitives | Custom (shadcn-style) + Radix UI + lucide-react |
| Maps | Leaflet + react-leaflet |
| Animation | Framer Motion |
| Routing | react-router-dom v6 |
| Fonts | Fraunces · Plus Jakarta Sans · Tajawal · JetBrains Mono |

---

## 📁 Project Structure

```
oil-spill-app/
├── index.html
├── package.json
├── tailwind.config.js
├── vite.config.ts            # /api → :8000 proxy
└── src/
    ├── main.tsx
    ├── App.tsx                # Routes
    ├── index.css
    ├── vite-env.d.ts          # Vite env types
    ├── types/index.ts
    ├── data/mockData.ts       # Fallback/dev mock data (no longer imported)
    ├── lib/
    │   ├── api.ts             # ★ All backend calls
    │   ├── i18n.ts            # AR + EN strings
    │   └── utils.ts
    ├── hooks/
    │   ├── useLang.tsx        # Language + RTL context
    │   └── useApi.ts          # ★ useSpills, useReports
    ├── components/
    │   ├── Layout.tsx
    │   └── ui/                # Button, Card, Badge, RiskPill
    └── pages/
        ├── Home.tsx           # ← useSpills()
        ├── MapPage.tsx        # ← useSpills()
        ├── Analyze.tsx        # ← analyzeImage()
        ├── Chatbot.tsx        # ← sendChat() + generateReport()
        ├── Reports.tsx        # ← useReports() + generateReport()
        └── About.tsx
```

---

## 🎨 Design Tokens

- **Risk colors** — Low `#10b981` · Medium `#f59e0b` · High `#f97316` · Critical `#ef4444`
- **Brand gradient** — `from-navy-500 to-teal-600`
- **Display font** — Fraunces
- **Body font** — Plus Jakarta Sans (EN) / Tajawal (AR via `dir="rtl"`)
- **Mono** — JetBrains Mono

---

## 🐛 Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| "Backend offline" on Map page | Backend isn't running. Start it on port 8000. |
| Empty spill list | DB connection failed. Check `/api/debug/db` in browser. |
| Analyze "404 / 500" | The `/api/analyze-image` endpoint needs a writable uploads dir. |
| Chatbot times out | The smart router calls RAG which needs `external_rag` files. Check `/api/rag/health`. |
| CORS errors | The backend allows `*`; if you see CORS, you're hitting the wrong URL. |

---

**Built with ❤️ for a healthier ocean.** 🌊
