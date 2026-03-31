import numpy as np
import pandas as pd
import os
from sklearn.preprocessing import MinMaxScaler
from typing import List, Tuple, Dict, Any, Optional
from config import MODEL_PATH_LSTM # الاعتماد على المسار المحدد في الإعدادات

# معالجة استيراد TensorFlow لضمان استقرار التشغيل وإخفاء التحذيرات التقنية
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# معالجة استيراد TensorFlow لضمان استقرار التشغيل
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model # type: ignore
    from tensorflow.keras.layers import LSTM, Dense, Dropout #type: ignore
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    Sequential = None
    load_model = None
    LSTM = None
    Dense = None
    Dropout = None

class LSTMEngine:
    """
    محرك تحليل الاتجاهات المتقدم (Collective Intelligence).
    يقوم بالتنبؤ باتجاه أداء الطلاب بناءً على خبرة المعلم الحالية 
    مدمجة مع الخبرة التاريخية للمنصة لنفس الدرس والصف.
    """
    
    def __init__(self, model_path=MODEL_PATH_LSTM):
        self.model_path = model_path
        self.model: Optional[Any] = None
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.look_back = 3  # عدد الحصص السابقة للتنبؤ بالحصة القادمة
        
        # التأكد من وجود مجلد النماذج قبل البدء
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        
        if TF_AVAILABLE:
            self._initialize_brain()

    def _initialize_brain(self):
        """تحميل النموذج أو بناء عقل جديد (Incremental Learning)."""
        if not TF_AVAILABLE or load_model is None:
            return

        if os.path.exists(self.model_path):
            try:
                self.model = load_model(self.model_path, compile=False)
                if self.model is not None:
                    self.model.compile(optimizer='adam',loss='mean_squared_error')
            except Exception as e:
                print(f"⚠️ خطأ في تحميل النموذج: {e}")
                self._build_new_brain()
        else:
            self._build_new_brain()

    def _build_new_brain(self):
        """بناء هيكلية LSTM قادرة على التعلم من السلاسل الزمنية الصغيرة."""
        if not TF_AVAILABLE or Sequential is None or LSTM is None or Dropout is None or Dense is None: 
            print("⚠️ TensorFlow غير متوفر، لا يمكن بناء النموذج.")
            return

        model =Sequential([
            LSTM(64, activation='relu', input_shape=(self.look_back, 1), return_sequences=True),
            Dropout(0.2),
            LSTM(32, activation='relu'),
            Dense(1) # مخرج رقمي يمثل الدرجة المتوقعة
        ])
        model.compile(optimizer='adam', loss='mean_squared_error')

        # تدريب أولي (Cold Start) لضمان جاهزية التنبؤ
        X_dummy = np.random.rand(10, self.look_back, 1)
        y_dummy = np.random.rand(10, 1)
        model.fit(X_dummy, y_dummy, epochs=1, verbose=0)
        self.save_brain()

    def save_brain(self):
        """حفظ حالة النموذج لضمان استمرارية التعلم."""
        if self.model is not None and TF_AVAILABLE:
            self.model.save(self.model_path)    

    def update_learning(self, new_history):
        """
        تطبيق مفهوم التعلم المستمر: 
        تحديث النموذج بالبيانات الجديدة دون فقدان الخبرات السابقة.
        """
        if not TF_AVAILABLE or self.model is None or len(new_history) < self.look_back + 1:
            return
        
        # تجهيز البيانات الجديدة باستخدام MinMaxScaler
        data = np.array(new_history).reshape(-1, 1)
        scaled_data = self.scaler.fit_transform(data)
        
        X, y = [], []
        for i in range(len(scaled_data) - self.look_back):
            X.append(scaled_data[i:(i + self.look_back), 0])
            y.append(scaled_data[i + self.look_back, 0])
        
        X_train = np.array(X).reshape((-1, self.look_back, 1))
        y_train = np.array(y)

        # تدريب جزئي (Fine-tuning) لتحديث الأوزان ديناميكياً
        self.model.fit(X_train, y_train, epochs=5, batch_size=1, verbose=0)
        self.save_brain()

    def analyze_global_trend(self,
                             teacher_history: list[float],
                             global_class_average: list[float]) -> Tuple[str, float]:
        """
        الوظيفة الديناميكية: قياس الاتجاه بناءً على خبرة المعلم + خبرة المنصة.
        
        البارامترات:
        - teacher_history: سجل درجات الطلاب مع المعلم الحالي.
        - global_class_average: متوسط درجات نفس الدرس لهذا الصف من معلمين سابقين.
        """
        if not TF_AVAILABLE or self.model is None:
            return "مستقر ↔️", 0.5 # حالة المعلم الجديد

        # المنطق الديناميكي: إذا كان المعلم جديداً (بياناته أقل من look_back)
        # نعتمد كلياً على التاريخ العام للصف لضمان الاستمرارية
        if len(teacher_history) < self.look_back:
            data_to_analyze = global_class_average
        else:
             # دمج بنسبة 70% للمعلم و30% للخبرة العامة لضبط الدقة
             # يتم أخذ آخر قيم بناءً على look_back
             combined = []
             for i in range(1, self.look_back + 1):
                 t_val = teacher_history[-i] if i <= len(teacher_history) else global_class_average[-i]
                 g_val = global_class_average[-i] if i<=len(global_class_average) else t_val
                 combined.append((t_val *0.7) + (g_val * 0.3))
             data_to_analyze = list(reversed(combined))
        
        if len(data_to_analyze) < 2:
            return "مستقر (بداية) 🆕", 0.5
        
        # تحويل الدرجات للنطاق (0-1) لزيادة الكفاءة
        scores_array = np.array(data_to_analyze).reshape(-1, 1)
        scaled_scores = self.scaler.fit_transform(scores_array)
        
        # التنبؤ بالقيمة القادمة
        if len(scaled_scores) >= self.look_back:
            input_seq = scaled_scores[-self.look_back:].reshape(1, self.look_back, 1)
            prediction_scaled = self.model.predict(input_seq, verbose=0)[0][0]
        else:
            # في حال قلة البيانات، نستخدم المتوسط المرجح كحل مؤقت
            prediction_scaled = np.mean(scaled_scores)

        # تحديد اتجاه المستوى (صعود أو هبوط)
        last_actual = scaled_scores[-1][0]
        diff = float(prediction_scaled) - last_actual

        if diff > 0.05:
            trend_label = "صعود 📈"
        elif diff < -0.05:
            trend_label = "هبوط 📉"
        else:
            trend_label = "مستقر ↔️"

        return trend_label, round(float(prediction_scaled), 2)

    def analyze_trend_lstm(self, history: list[float]) -> Tuple[str, float]:
        """دالة توافقية للاستدعاء البسيط (تعامل التاريخ كبيانات محلية وعامة معاً)."""
        return self.analyze_global_trend(history, history)
    