import os
import pandas as pd
import logging
from io import BytesIO
from datetime import datetime

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

# 2. تهيئة الكائنات المركزية
curriculum = CurriculumManager()
db_manager = DatabaseManager()
pdf_gen = LessonPDFGenerator()
orchestrator = AIModelOrchestrator()
ai_engine = AIEngine()

# --- المحرك المركزي للربط الثلاثي ---

async def get_ai_educational_response(grade_id, lesson_data, user_query, teacher_id, username):
    """يربط المنسق العام بمحرك GPT لتقديم رد تربوي دقيق."""
    try:
        # 1. تشغيل التحليل الشامل عبر المنسق (LSTM + XGBoost + BERT Context)
        analysis_result = orchestrator.run_full_analysis(
            teacher_id = str(teacher_id),
            surname = username,
            grade_level = str(grade_id),
            lesson_title = lesson_data.get('title',''),
            user_query = user_query
        )
        if not analysis_result or 'xgb_result' not in analysis_result:
            logging.error("Analysis result is None or incomplete")
            return "⚠️ عذراً، فشل تحليل البيانات التعليمية.", None

        # 2. تمرير المخرجات الرقمية والتوجيهية لمحرك التوليد GPT
        ml_insights = {
            'gap_probability': analysis_result['xgb_result'].get('gap_probability', 0),
            'trend': analysis_result.get('trend_label', 'stable'),
            'mastery': analysis_result['xgb_result'].get('mastery', 0)
        }

        response_text = await ai_engine.generate_dynanamic_lesson_content(
            user_query=user_query,
            lesson_data=lesson_data,
            ml_insights=ml_insights,
            system_guidance= analysis_result.get('final_prompt','')
        )
        return response_text, ml_insights
    except Exception as e:
        logging.error(f"Error in get_ai_educational_response: {e}")
        return "⚠️ عذراً، واجه المنسق الذكي صعوبة في تحليل البيانات.", None

# --- دوال التدفق ---

async def new_lesson_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء اختيار الصف الدراسي."""
    if not update.message: return ConversationHandler.END
    
    grades = curriculum.get_grades()
    if not grades:
        await update.message.reply_text("⚠️ خظأ: لم يتم العثور على بيانات المنهج")
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton(name, callback_data=f"GRADE_{gid}")] for gid, name in grades.items()]
    await update.message.reply_text(
        "📚 **مرحبًا بك مع مُيَّسِر**\n من فضلك اختر الفصل الدراسي:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    return CHOOSING_GRADE

async def grade_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الصف وعرض الدروس."""
    query = update.callback_query
    if not query or not query.data: return CHOOSING_GRADE
    await query.answer()

    grade_id = query.data.replace("GRADE_","")
    context.user_data['selected_grade'] = grade_id

    lessons = curriculum.get_lessons_for_grade(grade_id)
    if not lessons:
        await query.edit_message_text("⚠️ لا توجد دروس متاحة لهذا الصف.")
        return CHOOSING_GRADE
    
    keyboard = [[InlineKeyboardButton(f"📖 {lesson['title']}", callback_data=f"WEEK_{i}")] for i, lesson in enumerate(lessons)]
    
    await query.edit_message_text(
        f"📖 ✅ تم اختيار {curriculum.get_grades().get(grade_id)}\n\n"
        "🎯 **الرجاء اختيار الدرس المطلوب تحضيره:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    return CHOOSING_WEEK

async def week_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحديد الدرس والبدء في وضع الدردشة التعليمية"""
    query = update.callback_query
    if not query or not query.data or not query.message: return CHOOSING_WEEK
    await query.answer()
    
    lesson_index = int(query.data.replace("WEEK_",""))
    grade_id = context.user_data.get('selected_grade')
    lesson_details = curriculum.get_lesson_details(grade_id, lesson_index)
    if not lesson_details:
        await query.edit_message_text("⚠️ فشل جلب تفاصيل الدرس.")
        return CHOOSING_WEEK
    
    context.user_data["lesson_details"] = lesson_details

    user =update.effective_user
    uid = str(user.id) if user else "0"
    uname = user.first_name if user else "المعلم/ة"

    await query.edit_message_text("⚙️ **جاري تحليل البيانات وتصميم الخطة...**")
    
    # طلب الخطة المبدئية من المنسق
    response, _ = await get_ai_educational_response(grade_id, lesson_details, "خطة درس أولية", uid, uname)
    context.user_data['last_ai_response'] = response

    keyboard = [
        [InlineKeyboardButton(BTN_PRINT_PREP, callback_data="PRINT_REPLY")],
        [InlineKeyboardButton(BTN_START_EVAL, callback_data="START_EVAL")]
    ]
    await query.message.reply_text(response, reply_markup=InlineKeyboardMarkup(keyboard),parse_mode=ParseMode.MARKDOWN)
    return CHATTING

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة استفسارات المعلم المستمرة حول الدرس."""
    if not update.message or not update.message.text or not update.effective_user: return CHATTING

    user_query = update.message.text
    lesson_details = context.user_data.get('lesson_details')
    grade_id = context.user_data.get('selected_grade') # جلب البيانات المخزنة من الجلسة
    user = update.effective_user
    
    if not lesson_details:
        return ConversationHandler.END
    
    loading_msg = await update.message.reply_text("🔄 جاري معالجة طلبك...")
    

    response, _ = await get_ai_educational_response(grade_id, lesson_details, user_query, user.id, user.first_name) 
    context.user_data["last_ai_response"] = response
    
    keyboard = [
        [InlineKeyboardButton(BTN_PRINT_PREP, callback_data="PRINT_REPLY")],
        [InlineKeyboardButton(BTN_START_EVAL, callback_data="START_EVAL")]
    ]

    # إرسال الرد مع الأزرار
    await loading_msg.edit_text(response,reply_markup=InlineKeyboardMarkup(keyboard),parse_mode=ParseMode.MARKDOWN)
    return CHATTING

# --- دوال الطباعة ---

async def print_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طباعة الخطة الدراسية الحالية أو آخر رد من الذكاء الاصطناعي."""
    query = update.callback_query
    if not query or not query.message or not update.effective_user: return
    await query.answer("جاري تجهيز ملف PDF...")

    last_response = context.user_data.get('last_ai_response', "لا يوجد محتوى")
    user = update.effective_user
    current_lesson = context.user_data.get('lesson_details') or {}
    
    # استخراج العنوان كنص صريح لضمان عدم تمرير Dictionary
    pdf_buffer = pdf_gen.create_lesson_plan_pdf(
        lesson_title=current_lesson.get('title','خطة دراسية'),
        content=last_response,
        teacher_name=user.first_name if user else "معلم مُيَّسِر"
    )

    await query.message.reply_document(
        document=InputFile(pdf_buffer,filename=f"Lesson_Plan_{datetime.now.strftime('%H%M')}.pdf"),
        caption=f"✅ *مُيَّسِر* جاهز للطباعة: {lesson_details.get('title')}\n الصف: {lesson_details.get('grade_name')}"
    )

async def print_full_report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طباعة تقرير الأداء الشامل كما في السيناريو المطلوب."""
    query = update.callback_query
    if not query or not query.message: return
    await query.answer("🔄 جاري استخراج السجلات...")

    user_id =str(update.effective_user.id)

    # جلب كافة تقييمات المعلم من قاعدة البيانات
    try:
        df = pd.read_excel(EXCEL_DB_NAME, sheet_name=SHEET_EVALUATIONS)
        print(f"Columns in Excel: {df.columns.tolist()}")  # للتحقق من الأعمدة
        
        # 2. تصفية البيانات لهذا المعلم 
        teacher_df = df[df['teacher_id'] == user_id]
        
        if teacher_df.empty:
            await query.message.reply_text("⚠️ لا توجد سجلات تقييم كافية.")
            return
        
        report_data = []
        for _, row in teacher_df.iterrows():
            report_data.append({
                'grade': str(row.get('grade_level','---')),
                'title': str(row.get('lesson_title','---')),
                'score': int('eval_score',0),
                'timestamp': str(row.get('date_time','---'))
            })

        # 4. استدعاء دالة التقرير الشامل بالبارامترات الصحيحة
        pdf_buffer = pdf_gen.create_full_summary_pdf(update.effective_user.first_name,report_data)    
        await query.message.reply_document(
            document=InputFile(pdf_buffer, filename=f"Performance_Report_{update.effective_user.first_name}.pdf"),
            caption=f"📊 تقرير الأداء التحليلي ورؤية *مُيسِّر* المستقبلية لأداء الطلاب- المعلم: {update.effective_user.first_name}"
        )
    except Exception as e:
        print(f"Full Report Error: {e}")
        await query.message.reply_text(f"⚠️ حدث خطأ أثناء إعداد التقرير الشامل: {str(e)}")

# --- دوال التقييم ---

async def start_evaluation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء مرحلة التقييم بعد انتهاء الدرس."""
    query = update.callback_query
    if not query or not query.message: return CHATTING
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("⭐⭐⭐ ممتاز", callback_data="EVAL_3")],
        [InlineKeyboardButton("⭐⭐ جيد", callback_data="EVAL_2")],
        [InlineKeyboardButton("⭐ يحتاج تحسين", callback_data="EVAL_1")]
    ]
    await query.message.reply_text(
        "📊 **تقييم مخرجات التعلم:**\n بناءًا على تفاعل الطلاب؟ كيف تُقَيِّم مشاركتهم؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EVALUATING

async def submit_evaluation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حفظ التقييم وتحديث نموذج XGBoost (Online Learning)."""
    query = update.callback_query
    if not query or not query.data or not query.message or not update.effective_user: return EVALUATING
    await query.answer()
    
    score = int(query.data.replace("EVAL_",""))
    lesson_details = context.user_data.get('lesson_details',{})
    user =update._effective_user
    last_response = context.user_data.get('last_ai_response',"")

    if db_manager:
        db_manager.add_evaluation(
            teacher_id=str(user.id),
            lesson_title=lesson_details.get('title','غير محدد'),
            grade_level=context.user_data.get('selected_grade','---'),
            score=score,
            ai_reply=last_response,
            grade_name=lesson_details.get('grade_name','غير معروف') 
    )
    
    await query.edit_message_text(
        "✅ **تم تسجيل التقييم بنجاح!**\n"
        "ستساعد هذه البيانات محرك 'مُيسِّر' على تقديم توصيات أدق في دروسك القادمة.\n\n"
        "شكراً لك يا معلم!",
        reply_markup=MAIN_MENU_KEYBOARD
    )
    context.user_data.clear()
    return ConversationHandler.END
