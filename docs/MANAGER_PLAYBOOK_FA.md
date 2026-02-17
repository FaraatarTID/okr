# راهنمای عملیاتی مدیر (Manager Playbook)
Documentation HQ: [README](../README.md)

این سند، راهنمای اجرای نقش مدیر بر اساس رفتار فعلی کد در `streamlit_app/src/ui/*`، `streamlit_app/src/crud.py` و `streamlit_app/src/services/ai_service.py` است.

## ۱. نقش مدیر در سامانه

نقش مدیر در این محصول سه محور اصلی دارد:
- پایش تیم: کنترل کیفیت اجرا، ریسک، و انضباط check-in.
- تیم‌سازی/مربی‌گری: رفع مانع، بازتوزیع بار، و بهبود کیفیت KR.
- رهبری و escalation: تبدیل ریسک‌ها به اقدام و ارجاع موانع سیستمی به ادمین.

## ۲. پیش‌نیازهای دید و کنترل

برای اینکه مدیر بتواند تیم را ببیند/مدیریت کند، این موارد باید برقرار باشد:
1. نقش کاربر `manager` باشد.
2. اعضای تیم با `manager_id = شناسه مدیر` لینک شده باشند.
3. برای اعضا در چرخه فعال، Goal/Objective/KR وجود داشته باشد.
4. در شروع اجرا، Objective و KR از `DRAFT` به `ACTIVE` منتقل شوند.

## ۳. مدیر دقیقا چطور OKR و Task اعضا را می‌بیند؟

Atlas (`Focus Map`):
1. `Scope selector` را باز کنید.
2. `My Team` را انتخاب کنید تا مدیر + direct reportها بارگذاری شوند.
3. در صورت نیاز، scope یک عضو مشخص را انتخاب کنید.
4. با `Branch` lens یک شاخه Objective را عمیق بررسی کنید.

Leadership Insights (`Strategic Dashboard`):
1. داشبورد را باز کنید.
2. فیلتر تیم/عضو را اعمال کنید.
3. KPIها، لیست ریسک و Strategy Pulse را مرور کنید.

Project Timeline:
1. تایم‌لاین را باز کنید.
2. نمایش به‌صورت role-filtered است و مدیر فقط داده قابل‌دسترسی تیم را می‌بیند.
3. از آن برای خوشه‌های deadline و فشار ظرفیت استفاده کنید.

Inspector:
1. گره را از Focus Map انتخاب کنید.
2. جزئیات را بخوانید یا بر اساس مجوز ویرایش کنید.
3. مدیریت لینک‌های هم‌راستایی را در `Organizational Alignment` انجام دهید.

## ۴. مدل مجوز `Read/Edit/None`

| زمینه | ادمین | مدیر | عضو |
|---|---|---|---|
| آیتم‌های خود | Read/Edit | Read/Edit | Read/Edit |
| آیتم‌های direct report | Read/Edit | Read/Edit | None |
| هم‌تیمی غیر مستقیم | Read/Edit | Read (بدون edit مگر manager-of-owner) | None |
| آیتم‌های خارج تیم | Read/Edit | None | None |
| مدیریت کاربر/چرخه | Read/Edit | None | None |
| داشبوردهای مربی‌گری تیم | Read/Edit | Read/Edit در scope تیم | فقط scope شخصی |
| دریافت داده برای Gemini (`analyze_node`) | مطابق scope ادمین | مطابق scope مدیر | مطابق scope شخصی |

نکته پیاده‌سازی:
- `READ` مدیر برای direct report و same-team فعال است.
- `UPDATE/DELETE` مدیر فقط برای direct-report (یا مالکیت خود) مجاز است.

## ۵. ایمنی دسترسی در Gemini

سخت‌گیری فعلی در کد:
1. UI هویت actor را به فراخوانی AI پاس می‌دهد.
2. `analyze_node(...)` داده را از مسیر read مجاز می‌گیرد (`get_node(..., actor_username=...)`).
3. قبل از ساخت prompt، مجوز خواندن کنترل می‌شود.
4. نوشتن خروجی AI همچنان از مسیر مجوز نوشتن عبور می‌کند (`update_key_result(..., actor_username=...)`).
5. ایجاد/حذف alignment هم با مجوز mutation روی Goalهای درگیر کنترل می‌شود.

نتیجه:
- Gemini در جریان عادی UI مسیر bypass برای خواندن نود غیرمجاز ندارد.

## ۶. فرآیند و زمان‌بندی هفتگی (OKR الهام‌گرفته از SCRUM)

نکته زمان‌بندی:
- برنامه روز ثابت را اجبار نمی‌کند. ریتم زیر cadence پیشنهادی است.

ریتم پیشنهادی مدیر:
1. ابتدای هفته: Strategy Pulse + تعیین ۳ مداخله اصلی + اعتبارسنجی Weekly Focus.
2. میان‌هفته: مرور overdue/at-risk + اصلاح ownership/deadline/metric در Inspector.
3. پایان هفته: کنترل تکمیل Ritual همه direct reportها (Review Week -> Update KRs -> Plan Next Week).
4. پس از Ritual: مرور RetroBox و Weekly Report و تهیه جمع‌بندی مربی‌گری/escalation.

## ۷. استفاده از گزارش‌ها بر اساس نوع

Daily Report:
- بازه: روز جاری.
- کاربرد: نبض روزانه اجرا و کشف مانع سریع.

Weekly Report:
- بازه: ۷ روز اخیر.
- کاربرد: بسته شواهد برای جلسه راهبری هفتگی.

Ritual در برابر Retro:
- به‌روزرسانی KR در مرحله ۲ Ritual انجام می‌شود.
- RetroBox نمایش retrospectiveهای ذخیره‌شده است و مسیر update KR نیست.

## ۸. اسکریپت UAT برای مدیر نمونه

1. setup توسط ادمین: ۱ مدیر dummy + ۳ تا ۵ direct report بسازید.
2. داده چرخه: برای هر عضو Goal -> Objective -> KR -> Task بسازید.
3. فعال‌سازی: وضعیت Objective/KR را `ACTIVE` کنید.
4. تست visibility:
   - مدیر در Atlas، `My Team` را می‌بیند.
   - scope بیرون تیم برای مدیر نمایش داده نمی‌شود.
5. تست edit:
   - ویرایش KR direct report در Inspector باید مجاز باشد.
   - ویرایش آیتم outsider باید با PermissionError رد شود.
6. تست AI:
   - تحلیل KR مجاز direct report باید موفق باشد.
   - تحلیل نود غیرمجاز باید خطای مجوز بدهد.
7. تست Ritual:
   - همه اعضا Step 2 Ritual را تکمیل کنند.
   - مدیر کیفیت confidence/comment را بررسی کند.
8. بستن شواهد:
   - خروجی Weekly Report گرفته شود.
   - یک artifact خلاصه برای ادمین نگه داشته شود.

## ۹. رفع اشکال سریع

اگر مدیر تیم را نمی‌بیند:
1. مقدار `manager_id` کاربران را بررسی کنید.
2. چرخه فعال را بررسی کنید.
3. وضعیت‌های `DRAFT` را برای آیتم‌های اجرایی اصلاح کنید.
4. در Atlas، `My Team` را انتخاب کنید (نه `My OKRs`).

اگر مدیر می‌بیند ولی edit نمی‌تواند:
1. مالک نود باید direct report مدیر باشد.
2. نقش حساب باید `manager` و حساب فعال باشد.
3. خطاهای مجوز را در UI و audit log بررسی کنید.
