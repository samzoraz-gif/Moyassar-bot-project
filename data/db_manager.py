import pandas as pd
import os
from datetime import datetime
from config import EXCEL_DB_NAME, SHEET_TEACHERS, SHEET_EVALUATIONS

class DatabaseManager:
    def __init__(self):
        self.db_file = EXCEL_DB_NAME
        self._init_db()

    def _init_db(self):
        """تهيئة قاعدة البيانات إذا لم تكن موجودة كما في الكود الأصلي"""
        if not os.path.exists(self.db_file):
            columns1 = ['telegram_id', 'username', 'join_date']
            columns2 = ['id', 'teacher_id', 'lesson_title', 'grade_level', 'eval_score', 'ai_reply', 'grade_name', 'notes', 'date_time']
            with pd.ExcelWriter(self.db_file, engine='openpyxl') as writer:
                pd.DataFrame(columns=columns1).to_excel(writer, sheet_name=SHEET_TEACHERS, index=False)
                pd.DataFrame(columns=columns2).to_excel(writer, sheet_name=SHEET_EVALUATIONS, index=False)

    def add_evaluation(self, teacher_id, lesson_title, grade_level, score, ai_reply="", grade_name="", notes=""):
        """إضافة تقييم جديد مع مراعاة المنطق الحسابي الصحيح"""
        try:
            df = pd.read_excel(self.db_file, sheet_name=SHEET_EVALUATIONS)
            for col in ['ai_reply', 'grade_name']:
                if col not in df.columns:
                    df[col] = ""
                    
            new_id = df['id'].max() + 1 if not df.empty else 1
            
            new_row = {
                'id': new_id,
                'teacher_id': teacher_id,
                'lesson_title': lesson_title,
                'grade_level': grade_level,
                'eval_score': int(score), # ممتاز=3، جيد=2، ضعيف=1
                'ai_reply': ai_reply, # يمكن تخزين الملاحظات أو الردود من الذكاء الاصطناعي هنا
                'grade_name': grade_name, # تخزين اسم الصف الدراسي
                'notes': notes,
                'date_time': datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            self._save_to_sheet(SHEET_EVALUATIONS, df)
            return True
        except Exception as e:
            print(f"Error adding evaluation: {e}")
            return False

    def get_teacher_evaluation_history(self, teacher_id=None, grade_level=None):
        """جلب تاريخ التقييمات بناءً على المعلم أو مستوى الصف الدراسي أو كليهما."""
        try:
            if not os.path.exists(self.db_file):
                return []
            df = pd.read_excel(self.db_file, sheet_name=SHEET_EVALUATIONS)
            if teacher_id is not None:
                df = df[df['teacher_id'].astype(str) == str(teacher_id)]
            if grade_level is not None:
                df = df[df['grade_level'] == grade_level]
            return df['eval_score'].tolist()
        except Exception:
            return []

    def register_teacher(self, telegram_id, username):
        """تسجيل معلم جديد في النظام"""
        try:
            df = pd.read_excel(self.db_file, sheet_name=SHEET_TEACHERS)
            if telegram_id not in df['telegram_id'].values:
                new_teacher = {
                    'telegram_id': telegram_id,
                    'username': username,
                    'join_date': datetime.now().strftime("%Y-%m-%d")
                }
                df = pd.concat([df, pd.DataFrame([new_teacher])], ignore_index=True)
                self._save_to_sheet(SHEET_TEACHERS, df)
        except Exception as e:
            print(f"Error registering teacher: {e}")

    def _save_to_sheet(self, sheet_name, df):
        with pd.ExcelWriter(self.db_file, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)