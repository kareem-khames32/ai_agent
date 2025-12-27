"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/loading";
import {
  ArrowLeft,
  Save,
  Play,
  Square,
  Phone,
  Bot,
  Mic,
  Wrench,
  BarChart3,
  Settings,
  Shield,
  Code,
  Volume2,
  Maximize2,
} from "lucide-react";

// ============== LLM PROVIDERS & MODELS ==============
const modelProviders = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "google", label: "Google Gemini" },
  { value: "groq", label: "Groq (Fastest!)" },
  { value: "together", label: "Together AI (200+ models)" },
];

// ============== VOICE MODES ==============
const voiceModes = [
  { value: "pipeline", label: "Pipeline (STT → LLM → TTS)", description: "Traditional mode with separate components" },
  { value: "realtime", label: "Realtime API (Native Voice)", description: "Direct speech-to-speech, lowest latency" },
];

// ============== REALTIME PROVIDERS ==============
const realtimeProviders = [
  { value: "openai", label: "OpenAI Realtime", description: "gpt-4o-realtime - Native audio I/O" },
  { value: "google", label: "Google Gemini Live", description: "gemini-2.0-flash - Multimodal live" },
  { value: "groq", label: "Groq Ultra-Fast", description: "Fastest LLM inference + STT/TTS" },
  { value: "elevenlabs", label: "ElevenLabs Conversational", description: "Best voice quality, conversational AI" },
];

// Realtime models by provider
const realtimeModelsByProvider: Record<string, { value: string; label: string; description: string }[]> = {
  openai: [
    { value: "gpt-4o-realtime-preview", label: "GPT-4o Realtime Preview", description: "Audio in/out, function calling" },
    { value: "gpt-4o-realtime-preview-2024-12-17", label: "GPT-4o Realtime (Dec 2024)", description: "Latest stable version" },
    { value: "gpt-4o-mini-realtime-preview", label: "GPT-4o Mini Realtime", description: "Faster, cheaper option" },
  ],
  google: [
    { value: "gemini-2.0-flash-exp", label: "Gemini 2.0 Flash (Live)", description: "Multimodal live streaming" },
    { value: "gemini-2.0-flash-thinking-exp", label: "Gemini 2.0 Flash Thinking", description: "With reasoning" },
  ],
  groq: [
    { value: "llama-3.3-70b-versatile", label: "Llama 3.3 70B", description: "Best quality, 275 tok/s" },
    { value: "llama-3.1-8b-instant", label: "Llama 3.1 8B Instant", description: "Ultra fast, 750 tok/s" },
    { value: "mixtral-8x7b-32768", label: "Mixtral 8x7B", description: "Great for Arabic" },
  ],
  elevenlabs: [
    { value: "eleven_turbo_v2_5", label: "Turbo v2.5", description: "Lowest latency" },
    { value: "eleven_multilingual_v2", label: "Multilingual v2", description: "Best for Arabic" },
  ],
};

// Realtime voices by provider
const realtimeVoicesByProvider: Record<string, { value: string; label: string }[]> = {
  openai: [
    { value: "alloy", label: "Alloy (محايد)" },
    { value: "echo", label: "Echo (ذكر واضح)" },
    { value: "shimmer", label: "Shimmer (أنثى دافئ)" },
    { value: "ash", label: "Ash (جديد)" },
    { value: "ballad", label: "Ballad (جديد)" },
    { value: "coral", label: "Coral (جديد)" },
    { value: "sage", label: "Sage (جديد)" },
    { value: "verse", label: "Verse (جديد)" },
  ],
  google: [
    { value: "Puck", label: "Puck (Default)" },
    { value: "Charon", label: "Charon" },
    { value: "Kore", label: "Kore" },
    { value: "Fenrir", label: "Fenrir" },
    { value: "Aoede", label: "Aoede" },
  ],
  groq: [], // Uses separate TTS
  elevenlabs: [
    { value: "EXAVITQu4vr4xnSDxMaL", label: "Bella (عربي)" },
    { value: "21m00Tcm4TlvDq8ikWAM", label: "Rachel (محادثة)" },
    { value: "pNInz6obpgDQGcFmaJgB", label: "Adam (ذكر)" },
  ],
};

// ============== SYSTEM PROMPT TEMPLATES ==============
const systemPromptTemplates = [
  {
    value: "phone_call_ar",
    label: "مكالمة هاتفية احترافية (عربي)",
    prompt: `# هويتك
أنت موظف خدمة عملاء محترف تجري مكالمة هاتفية حقيقية. تصرف تماماً كما يتصرف الموظف البشري في المكالمات الهاتفية.

# سلوك المكالمة الهاتفية
- هذه مكالمة صوتية حقيقية وليست محادثة نصية
- تكلم بشكل طبيعي مثل البشر - استخدم كلمات مثل "آه"، "طيب"، "تمام"
- ردودك يجب أن تكون قصيرة (جملة أو جملتين فقط)
- انتظر رد العميل قبل الاستمرار في الحديث
- إذا قاطعك العميل، توقف فوراً واستمع له
- لا تقل أبداً "كيف يمكنني مساعدتك" في كل رد

# طريقة الكلام
- تحدث بالعامية السعودية/الخليجية الودودة
- استخدم نبرة صوت دافئة ومرحبة
- تجنب الردود الطويلة والرسمية المملة
- كن مباشراً ومختصراً

# تعامل مع السكوت
- إذا سكت العميل لثانيتين، اسأل "معاك؟" أو "سامعني؟"
- لا تكرر السؤال نفسه أكثر من مرة

# معلومات مهمة
- لا تتظاهر بأنك قادر على فعل أشياء خارج صلاحياتك
- إذا لم تعرف الجواب، قل "خليني أتأكد من المعلومة وأرجع لك"
- احترم وقت العميل - لا تطل في الحديث`
  },
  {
    value: "phone_call_en",
    label: "Professional Phone Call (English)",
    prompt: `# Your Identity
You are a professional customer service representative conducting a real phone call. Behave exactly like a human employee would in phone conversations.

# Phone Call Behavior
- This is a real voice call, not a text chat
- Speak naturally like humans do - use filler words occasionally like "um", "well", "so"
- Keep responses SHORT (1-2 sentences max)
- Wait for customer response before continuing
- If interrupted, STOP immediately and listen
- Never say "How can I help you?" in every response

# Speaking Style
- Use a warm, friendly tone
- Be conversational, not robotic
- Avoid long, formal responses
- Be direct and concise

# Handling Silence
- If customer is silent for 2 seconds, say "Are you still there?" or "Hello?"
- Don't repeat the same question more than once

# Important Rules
- Don't pretend you can do things outside your capabilities
- If you don't know something, say "Let me check on that and get back to you"
- Respect customer's time - keep it brief`
  },
  {
    value: "sales_ar",
    label: "وكيل مبيعات (عربي)",
    prompt: `# هويتك
أنت وكيل مبيعات محترف في مكالمة هاتفية. هدفك فهم احتياجات العميل وتقديم الحلول المناسبة.

# سلوك المكالمة
- تحدث بشكل طبيعي ومختصر
- اسأل أسئلة قصيرة لفهم الاحتياج
- لا تقدم عرض طويل - انتظر رد العميل
- إذا قال العميل "لا" احترم قراره

# طريقة البيع
- اسأل عن الاحتياج قبل تقديم العرض
- قدم فائدة واحدة في كل رد
- استخدم أسلوب السؤال بدلاً من الإلحاح

# ردود قصيرة
- "ممتاز! إيش اللي تبحث عنه بالضبط؟"
- "عندنا حل ممتاز لهذا الموضوع"
- "يعني تبي أوضح لك أكثر؟"`
  },
  {
    value: "support_ar",
    label: "دعم فني (عربي)",
    prompt: `# هويتك
أنت موظف دعم فني تساعد العملاء في حل مشاكلهم عبر الهاتف.

# سلوك المكالمة
- استمع للمشكلة أولاً بدون مقاطعة
- اسأل أسئلة توضيحية قصيرة
- قدم خطوة واحدة في كل مرة
- تأكد من نجاح كل خطوة قبل الانتقال للتالية

# حل المشاكل
- "طيب، خليني أفهم المشكلة أولاً"
- "جرب تعمل كذا وقولي النتيجة"
- "تمام، الحين نجرب خطوة ثانية"

# إذا ما قدرت تحل
- "المشكلة تحتاج متخصص، خليني أحولك"
- "أحسن حل نرفع تذكرة ويتواصلون معك"`
  },
  {
    value: "collection_ar",
    label: "تحصيل ديون (عربي)",
    prompt: `# هويتك
أنت موظف تحصيل ديون محترف. تتحدث بأسلوب مهني ومحترم مع الحفاظ على الحزم.

# سلوك المكالمة
- كن مهنياً ومحترماً دائماً
- لا تستخدم أي تهديدات أو إهانات
- استمع لظروف العميل
- قدم حلول دفع مرنة

# أسلوب التحصيل
- "نتصل بخصوص المبلغ المستحق عليكم"
- "هل فيه ظرف معين أثر على السداد؟"
- "ممكن نتفق على جدول سداد يناسبكم"

# قواعد مهمة
- لا تناقش تفاصيل الدين مع غير صاحب الحساب
- وثق أي اتفاق أو وعد بالسداد
- احترم رغبة العميل في إنهاء المكالمة`
  },
  {
    value: "appointment_ar",
    label: "حجز مواعيد (عربي)",
    prompt: `# هويتك
أنت موظف حجز مواعيد. مهمتك مساعدة العملاء في تحديد المواعيد المناسبة.

# سلوك المكالمة
- اسأل عن الخدمة المطلوبة أولاً
- قدم 2-3 خيارات للموعد
- تأكد من تفاصيل الموعد قبل التأكيد

# طريقة الحجز
- "أي خدمة تبي تحجز لها؟"
- "عندنا موعد يوم السبت الساعة 10 أو الأحد الساعة 3، أيهم يناسبك؟"
- "تمام، أأكد: موعدك يوم... الساعة... صح؟"

# معلومات مطلوبة
- الاسم الكامل
- رقم الجوال
- نوع الخدمة
- الموعد المختار`
  },
  {
    value: "custom",
    label: "مخصص",
    prompt: ""
  }
];

