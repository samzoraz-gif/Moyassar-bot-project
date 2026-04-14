import os
import pandas as pd
import logging
from io import BytesIO
from datetime import datetime
from typing import cast, Dict, Any, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# 1. الاستيرادات الأساسية من المشروع
from config import *
from data.curriculum import CurriculumManager
from data.db_manager import DatabaseManager
from utils.pdf_generator import LessonPDFGenerator
from .ai_orchestrator import AIModelOrchestrator
from models.ai_engine import AIEngine
from utils.visualizer import PerformanceVisualizer

# 2. تهيئة الكائنات المركزية
curriculum = CurriculumManager()
db_manager = DatabaseManager()
pdf_gen = LessonPDFGenerator()
orchestrator = AIModelOrchestrator()
ai_engine = AIEngine()
visualizer = PerformanceVisualizer()


def _ensure_user_data(context):
    if context.user_data is None:
        context.user_data = {}
    return context.user_data

# --- المحرك المركزي للربط الثلاثي ---

async def get_ai_educational_response(grade_id: str, lesson_data: Optional[Dict], user_query: str, teacher_id: str, username: str):
    """يربط المنسق العام بمحرك GPT لتقديم رد تربوي دقيق."""
    try:
        # 1. تشغيل التحليل الشامل عبر المنسق (LSTM + XGBoost + BERT Context)
        final_prompt = orchestrator.process_lesson_request(
            teacher_id=str(teacher_id),
            surname=username,
            lesson_title=lesson_data.get('title', 'درس جديد') if lesson_data else 'درس جديد',
            user_query=user_query,
            lesson_goal=lesson_data.get('goal', 'تحقيق نواتج التعلم') if lesson_data else 'تحقيق نواتج التعلم'
        )
        
        # التحقق من صحة النتيجة (يجب أن تكون قاموساً وتحتوي على 'xgb_result')
        if not isinstance(final_prompt, dict) or 'xgb_result' not in final_prompt:
            logging.error("Analysis result is None or incomplete (expected dict with 'xgb_result')")
            return "⚠️ عذراً، فشل تحليل البيانات التعليمية.", None

        prompt_dict = cast(Dict[str, Any], final_prompt)
        xgb_result = prompt_dict.get('xgb_result', {}) or {}
        system_guidance = prompt_dict.get('system_prompt', '')
        # 2. تمرير المخرجات الرقمية والتوجيهية لمحرك التوليد GPT
        ml_insights = {
            'gap_probability': xgb_result.get('gap_probability', 0),
            'trend': prompt_dict.get('trend_label', 'stable'),
            'mastery': xgb_result.get('mastery', 0)
        }

        response_text = await ai_engine.generate_dynamic_lesson_content(
            user_query=user_query,
            lesson_data=lesson_data or {},
            ml_insights=ml_insights,
            system_guidance=system_guidance
        )
        return response_text, ml_insights
    except Exception as e:
        logging.error(f"Error in get_ai_educational_response: {e}")
        return "⚠️ عذراً، واجه المنسق الذكي صعوبة في تحليل البيانات.", None

# --- دوال التدفق ---

