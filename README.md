# Voice AI Platform

منصة صوتية ذكية مشابهة لـ Vapi.ai - حل self-hosted لإنشاء وإدارة ونشر وكلاء الذكاء الاصطناعي الصوتيين للمكالمات الهاتفية.

## المميزات الرئيسية

- **بدون رسوم منصة** - تكلفة APIs المباشرة فقط
- **محسّن للعربية** - دعم RTL واللهجة السعودية
- **Self-hosted** - تحكم كامل في البيانات والبنية التحتية
- **أقل Latency** - Pipeline محسّن لاستجابة أسرع

## البنية التقنية

### Frontend
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- Zustand (State Management)

### Backend
- FastAPI (Python 3.11+)
- SQLAlchemy + PostgreSQL
- Redis (Caching)

### Voice Pipeline
- **STT**: Deepgram, Azure, Google, OpenAI Whisper
- **LLM**: Claude, GPT-4, Gemini
- **TTS**: ElevenLabs, Azure, Deepgram, CartesiaAI

## التشغيل السريع

### باستخدام Docker

```bash
cd docker
docker-compose up -d
```

### تشغيل محلي

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

## الصفحات

- `/overview` - لوحة التحكم الرئيسية
- `/assistants` - إدارة المساعدين الصوتيين
- `/tools` - إدارة الأدوات والوظائف
- `/phone-numbers` - إدارة أرقام الهاتف
- `/voice-library` - مكتبة الأصوات
- `/squads` - الفرق متعددة المساعدين
- `/call-logs` - سجلات المكالمات
- `/metrics` - التحليلات والإحصائيات
- `/settings` - الإعدادات

## المتغيرات البيئية

انظر `.env.example` لقائمة كاملة بالمتغيرات المطلوبة.

## API Documentation

بعد تشغيل الخادم:
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

## الترخيص

MIT License
