import torch
from transformers import AutoTokenizer, AutoModel
import numpy as np
from typing import Dict, Any, Optional

class EducationalBERTManager:
    """
    محرك DistilBERT المطور لتوجيه السياق التعليمي وإرشاد نماذج OpenAI.
    يعمل كجسر بين التنبؤات الرقمية (XGB/LSTM) وبين التوليد الإبداعي للخطة الدراسية.
    """
    def __init__(self):
        # استخدام نموذج DistilBERT يدعم العربية لفهم السياق التربوي
        self.model_name = "aubmindlab/bert-base-arabertv02"
        self.tokenizer: Optional[AutoTokenizer] = None
        self.model: Optional[Any] = None
        self.model_available = False
        self._initialize_bert()

    def _initialize_bert(self):
        """تحميل النموذج مع معالجة استثناءات الذاكرة أو الاتصال."""
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name)
            self.model_available = True
            print("✅ تم تحميل نموذج DistilBERT بنجاح.")
        except Exception as e:
            print(f"⚠️ تنبيه: تعذر تحميل DistilBERT، سيتم الاعتماد على المحرك المنطقي: {e}")
            

    def _get_embedding(self, text: str):
        """تحويل النصوص التعليمية إلى متجهات (Embeddings) لفهم المعنى."""
        if not self.model_available or self.tokenizer is None or self.model is None or not text:
            return None
        
        # التأكد من أن tokenizer قابل للاستدعاء
        inputs = self.tokenizer.encode_plus(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding="max_length"
        )
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state.mean(dim=1).numpy()

    def generate_context_guidance(self, user_query:str, lesson_data: Dict[str, Any], ml_insights: Optional[Dict[str,Any]]=None) -> str:
        """
        الوظيفة الرئيسية: استقبال نتائج XGBoost و LSTM وتحويلها لأوامر لـ OpenAI.
        
        البارامترات:
        - user_query: نص المعلم.
        - lesson_data: بيانات الدرس (العنوان والهدف).
        - ml_insights: قاموس يحتوي على (gap_probability من XGB و trend من LSTM).
        """
        title = "غير محدد"
        goal = "تحقيق نواتج التعلم"
        duration = 40 
        dynamic_instruction = "يرجى تقديم إرشاد تربوي عام بناءً على استفسار المعلم."

        if isinstance(lesson_data, str):
            title = lesson_data
        elif isinstance(lesson_data, dict):
            title = lesson_data.get('title', title)
            goal = lesson_data.get('goal', goal)
            duration = lesson_data.get('duration', duration)

        # تجهيز رؤى ML
        insights = ml_insights if ml_insights is not None else {'gap_probability': 0, 'trend': 'مستقر', 'mastery': 75}
        gap_prob = insights.get('gap_probability', 0)
        trend = insights.get('trend', 'مستقر↔️')

        # تحليل نية المعلم باستخدام BERT
        is_requesting_plan = any(word in user_query for word in ["حضر", "خطة", "تحضير", "درس"])
        is_help_needed = any(word in user_query for word in ["كيف", "مساعدة", "تستطيع", "ارشاد"])
        
        # --- المنطق الديناميكي للموجه السياقي ---
        
        # 1. تحديد استراتيجية التدريس بناءً على اتجاه LSTM
        if gap_prob > 35 or "هبوط" in trend:
            strategy = "التعلم العلاجي (Remedial Learning) عبر التبسيط المتناهي"
            difficulty = "سهلة"
        elif "صعود" in trend:
            strategy = "التعلم الإثرائي (Enrichment) عبر التحديات المعرفية"
            difficulty = "متقدمة"
        else:
            strategy = "التعلم المتمركز حول الطالب (Student-Centered)"
            difficulty = "متوازنة"

        # 2. تحديد نوع اللعبة التفاعلية بناءً على زمن الحصة
        if duration <= 15:
            game_format = f"لعبة سريعة (Energizer) لا تتجاوز 7 دقائق، مثل 'كسر الجليد' أو 'تحدي الثواني'."
        elif 15 < duration <= 30:
            game_format = f"لعبة تفاعلية متوسطة، تعتمد على المنافسة الثنائية، تناسب زمن {duration} دقيقة."
        else:
            game_format = f"لعبة تعليمية عميقة (Simulation/Role Play) تشمل محطات تعليمية متعددة."
        # 3. بناء الرد النهائي لـ OpenAI
        if is_requesting_plan:
            dynamic_instruction = (
                f"صمم خطة نشاط لدرس '{title}' الذي يهدف إلى '{goal}'. "
                f"بناءً على فجوة التعلم {gap_prob}%، واتجاه الأداء {trend}، استخدم استراتيجية {strategy}. "
                f"النشاط المطلوب {game_format} بصعوبة {difficulty}، ليتناسب مع {duration} دقيقة. "
                f"استفسار المعلم الإضافي: {user_query}"
        )

        # 4. نظام مساعدة وإرشاد المعلم (Teacher Guidance System)
        if is_help_needed:
            dynamic_instruction = (
                f"أرشد المعلم حول درس '{title}'. أخبره أن هناك فجوة {gap_prob}%  "
                f" في اتجاه أداء المشاركة {trend} تناسب الاستراتيجية {strategy}. اقترح عليه استخدام {game_format} بصعوبة {difficulty} هي الأنسب حاليًا."
                f"لمدة الدرس الإجمالية {duration} دقيقة. "
            )

        # 5. الحالة العامة
        return dynamic_instruction

    def guide_ai_generation(self, user_query:str, lesson_title:str, lesson_goal:str):
        """دالة توافقية للاستدعاء من conversation.py."""
        # في حال عدم وجود بيانات ML بعد (للمعلم الجديد)، نمرر قيم افتراضية آمنة
        lesson_data = {'title': lesson_title, 'goal': lesson_goal, 'duration':40}
        return self.generate_context_guidance(user_query, lesson_data)