const modelsByProvider: Record<string, { value: string; label: string; price?: string; context?: string }[]> = {
  openai: [
    { value: "gpt-4o", label: "GPT-4o", price: "$2.50/$10 per 1M", context: "128K" },
    { value: "gpt-4o-mini", label: "GPT-4o Mini", price: "$0.15/$0.60 per 1M", context: "128K" },
    { value: "gpt-4-turbo", label: "GPT-4 Turbo", price: "$10/$30 per 1M", context: "128K" },
    { value: "gpt-4", label: "GPT-4", price: "$30/$60 per 1M", context: "8K" },
    { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo", price: "$0.50/$1.50 per 1M", context: "16K" },
    { value: "gpt-4.1", label: "GPT-4.1 (New 2025)", price: "-", context: "-" },
    { value: "gpt-4.1-mini", label: "GPT-4.1 Mini (New 2025)", price: "-", context: "-" },
    { value: "gpt-4.1-nano", label: "GPT-4.1 Nano (Fastest)", price: "-", context: "1M" },
    { value: "o3", label: "O3 (Reasoning)", price: "-", context: "-" },
    { value: "o4-mini", label: "O4 Mini (Reasoning)", price: "-", context: "-" },
  ],
  anthropic: [
    { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4", price: "$3/$15 per 1M", context: "200K" },
    { value: "claude-3-5-sonnet-20241022", label: "Claude 3.5 Sonnet", price: "$3/$15 per 1M", context: "200K" },
    { value: "claude-3-5-haiku-20241022", label: "Claude 3.5 Haiku (Fast)", price: "$0.80/$4 per 1M", context: "200K" },
    { value: "claude-3-opus-20240229", label: "Claude 3 Opus", price: "$15/$75 per 1M", context: "200K" },
    { value: "claude-opus-4", label: "Claude Opus 4 (New 2025)", price: "-", context: "200K" },
    { value: "claude-sonnet-4.5", label: "Claude Sonnet 4.5 (Latest)", price: "-", context: "200K" },
    { value: "claude-opus-4.5", label: "Claude Opus 4.5 (Latest)", price: "-", context: "200K" },
    { value: "claude-haiku-4.5", label: "Claude Haiku 4.5 (Latest)", price: "-", context: "200K" },
  ],
  google: [
    { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro (Most Powerful)", price: "-", context: "-" },
    { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash (Best Value)", price: "-", context: "-" },
    { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash", price: "$0.075/$0.30 per 1M", context: "1M" },
    { value: "gemini-2.0-pro", label: "Gemini 2.0 Pro", price: "-", context: "2M" },
    { value: "gemini-2.0-flash-lite", label: "Gemini 2.0 Flash Lite (Cheapest)", price: "-", context: "-" },
    { value: "gemini-3-pro", label: "Gemini 3 Pro (Newest)", price: "-", context: "-" },
    { value: "gemini-1.5-pro", label: "Gemini 1.5 Pro", price: "$1.25/$5 per 1M", context: "2M" },
    { value: "gemini-1.5-flash", label: "Gemini 1.5 Flash", price: "$0.075/$0.30 per 1M", context: "1M" },
  ],
  groq: [
    { value: "llama-3.3-70b-versatile", label: "Llama 3.3 70B (Best)", price: "$0.59/$0.79 per 1M", context: "128K" },
    { value: "llama-3.2-90b-vision-preview", label: "Llama 3.2 90B Vision", price: "-", context: "-" },
    { value: "llama-3.2-11b-vision-preview", label: "Llama 3.2 11B Vision", price: "-", context: "-" },
    { value: "llama-3.1-8b-instant", label: "Llama 3.1 8B (Fastest)", price: "$0.05/$0.08 per 1M", context: "128K" },
    { value: "mixtral-8x7b-32768", label: "Mixtral 8x7B", price: "$0.24/$0.24 per 1M", context: "32K" },
    { value: "gemma2-9b-it", label: "Gemma 2 9B", price: "$0.20/$0.20 per 1M", context: "-" },
  ],
  together: [
    { value: "meta-llama/Llama-3.3-70B-Instruct-Turbo", label: "Llama 3.3 70B Turbo", price: "$0.88/$0.88 per 1M", context: "-" },
    { value: "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo", label: "Llama 3.2 11B Vision", price: "$0.18/$0.18 per 1M", context: "-" },
    { value: "Qwen/Qwen2.5-72B-Instruct-Turbo", label: "Qwen 2.5 72B (Best for Code)", price: "$1.20/$1.20 per 1M", context: "-" },
    { value: "Qwen/Qwen3-235B-A22B", label: "Qwen 3 235B MoE (Largest)", price: "-", context: "-" },
    { value: "mistralai/Mixtral-8x7B-Instruct-v0.1", label: "Mixtral 8x7B", price: "$0.60/$0.60 per 1M", context: "-" },
    { value: "mistralai/Mistral-Small-24B", label: "Mistral Small 24B", price: "-", context: "-" },
    { value: "deepseek-ai/DeepSeek-R1", label: "DeepSeek R1 (Reasoning)", price: "-", context: "-" },
  ],
};

// ============== TTS PROVIDERS & VOICES ==============
const voiceProviders = [
  { value: "azure", label: "Azure TTS (600+ voices - Best Arabic) - $16/1M chars" },
  { value: "elevenlabs", label: "ElevenLabs (Best Quality) - $300/1M chars" },
  { value: "openai", label: "OpenAI TTS - $15/1M chars" },
  { value: "deepgram", label: "Deepgram Aura (Fastest!) - $30/1M chars" },
];

// Voices organized by provider
const voicesByProvider: Record<string, { value: string; label: string; gender: string; language: string }[]> = {
  // ============== AZURE ARABIC VOICES (32 voices) ==============
  azure: [
    // Saudi Arabia
    { value: "ar-SA-HamedNeural", label: "Hamed (سعودي)", gender: "male", language: "ar-SA" },
    { value: "ar-SA-ZariyahNeural", label: "Zariyah (سعودي)", gender: "female", language: "ar-SA" },
    // Egypt
    { value: "ar-EG-SalmaNeural", label: "Salma (مصري)", gender: "female", language: "ar-EG" },
    { value: "ar-EG-ShakirNeural", label: "Shakir (مصري)", gender: "male", language: "ar-EG" },
    // UAE
    { value: "ar-AE-FatimaNeural", label: "Fatima (إماراتي)", gender: "female", language: "ar-AE" },
    { value: "ar-AE-HamdanNeural", label: "Hamdan (إماراتي)", gender: "male", language: "ar-AE" },
    // Bahrain
    { value: "ar-BH-AliNeural", label: "Ali (بحريني)", gender: "male", language: "ar-BH" },
    { value: "ar-BH-LailaNeural", label: "Laila (بحريني)", gender: "female", language: "ar-BH" },
    // Algeria
    { value: "ar-DZ-AminaNeural", label: "Amina (جزائري)", gender: "female", language: "ar-DZ" },
    { value: "ar-DZ-IsmaelNeural", label: "Ismael (جزائري)", gender: "male", language: "ar-DZ" },
    // Iraq
    { value: "ar-IQ-BasselNeural", label: "Bassel (عراقي)", gender: "male", language: "ar-IQ" },
    { value: "ar-IQ-RanaNeural", label: "Rana (عراقي)", gender: "female", language: "ar-IQ" },
    // Jordan
    { value: "ar-JO-SanaNeural", label: "Sana (أردني)", gender: "female", language: "ar-JO" },
    { value: "ar-JO-TaimNeural", label: "Taim (أردني)", gender: "male", language: "ar-JO" },
    // Kuwait
    { value: "ar-KW-FahedNeural", label: "Fahed (كويتي)", gender: "male", language: "ar-KW" },
    { value: "ar-KW-NouraNeural", label: "Noura (كويتي)", gender: "female", language: "ar-KW" },
    // Lebanon
    { value: "ar-LB-LaylaNeural", label: "Layla (لبناني)", gender: "female", language: "ar-LB" },
    { value: "ar-LB-RamiNeural", label: "Rami (لبناني)", gender: "male", language: "ar-LB" },
    // Libya
    { value: "ar-LY-ImanNeural", label: "Iman (ليبي)", gender: "female", language: "ar-LY" },
    { value: "ar-LY-OmarNeural", label: "Omar (ليبي)", gender: "male", language: "ar-LY" },
    // Morocco
    { value: "ar-MA-JamalNeural", label: "Jamal (مغربي)", gender: "male", language: "ar-MA" },
    { value: "ar-MA-MounaNeural", label: "Mouna (مغربي)", gender: "female", language: "ar-MA" },
    // Oman
    { value: "ar-OM-AbdullahNeural", label: "Abdullah (عماني)", gender: "male", language: "ar-OM" },
    { value: "ar-OM-AyshaNeural", label: "Aysha (عماني)", gender: "female", language: "ar-OM" },
    // Qatar
    { value: "ar-QA-AmalNeural", label: "Amal (قطري)", gender: "female", language: "ar-QA" },
    { value: "ar-QA-MoazNeural", label: "Moaz (قطري)", gender: "male", language: "ar-QA" },
    // Syria
    { value: "ar-SY-AmanyNeural", label: "Amany (سوري)", gender: "female", language: "ar-SY" },
    { value: "ar-SY-LaithNeural", label: "Laith (سوري)", gender: "male", language: "ar-SY" },
    // Tunisia
    { value: "ar-TN-HediNeural", label: "Hedi (تونسي)", gender: "male", language: "ar-TN" },
    { value: "ar-TN-ReemNeural", label: "Reem (تونسي)", gender: "female", language: "ar-TN" },
    // Yemen
    { value: "ar-YE-MaryamNeural", label: "Maryam (يمني)", gender: "female", language: "ar-YE" },
    { value: "ar-YE-SalehNeural", label: "Saleh (يمني)", gender: "male", language: "ar-YE" },
    // English voices
    { value: "en-US-JennyNeural", label: "Jenny (US)", gender: "female", language: "en-US" },
    { value: "en-US-GuyNeural", label: "Guy (US)", gender: "male", language: "en-US" },
    { value: "en-GB-SoniaNeural", label: "Sonia (UK)", gender: "female", language: "en-GB" },
    { value: "en-GB-RyanNeural", label: "Ryan (UK)", gender: "male", language: "en-GB" },
  ],

  // ============== ELEVENLABS VOICES (40+ voices) ==============
  elevenlabs: [
    { value: "EXAVITQu4vr4xnSDxMaL", label: "Rachel (هادئ)", gender: "female", language: "en-US" },
    { value: "pNInz6obpgDQGcFmaJgB", label: "Adam (عميق)", gender: "male", language: "en-US" },
    { value: "21m00Tcm4TlvDq8ikWAM", label: "Drew (واثق)", gender: "male", language: "en-US" },
    { value: "AZnzlk1XvdvUeBnXmlld", label: "Clyde (حربي)", gender: "male", language: "en-US" },
    { value: "CYw3kZ02Hs0563khs1Fj", label: "Paul (أخبار)", gender: "male", language: "en-US" },
    { value: "D38z5RcWu1voky8WS1ja", label: "Domi (قوي)", gender: "female", language: "en-US" },
    { value: "IKne3meq5aSn9XLyUdCD", label: "Dave (بريطاني)", gender: "male", language: "en-GB" },
    { value: "MF3mGyEYCl7XYWbV9V6O", label: "Fin (إيرلندي)", gender: "male", language: "en-IE" },
    { value: "N2lVS1w4EtoT3dr4eOWO", label: "Sarah (ناعم)", gender: "female", language: "en-US" },
    { value: "ODq5zmih8GrVes37Dizd", label: "Antoni (معبر)", gender: "male", language: "en-US" },
    { value: "SOYHLrjzK2X1ezoPC6cr", label: "Thomas (هادئ)", gender: "male", language: "en-US" },
    { value: "TX3LPaxmHKxFdv7VOQHJ", label: "Liam (مقالات)", gender: "male", language: "en-US" },
    { value: "XB0fDUnXU5powFXDhCwa", label: "Charlotte (سويدي)", gender: "female", language: "sv-SE" },
    { value: "XrExE9yKIg1WjnnlVkGX", label: "Matilda (دافئ)", gender: "female", language: "en-US" },
    { value: "Yko7PKs66lpKU65lgBr1", label: "Matthew (بريطاني)", gender: "male", language: "en-GB" },
    { value: "ZQe5CZNOzWyzPSCn5a3c", label: "James (أسترالي)", gender: "male", language: "en-AU" },
    { value: "Zlb1dXrM653N07WRdFW3", label: "Joseph (راوي)", gender: "male", language: "en-GB" },
    { value: "bVMeCyTHy58xNoL34h3p", label: "Jeremy (محادثة)", gender: "male", language: "en-US" },
    { value: "flq6f7yk4E4fJM5XTYuZ", label: "Michael (كبير)", gender: "male", language: "en-US" },
    { value: "g5CIjZEefAph4nQFvHAz", label: "Ethan", gender: "male", language: "en-US" },
    { value: "jBpfuIE2acCO8z3wKNLl", label: "Gigi (متحمس)", gender: "female", language: "en-US" },
    { value: "jsCqWAovK2LkecY7zXl4", label: "Freya", gender: "female", language: "en-US" },
    { value: "oWAxZDx7w5VEj9dCyTzz", label: "Grace (جنوبي)", gender: "female", language: "en-US" },
    { value: "onwK4e9ZLuTAKqWW03F9", label: "Daniel (بريطاني عميق)", gender: "male", language: "en-GB" },
    { value: "pFZP5JQG7iQjIQuC4Bku", label: "Serena (لطيف)", gender: "female", language: "en-US" },
    { value: "piTKgcLEGmPE4e6mEKli", label: "Nicole (همس)", gender: "female", language: "en-US" },
    { value: "pqHfZKP75CvOlQylNhV4", label: "Bill (راوي)", gender: "male", language: "en-US" },
    { value: "t0jbNlBVZ17f02VDIeMI", label: "Jessie (سريع)", gender: "male", language: "en-US" },
    { value: "wViXBPUzp2ZZixB1xQuM", label: "Sam (متحدث)", gender: "male", language: "en-US" },
    { value: "z9fAnlkpzviPz146aGWa", label: "Glinda (ساحرة)", gender: "female", language: "en-US" },
    { value: "zcAOhNBS3c14rBihAFp1", label: "Giovanni (إيطالي)", gender: "male", language: "it-IT" },
    { value: "zrHiDhphv9ZnVXBqCLjz", label: "Mimi (سويدي)", gender: "female", language: "sv-SE" },
    { value: "ThT5KcBeYPX3keUQqHPh", label: "Dorothy (بريطاني لطيف)", gender: "female", language: "en-GB" },
    { value: "VR6AewLTigWG4xSOukaG", label: "Arnold (راوي)", gender: "male", language: "en-US" },
    { value: "pMsXgVXv3BLzUgSXRplE", label: "Josh (عميق)", gender: "male", language: "en-US" },
    { value: "nPczCjzI2devNBz1zQrb", label: "Charlie (أسترالي)", gender: "male", language: "en-AU" },
    { value: "GBv7mTt0atIp3Br8iCZE", label: "Emily (هادئ)", gender: "female", language: "en-US" },
    { value: "MF3mGyEYCl7XYWbV9V6O", label: "Elli (شاب)", gender: "female", language: "en-US" },
    { value: "TxGEqnHWrfWFTfGW9XjX", label: "Callum (مشرق)", gender: "male", language: "en-US" },
    { value: "iP95p4xoKVk53GoZ742B", label: "Patrick (ناضج)", gender: "male", language: "en-US" },
    { value: "LcfcDJNUP1GQjkzn1xUU", label: "Harry (قلق)", gender: "male", language: "en-US" },
  ],

  // ============== OPENAI TTS VOICES ==============
  openai: [
    { value: "alloy", label: "Alloy (محايد)", gender: "neutral", language: "multi" },
    { value: "echo", label: "Echo (ذكر واضح)", gender: "male", language: "multi" },
    { value: "fable", label: "Fable (بريطاني راوي)", gender: "male", language: "multi" },
    { value: "onyx", label: "Onyx (ذكر عميق)", gender: "male", language: "multi" },
    { value: "nova", label: "Nova (أنثى ودود)", gender: "female", language: "multi" },
    { value: "shimmer", label: "Shimmer (أنثى دافئ)", gender: "female", language: "multi" },
    { value: "ash", label: "Ash (جديد)", gender: "male", language: "multi" },
    { value: "ballad", label: "Ballad (جديد)", gender: "neutral", language: "multi" },
    { value: "coral", label: "Coral (جديد)", gender: "female", language: "multi" },
    { value: "sage", label: "Sage (جديد)", gender: "neutral", language: "multi" },
    { value: "verse", label: "Verse (جديد)", gender: "neutral", language: "multi" },
  ],

  // ============== DEEPGRAM AURA VOICES (40+ voices) ==============
  deepgram: [
    // English - American Female
    { value: "aura-asteria-en", label: "Asteria (Default)", gender: "female", language: "en-US" },
    { value: "aura-luna-en", label: "Luna (ناعم)", gender: "female", language: "en-US" },
    { value: "aura-stella-en", label: "Stella", gender: "female", language: "en-US" },
    { value: "aura-hera-en", label: "Hera", gender: "female", language: "en-US" },
    // English - American Male
    { value: "aura-orion-en", label: "Orion", gender: "male", language: "en-US" },
    { value: "aura-arcas-en", label: "Arcas", gender: "male", language: "en-US" },
    { value: "aura-perseus-en", label: "Perseus", gender: "male", language: "en-US" },
    { value: "aura-orpheus-en", label: "Orpheus (دافئ)", gender: "male", language: "en-US" },
    { value: "aura-zeus-en", label: "Zeus (عميق)", gender: "male", language: "en-US" },
    // English - British
    { value: "aura-athena-en", label: "Athena (بريطاني)", gender: "female", language: "en-GB" },
    { value: "aura-helios-en", label: "Helios (بريطاني)", gender: "male", language: "en-GB" },
    // English - Irish
    { value: "aura-angus-en", label: "Angus (إيرلندي)", gender: "male", language: "en-IE" },
    // Aura 2 voices
    { value: "aura-2-thalia-en", label: "Thalia (Aura 2)", gender: "female", language: "en-US" },
  ],
};

// ============== STT PROVIDERS & MODELS ==============
const transcriberProviders = [
  { value: "deepgram", label: "Deepgram (Best for English) - $4.30/1K min" },
  { value: "groq", label: "Groq Whisper (Fastest!) - $0.04/hour" },
  { value: "openai", label: "OpenAI Whisper - $0.006/min" },
  { value: "azure", label: "Azure Speech - $16.67/1K min" },
  { value: "munsit", label: "Munsit (Best for Arabic!) 🇸🇦" },
];

// STT Models by provider
const sttModelsByProvider: Record<string, { value: string; label: string; price?: string }[]> = {
  deepgram: [
    { value: "nova-3", label: "Nova-3 (Latest - 53% more accurate)", price: "$4.30/1K min" },
    { value: "nova-2", label: "Nova-2 (Best for English)", price: "$4.30/1K min" },
    { value: "nova-2-meeting", label: "Nova-2 Meeting (للاجتماعات)", price: "$4.30/1K min" },
    { value: "nova-2-phonecall", label: "Nova-2 Phone Call (للمكالمات)", price: "$4.30/1K min" },
    { value: "nova-2-voicemail", label: "Nova-2 Voicemail (للرسائل)", price: "$4.30/1K min" },
    { value: "nova-2-finance", label: "Nova-2 Finance (للمالية)", price: "$4.30/1K min" },
    { value: "nova-2-conversationalai", label: "Nova-2 ConversationalAI (للوكلاء)", price: "$4.30/1K min" },
    { value: "nova", label: "Nova (الجيل الأول)", price: "$4.00/1K min" },
    { value: "whisper-large", label: "Whisper Large (للعربية)", price: "$4.80/1K min" },
    { value: "whisper-medium", label: "Whisper Medium", price: "$4.80/1K min" },
    { value: "whisper-small", label: "Whisper Small (سريع)", price: "$4.80/1K min" },
    { value: "whisper-tiny", label: "Whisper Tiny (الأسرع)", price: "$4.80/1K min" },
    { value: "flux", label: "Flux (Voice Agents - New!)", price: "-" },
  ],
  groq: [
    { value: "whisper-large-v3", label: "Whisper Large V3 (الأدق)", price: "Free tier" },
    { value: "whisper-large-v3-turbo", label: "Whisper Large V3 Turbo (216x faster!)", price: "$0.04/hour" },
  ],
  openai: [
    { value: "whisper-1", label: "Whisper-1 (Standard)", price: "$0.006/min" },
    { value: "gpt-4o-transcribe", label: "GPT-4o Transcribe (New 2025 - Most Accurate)", price: "-" },
    { value: "gpt-4o-mini-transcribe", label: "GPT-4o Mini Transcribe (Faster & Cheaper)", price: "-" },
  ],
  azure: [
    { value: "default", label: "Universal Language Model", price: "$16.67/1K min" },
    { value: "custom", label: "Custom Speech (Domain-specific)", price: "-" },
    { value: "whisper", label: "Azure Whisper", price: "-" },
  ],
  munsit: [
    { value: "munsit-1", label: "Munsit-1 (Best Arabic STT in the World!)", price: "Contact for pricing" },
  ],
};

const languages = [
  // Arabic dialects
  { value: "ar-SA", label: "العربية (سعودي)" },
  { value: "ar-EG", label: "العربية (مصري)" },
  { value: "ar-AE", label: "العربية (إماراتي)" },
  { value: "ar-BH", label: "العربية (بحريني)" },
  { value: "ar-DZ", label: "العربية (جزائري)" },
  { value: "ar-IQ", label: "العربية (عراقي)" },
  { value: "ar-JO", label: "العربية (أردني)" },
  { value: "ar-KW", label: "العربية (كويتي)" },
  { value: "ar-LB", label: "العربية (لبناني)" },
  { value: "ar-LY", label: "العربية (ليبي)" },
  { value: "ar-MA", label: "العربية (مغربي)" },
  { value: "ar-OM", label: "العربية (عماني)" },
  { value: "ar-PS", label: "العربية (فلسطيني)" },
  { value: "ar-QA", label: "العربية (قطري)" },
  { value: "ar-SY", label: "العربية (سوري)" },
  { value: "ar-TN", label: "العربية (تونسي)" },
  { value: "ar-YE", label: "العربية (يمني)" },
  // English
  { value: "en-US", label: "English (US)" },
  { value: "en-GB", label: "English (UK)" },
  { value: "en-AU", label: "English (Australia)" },
  // Other languages
  { value: "fr-FR", label: "Français" },
  { value: "de-DE", label: "Deutsch" },
  { value: "es-ES", label: "Español" },
  { value: "it-IT", label: "Italiano" },
  { value: "pt-BR", label: "Português (Brasil)" },
  { value: "ja-JP", label: "日本語" },
  { value: "ko-KR", label: "한국어" },
  { value: "zh-CN", label: "中文 (简体)" },
  { value: "hi-IN", label: "हिन्दी" },
  { value: "tr-TR", label: "Türkçe" },
];

const firstMessageModes = [
  { value: "assistant-speaks-first", label: "Assistant Speaks First" },
  { value: "user-speaks-first", label: "User Speaks First" },
  { value: "assistant-waits", label: "Assistant Waits for Greeting" },
];

export default function AssistantEditorPage() {
  const params = useParams();
  const router = useRouter();
  const isNew = params.id === "new";
  const [activeTab, setActiveTab] = React.useState("model");
  const [isSaving, setIsSaving] = React.useState(false);
  const [isExpandedPrompt, setIsExpandedPrompt] = React.useState(false);
  const [isPreviewPlaying, setIsPreviewPlaying] = React.useState(false);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);

  // Preview voice function
  const handlePreviewVoice = async () => {
    if (isPreviewPlaying) {
      // Stop current preview
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      setIsPreviewPlaying(false);
      return;
    }

    setIsPreviewPlaying(true);

    try {
      // Get TTS credentials from localStorage
      const creds = localStorage.getItem("provider_credentials");
      const credentials = creds ? JSON.parse(creds) : {};

      const provider = formData.voiceProvider;
      let apiKey = "";
      let region = "";

      switch (provider) {
        case "azure":
          apiKey = credentials.azure_tts?.api_key || "";
          region = credentials.azure_tts?.region || "eastus";
          break;
        case "elevenlabs":
          apiKey = credentials.elevenlabs?.api_key || "";
          break;
        case "openai":
          apiKey = credentials.openai_tts?.api_key || credentials.openai?.api_key || "";
          break;
      }

      if (!apiKey) {
        alert("Please configure TTS API key in Settings first");
        setIsPreviewPlaying(false);
        return;
      }

      // Sample preview text
      const previewText = formData.transcriberLanguage?.startsWith("ar")
        ? "مرحباً، كيف يمكنني مساعدتك اليوم؟"
        : "Hello, how can I help you today?";

      // Call backend TTS preview endpoint
      const response = await fetch("http://localhost:8000/api/voices/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: previewText,
          provider: provider,
          voice_id: formData.voiceId,
          api_key: apiKey,
          region: region,
        }),
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audioRef.current = audio;

        audio.onended = () => {
          setIsPreviewPlaying(false);
          URL.revokeObjectURL(url);
        };

        audio.onerror = () => {
          setIsPreviewPlaying(false);
          URL.revokeObjectURL(url);
        };

        await audio.play();
      } else {
        alert("Failed to preview voice. Check your API key and voice ID.");
        setIsPreviewPlaying(false);
      }
    } catch (error) {
      console.error("Preview error:", error);
      alert("Failed to preview voice");
      setIsPreviewPlaying(false);
    }
  };

  // Form state
  const [formData, setFormData] = React.useState({
    name: isNew ? "" : "Sales Agent",
    modelProvider: "anthropic",
    modelName: "claude-sonnet-4-20250514",
    temperature: 0.7,
    maxTokens: 1024,
    firstMessageMode: "assistant-speaks-first",
    firstMessage: "مرحبا! كيف يمكنني مساعدتك اليوم؟",
    systemPrompt: `أنت وكيل مبيعات محترف تعمل لصالح شركة متخصصة. مهمتك هي:

1. الترحيب بالعميل بطريقة ودية ومهنية
2. فهم احتياجات العميل بدقة
3. تقديم الحلول المناسبة
4. الإجابة على جميع الاستفسارات
5. المساعدة في إتمام عملية البيع

قواعد مهمة:
- تحدث بالعربية الفصحى السعودية
- كن مختصراً ومفيداً
- لا تقدم وعوداً كاذبة
- احترم خصوصية العميل`,
    voiceProvider: "elevenlabs",
    voiceId: "EXAVITQu4vr4xnSDxMaL",
    voiceSpeed: 1.0,
    voicePitch: 1.0,
    transcriberProvider: "deepgram",
    transcriberModel: "nova-2",
    transcriberLanguage: "ar-SA",
    endpointingMs: 500,
    summaryPrompt: "",
    successEvaluationPrompt: "",
    privacyEnabled: false,
    hipaaEnabled: false,
    voicemailDetection: true,
    maxDuration: 1800,
    silenceTimeout: 30,
    // Interruption settings
    interruptionEnabled: true,
    interruptionWordsThreshold: 0,  // 0 = immediate, up to 10 words
    // Voice Mode settings
    voiceMode: "pipeline" as "pipeline" | "realtime",  // pipeline or realtime
    realtimeProvider: "openai",
    realtimeModel: "gpt-4o-realtime-preview",
    realtimeVoice: "alloy",
  });

  const updateFormData = (field: string, value: unknown) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  // Mock assistants data for fallback
  const mockAssistantsData: Record<string, typeof formData & { id: string }> = {
    "1": {
      id: "1",
      name: "Sales Agent",
      modelProvider: "anthropic",
      modelName: "claude-sonnet-4-20250514",
      temperature: 0.7,
      maxTokens: 1024,
      firstMessageMode: "assistant-speaks-first",
      firstMessage: "مرحبا! كيف يمكنني مساعدتك اليوم؟",
      systemPrompt: `أنت وكيل مبيعات محترف تعمل لصالح شركة متخصصة. مهمتك هي:

1. الترحيب بالعميل بطريقة ودية ومهنية
2. فهم احتياجات العميل بدقة
3. تقديم الحلول المناسبة
4. الإجابة على جميع الاستفسارات
5. المساعدة في إتمام عملية البيع

قواعد مهمة:
- تحدث بالعربية الفصحى السعودية
- كن مختصراً ومفيداً
- لا تقدم وعوداً كاذبة
- احترم خصوصية العميل`,
      voiceProvider: "elevenlabs",
      voiceId: "EXAVITQu4vr4xnSDxMaL",
      voiceSpeed: 1.0,
      voicePitch: 1.0,
      transcriberProvider: "deepgram",
      transcriberModel: "nova-2",
      transcriberLanguage: "ar-SA",
      endpointingMs: 500,
      summaryPrompt: "",
      successEvaluationPrompt: "",
      privacyEnabled: false,
      hipaaEnabled: false,
      voicemailDetection: true,
      maxDuration: 1800,
      silenceTimeout: 30,
      interruptionEnabled: true,
      interruptionWordsThreshold: 0,
    },
    "2": {
      id: "2",
      name: "Support Agent",
      modelProvider: "openai",
      modelName: "gpt-4o",
      temperature: 0.5,
      maxTokens: 2048,
      firstMessageMode: "assistant-speaks-first",
      firstMessage: "Hello! How can I help you today?",
      systemPrompt: "You are a helpful support agent. Answer customer questions professionally and accurately.",
      voiceProvider: "azure",
      voiceId: "en-US-JennyNeural",
      voiceSpeed: 1.0,
      voicePitch: 1.0,
      transcriberProvider: "azure",
      transcriberModel: "default",
      transcriberLanguage: "en-US",
      endpointingMs: 500,
      summaryPrompt: "",
      successEvaluationPrompt: "",
      privacyEnabled: false,
      hipaaEnabled: false,
      voicemailDetection: true,
      maxDuration: 1800,
      silenceTimeout: 30,
      interruptionEnabled: true,
      interruptionWordsThreshold: 0,
    },
    "3": {
      id: "3",
      name: "Collection Agent - Arabic",
      modelProvider: "anthropic",
      modelName: "claude-3-5-haiku-20241022",
      temperature: 0.6,
      maxTokens: 1024,
      firstMessageMode: "assistant-speaks-first",
      firstMessage: "السلام عليكم، معك من شركة...",
      systemPrompt: "أنت وكيل تحصيل ديون محترف. تحدث بأسلوب مهني ومحترم.",
      voiceProvider: "elevenlabs",
      voiceId: "pNInz6obpgDQGcFmaJgB",
      voiceSpeed: 1.0,
      voicePitch: 1.0,
      transcriberProvider: "deepgram",
      transcriberModel: "nova-2",
      transcriberLanguage: "ar-SA",
      endpointingMs: 500,
      summaryPrompt: "",
      successEvaluationPrompt: "",
      privacyEnabled: false,
      hipaaEnabled: false,
      voicemailDetection: true,
      maxDuration: 1800,
      silenceTimeout: 30,
      interruptionEnabled: true,
      interruptionWordsThreshold: 0,
    },
  };

  // Load assistant data from localStorage on mount (with mock fallback)
  React.useEffect(() => {
    if (!isNew && params.id) {
      const saved = localStorage.getItem("assistants");
      let assistant = null;

      // First try localStorage
      if (saved) {
        try {
          const assistants = JSON.parse(saved);
          assistant = assistants[params.id as string];
        } catch (e) {
          console.error("Failed to load assistant from localStorage:", e);
        }
      }

      // Fallback to mock data if not found in localStorage
      if (!assistant && mockAssistantsData[params.id as string]) {
        assistant = mockAssistantsData[params.id as string];
        console.log("📋 Loaded mock assistant:", params.id);
      }

      if (assistant) {
        // Merge with defaults to ensure all fields exist
        setFormData(prev => ({
          ...prev,
          ...assistant,
        }));
        console.log("✅ Assistant loaded:", assistant.name);
      }
    }
  }, [isNew, params.id]);

  const handleSave = async () => {
    setIsSaving(true);

    try {
      // Save to localStorage
      const saved = localStorage.getItem("assistants");
      const assistants = saved ? JSON.parse(saved) : {};

      const assistantId = isNew ? `assistant-${Date.now()}` : params.id;
      assistants[assistantId as string] = {
        ...formData,
        id: assistantId,
        updatedAt: new Date().toISOString(),
        createdAt: assistants[assistantId as string]?.createdAt || new Date().toISOString(),
      };

      localStorage.setItem("assistants", JSON.stringify(assistants));

      // Also save as test_assistant for test-call to use
      localStorage.setItem("test_assistant", JSON.stringify({
        id: assistantId,
        name: formData.name,
        model_provider: formData.modelProvider,
        model_name: formData.modelName,
        system_prompt: formData.systemPrompt,
        first_message: formData.firstMessage,
        first_message_mode: formData.firstMessageMode,
        temperature: formData.temperature,
        max_tokens: formData.maxTokens,
        voice_provider: formData.voiceProvider,
        voice_id: formData.voiceId,
        voice_speed: formData.voiceSpeed,
        transcriber_provider: formData.transcriberProvider,
        transcriber_model: formData.transcriberModel,
        transcriber_language: formData.transcriberLanguage,
        // Stop Speaking Plan (barge-in/interruption settings)
        stop_speaking_plan: {
          enable_interruption: formData.interruptionEnabled,
          interruption_words: formData.interruptionWordsThreshold,
        },
        // Voice Mode settings
        voice_mode: formData.voiceMode,
        realtime_provider: formData.realtimeProvider,
        realtime_model: formData.realtimeModel,
        realtime_voice: formData.realtimeVoice,
      }));

      console.log("✅ Assistant saved:", assistantId);
    } catch (e) {
      console.error("Failed to save assistant:", e);
    }

    setIsSaving(false);
    router.push("/assistants");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => router.push("/assistants")}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <Input
              value={formData.name}
              onChange={(e) => updateFormData("name", e.target.value)}
              placeholder="Assistant Name"
              className="text-xl font-semibold border-0 bg-transparent p-0 h-auto focus:ring-0"
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => {
              // Save current form data before redirecting
              localStorage.setItem("test_assistant", JSON.stringify({
                id: params.id,
                name: formData.name,
                model_provider: formData.modelProvider,
                model_name: formData.modelName,
                system_prompt: formData.systemPrompt,
                first_message: formData.firstMessage,
                first_message_mode: formData.firstMessageMode,
                temperature: formData.temperature,
                max_tokens: formData.maxTokens,
                voice_provider: formData.voiceProvider,
                voice_id: formData.voiceId,
                voice_speed: formData.voiceSpeed,
                transcriber_provider: formData.transcriberProvider,
                transcriber_model: formData.transcriberModel,
                transcriber_language: formData.transcriberLanguage,
                // Stop Speaking Plan (barge-in/interruption settings)
                stop_speaking_plan: {
                  enable_interruption: formData.interruptionEnabled,
                  interruption_words: formData.interruptionWordsThreshold,
                },
                // Voice Mode settings
                voice_mode: formData.voiceMode,
                realtime_provider: formData.realtimeProvider,
                realtime_model: formData.realtimeModel,
                realtime_voice: formData.realtimeVoice,
              }));
              router.push(`/live-call?assistant=${params.id}`);
            }}
          >
            <Phone className="h-4 w-4 mr-2" />
            Test Call
          </Button>
          <Button onClick={handleSave} isLoading={isSaving}>
            <Save className="h-4 w-4 mr-2" />
            Save
          </Button>
        </div>
      </div>

      {/* Voice Mode Selection - TOP LEVEL */}
      <Card className="border-2 border-primary/20 bg-gradient-to-r from-primary/5 to-transparent">
        <CardContent className="pt-6">
          <div className="flex items-center gap-4 mb-4">
            <div className="text-lg font-semibold">🎯 Voice Processing Mode</div>
            <Badge variant={formData.voiceMode === "realtime" ? "default" : "secondary"}>
              {formData.voiceMode === "realtime" ? "⚡ Realtime" : "🔧 Pipeline"}
            </Badge>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {voiceModes.map((mode) => (
              <div
                key={mode.value}
                onClick={() => updateFormData("voiceMode", mode.value)}
                className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                  formData.voiceMode === mode.value
                    ? "border-primary bg-primary/10 shadow-lg"
                    : "border-border hover:border-primary/50 hover:bg-muted/50"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{mode.value === "pipeline" ? "🔧" : "⚡"}</span>
                  <div>
                    <div className="font-semibold">{mode.label}</div>
                    <div className="text-sm text-muted-foreground">{mode.description}</div>
                  </div>
                </div>
                {mode.value === "realtime" && (
                  <Badge className="mt-2" variant="secondary">Lowest Latency ~300ms</Badge>
                )}
                {mode.value === "pipeline" && (
                  <Badge className="mt-2" variant="outline">Full Control</Badge>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full justify-start overflow-x-auto">
          <TabsTrigger value="model">
            <Bot className="h-4 w-4 mr-2" />
            {formData.voiceMode === "realtime" ? "Realtime Config" : "Model"}
          </TabsTrigger>
          {formData.voiceMode === "pipeline" && (
            <>
              <TabsTrigger value="voice">
                <Volume2 className="h-4 w-4 mr-2" />
                Voice
              </TabsTrigger>
              <TabsTrigger value="transcriber">
                <Mic className="h-4 w-4 mr-2" />
                Transcriber
              </TabsTrigger>
            </>
          )}
          <TabsTrigger value="tools">
            <Wrench className="h-4 w-4 mr-2" />
            Tools
          </TabsTrigger>
          <TabsTrigger value="analysis">
            <BarChart3 className="h-4 w-4 mr-2" />
            Analysis
          </TabsTrigger>
          <TabsTrigger value="advanced">
            <Settings className="h-4 w-4 mr-2" />
            Advanced
          </TabsTrigger>
          <TabsTrigger value="compliance">
            <Shield className="h-4 w-4 mr-2" />
            Compliance
          </TabsTrigger>
        </TabsList>

        {/* Model Tab */}
        <TabsContent value="model">
          {/* REALTIME MODE CONFIG */}
          {formData.voiceMode === "realtime" ? (
            <div className="grid gap-6 md:grid-cols-2">
              {/* Realtime Provider Selection */}
              <Card className="md:col-span-2">
                <CardHeader>
                  <CardTitle>⚡ Realtime Provider</CardTitle>
                  <CardDescription>Choose your speech-to-speech API provider</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {realtimeProviders.map((provider) => (
                      <div
                        key={provider.value}
                        onClick={() => {
                          updateFormData("realtimeProvider", provider.value);
                          const models = realtimeModelsByProvider[provider.value] || [];
                          if (models.length > 0) updateFormData("realtimeModel", models[0].value);
                          const voices = realtimeVoicesByProvider[provider.value] || [];
                          if (voices.length > 0) updateFormData("realtimeVoice", voices[0].value);
                        }}
                        className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                          formData.realtimeProvider === provider.value
                            ? "border-primary bg-primary/10 shadow-lg"
                            : "border-border hover:border-primary/50"
                        }`}
                      >
                        <div className="font-semibold text-sm">{provider.label}</div>
                        <div className="text-xs text-muted-foreground mt-1">{provider.description}</div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Realtime Model & Voice */}
              <Card>
                <CardHeader>
                  <CardTitle>Model & Voice</CardTitle>
                  <CardDescription>Configure realtime model settings</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Model</label>
                    <Select
                      value={formData.realtimeModel}
                      onChange={(v) => updateFormData("realtimeModel", v)}
                      options={(realtimeModelsByProvider[formData.realtimeProvider] || []).map(m => ({
                        value: m.value,
                        label: m.label,
                      }))}
                    />
                    {(() => {
                      const model = (realtimeModelsByProvider[formData.realtimeProvider] || []).find(m => m.value === formData.realtimeModel);
                      return model ? <div className="text-xs text-muted-foreground">{model.description}</div> : null;
                    })()}
                  </div>

                  {(realtimeVoicesByProvider[formData.realtimeProvider] || []).length > 0 && (
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Voice</label>
                      <Select
                        value={formData.realtimeVoice}
                        onChange={(v) => updateFormData("realtimeVoice", v)}
                        options={(realtimeVoicesByProvider[formData.realtimeProvider] || []).map(v => ({
                          value: v.value,
                          label: v.label,
                        }))}
                      />
                    </div>
                  )}

                  {formData.realtimeProvider === "groq" && (
                    <div className="p-3 bg-yellow-500/10 rounded-lg border border-yellow-500/20">
                      <div className="text-sm text-yellow-600 dark:text-yellow-400">
                        ⚠️ Groq uses ultra-fast LLM + separate TTS. Configure TTS voice in Voice tab.
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* First Message */}
              <Card>
                <CardHeader>
                  <CardTitle>First Message</CardTitle>
                  <CardDescription>How the conversation starts</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Mode</label>
                    <Select
                      value={formData.firstMessageMode}
                      onChange={(v) => updateFormData("firstMessageMode", v)}
                      options={firstMessageModes}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">First Message</label>
                    <Textarea
                      value={formData.firstMessage}
                      onChange={(e) => updateFormData("firstMessage", e.target.value)}
                      placeholder="Enter the assistant's first message..."
                      className="min-h-[100px]"
                    />
                  </div>
                </CardContent>
              </Card>

              {/* System Prompt */}
              <Card className="md:col-span-2">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>System Prompt</CardTitle>
                      <CardDescription>Instructions for the assistant</CardDescription>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => setIsExpandedPrompt(!isExpandedPrompt)}>
                      <Maximize2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">قالب جاهز</label>
                    <Select
                      value="custom"
                      onChange={(v) => {
                        const template = systemPromptTemplates.find(t => t.value === v);
                        if (template && template.prompt) {
                          updateFormData("systemPrompt", template.prompt);
                        }
                      }}
                      options={systemPromptTemplates.map(t => ({
                        value: t.value,
                        label: t.label,
                      }))}
                    />
                  </div>
                  <Textarea
                    value={formData.systemPrompt}
                    onChange={(e) => updateFormData("systemPrompt", e.target.value)}
                    placeholder="Enter the system prompt..."
                    className={isExpandedPrompt ? "min-h-[400px]" : "min-h-[200px]"}
                    dir="auto"
                  />
                </CardContent>
              </Card>
            </div>
          ) : (
            /* PIPELINE MODE CONFIG */
            <div className="grid gap-6 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>LLM Configuration</CardTitle>
                  <CardDescription>Configure the language model</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Provider</label>
                    <Select
                      value={formData.modelProvider}
                      onChange={(v) => {
                        updateFormData("modelProvider", v);
                        updateFormData("modelName", modelsByProvider[v]?.[0]?.value || "");
                      }}
                      options={modelProviders}
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">Model</label>
                    <Select
                      value={formData.modelName}
                      onChange={(v) => updateFormData("modelName", v)}
                      options={(modelsByProvider[formData.modelProvider] || []).map(m => ({
                        value: m.value,
                        label: m.label,
                      }))}
                    />
                    {(() => {
                      const selectedModel = (modelsByProvider[formData.modelProvider] || []).find(m => m.value === formData.modelName);
                      if (selectedModel) {
                        return (
                          <div className="flex gap-2 mt-2 flex-wrap">
                            {selectedModel.price && <Badge variant="outline">💰 {selectedModel.price}</Badge>}
                            {selectedModel.context && <Badge variant="outline">📄 {selectedModel.context}</Badge>}
                          </div>
                        );
                      }
                      return null;
                    })()}
                  </div>

                  <Slider
                    label="Temperature"
                    value={formData.temperature}
                    onChange={(v) => updateFormData("temperature", v)}
                    min={0}
                    max={1}
                    step={0.1}
                  />

                  <div className="space-y-2">
                    <label className="text-sm font-medium">Max Tokens</label>
                    <Input
                      type="number"
                      value={formData.maxTokens}
                      onChange={(e) => updateFormData("maxTokens", parseInt(e.target.value))}
                    />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>First Message</CardTitle>
                  <CardDescription>How the conversation starts</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Mode</label>
                    <Select
                      value={formData.firstMessageMode}
                      onChange={(v) => updateFormData("firstMessageMode", v)}
                      options={firstMessageModes}
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">First Message</label>
                    <Textarea
                      value={formData.firstMessage}
                      onChange={(e) => updateFormData("firstMessage", e.target.value)}
                      placeholder="Enter the assistant's first message..."
                      className="min-h-[100px]"
                    />
                  </div>
                </CardContent>
              </Card>

              <Card className="md:col-span-2">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>System Prompt</CardTitle>
                      <CardDescription>Instructions for the assistant</CardDescription>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setIsExpandedPrompt(!isExpandedPrompt)}
                    >
                      <Maximize2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">قالب جاهز</label>
                    <Select
                      value="custom"
                      onChange={(v) => {
                        const template = systemPromptTemplates.find(t => t.value === v);
                        if (template && template.prompt) {
                          updateFormData("systemPrompt", template.prompt);
                        }
                      }}
                      options={systemPromptTemplates.map(t => ({
                        value: t.value,
                        label: t.label,
                      }))}
                    />
                  </div>
                  <Textarea
                    value={formData.systemPrompt}
                    onChange={(e) => updateFormData("systemPrompt", e.target.value)}
                    placeholder="Enter the system prompt..."
                    className={isExpandedPrompt ? "min-h-[400px]" : "min-h-[200px]"}
                    dir="auto"
                  />
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* Voice Tab - Only shown in Pipeline mode */}
        <TabsContent value="voice">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Voice Provider</CardTitle>
                <CardDescription>Select the TTS provider</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Provider</label>
                  <Select
                    value={formData.voiceProvider}
                    onChange={(v) => {
                      updateFormData("voiceProvider", v);
                      // Auto-select first voice for this provider
                      const voices = voicesByProvider[v] || [];
                      if (voices.length > 0) {
                        updateFormData("voiceId", voices[0].value);
                      }
                    }}
                    options={voiceProviders}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Voice</label>
                  <Select
                    value={formData.voiceId}
                    onChange={(v) => updateFormData("voiceId", v)}
                    options={(voicesByProvider[formData.voiceProvider] || []).map(v => ({
                      value: v.value,
                      label: v.label,
                    }))}
                  />
                  {/* Show voice details */}
                  {(() => {
                    const selectedVoice = (voicesByProvider[formData.voiceProvider] || []).find(v => v.value === formData.voiceId);
                    if (selectedVoice) {
                      return (
                        <div className="flex gap-2 mt-2">
                          <Badge variant="outline">{selectedVoice.gender}</Badge>
                          <Badge variant="outline">{selectedVoice.language}</Badge>
                        </div>
                      );
                    }
                    return null;
                  })()}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Custom Voice ID</label>
                  <Input
                    value={formData.voiceId}
                    onChange={(e) => updateFormData("voiceId", e.target.value)}
                    placeholder="Or enter custom voice ID"
                  />
                </div>

                <Button
                  variant="outline"
                  className="w-full"
                  onClick={handlePreviewVoice}
                  disabled={!formData.voiceId}
                >
                  {isPreviewPlaying ? (
                    <>
                      <Square className="h-4 w-4 mr-2" />
                      Stop Preview
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-2" />
                      Preview Voice
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Voice Settings</CardTitle>
                <CardDescription>Fine-tune voice output</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Slider
                  label="Speed"
                  value={formData.voiceSpeed}
                  onChange={(v) => updateFormData("voiceSpeed", v)}
                  min={0.5}
                  max={2}
                  step={0.1}
                />

                <Slider
                  label="Pitch"
                  value={formData.voicePitch}
                  onChange={(v) => updateFormData("voicePitch", v)}
                  min={0.5}
                  max={2}
                  step={0.1}
                />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Transcriber Tab */}
        <TabsContent value="transcriber">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Speech-to-Text</CardTitle>
                <CardDescription>Configure the transcription service</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Provider</label>
                  <Select
                    value={formData.transcriberProvider}
                    onChange={(v) => {
                      updateFormData("transcriberProvider", v);
                      // Auto-select first model for this provider
                      const models = sttModelsByProvider[v] || [];
                      if (models.length > 0) {
                        updateFormData("transcriberModel", models[0].value);
                      }
                    }}
                    options={transcriberProviders}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Model</label>
                  <Select
                    value={formData.transcriberModel || (sttModelsByProvider[formData.transcriberProvider]?.[0]?.value || "")}
                    onChange={(v) => updateFormData("transcriberModel", v)}
                    options={(sttModelsByProvider[formData.transcriberProvider] || []).map(m => ({
                      value: m.value,
                      label: m.label,
                    }))}
                  />
                  {/* Show model price */}
                  {(() => {
                    const selectedModel = (sttModelsByProvider[formData.transcriberProvider] || []).find(m => m.value === formData.transcriberModel);
                    if (selectedModel?.price) {
                      return (
                        <div className="flex gap-2 mt-2">
                          <Badge variant="outline">{selectedModel.price}</Badge>
                        </div>
                      );
                    }
                    return null;
                  })()}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Language</label>
                  <Select
                    value={formData.transcriberLanguage}
                    onChange={(v) => updateFormData("transcriberLanguage", v)}
                    options={languages}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Timing Settings</CardTitle>
                <CardDescription>Configure speech detection</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Endpointing (ms)</label>
                  <Input
                    type="number"
                    value={formData.endpointingMs}
                    onChange={(e) => updateFormData("endpointingMs", parseInt(e.target.value))}
                  />
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Time to wait before considering speech ended
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Tools Tab */}
        <TabsContent value="tools">
          <Card>
            <CardHeader>
              <CardTitle>Tools</CardTitle>
              <CardDescription>Add tools for the assistant to use during calls</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Wrench className="h-12 w-12 text-[var(--muted-foreground)] mb-4" />
                <h3 className="text-lg font-semibold mb-2">No tools added</h3>
                <p className="text-[var(--muted-foreground)] mb-4">
                  Add tools from the library or create custom ones
                </p>
                <Button>
                  Add Tool
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Analysis Tab */}
        <TabsContent value="analysis">
          <div className="grid gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Call Summary</CardTitle>
                <CardDescription>Prompt to generate call summaries</CardDescription>
              </CardHeader>
              <CardContent>
                <Textarea
                  value={formData.summaryPrompt}
                  onChange={(e) => updateFormData("summaryPrompt", e.target.value)}
                  placeholder="Enter a prompt to generate call summaries..."
                  className="min-h-[150px]"
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Success Evaluation</CardTitle>
                <CardDescription>Prompt to evaluate call success</CardDescription>
              </CardHeader>
              <CardContent>
                <Textarea
                  value={formData.successEvaluationPrompt}
                  onChange={(e) => updateFormData("successEvaluationPrompt", e.target.value)}
                  placeholder="Enter a prompt to evaluate if the call was successful..."
                  className="min-h-[150px]"
                />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Advanced Tab */}
        <TabsContent value="advanced">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Call Settings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Max Duration (seconds)</label>
                  <Input
                    type="number"
                    value={formData.maxDuration}
                    onChange={(e) => updateFormData("maxDuration", parseInt(e.target.value))}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Silence Timeout (seconds)</label>
                  <Input
                    type="number"
                    value={formData.silenceTimeout}
                    onChange={(e) => updateFormData("silenceTimeout", parseInt(e.target.value))}
                  />
                </div>

                <Switch
                  checked={formData.voicemailDetection}
                  onCheckedChange={(v) => updateFormData("voicemailDetection", v)}
                  label="Voicemail Detection"
                  description="Detect and handle voicemail greetings"
                />
              </CardContent>
            </Card>

            {/* Stop Speaking Plan - Interruption Settings */}
            <Card>
              <CardHeader>
                <CardTitle>Stop Speaking Plan</CardTitle>
                <CardDescription>Configure when the assistant should stop talking</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Switch
                  checked={formData.interruptionEnabled}
                  onCheckedChange={(v) => updateFormData("interruptionEnabled", v)}
                  label="Enable Interruption"
                  description="Allow customer to interrupt the assistant while speaking"
                />

                {formData.interruptionEnabled && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-[var(--muted-foreground)]">#</span>
                      <div className="flex-1">
                        <label className="text-sm font-medium">Number of words</label>
                        <p className="text-xs text-[var(--muted-foreground)]">
                          Words the customer must say before the assistant stops talking
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="flex-1">
                        <Slider
                          value={formData.interruptionWordsThreshold}
                          onChange={(v) => updateFormData("interruptionWordsThreshold", v)}
                          min={0}
                          max={10}
                          step={1}
                        />
                      </div>
                      <div className="w-12 h-10 flex items-center justify-center border rounded-md bg-[var(--muted)] text-sm font-medium">
                        {formData.interruptionWordsThreshold}
                      </div>
                    </div>
                    <p className="text-xs text-[var(--muted-foreground)]">
                      {formData.interruptionWordsThreshold === 0
                        ? "Immediate: Assistant stops as soon as customer speaks"
                        : `Wait for ${formData.interruptionWordsThreshold} word${formData.interruptionWordsThreshold > 1 ? 's' : ''} before stopping`
                      }
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Compliance Tab */}
        <TabsContent value="compliance">
          <Card>
            <CardHeader>
              <CardTitle>Compliance Settings</CardTitle>
              <CardDescription>Configure privacy and compliance options</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Switch
                checked={formData.privacyEnabled}
                onCheckedChange={(v) => updateFormData("privacyEnabled", v)}
                label="Privacy Mode"
                description="Redact sensitive information from transcripts and logs"
              />

              <Switch
                checked={formData.hipaaEnabled}
                onCheckedChange={(v) => updateFormData("hipaaEnabled", v)}
                label="HIPAA Compliance"
                description="Enable HIPAA-compliant data handling"
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
