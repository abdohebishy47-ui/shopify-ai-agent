# مساعد الذكاء الاصطناعي لمتجر الهدى (elhoda.net) 🛍️🤖

نظام متكامل يعتمد على الذكاء الاصطناعي (Gemini) لإدارة وتحديث الأسعار وتحسين محركات البحث (SEO) تلقائياً لمتجر شوبيفاي `elhoda.net`، مع دعم التحكم عبر:
- **لوحة تحكم ويب تفاعلية (Web Dashboard)**
- **بوت تليجرام (Telegram Bot)**
- **واجهة برمجية جاهزة للربط مع واتساب (FastAPI Endpoints)**

---

## 🚀 طريقة البدء والتشغيل السريع

### 1. إعداد مفاتيح الربط في ملف `.env`
قم بفتح ملف `.env` في مجلد المشروع واملأ البيانات التالية:

```env
# 1. إعدادات متجر الهدى
SHOPIFY_STORE_URL=elhoda.net
SHOPIFY_ADMIN_ACCESS_TOKEN=shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 2. مفتاح الذكاء الاصطناعي (Gemini)
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 3. بوت تيليجرام
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_ALLOWED_USER_IDS=12345678  # اختياري لتأمين البوت
```

---

### 🔑 كيفية استخراج المفاتيح:

#### أ) مفتاح شوبيفاي (Shopify Admin Access Token):
1. افتح لوحة تحكم متجر الهدى: `https://admin.shopify.com`
2. اذهب إلى: **Settings (الإعدادات)** ➔ **Apps and sales channels** ➔ **Develop apps**.
3. اضغط على **Create an app** وسمّه مثلاً `Elhoda AI Agent`.
4. في تبويب **Configuration**، اختر **Admin API integration**، وقم بتفعيل الصلاحيات التالية:
   - `read_products` و `write_products`
   - `read_product_listings`
5. اضغط **Save** ثم **Install app**.
6. انسخ الـ **Admin API access token** (يبدأ بـ `shpat_`) وضعه في ملف `.env`.

#### ب) مفتاح الذكاء الاصطناعي (Gemini API Key):
- ادخل على [Google AI Studio](https://aistudio.google.com/) واضغط **Create API Key** (مجاني).

#### ج) توكن بوت تيليجرام (Telegram Bot):
1. افتح تطبيق تيليجرام وابحث عن `@BotFather`.
2. أرسل الأمر `/newbot` واتبع التعليمات لاختيار اسم ويوزرنيم للبوت.
3. سيعطيك الـ `API Token`، ضعه في `.env`.

---

### 2. تشغيل المشروع:
من داخل المجلد عبر موجه الأوامر (Terminal):

```bash
python run.py
```

- افتح المتصفح على: `http://localhost:8000`
- ستفتح لك لوحة التحكم الخاصة بمتجر الهدى مباشرة.
- في نفس الوقت، سيعمل بوت التيليجرام في الخلفية لاستقبال أوامرك.

---

## 💬 أمثلة للأوامر التي يفهمها الـ AI:

- **تعديل السعر:**
  > "حدث سعر عباية الهدى الكريب وخليها بـ 450 جنيه"
- **تعديل السعر مع خصم (Compare-at price):**
  > "خلي سعر الطقم 600 بدل 750 جنيه"
- **تحسين محركات البحث (SEO):**
  > "حسن الـ SEO لمنتج فستان سواريه واكتب وصف جذاب وكلمات مفتاحية متصدرة"
- **الأمر الشامل:**
  > "ارفع سعر الشال لـ 150 وحسن السيو بتاعه لمحركات البحث"
