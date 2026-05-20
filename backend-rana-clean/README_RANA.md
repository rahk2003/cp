# NaftScan / Rana Backend متوافق مع الفرونت اند

هذه نسخة باك اند FastAPI متوافقة مع الفرونت اند المرفق `oil-spill-app`.

## أهم التعديلات

- إضافة `ReportRequest` حتى لا يتعطل `/api/generate-report`.
- إصلاح تعارض اسم `get_spills` الذي كان يكسر `/api/spills/{id}` و `/api/generate-report`.
- إضافة CORS لمنفذ Vite: `http://localhost:5173`.
- جعل قراءة أعمدة قاعدة البيانات مرنة، سواء كانت الأعمدة باسم `risk_level` أو `final_risk_level`، و `coral_risk_class` أو `coral_proximity_class`.
- جعل مسارات `CP_PATH`, `CSV_PATH`, `EXTERNAL_RAG_PATH` تُقرأ من `.env` بدل مسارات Mac الثابتة.
- جعل RAG يعطي رد واضح بدل 500 إذا كان المسار غير مضبوط.
- تجهيز endpoints التي يستخدمها الفرونت:
  - `GET /`
  - `GET /api/debug/db`
  - `GET /api/spills`
  - `GET /api/spills/{spill_id}`
  - `POST /api/analyze-image`
  - `POST /api/chat`
  - `POST /api/generate-report`
  - `GET /api/reports`
  - `GET /api/reports/{report_id}`
  - `POST /api/solutions`
  - `GET /api/rag/health`
  - `POST /api/rag/ask`

## التشغيل على Windows PowerShell

```powershell
cd C:\Users\jojoo\Desktop\oil-spill-project\backend-rana-clean
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
uvicorn main:app --reload --port 8000
```

بعد تعديل `.env` افتحي:

- http://localhost:8000/
- http://localhost:8000/api/debug/db
- http://localhost:8000/api/spills
- http://localhost:8000/docs

## تشغيل الفرونت اند

```powershell
cd C:\Users\jojoo\Desktop\oil-spill-project\oil-spill-app
npm install
npm run dev
```

افتحي:

- http://localhost:5173

## اختبار سريع

```powershell
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/api/spills
curl -X POST http://127.0.0.1:8000/api/chat -H "Content-Type: application/json" -d '{"message":"كم عدد حالات التسرب؟","language":"ar"}'
```

## ملاحظة مهمة

لا تضيفي ملف `.env` إلى GitHub لأنه يحتوي كلمة مرور قاعدة البيانات ومفاتيح API. ارفعي فقط `.env.example`.
