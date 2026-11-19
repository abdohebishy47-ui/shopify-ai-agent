import json
import logging
from typing import Any, Optional
import httpx
from src.config import settings
from src.shopify_client import ShopifyClient

logger = logging.getLogger("ai_agent")

class AIAgent:
    def __init__(self, shopify_client: Optional[ShopifyClient] = None):
        self.shopify = shopify_client or ShopifyClient()
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL or "gemini-2.5-flash"

    async def _call_gemini(self, prompt: str, system_instruction: str = "", json_mode: bool = False) -> str:
        """Call Google Gemini API using REST endpoint."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        body: dict[str, Any] = {"contents": contents}

        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        generation_config: dict[str, Any] = {
            "temperature": 0.4,
            "maxOutputTokens": 2048,
        }
        if json_mode:
            generation_config["responseMimeType"] = "application/json"

        body["generationConfig"] = generation_config

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=body)
            if resp.status_code != 200:
                logger.error(f"Gemini API error: {resp.status_code} - {resp.text}")
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")

            result = resp.json()
            candidates = result.get("candidates", [])
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join([p.get("text", "") for p in parts]).strip()

    async def parse_user_intent(self, user_message: str) -> dict[str, Any]:
        """Analyze Arabic or English user command to extract product name, price, and actions."""
        system_prompt = (
            "You are an AI eCommerce Assistant specialized in Shopify management.\n"
            "Analyze the user's message (which is typically in Arabic or English) and extract the intent.\n"
            "Return JSON matching this exact schema:\n"
            "{\n"
            '  "action": "update_price" | "optimize_seo" | "update_price_and_seo" | "search" | "unknown",\n'
            '  "product_query": "string (name or keywords of the product mentioned)",\n'
            '  "new_price": float or null,\n'
            '  "compare_at_price": float or null,\n'
            '  "custom_instructions": "string or null (e.g. tone, target keyword, discounts)"\n'
            "}"
        )

        raw = await self._call_gemini(
            prompt=f"User command: {user_message}",
            system_instruction=system_prompt,
            json_mode=True
        )
        try:
            return json.loads(raw)
        except Exception:
            return {
                "action": "unknown",
                "product_query": user_message,
                "new_price": None,
                "compare_at_price": None,
                "custom_instructions": None
            }

    async def generate_seo(self, product: dict[str, Any], custom_instructions: str = "") -> dict[str, Any]:
        """Generate high-ranking SEO metadata and persuasive Arabic product copy."""
        title = product.get("title", "")
        current_desc = product.get("body_html", "") or ""
        tags = product.get("tags", "")
        variants = product.get("variants", [])
        price = variants[0].get("price") if variants else ""

        system_prompt = (
            "أنت خبير محترف في تحسين محركات البحث (SEO Expert) وكتابة الإعلانات للمتاجر الإلكترونية (Shopify).\n"
            "مهمتك: صياغة بيانات SEO قوية جداً باللغة العربية تضمن تصدر نتائج بحث Google ومضاعفة المبيعات لمتجر الهدى (elhoda.net).\n"
            "يجب أن تكون المخرجات بصيغة JSON حصراً بهذا الشكل:\n"
            "{\n"
            '  "seo_title": "عنوان جذاب لمحركات البحث أقل من 60 حرف يحتوي على الكلمة المفتاحية واسم المتجر",\n'
            '  "seo_description": "وصف ميتا قوي أقل من 160 حرف يحتوي على دعوة لاتخاذ إجراء CTA",\n'
            '  "improved_body_html": "وصف تسويقي كامل بصيغة HTML منسق (فقرة افتتاحية جذابة، قائمة بالمميزات <ul><li>، المواصفات، وخاتمة تحث على الشراء)",\n'
            '  "tags": ["قائمة", "من", "5-8", "كلمات", "مفتاحية"],\n'
            '  "seo_highlights": "شرح موجز بالعربي لأسباب اختيار هذه الكلمات وتأثيرها على ترتيب البحث"\n'
            "}"
        )

        user_content = (
            f"بيانات المنتج الحالي:\n"
            f"- اسم المنتج: {title}\n"
            f"- السعر: {price}\n"
            f"- الكلمات المفتاحية الحالية: {tags}\n"
            f"- الوصف الحالي: {current_desc[:500]}\n"
            f"- تعليمات إضافية: {custom_instructions or 'لا توجد'}\n"
            f"قم بإنشاء أفضل تحسين SEO متكامل لهذا المنتج."
        )

        raw = await self._call_gemini(
            prompt=user_content,
            system_instruction=system_prompt,
            json_mode=True
        )
        return json.loads(raw)

    async def execute_command(self, user_message: str) -> dict[str, Any]:
        """Full end-to-end processing pipeline for a natural language user command."""
        # 1. Parse intent
        intent = await self.parse_user_intent(user_message)
        action = intent.get("action", "unknown")
        product_query = intent.get("product_query", "").strip()

        if not product_query:
            return {
                "success": False,
                "message": "لم أتمكن من استخراج اسم المنتج من رسالتك. يرجى ذكر اسم المنتج بوضوح (مثال: 'حدث سعر شنطة يد لـ 300 جنيه')."
            }

        # 2. Search for the product in Shopify
        products = await self.shopify.search_products(product_query, limit=5)
        if not products:
            return {
                "success": False,
                "message": f"عذراً، لم أجد أي منتج في متجر الهدى يطابق: '{product_query}'."
            }

        target_product = products[0]
        prod_id = target_product["id"]
        prod_title = target_product["title"]

        results: dict[str, Any] = {
            "success": True,
            "product_id": prod_id,
            "product_title": prod_title,
            "actions_taken": [],
            "details": {}
        }

        # 3. Handle Price Update
        new_price = intent.get("new_price")
        compare_at = intent.get("compare_at_price")
        if new_price is not None or action in ["update_price", "update_price_and_seo"]:
            if new_price is not None:
                price_res = await self.shopify.update_product_price(
                    product_id=prod_id,
                    new_price=new_price,
                    compare_at_price=compare_at
                )
                if price_res.get("success"):
                    results["actions_taken"].append("price_updated")
                    results["details"]["price"] = {
                        "new_price": new_price,
                        "compare_at_price": compare_at,
                        "variants_count": price_res.get("variants_updated")
                    }

        # 4. Handle SEO Optimization
        if action in ["optimize_seo", "update_price_and_seo"] or "سيو" in user_message or "seo" in user_message.lower():
            seo_data = await self.generate_seo(target_product, intent.get("custom_instructions") or "")
            seo_res = await self.shopify.update_product_seo(
                product_id=prod_id,
                seo_title=seo_data.get("seo_title"),
                seo_description=seo_data.get("seo_description"),
                tags=seo_data.get("tags"),
                body_html=seo_data.get("improved_body_html")
            )
            if seo_res.get("success"):
                results["actions_taken"].append("seo_optimized")
                results["details"]["seo"] = seo_data

        # 5. Format friendly Arabic response message
        if not results["actions_taken"]:
            results["message"] = (
                f"تم العثور على المنتج: **{prod_title}**\n"
                f"السعر الحالي: {target_product.get('variants', [{}])[0].get('price')} جنيه.\n"
                f"يرجى تحديد ما إذا كنت تريد تعديل السعر (مثال: 'خليه 400') أو تحسين السيو (مثال: 'حسن السيو')."
            )
        else:
            msg_parts = [f"✅ **تم تحديث المنتج بنجاح في متجر الهدى!**\n📌 **المنتج:** {prod_title}"]
            if "price_updated" in results["actions_taken"]:
                p_info = results["details"]["price"]
                msg_parts.append(f"💰 **السعر الجديد:** {p_info['new_price']} جنيه" + (f" (سعر قبل الخصم: {p_info['compare_at_price']})" if p_info['compare_at_price'] else ""))
            if "seo_optimized" in results["actions_taken"]:
                s_info = results["details"]["seo"]
                msg_parts.append(f"🔍 **تحسينات الـ SEO:**")
                msg_parts.append(f"• **العنوان الجديد (Meta Title):** {s_info.get('seo_title')}")
                msg_parts.append(f"• **الوصف (Meta Description):** {s_info.get('seo_description')}")
                msg_parts.append(f"• **الكلمات المفتاحية:** {', '.join(s_info.get('tags', []))}")
                if s_info.get("seo_highlights"):
                    msg_parts.append(f"💡 **سبب التحسين:** {s_info.get('seo_highlights')}")

            results["message"] = "\n".join(msg_parts)

        return results
