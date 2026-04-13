from fpdf import FPDF
from fpdf.enums import XPos, YPos
from io import BytesIO
from typing import Any
import arabic_reshaper
from bidi.algorithm import get_display
from datetime import datetime
from pathlib import Path
import logging
from config import BASE_DIR
from utils.text_processor import ArabicTextProcessor


class LessonPDFGenerator:
    """توليد ملفات PDF للدروس والتقارير مع دعم العربية وتخطيط آمن من التداخل."""

    def __init__(self):
        self.processor = ArabicTextProcessor()
        self.font_regular_path = Path(BASE_DIR) / "Amiri-Regular.ttf"
        self.font_bold_path = Path(BASE_DIR) / "Amiri-Bold.ttf"

    def _register_fonts(self, pdf: FPDF) -> bool:
        """Register Arabic fonts (regular & bold) with fallbacks."""
        try:
            if self.font_regular_path.exists() and self.font_bold_path.exists():
                pdf.add_font("Amiri", "", str(self.font_regular_path))
                pdf.add_font("AmiriBold", "", str(self.font_bold_path))
                return True
            return False
        except Exception as exc:
            logging.error(f"خطأ في تسجيل الخطوط: {exc}")
            return False

    def process_text(self, text: Any) -> str:
        """دالة وسيطة لضمان استخدام معالج النصوص العربي"""
        if text is None or str(text).strip() == "":
            return ""
        text = str(text).strip()
        text = text.replace("**", "").replace("###", "").replace("#", "")

        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text, base_dir="R")
        return str(bidi_text)

    def _generate_pdf_buffer(self, pdf: FPDF) -> BytesIO:
        """حفظ الملف في الذاكرة ليرسله البوت"""
        buffer = BytesIO()
        pdf.output(buffer)
        buffer.seek(0)
        return buffer

    def setup_pdf_footer(self, pdf: FPDF, font_regular: str) -> None:
        """تذييل الصفحة — دون استخدام set_y(10) الذي كان يطبع فوق الرأس"""

        def footer() -> None:
            pdf.set_y(-18)
            pdf.set_font(font_regular, "", 8)
            pdf.set_text_color(120, 120, 120)
            pdf.set_draw_color(220, 220, 220)
            y_line = pdf.get_y()
            pdf.line(pdf.l_margin, y_line, pdf.w - pdf.r_margin, y_line)
            pdf.ln(2)
            date_str = datetime.now().strftime("%Y-%m-%d")
            line = self.process_text(
                f"تم إنشاء هذا المستند آلياً بواسطة مُيسِر — {date_str} — صفحة {pdf.page_no()}"
            )
            pdf.cell(
                0,
                5,
                line,
                align="C",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )

        pdf.footer = footer  # type: ignore[method-assign]

    def rtl_cell(
        self,
        pdf: FPDF,
        width: float,
        height: float,
        txt: str,
        border: str | int = "1",
        align: str = "L",
        fill: bool = False,
    ) -> float:
        """خلية محاذاة من اليمين داخل عرض الأعمدة"""
        pdf.set_x(pdf.w - pdf.r_margin - width)
        pdf.cell(
            width,
            height,
            self.process_text(txt),
            border=border,
            align=align,
            fill=fill,
            new_x=XPos.RIGHT,
            new_y=YPos.TOP,
        )
        return width

    def _arabic_paragraph(
        self,
        pdf: FPDF,
        text: str,
        font_name: str,
        size: float,
        line_height: float,
        text_color: tuple[int, int, int],
    ) -> None:
        """فقرة عربية مع لف تلقائي داخل epw (تفادي تراكب cell على أسطر طويلة)."""
        pdf.set_font(font_name, "", size)
        pdf.set_text_color(*text_color)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            pdf.epw,
            line_height,
            self.process_text(text),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    def create_lesson_plan_pdf(self, item: Any, ai_reply: str, grade_name: str) -> BytesIO:
        pdf = FPDF()
        fonts_loaded = self._register_fonts(pdf)
        font_regular = "Amiri" if fonts_loaded else "Helvetica"
        font_bold = "AmiriBold" if fonts_loaded else "Helvetica"

        pdf.set_margins(15, 15, 15)
        pdf.set_auto_page_break(auto=True, margin=22)
        self.setup_pdf_footer(pdf, font_regular)
        pdf.add_page()

        primary_color = (41, 128, 185)
        header_gray = (245, 245, 245)
        border_color = (180, 180, 180)
        data_white = (255, 255, 255)
        note_box_color = (248, 249, 250)
        text_main = (44, 62, 80)

        pdf.set_font(font_regular, "", 12)

        # --- 1. الرأس ---
        pdf.set_fill_color(*primary_color)
        pdf.rect(0, 0, 210, 50, "F")
        pdf.set_y(10)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(font_bold, "", 24)
        pdf.cell(
            0,
            14,
            self.process_text("خطة تحضير الدرس"),
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_font(font_bold, "", 18)
        pdf.cell(
            0,
            10,
            self.process_text(item.get("title", "")),
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_font(font_regular, "", 10)
        pdf.set_text_color(235, 245, 255)
        pdf.cell(
            0,
            6,
            self.process_text("وثيقة تخطيط درس احترافية باللغة العربية"),
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

        # --- 2. جدول معلومات الدرس (مجموع الأعمدة = epw) ---
        pdf.set_y(52)
        pdf.set_draw_color(*border_color)
        pdf.set_line_width(0.2)

        row_data = [
            [f"{item.get('duration', '40')} ", "زمن الحصـة", str(grade_name), "الصـف الدراسي"],
            [
                str(item.get("page_ref", "-")),
                "رقم الصفحة",
                item.get("activity", "غير محدد"),
                "النشاط التفاعلي",
            ],
        ]
        col_widths = [52, 38, 52, 38]

        for row in row_data:
            for i, txt in enumerate(row):
                is_label = i % 2 == 0
                pdf.set_fill_color(*(data_white if is_label else header_gray))
                pdf.set_font(font_regular if is_label else font_bold, "", 10)
                pdf.set_text_color(*text_main)
                self.rtl_cell(pdf, col_widths[i], 12, txt, fill=True)
            pdf.ln(12)

        # --- 3. الأنشطة التعليمية ---
        pdf.ln(6)
        pdf.set_x(pdf.l_margin)
        pdf.set_font(font_bold, "", 14)
        pdf.set_text_color(*primary_color)
        pdf.cell(
            pdf.epw,
            10,
            self.process_text("الأنشطة التعليمية والخطوات الإجرائية"),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

        pdf.set_font(font_regular, "", 11)
        pdf.set_text_color(0, 0, 0)

        if ai_reply:
            clean_reply = ai_reply.replace("**", "").replace("###", "").strip()
            blocks = [b.strip() for b in clean_reply.split("\n\n") if b.strip()]
            if not blocks:
                blocks = [clean_reply]

            for block in blocks:
                for line in [ln.strip() for ln in block.split("\n") if ln.strip()]:
                    self._arabic_paragraph(
                        pdf,
                        line,
                        font_regular,
                        11,
                        6.5,
                        (0, 0, 0),
                    )
                pdf.ln(2)

        # --- 4. التأمل المهني ---
        if pdf.get_y() > 235:
            pdf.add_page()

        pdf.ln(8)
        y_box = pdf.get_y()
        box_height = 42.0
        pdf.set_draw_color(220, 220, 220)
        pdf.set_fill_color(*note_box_color)
        pdf.rect(pdf.l_margin, y_box, pdf.epw, box_height, style="DF")

        pdf.set_y(y_box + 4)
        pdf.set_font(font_bold, "", 13)
        pdf.set_text_color(*text_main)
        pdf.set_x(pdf.l_margin + 4)
        pdf.multi_cell(
            pdf.epw - 8,
            8,
            self.process_text("التأمل المهني بعد التنفيذ (يُملأ يدوياً أو رقمياً):"),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

        pdf.set_y(y_box + box_height + 6)
        pdf.set_text_color(80, 80, 80)
        pdf.set_font(font_regular, "", 11)
        half = pdf.epw / 2 - 2
        pdf.set_x(pdf.l_margin)
        pdf.cell(
            half,
            8,
            self.process_text("توقيع مُعلم/ة المادة: ......................"),
            align="R",
            new_x=XPos.RIGHT,
            new_y=YPos.TOP,
        )
        pdf.cell(
            half,
            8,
            self.process_text("توقيع خبير/ة المادة: ......................"),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

        return self._generate_pdf_buffer(pdf)

    def create_evaluation_report_pdf(self, eval_data: dict[str, Any], teacher_name: str) -> BytesIO:
        pdf = FPDF()
        fonts_loaded = self._register_fonts(pdf)
        font_regular = "Amiri" if fonts_loaded else "Helvetica"
        font_bold = "AmiriBold" if fonts_loaded else "Helvetica"
        pdf.set_margins(15, 15, 15)
        pdf.set_auto_page_break(auto=True, margin=22)
        self.setup_pdf_footer(pdf, font_regular)
        pdf.add_page()

        header_green = (23, 165, 137)

        pdf.set_font(font_regular, "", 12)

        pdf.set_fill_color(*header_green)
        pdf.rect(0, 0, 210, 40, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(font_regular, "", 18)
        pdf.set_y(15)
        header_title = f"تقرير أداء الطلبة - المعلم/ة {teacher_name}"
        pdf.cell(
            0,
            10,
            self.process_text(header_title),
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

        pdf.set_y(50)
        pdf.set_text_color(0, 0, 0)

        items = [
            ("الدرس المستهدف:", eval_data["lesson"]),
            ("تقييم التفاعل:", f"{eval_data['score']} من 3"),
            ("تحليل الاتجاه (Trend):", eval_data["trend"]),
            (
                "توصية مُيسِر:",
                "استمر بهذا النهج التفاعلي"
                if eval_data["score"] == 3
                else "جرب تنويع الأنشطة الحركية",
            ),
        ]

        for label, val in items:
            pdf.set_font(font_bold, "", 13)
            pdf.set_text_color(*header_green)
            pdf.cell(
                pdf.epw,
                9,
                self.process_text(label),
                align="R",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
            pdf.set_font(font_regular, "", 12)
            pdf.set_text_color(0, 0, 0)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(
                pdf.epw,
                7,
                self.process_text(str(val)),
                align="R",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
            pdf.ln(3)

        return self._generate_pdf_buffer(pdf)

    def create_full_summary_pdf(self, teacher_name: str, history_data: list[dict[str, Any]]) -> BytesIO:
        pdf = FPDF()
        fonts_loaded = self._register_fonts(pdf)
        font_regular = "Amiri" if fonts_loaded else "Helvetica"
        font_bold = "AmiriBold" if fonts_loaded else "Helvetica"

        pdf.set_margins(15, 15, 15)
        pdf.set_auto_page_break(auto=True, margin=22)
        self.setup_pdf_footer(pdf, font_regular)
        pdf.add_page()

        brand_color = (108, 52, 131)
        bg_light = (248, 249, 249)

        pdf.set_font(font_regular, "", 12)

        pdf.set_fill_color(*brand_color)
        pdf.rect(0, 0, 210, 45, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(font_bold, "", 22)
        pdf.set_y(12)
        pdf.cell(
            0,
            12,
            self.process_text("التقرير الشامل لتحليل الأداء التربوي"),
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_font(font_regular, "", 14)
        pdf.cell(
            0,
            10,
            self.process_text(f"للمعلم/ة: {teacher_name}"),
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

        pdf.set_y(55)
        pdf.set_text_color(*brand_color)
        pdf.set_font(font_bold, "", 16)
        pdf.cell(
            pdf.epw,
            10,
            self.process_text("الملخص الإحصائي"),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_draw_color(*brand_color)
        pdf.line(150, pdf.get_y() - 2, pdf.w - pdf.r_margin, pdf.get_y() - 2)
        pdf.ln(5)

        total_lessons = len(history_data)
        avg_score = (
            sum(item["eval_score"] for item in history_data) / total_lessons if total_lessons > 0 else 0
        )

        pdf.set_text_color(44, 62, 80)
        pdf.set_font(font_regular, "", 13)
        stats_txt = (
            f"• إجمالي الدروس: {total_lessons} درساً.\n"
            f"• متوسط التقييم: {avg_score:.2f} من 3.\n"
            f"• مسـتوى الإتقان: {min(100, avg_score * 33.3):.1f}%."
        )
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            pdf.epw,
            9,
            self.process_text(stats_txt),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

        pdf.ln(10)
        pdf.set_font(font_bold, "", 16)
        pdf.set_text_color(*brand_color)
        pdf.cell(
            pdf.epw,
            10,
            self.process_text("سجل الأداء التفصيلي"),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

        w_score, w_grade, w_title, w_date = 28, 28, 84, 40

        pdf.set_fill_color(230, 230, 230)
        pdf.set_font(font_bold, "", 11)
        pdf.set_text_color(0, 0, 0)
        cols = [
            ("التقييم", w_score),
            ("الصف", w_grade),
            ("عنوان الدرس", w_title),
            ("التاريخ", w_date),
        ]
        for label, width in cols:
            pdf.cell(width, 10, self.process_text(label), border="1", align="C", fill=True)
        pdf.ln()

        pdf.set_font(font_regular, "", 10)
        for row in history_data:
            score_val = str(row.get("eval_score", row.get("score", "0")))
            title_val = row.get("lesson_title", row.get("title", "---"))
            grade_val = str(row.get("grade", "---"))
            timestamp_val = str(row.get("date_time", row.get("timestamp", "---")))[:10]

            pdf.cell(w_score, 10, self.process_text(score_val), border="1", align="C")
            pdf.cell(w_grade, 10, self.process_text(grade_val), border="1", align="C")
            pdf.cell(w_title, 10, self.process_text(str(title_val)), border="1", align="R")
            pdf.cell(w_date, 10, self.process_text(timestamp_val), border="1", align="C")
            pdf.ln()

        pdf.ln(10)
        if pdf.get_y() > 220:
            pdf.add_page()

        y_insight = pdf.get_y()
        insight_h = 48.0
        pdf.set_fill_color(*bg_light)
        pdf.set_draw_color(*brand_color)
        pdf.rect(pdf.l_margin, y_insight, pdf.epw, insight_h, style="DF")

        pdf.set_y(y_insight + 5)
        pdf.set_font(font_bold, "", 14)
        pdf.set_text_color(*brand_color)
        pdf.set_x(pdf.l_margin + 4)
        pdf.multi_cell(
            pdf.epw - 8,
            8,
            self.process_text("رؤية مُيسِر لسد الفجوات التعليمية"),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

        pdf.set_font(font_regular, "", 12)
        pdf.set_text_color(0, 0, 0)
        if avg_score > 2.5:
            insight = (
                "ينبؤنا مُيَّسِر أن الطلاب يظهرون استجابة ممتازة للأنشطة الإثرائية. "
                "يوصى بالانتقال إلى استراتيجيات التعلم الذاتي والاكتشاف."
            )
        elif avg_score > 1.8:
            insight = (
                "يخبرنا مُيَّسِر أن الأداء مستقر بشكل عام، ولكن توجد فجوات بسيطة في الدروس الطولية. "
                "يوصى بتقسيم المهام وتكثيف الأنشطة الحركية."
            )
        else:
            insight = (
                "بيانات مُيَّسِر تخبرنا أن الطلاب يواجهون صعوبة، والحل هو تبسيط الشرح "
                "وتدريبهم عبر رؤية المعلم وهو يطبق الخطوات أمامهم خطوة بخطوة."
            )

        pdf.set_x(pdf.l_margin + 6)
        pdf.multi_cell(
            pdf.epw - 12,
            7,
            self.process_text(insight),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

        return self._generate_pdf_buffer(pdf)
