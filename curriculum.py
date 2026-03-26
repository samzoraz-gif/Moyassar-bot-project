import pandas as pd
import os
from config import DB_FILENAME, SHEET_CURRICULUM, SHEET_GAMES

class CurriculumManager:
    def __init__(self):
        self.db_filename = DB_FILENAME
        self.curriculum_data = {}
        self.load_curriculum()

    def load_curriculum(self):
        """تحميل المنهج الدراسي وتفكيكه إلى هيكل بيانات منظم"""
        if not os.path.exists(self.db_filename):
            print(f"⚠️ ملف المنهج {self.db_filename} غير موجود!")
            return

        try:
            # قراءة ورقة المنهج وتصفية القيم الفارغة في الأعمدة الأساسية
            df = pd.read_excel(self.db_filename, sheet_name=SHEET_CURRICULUM)
            df = df.dropna(subset=['Grade_ID', 'Title'])
            
            for _, row in df.iterrows():
                # تحويل معرف الصف إلى نص لضمان التوافق
                gid = str(int(float(row['Grade_ID'])))
                
                if gid not in self.curriculum_data:
                    self.curriculum_data[gid] = {
                        "name": str(row.get('Grade_Name', f"صف {gid}")),
                        "topics": []
                    }
                
                # إضافة بيانات الدرس بالتفصيل كما في الكود الأصلي
                self.curriculum_data[gid]["topics"].append({
                    "title": str(row.get('Title', '')),
                    "goal": str(row.get('Goal', '')),
                    "material": str(row.get('Material', '')),
                    "activity": str(row.get('Activity', '')),
                    "duration": str(row.get('Duration', '40 دقيقة')),
                    "page_ref": str(row.get('Page_Ref', '---'))
                })
        except Exception as e:
            print(f"❌ خطأ أثناء تحميل المنهج: {e}")

    def get_grades(self):
        """جلب قائمة الصفوف المتاحة"""
        return {gid: info["name"] for gid, info in self.curriculum_data.items()}

    def get_lessons_for_grade(self, grade_id):
        """جلب الدروس الخاصة بصف معين"""
        grade_info = self.curriculum_data.get(str(grade_id))
        return grade_info["topics"] if grade_info else []

    def get_lesson_details(self, grade_id, lesson_index):
        """جلب تفاصيل درس محدد بواسطة فهرسه"""
        lessons = self.get_lessons_for_grade(grade_id)
        if 0 <= lesson_index < len(lessons):
            return lessons[lesson_index]
        return {"title":"درس غير محدد","goal":"عام"}