import matplotlib
import matplotlib.pyplot as plt
from io import BytesIO
from utils.text_processor import ArabicTextProcessor

matplotlib.use('Agg')  # استخدام الخلفية غير التفاعلية لتجنب مشاكل العرض في بيئات السيرفر

class PerformanceVisualizer:
    def __init__(self):
        self.processor = ArabicTextProcessor()
        self.actual_color = '#17A589'  # أخضر للواقع

    def _safe_text(self, value):
        if isinstance(value, (bytes, bytearray)):
            return value.decode('utf-8')
        return str(value)

    def generate_smart_chart(
        self,
        history_scores: list,
        prediction: float,
        gap_prob: float,
        lesson_title: str,
    ):
        """
        توليد رسم بياني خطي يوضح اتجاه مشاركة الطلاب.
        history_scores: آخر التقييمات (بعد حفظ التقييم الحالي في قاعدة البيانات) دون تكرار.
        """
        if history_scores:
            all_scores = [max(1, min(3, int(s))) for s in history_scores]
        else:
            pv = max(1, min(3, int(round(float(prediction)))))
            all_scores = [pv]
        plt.figure(figsize=(10, 5))

        # رسم الخط الفعلي
        x_actual =list(range(1, len(all_scores) + 1))
        plt.plot(x_actual, all_scores, marker='o', color=self.actual_color,
                 linewidth =3, markersize=10, label=self.processor.format_text('الأداء الحالي والسابق'))

        # تحديد لون وحجم نقطة التنبؤ بناءً على فجوة XGBoost
        # إذا كانت الفجوة > 50% نستخدم اللون الأحمر للتحذير
        p_color = '#C0392B' if gap_prob > 50 else '#E67E22'  # أحمر للفجوة الكبيرة، برتقالي للفجوة الصغيرة
        p_size = 150  + (gap_prob * 2)  # زيادة حجم النقطة بناءً على نسبة الفجوة

        x_pred = len(all_scores) + 1
        plt.scatter(x_pred, prediction, color=p_color, s= p_size, edgecolors='black', zorder=5,
                    label=self.processor.format_text(f"تنبؤ الحصة القادمة (فجوة {gap_prob}%)"))
        
        plt.plot([x_actual[-1], x_pred], [all_scores[-1], prediction],
                 linestyle="--", color='gray', alpha=0.5)

        ytitle = self._safe_text(self.processor.format_text(f"تحليل أداء الدرس: {lesson_title}"))
        plt.title(ytitle, fontsize=14)
        ylabel = self._safe_text(self.processor.format_text("مستوى التفاعل (1-3)"))
        plt.ylabel(ylabel)
        
        plt.yticks([1, 2, 3], [
            self._safe_text(self.processor.format_text("ضعيف")),
            self._safe_text(self.processor.format_text("جيد")),
            self._safe_text(self.processor.format_text("ممتاز"))
        ])
        plt.ylim(0.5, 3.5)
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.legend(loc='upper left')

        buf =BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=120)
        buf.seek(0)
        plt.close()
        return buf