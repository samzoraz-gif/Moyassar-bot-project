from fpdf import FPDF
from io import BytesIO
from datetime import datetime
import os
from config import FONT_PATH
from utils.text_processor import ArabicTextProcessor

class LessonPDFGenerator:
    def __init__(self):
        self.processor = ArabicTextProcessor()
        # تعريف المسار هنا لضمان عمل الدالة
        self.font_path = FONT_PATH if os.path.exists(FONT_PATH) else None

    def process_text(self, text):
        """دالة وسيطة لضمان استخدام معالج النصوص العربي"""
        return self.processor.format_text(text)
    
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
            pdf.cell(210, 10, footer_txt, align='C')
        pdf.footer = footer

    def create_lesson_plan_pdf(self, item, ai_reply, grade_name):
        pdf = FPDF()
        self.setup_pdf_footer(pdf)
        pdf.add_page()
        
        # الألوان (أزرق ملكي)
        header_blue = (41, 128, 185)
        table_label_bg = (245, 247, 249)
        table_border = (200, 200, 200)
        text_dark = (44, 62, 80)
        
        # إعداد الخطوط
        if self.font_path:
            pdf.add_font('Amiri', '', self.font_path)
            pdf.add_font('AmiriBold', '', self.font_path) 
            pdf.set_font('Amiri', '', 12)
        else:
            pdf.set_font('Arial', '', 12)

        # --- 1. رأس الصفحة (Header) ---
        pdf.set_fill_color(*header_blue)
        pdf.rect(0, 0, 210, 40, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('AmiriBold' if self.font_path else 'Arial', '', 20)
        pdf.set_y(15)
        pdf.cell(0, 10, self.process_text(f"خطة تحضير الدرس - {item.get('title', '')}"), ln=1, align='C')
        
        # --- 2. الجدول التعريفي ---
        pdf.set_y(50)
        pdf.set_draw_color(*table_border)
        pdf.set_text_color(*text_dark)
        pdf.set_line_width(0.3)

        def draw_four_col_row(label1, val1, label2, val2):
            w_label, w_val, h = 35, 60, 12
            # الأعمدة من اليمين لليسار
            positions = [10 + 60 + 35 + 60, 10 + 60 + 35, 10 + 60, 10]
            
            # الخلية 1 (العنوان 1)
            pdf.set_xy(positions[0], pdf.get_y())
            pdf.set_fill_color(*table_label_bg)
            pdf.set_font('AmiriBold' if self.font_path else 'Arial', '', 11)
            pdf.cell(w_label, h, self.process_text(label1), border=1, fill=True, align='R')
            
            # الخلية 2 (القيمة 1)
            pdf.set_xy(positions[1], pdf.get_y())
            pdf.set_fill_color(255, 255, 255)
            pdf.set_font('Amiri', '', 11)
            pdf.cell(w_val, h, self.process_text(val1), border=1, fill=True, align='R')

            # الخلية 3 (العنوان 2)
            pdf.set_xy(positions[2], pdf.get_y())
            pdf.set_fill_color(*table_label_bg)
            pdf.set_font('AmiriBold' if self.font_path else 'Arial', '', 11)
            pdf.cell(w_label, h, self.process_text(label2), border=1, fill=True, align='R')
            
            # الخلية 4 (القيمة 2)
            pdf.set_xy(positions[3], pdf.get_y())
            pdf.set_fill_color(255, 255, 255)
            pdf.set_font('Amiri', '', 11)
            pdf.cell(w_val, h, self.process_text(val2), border=1, fill=True, align='R')
            pdf.ln(h)

        draw_four_col_row("الصف الدراسي:", grade_name, "الهدف التعليمي:", item.get('goal', '---'))
        draw_four_col_row("زمن الحصة:", item.get('duration', '40 دقيقة'), "رقم الصفحة:", item.get('page_ref', '---'))

        # --- 3. المحتوى الذكي ---
        pdf.ln(10)
        pdf.set_font('AmiriBold' if self.font_path else 'Arial', '', 16)
        pdf.set_text_color(*header_blue) 
        pdf.cell(0, 10, self.process_text("الأنشطة التعليمية المقترحة (مُيسِر AI)"), ln=1, align='R')
        pdf.set_draw_color(*header_blue)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        pdf.set_font('Amiri', '', 12)
        pdf.set_text_color(0, 0, 0)
        clean_reply = ai_reply.replace('**', '').replace('###', '').replace('-', '•')
        pdf.multi_cell(0, 9, self.process_text(clean_reply), align='R')

        # --- 4. الملاحظات والتوقيعات ---
        current_y = pdf.get_y()
        if current_y > 230: pdf.add_page(); current_y = 20
        
        pdf.ln(10)
        pdf.set_font('Amiri', '', 14)
        pdf.set_text_color(19, 38, 250)
        # عنوان عريض للملاحظات
        pdf.cell(0, 10, self.process_text("ملاحظات المعلم:"), ln=1, align='R')
        
        # رسم مربع الملاحظات (ارتفاع 3 سم = 30 ملم) بلون هادئ جداً
        pdf.set_fill_color(250, 252, 255) # لون سماوي باهت جداً
        pdf.set_draw_color(220, 220, 220)
        current_y = pdf.get_y()
        pdf.rect(10, current_y, 190, 30, 'DF') # مربع بمساحة 3 سم
        pdf.set_y(current_y + 35) # الانتقال لما بعد المربع
        
        pdf.set_font('AmiriBold' if self.font_path else 'Arial','',11)
        pdf.set_text_color(44, 62, 80)

        pdf.set_x(105) # نبدأ من اليسار بعد ترك مساحة للتوقيع الأول
        pdf.cell(95, 10, self.process_text("توقيع معلــم المـادة: ..........................."), align='R',ln=0)
        
        pdf.set_x(10) # نبدأ من اليسار للتوقيع الثاني
        pdf.cell(95, 10, self.process_text("توقيع الخبير التربوي: ..........................."), align='L',ln=1)

        return self._generate_pdf_buffer(pdf)
    
    def create_evaluation_report_pdf(self, eval_data, teacher_name):
        pdf = FPDF()
        self.setup_pdf_footer(pdf)
        pdf.add_page()
        
        # الألوان لتقرير التقييم (أخضر مريح)
        header_green = (23, 165, 137)
        
        if self.font_path:
            pdf.add_font('Amiri', '', self.font_path)
            pdf.set_font('Amiri', '', 12)

        # الرأس
        pdf.set_fill_color(*header_green)
        pdf.rect(0, 0, 210, 40, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font_size(18)
        header_title = f"تقرير أداء الطلبة - المعلم/ة {teacher_name}"
        pdf.set_y(15)
        pdf.cell(0, 10, self.process_text(header_title), ln=1, align='C')
        
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
            pdf.cell(0, 10, self.process_text(label), ln=1, align='R')
            pdf.set_font_size(12)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 8, self.process_text(val), align='R')
            pdf.ln(2)

        return self._generate_pdf_buffer(pdf)

    def create_full_summary_pdf(self, teacher_name, history_data):
        """
        توليد التقرير الشامل للأداء التربوي (Full Performance Report).
        يستعرض الإحصائيات التراكمية، تحليل الاتجاهات، وتوصيات الذكاء الاصطناعي.
        """
        pdf = FPDF()
        self.setup_pdf_footer(pdf)
        pdf.add_page()
        
        # الألوان (أرجواني غامق للتقارير الاستراتيجية)
        brand_color = (108, 52, 131)
        bg_light = (248, 249, 249)
        
        if self.font_path:
            pdf.add_font('Amiri', '', self.font_path)
            pdf.add_font('AmiriBold', '', self.font_path)
            pdf.set_font('Amiri', '', 12)

        # --- 1. رأس التقرير (Header) ---
        pdf.set_fill_color(*brand_color)
        pdf.rect(0, 0, 210, 45, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('AmiriBold' if self.font_path else 'Arial', '', 22)
        pdf.set_y(12)
        pdf.cell(0, 12, self.process_text("التقرير الشامل لتحليل الأداء التربوي"), ln=1, align='C')
        pdf.set_font_size(14)
        pdf.cell(0, 10, self.process_text(f"للمعلم/ة: {teacher_name}"), ln=1, align='C')
        
        # --- 2. ملخص الإحصائيات (Executive Summary) ---
        pdf.set_y(55)
        pdf.set_text_color(*brand_color)
        pdf.set_font('AmiriBold' if self.font_path else 'Arial', '', 16)
        pdf.cell(0, 10, self.process_text("📊 الملخص الإحصائي:"), ln=1, align='R')
        pdf.set_draw_color(*brand_color)
        pdf.line(150, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        total_lessons = len(history_data)
        avg_score = sum(item['eval_score'] for item in history_data) / total_lessons if total_lessons > 0 else 0
        
        pdf.set_text_color(44, 62, 80)
        pdf.set_font('Amiri' if self.font_path else 'Arial', '', 13)
        
        stats_txt = (
            f"• إجمالي الدروس التي تم تحليلها: {total_lessons} درساً.\n"
            f"• متوسط تقييم تفاعل الطلاب: {avg_score:.2f} من 3.\n"
            f"• مستوى الإتقان العام المتوقع: {min(100, avg_score * 33.3):.1f}%."
        )
        pdf.multi_cell(0, 10, self.process_text(stats_txt), align='R')

        # --- 3. جدول السجلات التاريخية (History Table) ---
        pdf.ln(10)
        pdf.set_font('AmiriBold' if self.font_path else 'Arial', '', 16)
        pdf.set_text_color(*brand_color)
        pdf.cell(0, 10, self.process_text("📑 سجل الأداء التفصيلي:"), ln=1, align='R')
        
        # رأس الجدول
        pdf.set_fill_color(230, 230, 230)
        pdf.set_font_size(11)
        cols = [("التقييم", 30), ("الصف", 30), ("عنوان الدرس", 90), ("التاريخ", 40)]
        
        # رسم الرأس
        for label, width in cols:
            pdf.cell(width, 10, self.process_text(label), border=1, align='C', fill=True)
        pdf.ln()

        # بيانات الجدول
        pdf.set_font('Amiri' if self.font_path else 'Arial', '', 10)
        for row in history_data:
            pdf.cell(30, 10, self.process_text(str(row['eval_score'])), border=1, align='C')
            pdf.cell(30, 10, self.process_text(str(row['grade'])), border=1, align='C')
            pdf.cell(90, 10, self.process_text(row['lesson_title']), border=1, align='R')
            pdf.cell(40, 10, self.process_text(str(row['timestamp'])[:10]), border=1, align='C')
            pdf.ln()

        # --- 4. تحليل النماذج الذكية (AI Insights) ---
        pdf.ln(10)
        if pdf.get_y() > 220: pdf.add_page()
        
        pdf.set_fill_color(*bg_light)
        pdf.set_draw_color(*brand_color)
        pdf.rect(10, pdf.get_y(), 190, 45, 'DF')
        
        pdf.set_y(pdf.get_y() + 5)
        pdf.set_font('AmiriBold' if self.font_path else 'Arial', '', 14)
        pdf.set_text_color(*brand_color)
        pdf.cell(0, 8, self.process_text("💡 رؤية 'مُيسِر' لسد الفجوات التعليمية:"), ln=1, align='R')
        
        pdf.set_font('Amiri' if self.font_path else 'Arial', '', 12)
        pdf.set_text_color(0, 0, 0)
        
        # منطق ذكي بناءً على المتوسط
        if avg_score > 2.5:
            insight = "ينبؤنا مُيَّسِر أن الطلاب يظهرون استجابة ممتازة للأنشطة الإثرائية. يوصى بالانتقال إلى استراتيجيات التعلم الذاتي والاكتشاف."
        elif avg_score > 1.8:
            insight = "يخبرنا مُيَّسِر أن الأداء مستقر بشكل عام، ولكن توجد فجوات بسيطة في الدروس الطويلة. يوصى بتقسيم المهام وتكثيف الأنشطة الحركية."
        else:
            insight = "بيانات مُيَّسِر تخبرنا أن الطلاب بواجهون صعوبة، والحل هو تبسيط الشرح وتدريبهم عبر رؤية المعلم وهو يطبق الخطوات أمامهم خطوة بخطوة."
            
        pdf.set_x(15)
        pdf.multi_cell(180, 8, self.process_text(insight), align='R')

        return self._generate_pdf_buffer(pdf)    