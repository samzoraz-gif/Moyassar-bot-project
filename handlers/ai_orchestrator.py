import pandas as pd
import os

# استدعاء النماذج من مجلد models
from models.trend_analyzer import LSTMEngine
from models.predictor import EducationalXGBManager
from models.nlp_engine import EducationalBERTManager
from data.db_manager import DatabaseManager

# استيراد الاعدادات المركزية
from config import *

class AIModelOrchestrator:
    """
    المنسق العام لنماذج الذكاء الاصطناعي.
    يقوم بإدارة تدفق البيانات بين (LSTM -> XGBoost -> DistilBERT) 
    لإنتاج موجه (Prompt) دقيق واحترافي لـ OpenAI.
    """
    def __init__(self):
        print("⏳ جاري تهيئة محركات الذكاء الاصطناعي (المنسق العام)...")
        self.lstm_engine = LSTMEngine()
        self.xgb_engine = EducationalXGBManager()
        self.nlp_engine = EducationalBERTManager()
        print("✅ جميع المحركات جاهزة للعمل.")

    def _get_historical_evaluations(self, teacher_id: str, surname:str, grade_level: str) -> list:
        """دالة مساعدة لجلب تاريخ تقييمات المعلم من ملف الإكسيل لتغذية LSTM."""
        try:
            if not os.path.exists(EXCEL_DB_NAME):
                return[]
            df = pd.read_excel(EXCEL_DB_NAME, sheet_name=SHEET_EVALUATIONS)
            teacher_data = df[df['teacher_id'] == teacher_id]['eval_score'].tolist()
            
            teacher_df = pd.read_excel(EXCEL_DB_NAME, sheet_name=SHEET_TEACHERS)
            teacher_info = teacher_df[teacher_df['surname'] == surname]
            # إذا كان المعلم جديداً، نجلب متوسط تقييمات الصف
            if not teacher_data:
                class_data = df[df['grade'] == grade_level]['eval_score'].tolist()
                return class_data if class_data else [2.0, 2.0]
            
            return teacher_data
        except Exception as e:
            print(f"⚠️ خطأ في قراءة سجل التقييمات: {e}")
            return [2.0]

    def process_lesson_request(self, teacher_id: str, surname: str, lesson_title: str, user_query: str, lesson_goal: str, grade_level: str = '1') -> dict:
        """
        الوظيفة الرئيسية: تستقبل طلب المعلم، تمرره على النماذج الثلاثة，
        وتعيد النص النهائي (Prompt) الجاهز للإرسال إلى OpenAI.
        """
        try:
            history=self._get_historical_evaluations(teacher_id , surname, grade_level=grade_level)

            features = {
            'teacher_id': teacher_id,
            'lesson_title': lesson_title, # تم التأكد من الاسم هنا
            'user_query': user_query,
            'grade_level': grade_level
            }
        # ==========================================
        # 1. جلب البيانات الديناميكية (XGBoost Feature Fetcher)
        # ==========================================
            features = self.xgb_engine.fetch_dynamic_features(teacher_id, surname, lesson_title)
            
            # استخراج الصف لسحب التاريخ (نفترض أن المنهج يحدد الصف، وإلا نستخدم grade_level الممرر إلى الدالة)
            dynamic_grade = features.get('grade_level', grade_level)
            
            # ==========================================
            # 2. تحليل الاتجاه الزمني (LSTM Engine)
            # ==========================================
            history_scores = self._get_historical_evaluations(teacher_id=teacher_id , surname=surname, grade_level=dynamic_grade)
            
            # استدعاء دالة التنبؤ من LSTM (نستخدم الدالة الموجودة في الملف المرفق)
            # بناءً على الكود المرفق، LSTMEngine يحتوي على منطق التنبؤ داخله
            trend_label, trend_value = self.lstm_engine.analyze_trend_lstm(history_scores) if hasattr(self.lstm_engine, 'analyze_trend_lstm') else ("مستقر", 0.5)

            # ==========================================
            # 3. التنبؤ بالفجوة التعليمية (XGBoost Engine)
            # ==========================================
            xgb_result = self.xgb_engine.predict_educational_outcome(
                participation=features.get('participation',0.7),
                lstm_trend=trend_value,
                difficulty=features.get('difficulty', 'متوسط'),
                duration=features.get('duration', 40),
                game_template=features.get('game_template', 'جماعي')
            )

            # ==========================================
            # 4. بناء الموجه السياقي (DistilBERT / NLP Engine)
            # ==========================================
            # نمرر النتائج لمحرك NLP ليبني رسالة دقيقة لـ OpenAI
            # يتم تمرير المتغيرات المستخرجة إلى دالة guide_ai_generation
            
            # تجهيز المتغيرات لـ NLP
            gap_prob = xgb_result['gap_probability']
            strategy = xgb_result['strategy']
            game_format = "جماعي" if features['game_template'] == 2 else "فردي"
            
            # ملاحظة: نظراً لأن دالة guide_ai_generation في ملفك تتوقع متغيرات معينة
            # نقوم بتمريرها أو دمجها في الـ user_query إذا كانت الدالة لا تستقبلها كـ arguments صريحة.
            
            # إذا كانت دالة NLP معدلة لتستقبل هذه المعطيات (كما ظهر في كودك المرفق):
            if hasattr(self.nlp_engine, 'guide_ai_generation'):
                # سنقوم بتضمين المعطيات الفنية داخل الاستعلام لضمان التقاط BERT لها
                enriched_query = (
                    f"{user_query} | "
                    f"[معلومات النظام: فجوة={gap_prob}%، اتجاه={trend_label}، استراتيجية={strategy}، "
                    f"لعبة={game_format}، صعوبة={features['difficulty']}، زمن={features['duration']}دقيقة]"
                )
                final_system_prompt = self.nlp_engine.guide_ai_generation(
                    user_query=enriched_query, 
                    lesson_title=lesson_title, 
                    lesson_goal=lesson_goal
                )
            else:
                final_system_prompt = f"قم بتحضير درس {lesson_title}. الطلب: {user_query}"

            return {
                'system_prompt': final_system_prompt,
                'xgb_result': {
                    'gap_probability': gap_prob,
                    'mastery': 1 - gap_prob/100,

                    'strategy': strategy
                },
                'trend_label': trend_label,
                'trend_value': trend_value
            
            }
    
        except Exception as e:
            print(f"⚠️ خطأ في معالجة طلب الدرس: {e}")
            return {
                'system_prompt': user_query,
                'xgb_result': {},
                'trend_label': None,
                'trend_value': None
            }
        
    def prepare_visual_insights(self, teacher_id, grade_level, current_score, lesson_title):
        """توليد رسم بياني ذكي يوضح الاتجاه والفجوة الحالية."""
        db = DatabaseManager()
        history =db.get_teacher_evaluation_history(grade_level)

        _, predicted_val = self.lstm_engine.analyze_trend_lstm(history + [current_score])

        xgb_res = self.xgb_engine.predict_educational_outcome(
            participation=current_score,
            lstm_trend=predicted_val,
            difficulty='متوسط',
            duration=40,
            game_template='جماعي'
        )

        return {
            'history': history[-5:],
            'current_score': current_score,
            'prediction': predicted_val,
            'gap_prob': xgb_res.get('gap_probability', 0),
            'title': lesson_title
        }