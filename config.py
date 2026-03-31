import logging
import os
from dotenv import load_dotenv
from telegram import KeyboardButton, ReplyKeyboardMarkup

# المسارات الأساسية للمجلدات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# تحميل متغيرات البيئة من ملف .env
load_dotenv(dotenv_path=os.path.join(BASE_DIR, '.env'), override=True)

MODEL_DIR = os.path.join(BASE_DIR, "models")
# التأكد من وجود مجلد النماذج
if not os.path.exists(MODEL_DIR):
    os.makedirs(MODEL_DIR)

# مفاتيح الوصول (API Keys) ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN') #للموديلات التي تستخدم استدعاء GitHub

# مسارات ملفات البيانات والخطوط
# ملف المنهج الدراسي الأساسي (المدخلات)
DB_FILENAME = os.path.join(BASE_DIR, "Master_Database.xlsx")
# ملف بيانات المدرسة والتقييمات (المخرجات)
EXCEL_DB_NAME = os.path.join(BASE_DIR, "School_Data.xlsx")
# إعدادات الملفات والخطوط
FONT_PATH =os.path.join(BASE_DIR, "Amiri-Regular.ttf") #
OUTPUT_PDF_DIR = "generated_pdfs/"
# التأكد من وجود مجلد المخرجات
if not os.path.exists(OUTPUT_PDF_DIR):
    os.makedirs(OUTPUT_PDF_DIR)

# قسم إعدادات التسجيل (Logging Configuration)
# تقليل ضجيج TensorFlow (الأخبار غير المهمة)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# إعداد شكل الرسائل التي تظهر في الشاشة السوداء (Terminal)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# إسكات رسائل الـ Debug المزعجة من مكتبات محددة
logging.getLogger('tensorflow').setLevel(logging.ERROR)
logging.getLogger('PIL').setLevel(logging.WARNING)  # إذا كنت تستخدم Pillow للصور

# ثوابت قاعدة البيانات (Sheet Names)- DB Tables
SHEET_TEACHERS = 'Teachers' #
SHEET_EVALUATIONS = 'Evaluations' #
SHEET_CURRICULUM = 'Curriculum' #
SHEET_GAMES = 'Games' #

#  نصوص وأزرار الواجهة (UI Constants) 
# نصوص الأزرار الرئيسية
BTN_NEW_LESSON = "📚 درس جديد"
BTN_PROFILE = "👤 ملفي الشخصي"
BTN_HELP = "❓ مساعدة"
BTN_CANCEL = "❌ إنهاء الجلسة"

# نصوص أزرار الطباعة والتقارير (التي سألت عنها)
BTN_PRINT_PREP = "📄 طباعة التحضير"
BTN_PRINT_REPORT = "📊 طباعة تقرير الأداء"
BTN_START_EVAL = "⭐ تقييم التفاعل"

# تصميم لوحة المفاتيح الرئيسية
MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BTN_NEW_LESSON), KeyboardButton(BTN_PROFILE)],
        [KeyboardButton(BTN_HELP), KeyboardButton(BTN_CANCEL)]
    ],
    resize_keyboard=True
)

# قواعد تقييم مشاركة الطلاب (Logic Constants)
# تم تعديلها لتوافق المنطق الحسابي الصحيح
EVAL_MAPPING = {
    3: "ممتاز", 
    2: "جيد", 
    1: "ضعيف"
}

#  حالات المحادثة (Conversation States) 
CHOOSING_GRADE, CHOOSING_WEEK, CHATTING, GENERATING, EVALUATING = range(5) #

#  إعدادات النماذج (ML Config) 
# مسارات حفظ النماذج المدربة مستقبلاً
XGB_WEIGHTS_PATH = os.path.join(MODEL_DIR, "dynamic_weights.json")
MODEL_PATH_XGB = os.path.join(MODEL_DIR, "xgb_model.json")
MODEL_PATH_LSTM = os.path.join(MODEL_DIR, "student_trend_lstm_model.h5")