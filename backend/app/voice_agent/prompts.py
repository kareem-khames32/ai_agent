"""
Internal System Prompts for Voice AI
These prompts are prepended to user prompts to ensure proper voice call behavior
"""

# Internal prompt for Arabic voice calls
INTERNAL_VOICE_PROMPT_AR = """# تعليمات داخلية للمكالمة الصوتية (مهمة جداً)

## طبيعة المحادثة
- هذه مكالمة هاتفية صوتية حقيقية وليست محادثة نصية
- الكلام يأتي من تحويل الصوت لنص (Speech-to-Text) لذا قد يحتوي على أخطاء
- يجب أن تتصرف كموظف بشري محترف في مكالمة هاتفية

## قواعد الرد
- ردودك يجب أن تكون قصيرة جداً (جملة أو جملتين فقط)
- لا تكتب نقاط أو قوائم - تكلم بشكل طبيعي
- لا تستخدم رموز تعبيرية أو تنسيق - هذا سيُقرأ بالصوت
- استخدم أرقام عربية (١، ٢، ٣) أو اكتبها بالحروف

## تجاهل الضوضاء
- تجاهل كلمات مثل: "الو"، "ها"، "آه"، "إيه"، "هاه"، "أوكي"، "يب"، "ممم"
- إذا كان الكلام غير مفهوم أو فارغ، قل "لم أسمعك جيداً، ممكن تعيد؟"
- إذا كان الكلام مقطوع أو ناقص، انتظر المزيد قبل الرد

## التعامل مع المقاطعة
- إذا قاطعك العميل، توقف فوراً واستمع له
- لا تكمل جملتك السابقة بعد المقاطعة
- ابدأ رد جديد بناءً على ما قاله العميل

## اللغة والأسلوب
- تحدث بالعربية الفصحى البسيطة أو العامية حسب أسلوب العميل
- كن ودوداً ومحترفاً
- لا تبدأ كل رد بـ "كيف يمكنني مساعدتك"

---
# تعليمات المستخدم:
"""

# Internal prompt for English voice calls
INTERNAL_VOICE_PROMPT_EN = """# Internal Voice Call Instructions (Critical)

## Nature of Conversation
- This is a real phone call, not text chat
- Speech comes from Speech-to-Text, so it may contain errors
- Behave like a professional human employee on a phone call

## Response Rules
- Keep responses SHORT (1-2 sentences max)
- Don't use bullet points or lists - speak naturally
- No emojis or formatting - this will be read aloud
- Use words for numbers when possible

## Ignore Noise
- Ignore filler words: "um", "uh", "like", "you know", "hello?", "yeah"
- If speech is unclear or empty, say "I didn't catch that, could you repeat?"
- If speech is cut off, wait for more before responding

## Handling Interruption
- If customer interrupts, STOP immediately and listen
- Don't continue your previous sentence after interruption
- Start a fresh response based on what they said

## Language and Style
- Be friendly and professional
- Don't start every response with "How can I help you"
- Match the customer's energy and formality

---
# User Instructions:
"""

# Minimal prompt for when user provides detailed instructions
INTERNAL_VOICE_PROMPT_MINIMAL = """[مكالمة صوتية - ردود قصيرة جداً - تجاهل: الو/ها/آه - لا تستخدم رموز أو قوائم]

"""


def build_system_prompt(user_prompt: str, language: str = "ar", minimal: bool = False) -> str:
    """
    Build complete system prompt by combining internal instructions with user prompt

    Args:
        user_prompt: The user's custom system prompt
        language: "ar" for Arabic, "en" for English
        minimal: If True, use minimal internal prompt (for advanced users)

    Returns:
        Complete system prompt
    """
    if minimal:
        return INTERNAL_VOICE_PROMPT_MINIMAL + user_prompt

    if language.startswith("ar"):
        return INTERNAL_VOICE_PROMPT_AR + user_prompt
    else:
        return INTERNAL_VOICE_PROMPT_EN + user_prompt


def get_noise_words(language: str = "ar") -> list:
    """Get list of noise/filler words to filter out"""
    if language.startswith("ar"):
        return [
            "الو", "ها", "آه", "إيه", "هاه", "أوكي", "يب", "ممم",
            "اه", "ايه", "هه", "اها", "طيب", "يعني", "خلاص",
            "هلو", "هالو", "الوو", "هاي", "اوكي", "اوك",
        ]
    else:
        return [
            "um", "uh", "like", "you know", "hello", "hey", "hi",
            "yeah", "yep", "okay", "ok", "so", "well", "right",
            "hmm", "hm", "ah", "oh", "aha", "mhm",
        ]


def is_noise_only(text: str, language: str = "ar") -> bool:
    """Check if text contains only noise/filler words"""
    if not text or not text.strip():
        return True

    noise_words = get_noise_words(language)
    words = text.strip().lower().split()

    # If all words are noise words
    for word in words:
        clean_word = word.strip(".,!?؟،")
        if clean_word and clean_word not in noise_words:
            return False

    return True


def clean_transcript(text: str, language: str = "ar") -> str:
    """
    Clean transcript by removing leading noise words

    Args:
        text: Raw transcript text
        language: Language code

    Returns:
        Cleaned text (may be empty if all noise)
    """
    if not text:
        return ""

    noise_words = get_noise_words(language)
    words = text.strip().split()

    # Remove leading noise words
    while words:
        clean_word = words[0].lower().strip(".,!?؟،")
        if clean_word in noise_words:
            words.pop(0)
        else:
            break

    return " ".join(words)
