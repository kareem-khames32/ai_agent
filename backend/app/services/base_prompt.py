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
            now = datetime.now(tz.utc)
    else:
        now = datetime.now(tz.utc)

    arabic_days = {0: "الإثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس", 4: "الجمعة", 5: "السبت", 6: "الأحد"}
    arabic_months = {1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"}

    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "day_name": arabic_days.get(now.weekday(), ""),
        "day": now.day,
        "month": now.month,
        "month_name": arabic_months.get(now.month, ""),
        "year": now.year,
    }


def build_base_system_prompt(timezone: str = "Africa/Cairo", language: str = "ar") -> str:
    """Build minimal base system prompt for fast LLM response."""
    dt = get_current_datetime_info(timezone)

    # 🚀 ULTRA-MINIMAL prompt for fastest first token
    base_prompt = f"""[الآن: {dt['day_name']} {dt['day']}/{dt['month']} - {dt['time']}]
مكالمة تليفون حية. كلامك مختصر وطبيعي. لو مش فاهم قول "ممكن تعيد؟"

"""
    return base_prompt


def combine_prompts(user_prompt: Optional[str], timezone: str = "Africa/Cairo", language: str = "ar") -> str:
    """Combine base prompt with user's custom prompt."""
    base = build_base_system_prompt(timezone=timezone, language=language)
    return base + (user_prompt or "أنت مساعد صوتي ذكي. ساعد العميل.")
