import os

from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ConversationHandler
from config import (
    TELEGRAM_BOT_TOKEN, BTN_NEW_LESSON, BTN_PROFILE, BTN_CANCEL, 
    CHOOSING_GRADE, CHOOSING_WEEK, CHATTING, EVALUATING
    )
from handlers.commands import start, show_profile, cancel_action
from handlers.conversation import (
    new_lesson_flow, grade_choice, week_choice, 
    handle_ai_chat, start_evaluation, submit_evaluation, 
    print_reply_handler, print_full_report_handler
)

def main():
    # تحقق من وجود التوكن
    if TELEGRAM_BOT_TOKEN is None:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set. Please check your config.")
    # بناء التطبيق
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # إعداد إدارة المحادثات (ConversationHandler)
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start), 
            MessageHandler(filters.Regex(f"^{BTN_NEW_LESSON}$"), new_lesson_flow)
        ],
        states={
            CHOOSING_GRADE: [CallbackQueryHandler(grade_choice, pattern="^GRADE_")],
            CHOOSING_WEEK: [CallbackQueryHandler(week_choice, pattern="^WEEK_")],
            CHATTING: [
                CallbackQueryHandler(print_reply_handler, pattern="^PRINT_REPLY$"),
                CallbackQueryHandler(start_evaluation, pattern="^START_EVAL$"),
                CallbackQueryHandler(print_full_report_handler, pattern="^PRINT_EVAL_REPORT$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^{BTN_CANCEL}$"), handle_ai_chat)
            ],
            EVALUATING: [CallbackQueryHandler(submit_evaluation, pattern="^EVAL_")]
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{BTN_CANCEL}$"), cancel_action),
            CommandHandler("cancel", cancel_action),
            CommandHandler("start", start)],
        allow_reentry=True
    )

    # إضافة الـ Handlers الأساسية
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_PROFILE}$"), show_profile))
    #app.add_handler(CallbackQueryHandler(print_full_report_handler, pattern="^PRINT_FULL_REPORT$"))

    print("🚀 نظام مُيَّسِر الذكي يعمل الآن بكامل طاقته...")
    app.run_polling()

if __name__ == "__main__":
    main()