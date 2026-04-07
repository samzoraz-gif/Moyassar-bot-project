from fpdf import FPDF
from io import BytesIO
from datetime import datetime
from pathlib import Path
import logging
from config import FONT_PATH
from utils.text_processor import ArabicTextProcessor

class LessonPDFGenerator:
    def __init__(self):
        self.processor = ArabicTextProcessor()
        self.font_path = Path(FONT_PATH) if Path(FONT_PATH).exists() else None

    def _register_fonts(self, pdf: FPDF) -> bool:
        """Register Arabic font once and fall back cleanly on failure."""
        if not self.font_path:
            return False

        try:
            pdf.add_font('Amiri', '', str(self.font_path))
            pdf.add_font('AmiriBold', '', str(self.font_path))
            return True
        except Exception as exc:
            logging.warning(
                "Failed to register custom PDF font '%s': %s. Falling back to Arial.",
                self.font_path,
                exc,
            )
            self.font_path = None
            return False

    def process_text(self, text) -> str:
        """دالة وسيطة لضمان استخدام معالج النصوص العربي"""
        processed = self.processor.format_text(text)
        if not isinstance(processed, str):
            processed = processed.decode('utf-8', errors='replace')
        return str(processed)
    
    def _generate_pdf_buffer(self, pdf):
        """حفظ الملف في الذاكرة ليرسله البوت"""
        buffer = BytesIO()
        pdf.output(buffer)
        buffer.seek(0)
        return buffer

    def setup_pdf_footer(self, pdf):
        """إضافة تذييل الصفحة التلقائي"""
        def footer():
            pdf.set_y(-15)
            pdf.set_font('Amiri' if self.font_path else 'Arial', '', 8)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(0, 10, f"{pdf.page_no()} ص", align='R')
            pdf.set_x(0)
            date_str = datetime.now().strftime('%Y-%m-%d')
            footer_txt = self.process_text(f"تم إنشاء هذا المستند آلياً بواسطة مُيسِر - بتاريخ {date_str}")
            pdf.cell(0, 10, footer_txt, align='C')
        pdf.footer = footer

    def create_lesson_plan_pdf(self, item, ai_reply, grade_name):
        pdf = FPDF()
        self.setup_pdf_footer(pdf)
        pdf.add_page()
        
        # --- ألوان وتصميم ---
        primary_color = (41, 128, 185) # أزرق
        light_gray = (240, 240, 240)
        border_color = (200, 200, 200)
        text_main = (44, 62, 80)
        
        # إعداد الخطوط
        fonts_loaded = self._register_fonts(pdf)
        font_regular = 'Amiri' if fonts_loaded else 'Arial'
        font_bold = 'AmiriBold' if fonts_loaded else 'Arial'

        # --- 1. الرأس الاحترافي (Header) ---
        pdf.set_fill_color(*primary_color)
        pdf.rect(0, 0, 210, 50, 'F') # خلفية كاملة للعرض
        
        pdf.set_y(25)
        pdf.set_font(font_bold, '', 24)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 12, "خطة تحضير الدرس", align='C', ln='DEPRECATED')
        
        pdf.set_font(font_regular, '', 14)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 10, f"الصف: {grade_name}  |  {item.get('title', 'الدرس')}", align='C', ln='DEPRECATED')

        # --- 2. شريط المعلومات (Info Bar) ---
        pdf.set_y(60)
        pdf.set_draw_color(*primary_color)
        pdf.set_line_width(1)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y()) # خط فاصل
        pdf.ln(5)

        # جدول المعلومات الصغير
        pdf.set_font(font_bold, '', 11)
        pdf.set_text_color(*text_main)
        
        # الصف الأول (المواصفات)
        row_height = 10
        pdf.set_x(10)
        pdf.cell(20, row_height, "الصف:", border=0, fill=False, align='R')
        pdf.set_x(30)
        pdf.set_font(font_regular, '', 11)
        pdf.cell(40, row_height, grade_name, border=1, fill=True, align='C') # خلفية مملوءة خفيفة
        
        pdf.set_x(75)
        pdf.set_font(font_bold, '', 11)
        pdf.cell(25, row_height, "زمن الحصة:", border=0, fill=False, align='R')
        pdf.set_x(100)
        pdf.set_font(font_regular, '', 11)
        pdf.cell(40, row_height, str(item.get('duration', '40 دقيقة')), border=1, fill=True, align='C')

        pdf.set_x(145)
        pdf.set_font(font_bold, '', 11)
        pdf.cell(25, row_height, "رقم الصفحة:", border=0, fill=False, align='R')
        pdf.set_x(170)
        pdf.set_font(font_regular, '', 11)
        pdf.cell(30, row_height, str(item.get('page_ref', '-')), border=1, fill=True, align='C')
        
        pdf.ln(row_height + 2)
        
        # الصف الثاني (الهدف)
        pdf.set_x(10)
        pdf.set_font(font_bold, '', 11)
        pdf.cell(25, row_height, "الهدف:", border=0, fill=False, align='R')
        pdf.set_x(35)
        pdf.set_font(font_regular, '', 11)
        pdf.cell(165, row_height, str(item.get('goal', '---')), border=1, fill=True, align='R')
        
        pdf.ln(15)

        # --- 3. المحتوى التعليمي (Body) ---
        pdf.set_font(font_bold, '', 16)
        pdf.set_text_color(*primary_color)
        pdf.cell(0, 10, "📝 الأنشطة التعليمية المقترحة (بمُيَّسِر AI)", align='R', ln='DEPRECATED')
        
        pdf.set_draw_color(*primary_color)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        pdf.set_font(font_regular, '', 12)
        pdf.set_text_color(0, 0, 0)
        
        # تنظيف النص
        clean_reply = ai_reply.replace('**', '').replace('###', '').replace('-', '•')
        pdf.multi_cell(0, 9, self.process_text(clean_reply), align='R')

        # --- 4. منطقة التوقيعات (Footer Area) ---
        current_y = pdf.get_y()
        if current_y > 220: 
            pdf.add_page()
            current_y = 20
        
        pdf.ln(20)
        pdf.set_draw_color(*border_color)
        pdf.set_line_width(0.2)
        
        # رسم صندوق الملاحظات والتوقيع
        pdf.set_fill_color(250, 252, 255) # لون خلفية باهت
        pdf.rect(10, pdf.get_y(), 190, 35, 'DF') # صندوق بحجم 3.5 سم
        
        pdf.set_y(pdf.get_y() + 5)
        pdf.set_font(font_bold, '', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 8, "ملاحظات المعلم:", align='R')
        
        # توقيعات في الأسفل
        pdf.set_y(pdf.get_y() + 20)
        pdf.set_x(10)
        pdf.cell(90, 10, "توقيع الخبير التربوي: ........................", align='L')
        pdf.set_x(110)
        pdf.cell(90, 10, "توقيع المعلم: ........................", align='R')

        return self._generate_pdf_buffer(pdf)
    
    def create_evaluation_report_pdf(self, eval_data, teacher_name):
        pdf = FPDF()
        self.setup_pdf_footer(pdf)
        pdf.add_page()
        
        header_green = (23, 165, 137)
        
        fonts_loaded = self._register_fonts(pdf)
        pdf.set_font('Amiri' if fonts_loaded else 'Arial', '', 12)

        # الرأس
        
        pdf.set_fill_color(*header_green)
        pdf.rect(0, 0, 210, 40, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font_size(18)
        header_title = f"تقرير أداء الطلبة - المعلم/ة {teacher_name}"
        pdf.set_y(15)
        pdf.cell(0, 10, self.process_text(header_title), align='C')
        
        # المحتوى
        pdf.set_y(50)
        pdf.set_text_color(0, 0, 0)
        
        items = [
            ("الدرس المستهدف:", eval_data['lesson']),
            ("تقييم التفاعل:", f"{eval_data['score']} من 3"),
            ("تحليل الاتجاه (Trend):", eval_data['trend']),
            ("توصية مُيسِر:", "استمر بهذا النهج التفاعلي" if eval_data['score'] == 3 else "جرب تنويع الأنشطة الحركية")
        ]
        
        for label, val in items:
            pdf.set_font_size(13)
            pdf.set_text_color(*header_green)
            pdf.cell(0, 10, self.process_text(label), align='R')
            pdf.set_font_size(12)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 8, self.process_text(val), align='R')
            pdf.ln(2)

        return self._generate_pdf_buffer(pdf)

    def create_full_summary_pdf(self, teacher_name, history_data):
        pdf = FPDF()
        self.setup_pdf_footer(pdf)
        pdf.add_page()
        
        brand_color = (108, 52, 131)
        bg_light = (248, 249, 249)
        
        fonts_loaded = self._register_fonts(pdf)
        font_regular = 'Amiri' if fonts_loaded else 'Arial'
        font_bold = 'AmiriBold' if fonts_loaded else 'Arial'
        pdf.set_font(font_regular, '', 12)

        # رأس التقرير
        pdf.set_fill_color(*brand_color)
        pdf.rect(0, 0, 210, 45, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(font_bold, '', 22)
        pdf.set_y(12)
        pdf.cell(0, 12, self.process_text("التقرير الشامل لتحليل الأداء التربوي"), align='C')
        pdf.set_font_size(14)
        pdf.cell(0, 10, self.process_text(f"للمعلم/ة: {teacher_name}"), align='C')
        
        # ملخص الإحصائيات
        pdf.set_y(55)
        pdf.set_text_color(*brand_color)
        pdf.set_font(font_bold, '', 16)
        pdf.cell(0, 10, self.process_text("📊 الملخص الإحصائي:"), align='R')
        pdf.set_draw_color(*brand_color)
        pdf.line(150, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        total_lessons = len(history_data)
        avg_score = sum(item['eval_score'] for item in history_data) / total_lessons if total_lessons > 0 else 0
        
        pdf.set_text_color(44, 62, 80)
        pdf.set_font(font_regular, '', 13)
        
        stats_txt = (
            f"• إجمالي الدروس التي تم تحليلها: {total_lessons} درساً.\n"
            f"• متوسط تقييم تفاعل الطلاب: {avg_score:.2f} من 3.\n"
            f"• مستوى الإتقان العام المتوقع: {min(100, avg_score * 33.3):.1f}%."
        )
        pdf.multi_cell(0, 10, self.process_text(stats_txt), align='R')

        # جدول السجلات
        pdf.ln(10)
        pdf.set_font(font_bold, '', 16)
        pdf.set_text_color(*brand_color)
        pdf.cell(0, 10, self.process_text("📑 سجل الأداء التفصيلي:"), align='R')
        
        # رأس الجدول
        pdf.set_fill_color(230, 230, 230)
        pdf.set_font_size(11)
        cols = [("التقييم", 30), ("الصف", 30), ("عنوان الدرس", 90), ("التاريخ", 40)]
        
        for label, width in cols:
            pdf.cell(width, 10, self.process_text(label), border=1, align='C', fill=True)
        pdf.ln()

        # بيانات الجدول
        pdf.set_font(font_regular, '', 10)
        for row in history_data:
            score_val = str(row.get('eval_score', row.get('score', '0')))
            title_val = row.get('lesson_title', row.get('title', '---'))
            grade_val = str(row.get('grade', '---'))
            timestamp_val = str(row.get('date_time', row.get('timestamp', '---')))[:10]
            
            pdf.cell(30, 10, self.process_text(score_val), border=1, align='C')
            pdf.cell(30, 10, self.process_text(grade_val), border=1, align='C')
            pdf.cell(90, 10, self.process_text(title_val), border=1, align='R')
            pdf.cell(40, 10, self.process_text(timestamp_val), border=1, align='C')
            pdf.ln()

        # تحليل AI
        pdf.ln(10)
        if pdf.get_y() > 220: pdf.add_page()
        
        pdf.set_fill_color(*bg_light)
        pdf.set_draw_color(*brand_color)
        pdf.rect(10, pdf.get_y(), 190, 45, 'DF')
        
        pdf.set_y(pdf.get_y() + 5)
        pdf.set_font(font_bold, '', 14)
        pdf.set_text_color(*brand_color)
        pdf.cell(0, 8, self.process_text("💡 رؤية 'مُيسِر' لسد الفجوات التعليمية:"), align='R')
        
        pdf.set_font(font_regular, '', 12)
        pdf.set_text_color(0, 0, 0)
        
        if avg_score > 2.5:
            insight = "ينبؤنا مُيَّسِر أن الطلاب يظهرون استجابة ممتازة للأنشطة الإثرائية. يوصى بالانتقال إلى استراتيجيات التعلم الذاتي والاكتشاف."
        elif avg_score > 1.8:
            insight = "يخبرنا مُيَّسِر أن الأداء مستقر بشكل عام، ولكن توجد فجوات بسيطة في الدروس الطويلة. يوصى بتقسيم المهام وتكثيف الأنشطة الحركية."
        else:
            insight = "بيانات مُيَّسِر تخبرنا أن الطلاب بواجهون صعوبة، والحل هو تبسيط الشرح وتدريبهم عبر رؤية المعلم وهو يطبق الخطوات أمامهم خطوة بخطوة."
        
        pdf.set_x(15)
        pdf.multi_cell(180, 8, self.process_text(insight), align='R')

        return self._generate_pdf_buffer(pdf)