async def new_lesson_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء اختيار الصف الدراسي."""
    if not update.message: 
        return ConversationHandler.END
    
    grades = curriculum.get_grades()
    if not grades:
        await update.message.reply_text("⚠️ خطأ: لم يتم العثور على بيانات المنهج")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"GRADE_{gid}")] 
        for gid, name in grades.items()
    ]
    await update.message.reply_text(
        "📚 **مرحباً بك مع مُيسِر**\\nمن فضلك اختر الفصل الدراسي:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    return CHOOSING_GRADE

async def grade_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الصف وعرض الدروس."""
    query = update.callback_query
    if not query or not query.data: 
        return CHOOSING_GRADE
    await query.answer()

    grade_id = query.data.replace("GRADE_", "")
    user_data = _ensure_user_data(context)
    user_data['selected_grade'] = grade_id

    lessons = curriculum.get_lessons_for_grade(grade_id)
    lessons = [lesson for lesson in lessons if isinstance(lesson, dict)] if lessons else []
    if not lessons:
        await query.edit_message_text("⚠️ لا توجد دروس متاحة لهذا الصف.")
        return CHOOSING_GRADE
    
    keyboard = [
        [InlineKeyboardButton(
            f"📖 {lesson.get('title', 'درس غير معروف')}",
            callback_data=f"WEEK_{i}"
        )] for i, lesson in enumerate(lessons)
    ]
    
    grade_name = curriculum.get_grades().get(grade_id, 'غير معروف')
    await query.edit_message_text(
        f"📖 ✅ تم اختيار {grade_name}\\n\\n"
        "🎯 **الرجاء اختيار الدرس المطلوب تحضيره:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    return CHOOSING_WEEK

async def week_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحديد الدرس والبدء في وضع الدردشة التعليمية"""
    query = update.callback_query
    if not query or not query.data or not query.message: 
        return CHOOSING_WEEK
    await query.answer()
    
    user_data = _ensure_user_data(context)
    lesson_index = int(query.data.replace("WEEK_", ""))
    grade_id = str(user_data.get('selected_grade', ''))
    lesson_details = curriculum.get_lesson_details(grade_id, lesson_index)
    if not lesson_details:
        await query.edit_message_text("⚠️ فشل جلب تفاصيل الدرس.")
        return CHOOSING_WEEK
    
    user_data["lesson_details"] = lesson_details

    user = update.effective_user
    uid = str(user.id) if user else "0"
    uname = user.first_name if user else "المعلم/ة"

    await query.edit_message_text("⚙️ **جاري تحليل البيانات وتصميم الخطة...**")
    
    # طلب الخطة المبدئية من المنسق
    response, _ = await get_ai_educational_response(str(grade_id or ''), lesson_details, "خطة درس أولية", uid, uname)
    user_data['last_ai_response'] = response

    keyboard = [
        [InlineKeyboardButton(BTN_PRINT_PREP, callback_data="PRINT_REPLY")],
        [InlineKeyboardButton(BTN_START_EVAL, callback_data="START_EVAL")]
    ]
    await query.message.reply_text(response, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return CHATTING

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة استفسارات المعلم المستمرة حول الدرس."""
    if not update.message or not update.message.text or not update.effective_user: 
        return CHATTING

    user_data = _ensure_user_data(context)
    user_query = update.message.text
    lesson_details = user_data.get('lesson_details')
    grade_id = str(user_data.get('selected_grade', ''))
    user = update.effective_user
    
    if not lesson_details:
        return ConversationHandler.END
    
    loading_msg = await update.message.reply_text("🔄 جاري معالجة طلبك...")

    response, _ = await get_ai_educational_response(grade_id, lesson_details, user_query, str(user.id), user.first_name or "المعلم/ة") 
    user_data["last_ai_response"] = response
    
    keyboard = [
        [InlineKeyboardButton(BTN_PRINT_PREP, callback_data="PRINT_REPLY")],
        [InlineKeyboardButton(BTN_START_EVAL, callback_data="START_EVAL")]
    ]

    await loading_msg.edit_text(response, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return CHATTING

# --- دوال الطباعة ---

async def print_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طباعة الخطة الدراسية الحالية أو آخر رد من الذكاء الاصطناعي."""
    query = update.callback_query
    if not query or not query.message or not update.effective_user: 
        return
    await query.answer("جاري تجهيز ملف PDF...")

    user_data = _ensure_user_data(context)
    last_response = str(user_data.get('last_ai_response', "لا يوجد محتوى"))
    current_lesson = user_data.get('lesson_details') or {}

    grade_id = user_data.get('selected_grade')
    grade_name = curriculum.get_grades().get(grade_id, 'غير معروف') if grade_id else 'غير معروف'
    
    pdf_buffer = pdf_gen.create_lesson_plan_pdf(
        item=current_lesson,
        ai_reply=last_response,
        grade_name=grade_name
    )

    await query.message.reply_document(
        document=InputFile(pdf_buffer, filename=f"Lesson_Plan_{datetime.now().strftime('%H%M')}.pdf"),
        caption=f"✅ *مُيَّسِر* جاهز للطباعة: {current_lesson.get('title', 'غير محدد')}\\nالصف: {current_lesson.get('grade_name', 'غير محدد')}",
        parse_mode=ParseMode.MARKDOWN
    )

async def print_full_report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طباعة تقرير الأداء الشامل كما في السيناريو المطلوب."""
    query = update.callback_query
    if not query or not query.message or not update.effective_user: 
        return
    await query.answer("🔄 جاري استخراج السجلات...")

    user = update.effective_user
    user_id = str(user.id)
    user_name = user.first_name or "المعلم/ة"

    # جلب كافة تقييمات المعلم من قاعدة البيانات
    try:
        if not os.path.exists(EXCEL_DB_NAME):
            await query.message.reply_text("⚠️ قاعدة البيانات غير موجودة حالياً.")
            return
        
        df = pd.read_excel(EXCEL_DB_NAME, sheet_name=SHEET_EVALUATIONS)
        if df is None or df.empty:
            await query.message.reply_text("⚠️ لا توجد بيانات تقييم.")
            return
        
        # تصفية البيانات لهذا المعلم 
        teacher_df = df[df['teacher_id'].astype(str) == user_id]
        
        if teacher_df.empty:
            await query.message.reply_text("⚠️ لا توجد سجلات تقييم كافية.")
            return
        
        report_data = []
        for _, row in teacher_df.iterrows():
            row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
            eval_score = int(row_dict.get('eval_score', row_dict.get('score', 0)))
            report_data.append({
                'grade': str(row_dict.get('grade_level', '---')),
                'title': str(row_dict.get('lesson_title', row_dict.get('title', '---'))),
                'lesson_title': str(row_dict.get('lesson_title', row_dict.get('title', '---'))),
                'score': eval_score,
                'eval_score': eval_score,
                'date_time': str(row_dict.get('date_time', row_dict.get('timestamp', '---'))),
                'timestamp': str(row_dict.get('date_time', row_dict.get('timestamp', '---')))[:10]
            })

        pdf_buffer = pdf_gen.create_full_summary_pdf(user_name, report_data)    
        await query.message.reply_document(
            document=InputFile(pdf_buffer, filename=f"Performance_Report_{user_name}.pdf"),
            caption=f"📊 تقرير الأداء التحليلي ورؤية *مُيسِّر* المستقبلية لأداء الطلاب- المعلم: {user_name}",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logging.error(f"Full Report Error: {e}")
        await query.message.reply_text(f"⚠️ حدث خطأ أثناء إعداد التقرير الشامل: {str(e)}")

# --- دوال التقييم ---

async def start_evaluation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء مرحلة التقييم بعد انتهاء الدرس."""
    query = update.callback_query
    if not query or not query.message: 
        return CHATTING
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("⭐⭐⭐ ممتاز", callback_data="EVAL_3")],
        [InlineKeyboardButton("⭐⭐ جيد", callback_data="EVAL_2")],
        [InlineKeyboardButton("⭐ يحتاج تحسين", callback_data="EVAL_1")]
    ]
    await query.message.reply_text(
        "📊 **تقييم مخرجات التعلم:**\\nبناءًا على تفاعل الطلاب؟ كيف تُقَيِّم مشاركتهم؟",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    return EVALUATING

async def submit_evaluation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حفظ التقييم وتحديث نموذج XGBoost (Online Learning)."""
    query = update.callback_query
    if not query or not query.data or not query.message or not update.effective_user:
        return ConversationHandler.END
     
    await query.answer()
    
    user_data = _ensure_user_data(context)
    score = int(query.data.replace("EVAL_", ""))
    user = update.effective_user
    lesson_details = user_data.get('lesson_details', {})
    last_response = user_data.get('last_ai_response', "")

    current_grade = user_data.get('selected_grade', '---')
    lesson_title = lesson_details.get('title', 'درس جديد') if lesson_details else 'درس جديد'
    grade_name = lesson_details.get('grade_name', 'غير معروف') if lesson_details else 'غير معروف'

    try:
        if db_manager:
            db_manager.add_evaluation(
                teacher_id=str(user.id),
                lesson_title=lesson_title,
                grade_level=current_grade,
                score=score,
                ai_reply=last_response,
                grade_name=grade_name
            )
    except Exception as e:
        logging.error(f"Database Error: {e}")

    # 3. الربط مع الرسام والمحلل الذكي
    try:
        history = db_manager.get_teacher_evaluation_history(
            teacher_id=str(user.id),
            grade_level=current_grade
        ) or []

        viz_data = orchestrator.process_lesson_request(
            teacher_id=str(user.id),
            surname=user.first_name or user.username or "المعلم",
            lesson_title=lesson_title,
            user_query="تقييم روتيني",
            lesson_goal="---",
            grade_level=current_grade
        ) or {}

        predicted_val = float(viz_data.get("trend_value") or 2.0)
        xgb_result = viz_data.get("xgb_result", {}) or {}
        gap_prob = xgb_result.get("gap_probability", 0)
        try:
            gap_prob = float(gap_prob)
        except (TypeError, ValueError):
            gap_prob = 0.0
        trend_label = viz_data.get("trend_label")

        score_history = history[-5:] if history else []
        chart_buf = visualizer.generate_smart_chart(
            history_scores=score_history,
            prediction=predicted_val,
            gap_prob=gap_prob,
            lesson_title=lesson_title,
        )

        chart_png = chart_buf.getvalue()
        photo_io = BytesIO(chart_png)

        teacher_dn = user.first_name or user.username or "المعلم"
        body_paragraphs = [
            "تم تسجيل تقييم تفاعل الطلاب لهذا الدرس بنجاح.",
            "يوضح الرسم البياني أداء التفاعل في آخر التقييمات مع تنبؤ للحصة القادمة وفق نموذج تحليل الفجوة.",
            f"مستوى التفاعل المسجّل لهذا الدرس: {score} من 3.",
            f"تقدير احتمالية الفجوة في الحصة القادمة: {gap_prob:g}٪.",
            "يُنصح بمتابعة الاستراتيجيات الناجحة عند ارتفاع التفاعل، أو تنويع الأنشطة والتدرج في الصعوبة عند الحاجة.",
        ]

        caption = (
            "✅ *تم تسجيل التقييم بنجاح!*\n\n"
            "📊 *رؤية مُيسّر الذكية للدرس القادم:*\n"
            f"• مستوى التفاعل الحالي: {score}/3\n"
            f"• احتمالية الفجوة القادمة: {gap_prob:g}%\n\n"
            "💡 الرسم البياني يوضح اتجاه الأداء المتوقع وفقاً لصعوبة المنهج وتاريخ الصف."
        )

        await query.message.reply_photo(
            photo=photo_io,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
        )

        try:
            eval_pdf = pdf_gen.create_interaction_evaluation_pdf(
                teacher_name=teacher_dn,
                lesson_title=lesson_title,
                grade_name=grade_name,
                score=score,
                gap_prob=gap_prob,
                trend_label=str(trend_label) if trend_label is not None else None,
                chart_image=BytesIO(chart_png),
                body_paragraphs=body_paragraphs,
            )
            await query.message.reply_document(
                document=InputFile(
                    eval_pdf,
                    filename=f"Interaction_Eval_{datetime.now().strftime('%H%M')}.pdf",
                ),
                caption="📄 نسخة PDF من التقييم والرسم البياني (نفس ألوان تقارير مُيسّر)",
            )
        except Exception as pdf_err:
            logging.error("Interaction evaluation PDF failed: %s", pdf_err)

        await query.delete_message()
        
    except Exception as e:
        logging.error(f"Error generating visual report: {e}")
        await query.message.reply_text(f"✅ تم حفظ التقييم بنجاح لمستوى {current_grade}، ولكن تعذر رسم المخطط.")
        
    return ConversationHandler.END
