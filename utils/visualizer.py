import matplotlib.pyplot as plt
from io import BytesIO
from utils.text_processor import ArabicTextProcessor

class PerformanceVisualizer:
    def __init__(self):
        self.processor = ArabicTextProcessor()

    def generate_trend_chart(self, history_scores):
        """
        توليد رسم بياني خطي يوضح اتجاه مشاركة الطلاب.
        """
        if not history_scores:
            return None

        plt.figure(figsize=(8, 4))
        # رسم الخط باللون الأخضر المميز لنظامك
        plt.plot(history_scores, marker='o', linestyle='-', color='#17A589', linewidth=2, markersize=8)
        
        # معالجة العناوين بالعربية
        title = self.processor.format_text("مخطط تقدم مشاركة الطلاب")
        ylabel = self.processor.format_text("التقييم (1-3)")
        xlabel = self.processor.format_text("الحصص الأخيرة")
        
        plt.title(title)
        plt.ylabel(ylabel)
        plt.xlabel(xlabel)
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.ylim(0, 4) # لأن أعلى تقييم هو 3 (ممتاز)

        # حفظ الرسم البياني كصورة في الذاكرة
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf