import os
import pandas as pd
import logging
from io import BytesIO
from datetime import datetime
from typing import cast, Dict, Any

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

# --- المحرك المركزي للربط الثلاثي ---

async def get_ai_educational_response(grade_id, lesson_data, user_query, teacher_id, username):
    """يربط المنسق العام بمحرك GPT لتقديم رد تربوي دقيق."""
    try:
        # 1. تشغيل التحليل الشامل عبر المنسق (LSTM + XGBoost + BERT Context)
        final_prompt = orchestrator.process_lesson_request(
            teacher_id = str(teacher_id),
            surname = username,
            lesson_title = lesson_data.get('title','درس جديد'),
            user_query = user_query,
            lesson_goal = lesson_data.get('goal', 'تحقيق نواتج التعلم')
        )
        
        # التحقق من صحة النتيجة (يجب أن تكون قاموساً وتحتوي على 'xgb_result')
        if not isinstance(final_prompt, dict) or 'xgb_result' not in final_prompt:
            logging.error("Analysis result is None or incomplete(expected dict with 'xgb_result')")
            return "⚠️ عذراً، فشل تحليل البيانات التعليمية.", None

        prompt_dict = cast(Dict[str, Any], final_prompt)
        xgb_result = prompt_dict.get('xgb_result', {})
        system_guidance = prompt_dict.get('system_prompt', '')
        # 2. تمرير المخرجات الرقمية والتوجيهية لمحرك التوليد GPT
        ml_insights = {
            'gap_probability': xgb_result.get('gap_probability', 0),
            'trend': prompt_dict.get('trend_label','stable'),
            'mastery': xgb_result.get('mastery', 0)
        }

        response_text = await ai_engine.generate_dynanamic_lesson_content(
            user_query=user_query,
            lesson_data=lesson_data,
            ml_insights=ml_insights,
            system_guidance= system_guidance
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
    
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"GRADE_{gid}")] 
        for gid, name in grades.items()]
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
    lessons = [lesson for lesson in lessons if isinstance(lesson, dict)]
    if not lessons:
        await query.edit_message_text("⚠️ لا توجد دروس متاحة لهذا الصف.")
        return CHOOSING_GRADE
    
    keyboard = [
        [InlineKeyboardButton(
            f"📖 {lesson.get('title','درس غير معروف')}",
            callback_data=f"WEEK_{i}"
        )] for i, lesson in enumerate(lessons)
    ]
    
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

    last_response = str(context.user_data.get('last_ai_response', "لا يوجد محتوى"))
    current_lesson = context.user_data.get('lesson_details') or {}
    
    # استخراج العنوان كنص صريح لضمان عدم تمرير Dictionary
    pdf_buffer = pdf_gen.create_lesson_plan_pdf(
        item= current_lesson,
        ai_reply=last_response,
        grade_name=str(current_lesson.get('grade_name', 'غير محدد'))
    )

    await query.message.reply_document(
        document=InputFile(pdf_buffer,filename=f"Lesson_Plan_{datetime.now().strftime('%H%M')}.pdf"),
        caption=f"✅ *مُيَّسِر* جاهز للطباعة: {current_lesson.get('title')}\n الصف: {current_lesson.get('grade_name')}"
    )

async def print_full_report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طباعة تقرير الأداء الشامل كما في السيناريو المطلوب."""
    query = update.callback_query
    if not query or not query.message: return
    await query.answer("🔄 جاري استخراج السجلات...")

    user_id =str(update.effective_user.id)

    # جلب كافة تقييمات المعلم من قاعدة البيانات
    try:
        if not os.path.exists(EXCEL_DB_NAME):
            await query.message.reply_text("⚠️ قاعدة البيانات غير موجودة حالياً.")
            return
        
        df = pd.read_excel(EXCEL_DB_NAME, sheet_name=SHEET_EVALUATIONS)
        #print(f"Columns in Excel: {df.columns.tolist()}")  # للتحقق من الأعمدة
        
        # 2. تصفية البيانات لهذا المعلم 
        teacher_df = df[df['teacher_id'].astype(str) == user_id]
        
        if teacher_df.empty:
            await query.message.reply_text("⚠️ لا توجد سجلات تقييم كافية.")
            return
        
        report_data = []
        for _, row in teacher_df.iterrows():
            eval_score = int(row.get('eval_score', row.get('score', 0)))
            report_data.append({
                'grade': str(row.get('grade_level','---')),
                'title': str(row.get('lesson_title',row.get('title','---'))),
                'lesson_title': str(row.get('lesson_title',row.get('title','---'))),
                'score': eval_score,
                'eval_score': eval_score,
                'date_time': str(row.get('date_time', row.get('timestamp', '---'))),
                'timestamp': str(row.get('date_time', row.get('timestamp', '---')))[:10]
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
    if not query or not query.data or not query.message or not update.effective_user:
        return ConversationHandler.END
     
    await query.answer()
    
    # 1. تعريف المتغيرات الأساسية من سياق المستخدم (Context)
    score = int(query.data.replace("EVAL_",""))
    user =update.effective_user
    lesson_details = context.user_data.get('lesson_details',{})
    last_response = context.user_data.get('last_ai_response',"")
    

    # استخراج grade_level بشكل آمن وتخزينه في متغير محلي لتجنب خطأ Undefined
    current_grade = context.user_data.get('selected_grade', '---')
    lesson_title = lesson_details.get('title', 'درس جديد')
    grade_name = lesson_details.get('grade_name', 'غير معروف')

    try:
        # 2. الحفظ في قاعدة البيانات باستخدام المسميات الصحيحة في db_manager
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
        )

        # استدعاء المنسق للحصول على تنبؤ LSTM وفجوة XGBoost
        viz_data = orchestrator.process_lesson_request(
            lesson_title=lesson_title,
            user_query="تقييم روتيني",
            lesson_goal="---",
            grade_level=current_grade
        )

        # استخراج القيم التنبؤية
        predicted_val = viz_data.get('trend_value', 2.0)
        gap_prob = viz_data.get('xgb_result', {}).get('gap_probability', 0)

        # 4. توليد الرسم البياني عبر PerformanceVisualizer
        # نرسل آخر 5 تقييمات للوضوح
        chart_buf = visualizer.generate_smart_chart(
            history=history[-5:] if len(history) > 0 else [score],
            current_score=score,
            prediction=predicted_val,
            gap_prob=gap_prob,
            lesson_title=lesson_title
        )
        
        # 5. إرسال الصورة والتقرير النهائي للمعلم
        await query.message.reply_photo(
            photo=chart_buf,
            caption=(
                f"✅ **تم تسجيل التقييم بنجاح!**\n\n"
                f"📊 **رؤية مُيَسِّر الذكية للدرس القادم:**\n"
                f"• مستوى التفاعل الحالي: {score}/3\n"
                f"• احتمالية الفجوة القادمة: {gap_prob}%\n\n"
                f"💡 *الرسم البياني يوضح اتجاه الأداء المتوقع بناءً على صعوبة المنهج وتاريخ الصف.*"
            ),
            parse_mode=ParseMode.MARKDOWN)
        
        await query.delete_message()  # حذف رسالة التقييم لتقليل الفوضى في الدردشة
        
    except Exception as e:
        logging.error(f"Error generating visual report: {e}")
        await query.message.reply_text(f"✅ تم حفظ التقييم بنجاح لمستوى {current_grade}، ولكن تعذر رسم المخطط.")
        
    #context.user_data.clear()
    return ConversationHandler.END
