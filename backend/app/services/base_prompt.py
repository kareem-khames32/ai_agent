"""
Base system prompt builder for voice AI agents.
Contains essential behaviors that all agents should have.
"""
from datetime import datetime, timezone as tz
from typing import Optional

# Try to use zoneinfo (Python 3.9+), fallback to basic UTC
try:
    from zoneinfo import ZoneInfo
    HAS_ZONEINFO = True
except ImportError:
    HAS_ZONEINFO = False


def get_current_datetime_info(timezone: str = "Africa/Cairo") -> dict:
    """Get current date/time information for the specified timezone."""
    if HAS_ZONEINFO:
        try:
            zone = ZoneInfo(timezone)
            now = datetime.now(zone)
        except Exception:
            # Fallback to UTC
            now = datetime.now(tz.utc)
    else:
        # No zoneinfo - use UTC
        now = datetime.now(tz.utc)

    # Arabic day names
    arabic_days = {
        0: "الإثنين",
        1: "الثلاثاء",
        2: "الأربعاء",
        3: "الخميس",
        4: "الجمعة",
        5: "السبت",
        6: "الأحد"
    }

    # Arabic month names
    arabic_months = {
        1: "يناير",
        2: "فبراير",
        3: "مارس",
        4: "أبريل",
        5: "مايو",
        6: "يونيو",
        7: "يوليو",
        8: "أغسطس",
        9: "سبتمبر",
        10: "أكتوبر",
        11: "نوفمبر",
        12: "ديسمبر"
    }

    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "day_name": arabic_days.get(now.weekday(), now.strftime("%A")),
        "day": now.day,
        "month": now.month,
        "month_name": arabic_months.get(now.month, now.strftime("%B")),
        "year": now.year,
        "timezone": timezone,
    }


def build_base_system_prompt(
    timezone: str = "Africa/Cairo",
    language: str = "ar"
) -> str:
    """
    Build the base system prompt with essential behaviors.
    This is prepended to the user's custom prompt.
    """
    dt = get_current_datetime_info(timezone)

    base_prompt = f"""## معلومات أساسية عن المكالمة

**التاريخ والوقت الحالي:**
- التاريخ: {dt['day_name']} {dt['day']} {dt['month_name']} {dt['year']}
- الوقت: {dt['time']}
- المنطقة الزمنية: {timezone}

**حساب التواريخ:**
- اليوم: {dt['day_name']} {dt['day']}/{dt['month']}/{dt['year']}
- بكرة/غداً: اليوم التالي
- بعد بكرة: بعد يومين من اليوم
- الأسبوع الجاي: بعد 7 أيام

---

## قواعد أساسية للمكالمة الصوتية

### 1. أنت في مكالمة هاتفية حية (Live Call)
- تذكر دائماً أنك تتحدث مع شخص حقيقي عبر الهاتف
- ردودك يجب أن تكون طبيعية ومختصرة كأنك تتكلم في تليفون
- لا تستخدم formatting أو bullet points - تكلم بشكل طبيعي
- لا تقول "كمساعد ذكي" أو "كنموذج لغوي" - أنت موظف حقيقي

### 2. التعامل مع مشاكل الصوت
- إذا كان صوت العميل واطي أو مش واضح، قول: "معلش ممكن تعلي صوتك شوية؟"
- إذا سمعت ضوضاء أو كلام مش مفهوم، قول: "آسف مسمعتش، ممكن تعيد تاني؟"
- تجاهل الضوضاء الخلفية أو الأصوات العشوائية ولا ترد عليها
- إذا سمعت كلمة واحدة غريبة بدون سياق، انتظر أو اسأل "معلش، قولت إيه؟"

### 3. تذكر المحادثة (Conversation History)
- تذكر كل ما قاله العميل من بداية المكالمة
- إذا قال العميل "قولتلك من شوية كذا" - ارجع للمحادثة السابقة
- لا تنسى الأرقام أو التفاصيل التي ذكرها العميل
- إذا كنت في تفاوض، تذكر آخر عرض وصلتوله

### 4. العمليات الحسابية
- احسب بدقة أي أرقام أو أسعار
- إذا طلب العميل حساب، قم به بشكل صحيح
- تأكد من الأرقام قبل ذكرها
- مثال: "يعني 3 قطع × 50 جنيه = 150 جنيه"

### 5. أسلوب الكلام
- استخدم العامية المصرية أو اللهجة المناسبة للعميل
- كن ودود وطبيعي
- لا تطول في الكلام - اختصر
- استخدم كلمات مثل "تمام"، "حاضر"، "أكيد"، "طبعاً"

---

## التعليمات الخاصة بالوكيل:

"""

    return base_prompt


def combine_prompts(
    user_prompt: Optional[str],
    timezone: str = "Africa/Cairo",
    language: str = "ar"
) -> str:
    """
    Combine base prompt with user's custom prompt.
    """
    base = build_base_system_prompt(timezone=timezone, language=language)

    if user_prompt:
        return base + user_prompt
    else:
        return base + "أنت مساعد صوتي ذكي. ساعد العميل بأفضل طريقة ممكنة."
