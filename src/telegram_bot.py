import logging
from typing import Optional
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.config import settings
from src.shopify_client import ShopifyClient
from src.ai_agent import AIAgent

logger = logging.getLogger("telegram_bot")

class TelegramBotService:
    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.shopify = ShopifyClient()
        self.agent = AIAgent(self.shopify)
        self.allowed_users = settings.allowed_telegram_users()
        self.app: Optional[Application] = None

    def _is_authorized(self, user_id: int) -> bool:
        if not self.allowed_users:
            return True  # If not set, allow all (or recommend setting ID)
        return user_id in self.allowed_users

    async def start_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not self._is_authorized(user.id):
            await update.message.reply_text("⛔ عذراً، هذا البوت مخصص لإدارة متجر الهدى ومقيد بمصادقة المسؤول فقط.")
            return

        text = (
            f"👋 أهلاً بك يا {user.first_name or 'يا فندم'} في **مساعد الذكاء الاصطناعي لمتجر الهدى (elhoda.net)**!\n\n"
            "🤖 أنا وكيلك الذكي المتصل مباشرة بمتجر شوبيفاي، يمكنك إرسال أي أمر عادي باللغة العربية وسأقوم بتنفيذه فوراً.\n\n"
            "✨ **أمثلة لما يمكنني فعله:**\n"
            "• *«حدث سعر طقم الهدى لـ 450 جنيه»*\n"
            "• *«حسن الـ SEO لمنتج عباية كريب واكتب وصف قوي»*\n"
            "• *«خلّي سعر الشال 120 بدل 150 وحسّن كلماته المفتاحية»*\n\n"
            "⚡ **أوامر سريعة:**\n"
            "/products - عرض أحدث المنتجات وأسعارها\n"
            "/help - مساعدة وشرح الأوامر"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "📖 **دليل الاستخدام السريع:**\n\n"
            "1️⃣ **لتعديل السعر:** فقط اذكر اسم المنتج والسعر الجديد.\n"
            "2️⃣ **لتحسين محركات البحث (SEO):** اطلب تحسين السيو لاسم المنتج، وسيقوم الـ AI بصياغة عنوان ووصف ميتا ووصف تسويقي كامل.\n"
            "3️⃣ **كلاهما معاً:** يمكنك دمج الأمرين في رسالة واحدة.\n"
            "4️⃣ **/products:** يعرض لك قائمة سريعة بآخر المنتجات في المتجر."
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def list_products_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not self._is_authorized(user.id):
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        products = await self.shopify.list_products(limit=10)
        if not products:
            await update.message.reply_text("❌ لم يتم العثور على منتجات أو تعذر الاتصال بـ Shopify.")
            return

        lines = ["📦 **أحدث المنتجات في متجر الهدى:**\n"]
        for p in products:
            title = p.get("title", "بدون عنوان")
            variants = p.get("variants", [])
            price = variants[0].get("price", "غير محدد") if variants else "0"
            lines.append(f"• **{title}** — {price} ج.م")

        lines.append("\n💡 يمكنك إرسال اسم أي منتج منها لتعديل سعره أو تحسين السيو الخاص به فوراً.")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not self._is_authorized(user.id):
            await update.message.reply_text("⛔ غير مصرح لك بإصدار أوامر لهذا المتجر.")
            return

        user_text = update.message.text
        if not user_text:
            return

        # Show typing indicator
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

        try:
            result = await self.agent.execute_command(user_text)
            reply = result.get("message", "تم تنفيذ الأمر.")
            await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.exception("Error executing agent command")
            await update.message.reply_text(f"⚠️ حدث خطأ أثناء معالجة الأمر:\n`{str(e)}`", parse_mode=ParseMode.MARKDOWN)

    def build_application(self) -> Application:
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not configured.")
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start", self.start_cmd))
        app.add_handler(CommandHandler("help", self.help_cmd))
        app.add_handler(CommandHandler("products", self.list_products_cmd))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app = app
        return app
