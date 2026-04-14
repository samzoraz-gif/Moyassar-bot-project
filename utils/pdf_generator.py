from __future__ import annotations

import re
from fpdf import FPDF
from fpdf.enums import Align, TableBordersLayout, VAlign, WrapMode, XPos, YPos
from fpdf.fonts import FontFace
from io import BytesIO
from typing import Any, Iterator
import arabic_reshaper
from bidi.algorithm import get_display
from datetime import datetime
from pathlib import Path
import logging
from config import BASE_DIR
from utils.text_processor import ArabicTextProcessor

# ألوان موحّدة: التحضير والتقييم الحالي (أزرق)، لمسة بصرية تربط بالرسم (تركواز)، التقرير الشامل (بنفسجي منفصل)
THEME_LESSON_BLUE = (41, 128, 185)
THEME_EVAL_ACCENT = (23, 165, 137)
THEME_FULL_REPORT = (108, 52, 131)


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

    def _arabic_paragraph(
        self,
        pdf: FPDF,
        text: str,
        font_name: str,
        size: float,
        line_height: float,
        text_color: tuple[int, int, int],
        x_offset: float = 0.0,
    ) -> None:
        """فقرة عربية مع لف تلقائي داخل epw (تفادي تراكب cell على أسطر طويلة)."""
        pdf.set_font(font_name, "", size)
        pdf.set_text_color(*text_color)
        w = pdf.epw - x_offset
        pdf.set_x(pdf.l_margin + x_offset)
        pdf.multi_cell(
            w,
            line_height,
            self.process_text(text),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    _RE_MD_HEADING = re.compile(r"^\s*#{1,3}\s*(.+?)\s*$")
    _RE_MD_BOLD_LINE = re.compile(r"^\s*\*\*(.+?)\*\*\s*$")
    _RE_LIST_OR_NUM = re.compile(r"^(\s*[-•]\s+|\s*\d+[\.\)]\s+)")

    def _iter_lesson_ai_segments(self, raw: str) -> Iterator[tuple[str, str]]:
        """يُنتج (نوع، نص): h3_under | bold_title | body — دون الاعتماد على process_text لإزالة العلامات قبل التصنيف."""
        blocks = [b.strip() for b in raw.split("\n\n") if b.strip()]
        if not blocks:
            blocks = [raw.strip()] if raw.strip() else []
        for block in blocks:
            for line in block.split("\n"):
                line = line.strip()
                if not line:
                    continue
                m = self._RE_MD_HEADING.match(line)
                if m:
                    yield ("h3_under", m.group(1).strip())
                    continue
                m = self._RE_MD_BOLD_LINE.match(line)
                if m:
                    yield ("bold_title", m.group(1).strip())
                    continue
                yield ("body", line)

    def _draw_lesson_info_table(
        self,
        pdf: FPDF,
        item: Any,
        grade_name: str,
        font_regular: str,
        font_bold: str,
        primary_color: tuple[int, int, int],
        text_main: tuple[int, int, int],
    ) -> None:
        """
        جدول معلومات الدرس عبر fpdf2.table(): تفاف تلقائي للنصوص الطويلة وارتفاع صفوف ديناميكي.
        ترتيب الأعمدة (يسار→يمين): قيمة | تسمية | قيمة | تسمية.
        """
        epw = pdf.epw
        lm = pdf.l_margin
        label_bg = (230, 240, 248)
        value_bg = (255, 255, 255)
        w_l = 41.0
        w_v = (epw - 2 * w_l) / 2

        pdf.set_draw_color(*primary_color)
        pdf.set_line_width(0.35)

        title_face = FontFace(
            family=font_bold,
            size_pt=11,
            color=(255, 255, 255),
            fill_color=primary_color,
        )
        label_face = FontFace(
            family=font_bold,
            size_pt=9,
            color=primary_color,
            fill_color=label_bg,
        )
        value_face = FontFace(
            family=font_regular,
            size_pt=10,
            color=text_main,
            fill_color=value_bg,
        )

        dur = f"{item.get('duration', '40')}"
        page_ref = str(item.get("page_ref", "-"))
        activity = str(item.get("activity", "غير محدد"))
        grade_s = str(grade_name)

        pdf.set_x(lm)
        with pdf.table(
            width=epw,
            col_widths=(w_v, w_l, w_v, w_l),
            text_align=Align.R,
            line_height=5.5,
            padding=(2, 3, 2, 3),
            wrapmode=WrapMode.CHAR,
            v_align=VAlign.M,
            borders_layout=TableBordersLayout.ALL,
            align=Align.L,
            first_row_as_headings=False,
            num_heading_rows=0,
        ) as table:
            title_row = table.row()
            title_row.cell(
                self.process_text("معلومات الدرس"),
                colspan=4,
                align=Align.R,
                style=title_face,
            )

            r1 = table.row()
            r1.cell(self.process_text(dur), align=Align.R, style=value_face)
            r1.cell(self.process_text("زمن الحصـة"), align=Align.R, style=label_face)
            r1.cell(self.process_text(grade_s), align=Align.R, style=value_face)
            r1.cell(self.process_text("الصـف الدراسي"), align=Align.R, style=label_face)

            r2 = table.row()
            r2.cell(self.process_text(page_ref), align=Align.R, style=value_face)
            r2.cell(self.process_text("رقم الصفحة"), align=Align.R, style=label_face)
            r2.cell(self.process_text(activity), align=Align.R, style=value_face)
            r2.cell(self.process_text("النشاط التفاعلي"), align=Align.R, style=label_face)

        pdf.set_text_color(*text_main)
        pdf.set_draw_color(*primary_color)
        pdf.set_line_width(0.2)

    def _emit_lesson_ai_segment(
        self,
        pdf: FPDF,
        kind: str,
        text: str,
        font_regular: str,
        font_bold: str,
        primary_color: tuple[int, int, int],
        text_main: tuple[int, int, int],
    ) -> None:
        if kind == "h3_under":
            pdf.ln(2)
            pdf.set_font(font_bold, "", 11.5)
            pdf.set_text_color(*primary_color)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(
                pdf.epw,
                7.0,
                self.process_text(text),
                align="R",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
            y_line = pdf.get_y()
            pdf.set_draw_color(*primary_color)
            pdf.set_line_width(0.45)
            pdf.line(pdf.l_margin, y_line, pdf.l_margin + pdf.epw, y_line)
            pdf.set_line_width(0.2)
            pdf.ln(4)
            pdf.set_text_color(*text_main)
            return

        if kind == "bold_title":
            pdf.ln(1)
            pdf.set_font(font_bold, "", 11)
            pdf.set_text_color(*text_main)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(
                pdf.epw,
                6.8,
                self.process_text(text),
                align="R",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
            pdf.ln(2)
            return

        # body
        indent = 0.0
        body = text
        if self._RE_LIST_OR_NUM.match(body):
            indent = 5.0
        self._arabic_paragraph(
            pdf,
            body,
            font_regular,
            11,
            6.5,
            (0, 0, 0),
            x_offset=indent,
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

        primary_color = THEME_LESSON_BLUE
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

        # --- 2. جدول معلومات الدرس ---
        pdf.set_y(52)
        self._draw_lesson_info_table(
            pdf,
            item,
            grade_name,
            font_regular,
            font_bold,
            primary_color,
            text_main,
        )

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
            raw_reply = ai_reply.strip()
            for kind, segment_text in self._iter_lesson_ai_segments(raw_reply):
                self._emit_lesson_ai_segment(
                    pdf,
                    kind,
                    segment_text,
                    font_regular,
                    font_bold,
                    primary_color,
                    text_main,
                )

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
            self.process_text("توقيع خبير/ة المادة: ......................"),
            align="R",
            new_x=XPos.RIGHT,
            new_y=YPos.TOP,
        )
        pdf.cell(
            half,
            8,
            self.process_text("توقيع مُعلم/ة المادة: ......................"),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

        return self._generate_pdf_buffer(pdf)

    def create_interaction_evaluation_pdf(
        self,
        teacher_name: str,
        lesson_title: str,
        grade_name: str,
        score: int,
        gap_prob: float | int,
        trend_label: str | None,
        chart_image: BytesIO,
        body_paragraphs: list[str],
    ) -> BytesIO:
        """
        تقرير تقييم التفاعل الحالي: رأس بنفس أسلوب خطة الدرس (أزرق) + صورة الرسم البياني + نص منسّق.
        """
        pdf = FPDF()
        fonts_loaded = self._register_fonts(pdf)
        font_regular = "Amiri" if fonts_loaded else "Helvetica"
        font_bold = "AmiriBold" if fonts_loaded else "Helvetica"
        pdf.set_margins(15, 15, 15)
        pdf.set_auto_page_break(auto=True, margin=22)
        self.setup_pdf_footer(pdf, font_regular)
        pdf.add_page()

        header_blue = THEME_LESSON_BLUE
        accent = THEME_EVAL_ACCENT
        text_main = (44, 62, 80)

        pdf.set_font(font_regular, "", 12)

        pdf.set_fill_color(*header_blue)
        pdf.rect(0, 0, 210, 50, "F")
        pdf.set_y(8)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(font_bold, "", 20)
        pdf.cell(
            0,
            11,
            self.process_text("تقرير تقييم التفاعل"),
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_font(font_regular, "", 11)
        pdf.set_text_color(235, 245, 255)
        pdf.cell(
            0,
            6,
            self.process_text(f"المعلم/ة: {teacher_name}"),
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_draw_color(*accent)
        pdf.set_line_width(1.2)
        pdf.line(60, pdf.get_y() + 1, 150, pdf.get_y() + 1)
        pdf.set_line_width(0.2)

        pdf.set_y(54)
        pdf.set_text_color(*text_main)
        pdf.set_font(font_bold, "", 13)
        pdf.set_text_color(*header_blue)
        pdf.cell(
            pdf.epw,
            8,
            self.process_text(lesson_title),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_font(font_regular, "", 10)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(
            pdf.epw,
            6,
            self.process_text(f"الصف: {grade_name}"),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

        pdf.ln(4)
        chart_image.seek(0)
        try:
            pdf.image(chart_image, x=pdf.l_margin, w=pdf.epw)
        except Exception as exc:
            logging.warning("تعذر تضمين صورة الرسم في PDF: %s", exc)
            pdf.set_font(font_regular, "", 10)
            pdf.multi_cell(
                pdf.epw,
                6,
                self.process_text("(تعذر تحميل صورة الرسم البياني في الملف)"),
                align="R",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )

        pdf.ln(6)
        pdf.set_font(font_bold, "", 12)
        pdf.set_text_color(*header_blue)
        pdf.cell(
            pdf.epw,
            8,
            self.process_text("ملخص التقييم والرؤية"),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_draw_color(*accent)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + pdf.epw, pdf.get_y())
        pdf.ln(4)

        pdf.set_font(font_regular, "", 11)
        pdf.set_text_color(0, 0, 0)
        for para in body_paragraphs:
            p = para.strip()
            if not p:
                pdf.ln(3)
                continue
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(
                pdf.epw,
                6.2,
                self.process_text(p),
                align="R",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
            pdf.ln(2)

        pdf.set_font(font_regular, "", 10)
        pdf.set_text_color(80, 80, 80)
        pdf.ln(2)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            pdf.epw,
            5.5,
            self.process_text(
                f"التفاعل الحالي: {score}/3 — احتمالية الفجوة: {gap_prob}% — الاتجاه: {trend_label or '—'}"
            ),
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

        header_theme = THEME_LESSON_BLUE
        accent = THEME_EVAL_ACCENT

        pdf.set_font(font_regular, "", 12)

        pdf.set_fill_color(*header_theme)
        pdf.rect(0, 0, 210, 42, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(font_bold, "", 18)
        pdf.set_y(14)
        header_title = f"تقرير أداء الطلبة - المعلم/ة {teacher_name}"
        pdf.cell(
            0,
            10,
            self.process_text(header_title),
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_draw_color(*accent)
        pdf.set_line_width(0.8)
        pdf.line(55, pdf.get_y() + 1, 155, pdf.get_y() + 1)
        pdf.set_line_width(0.2)

        pdf.set_y(48)
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
            pdf.set_text_color(*header_theme)
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

        brand_color = THEME_FULL_REPORT
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

        head_face = FontFace(
            family=font_bold,
            size_pt=11,
            color=(0, 0, 0),
            fill_color=(230, 230, 230),
        )
        cell_face = FontFace(
            family=font_regular,
            size_pt=10,
            color=(0, 0, 0),
            fill_color=(255, 255, 255),
        )

        pdf.set_x(pdf.l_margin)
        pdf.set_draw_color(*brand_color)
        with pdf.table(
            width=pdf.epw,
            col_widths=(w_score, w_grade, w_title, w_date),
            text_align=Align.R,
            line_height=5.5,
            padding=(2, 2, 2, 2),
            wrapmode=WrapMode.CHAR,
            v_align=VAlign.M,
            borders_layout=TableBordersLayout.ALL,
            align=Align.L,
            first_row_as_headings=False,
            num_heading_rows=0,
        ) as table:
            hr = table.row()
            hr.cell(self.process_text("التقييم"), align=Align.C, style=head_face)
            hr.cell(self.process_text("الصف"), align=Align.C, style=head_face)
            hr.cell(self.process_text("عنوان الدرس"), align=Align.R, style=head_face)
            hr.cell(self.process_text("التاريخ"), align=Align.C, style=head_face)

            for row in history_data:
                score_val = str(row.get("eval_score", row.get("score", "0")))
                title_val = row.get("lesson_title", row.get("title", "---"))
                grade_val = str(row.get("grade", "---"))
                timestamp_val = str(row.get("date_time", row.get("timestamp", "---")))[:10]

                dr = table.row()
                dr.cell(self.process_text(score_val), align=Align.C, style=cell_face)
                dr.cell(self.process_text(grade_val), align=Align.C, style=cell_face)
                dr.cell(self.process_text(str(title_val)), align=Align.R, style=cell_face)
                dr.cell(self.process_text(timestamp_val), align=Align.C, style=cell_face)

        pdf.set_text_color(0, 0, 0)
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
