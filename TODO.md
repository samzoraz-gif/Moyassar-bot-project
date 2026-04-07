# خطة إصلاح خطأ Pylance في create_lesson_plan_pdf

## الخطوات:
- [x] 1. تحديث utils/pdf_generator.py: استبدال جميع `ln=True` بـ `ln=1` في pdf.cell()
- [ ] 2. التحقق من عدم وجود أخطاء أخرى في الملف
- [ ] 3. اختبار إنشاء PDF من handlers/conversation.py
- [ ] 4. إكمال المهمة بـ attempt_completion

حالة التقدم: تم استبدال `ln=True` في 3 مواقع، لكن ظهرت أخطاء تهيئة في pdf_generator.py بسبب مشاكل indentation. سأقوم بإعادة كتابة الملف كاملاً
