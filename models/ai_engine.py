from openai import AsyncOpenAI
from config import GITHUB_TOKEN  # الاعتماد الكلي على التوكين من config

class AIEngine:
    """
محرك توليد المحتوى التربوي الديناميكي
يربط بين الرؤى الرقمية (ML Insights) والتوجيه السياقي (BERT) لانتاج خطط دراسية واقعية
    """
    def __init__(self):
        # إعداد العميل باستخدام التوكن المركزي       
        self.client = AsyncOpenAI(
            base_url="https://models.github.ai/inference",
            api_key=GITHUB_TOKEN
        )
        self.model_name = "gpt-4o-mini"  # اختيار نموذج مناسب لتوليد المحتوى التعليمي

    async def generate_dynamic_lesson_content(self, user_query, lesson_data, ml_insights, system_guidance):
        """
        توليد استجابة ذكية مبنية علي بيانات حقيقية (فجوات، اتجاهات، سباق).
        
        البارامترات:
        - user_query: نص المعلم (الطلب).
        - lesson_data: قاموس يحتوي على (title, goal).
        - ml_insights: مخرجات XGBoost و LSTM (gap_probability, trend, mastery).
        - system_guidance: النص التوجيهي المولد من محرك BERT.
        """
        try:
            # استخراج البيانات الرقمية لضمان واقعية الرد
            gap = ml_insights.get('gap_probability', 0)
            trend = ml_insights.get('trend', 'مستقر')
            mastery = ml_insights.get('mastery', 75)
            
            # بناء سياق "النظام الخبير" بدمج كافة المحركات
            prompt_context = (
                f"انت خبير تربوي في منصة *مُيَّسِر*. وظيفتك تصميم محتوى تعليمي بناءً على لأدلة التالية:\n"
                f"1. التوجيه السياقي:{system_guidance}\n"
                f"2. تحليل الفجوة التعليمية:{gap}%\n"
                f"3. تحليل اتجاه مشاركة الطلاب:{trend}\n"
                f"4. مستوى الدقة الحالية:{mastery}\n"
                f" الهدف: صمم خطة لدرس'{lesson_data.get('title')}' تحقق الهدف '{lesson_data.get('goal')}' "
                f"مع مراعاة سد الفجوة المذكورة إذا تجاوزت 35%."
            )
            # صياغة الرسالة بنظام الأدوار لضمان الالتزام بالسياق التربوي
            messages=[
                    {"role": "system", 
                     "content":(
                         f"{prompt_context}\n\n"
                         "قواعد صارمة للرد:\n"
                         "1. يجب أن تكون الاستراتيجية المقترحة متوافقة تماماً مع نسبة الفجوة المذكورة.\n"
                        "2. إذا كان الاتجاه 'هابط'، ركز على التبسيط والتدريب المكثف.\n"
                        "3. الالتزام التام بقالب الألعاب التفاعلية المعتمد في النظام."
                     )},
                    {"role": "user", "content": user_query}
                ]
            
            response = await self.client.chat.completions.create(
                messages=messages,
                model=self.model_name,
                temperature=0.75, # توازن بين الإبداع والدقة التربوية
                max_tokens=2500
            )
            raw_content = response.choices[0].message.content
            return self.format_educational_response(raw_content)
        
        except Exception as e:
            # معالجة الأخطاء بشكل احترافي بدلاً من انهيار البرنامج
            return f"⚠️ عذراً، واجه محرك الذكاء الاصطناعي مشكلة: {str(e)}"

    def format_educational_response(self, raw_text):
        """تحسين تنسيق المخرجات لتكون جاهزة للطباعة كـ PDF."""
        # إضافة لمسات تنسيقية (Markdown) لضمان وضوح الخطة الدراسية
        formatted = raw_text.replace("الهدف:", "🎯 **الهدف التربوي:**")
        formatted = formatted.replace("النشاط:", "🎮 **النشاط التفاعلي المقترح:**")
        formatted = formatted.replace("التقييم:", "📝 **أداة قياس الأثر:**")
        return formatted