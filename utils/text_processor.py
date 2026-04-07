import arabic_reshaper
from bidi.algorithm import get_display

class ArabicTextProcessor:
    @staticmethod
    def format_text(text: str) -> str:
        """
        إعادة تشكيل النص العربي وعكسه ليظهر بشكل صحيح في المكتبات التي لا تدعم العربية افتراضياً.
        مستوحى من منطق المعالجة في الكود الأصلي.
        """
        if not text or not isinstance(text, str):
            return ""
        try:
            # 1. إعادة تشكيل الحروف (Reshaping)
            reshaped_text = arabic_reshaper.reshape(text)
            # 2. عكس الاتجاه (Bidi)
            bidi_text = get_display(reshaped_text)
            if not isinstance(bidi_text, str):
                bidi_text = bidi_text.decode('utf-8')
            return bidi_text
        except Exception as e:
            print(f"Error in text processing: {e}")
            return text
