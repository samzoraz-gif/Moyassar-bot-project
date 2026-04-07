import pandas as pd
import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# 1. الاستيراد من الإعدادات والموديلات
from config import EXCEL_DB_NAME, BTN_PRINT_REPORT, BTN_HELP, MAIN_MENU_KEYBOARD # المستوردة من إعدادات النظام
from data.db_manager import DatabaseManager
from .ai_orchestrator import AIModelOrchestrator

# تهيئة المحركات مع ضمان النوع
db_manager: DatabaseManager = DatabaseManager()
orchestrator: AIModelOrchestrator = AIModelOrchestrator()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نقطة انطلاق البوت وتسجيل المعلم."""
    if not update._effective_user or not update.message:
        return
    
    user = update.effective_user
    if not user: return
    user_id = str(user.id)
    username = user.username  or user.first_name or "Unkown"
    if db_manager:
        db_manager.register_teacher(user_id, username=username)
    
    welcome_message = (
        f"🌟 **مرحباً بك يا معلم/ة {user.first_name} في نظام مُيسِّر الذكي!**\n\n"
        "أنا رفيقك الرقمي المدعوم بتقنيات الذكاء الاصطناعي "
        "لتحويل بياناتك الصفية إلى رؤى تربوية ملهمة. 🚀\n\n"
        "🎯 **كيف أساعدك اليوم؟**\n"
        "• ابدأ بتحضير درس جديد بلمسة ذكية.\n"
        "• تابع تقارير أدائك وتحليل اتجاه طلابك.\n"
        "• احصل على توصيات تربوية مخصصة.\n\n"
        "💡 **ابدأ الآن باختيار 'درس جديد' من القائمة أدناه.**"
    )
    await update.message.reply_text(welcome_message, reply_markup=MAIN_MENU_KEYBOARD, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END # لضمان الخروج من أي محادثة سابقة

async def help_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض رسالة المساعدة عند الضغط على زر المساعدة أو كتابة /help."""
    help_text = (
        "❓ **مساعدة مُيَّسِر**\n\n"
        "• اضغط على 'درس جديد' لبدء تحضير درس.\n"
        "• اضغط على '👤 ملفي الشخصي' لعرض تقرير الأداء.\n"
        "• اضغط على '❌ إنهاء الجلسة' للخروج من أي وضع.\n"
        "• يمكنك أيضًا إرسال أي سؤال تعليمي خلال المحادثة."
    )
    if update.callback_query:
        await update.callback_query.answer()
        if update.callback_query.message:
            await update.callback_query.message.reply_text(help_text, reply_markup=MAIN_MENU_KEYBOARD, parse_mode=ParseMode.MARKDOWN)
    elif update.message:
        await update.message.reply_text(help_text, reply_markup=MAIN_MENU_KEYBOARD, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات المعلم وتحليل الأداء بناءً على البيانات التاريخية."""
    if not update.effective_user or not update.message:
        return
    
    user = update.effective_user
    teacher_id = str(user.id)
    username = user.username or user.first_name or "المعلمة"
    try:
        history = db_manager.get_teacher_evaluation_history(teacher_id=teacher_id)

        if not orchestrator:
            await update.message.reply_text("⚠️ النظام التحليلي غير جاهز حالياً.")
            return

        # 2. تحليل الاتجاه عبر محرك LSTM الموجود داخل المنسق
        trend_label, _ = orchestrator.lstm_engine.analyze_trend_lstm(history)

        # 3. حساب المتوسط
        avg_score = sum(history) / len(history) if history else 0
        
        # 4. صياغة التوصية
        if not history:
            status = "لم نجمع بيانات كافية بعد. ابدأ بتحضير دروسك لنقوم بتحليل أداء طلابك."
        elif avg_score > 2.5:
            status = "أداء طلابك ممتاز! نظام مُيسِّر سيوصي بأنشطة إثرائية وتحديات أعلى."
        elif avg_score < 1.5:
            status = "هناك فجوة تعليمية ملحوظة. النظام سيركز على استراتيجيات التبسيط والدعم."
        else:
            status = "الأداء مستقر. سنعمل على تعزيز المشاركة النشطة في دروسك القادمة."    
        
        # --- ج. بناء واجهة المستخدم (UI) ---    
        response = (
            f"👤 **الملف الشخصي للمعلم/ة:{user.first_name}**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🤖 **رؤية مُيسِر التحليلية:**\n"
            f"📊 *المعدل ألاداء العام:* {avg_score:.2f}/3\n"
            f"📈 *اتجاه مستوى ومشاركة الطلاب:* {trend_label}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💡 **توصية نظام مُيَّسِر :**\n"
            f"{status}\n"
            f"*يمكنك طلب تقرير مفصل عبر الزر أدناه:*"
        )

        keyboard = [[InlineKeyboardButton(BTN_PRINT_REPORT, callback_data="PRINT_FULL_REPORT")]]
        await update.message.reply_text(response, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    except Exception as e:
        logging.error(f"Error in show_profile: {e}")
        await update.message.reply_text(f"⚠️ خطأ في جلب البيانات: {e}")
        return ConversationHandler.END

async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إيقاف الجلسة الحالية وتنظيف البيانات المؤقتة."""
    if context.user_data is not None:
        context.user_data.clear() # تنظيف بيانات الجلسة المؤقته

    farewell_message = (
        "🛑 **تم إنهاء الجلسة الحالية.**\n\n"
        "شكراً لثقتك في **مُيَّسِر** كشريك في رحلتك التعليمية.\n "
        "✨ **دمت ملهمًا لطلابك!**"
    )
    if update.callback_query:
        await update.callback_query.answer()
        if update.callback_query.message:
            await update.callback_query.message.reply_text(
                farewell_message,
                reply_markup=MAIN_MENU_KEYBOARD,
                parse_mode=ParseMode.MARKDOWN
            )
    elif update.message:
        await update.message.reply_text(farewell_message, reply_markup=MAIN_MENU_KEYBOARD, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END