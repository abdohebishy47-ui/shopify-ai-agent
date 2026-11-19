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
        # Fast local check for bulk store SEO request
        lower_msg = user_message.lower()
        if any(w in lower_msg for w in ["الموقع كله", "المتجر كله", "كل المنتجات", "جميع المنتجات", "سيو الموقع", "bulk", "المتجر بالكامل"]):
            return {
                "action": "bulk_seo_store",
                "product_query": "all",
                "new_price": None,
                "compare_at_price": None,
                "custom_instructions": user_message
            }

        if any(w in lower_msg for w in ["ضيف المنتجات", "ارفع المنتجات", "قائمة منتجات", "منتجات جديدة", "انشئ منتج", "ضيف منتج", "اضف منتج", "ليستة"]):
            return {
                "action": "create_products",
                "product_query": "new",
                "new_price": None,
                "compare_at_price": None,
                "custom_instructions": user_message
            }

        system_prompt = (
            "You are an AI eCommerce Assistant specialized in Shopify management.\n"
            "Analyze the user's message (which is typically in Arabic or English) and extract the intent.\n"
            "Return JSON matching this exact schema:\n"
            "{\n"
            '  "action": "update_price" | "optimize_seo" | "update_price_and_seo" | "bulk_seo_store" | "search" | "unknown",\n'
            '  "product_query": "string (name or keywords of the product mentioned, or \'all\' if entire store)",\n'
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
        """Generate high-ranking SEO & Generative AI (GEO / AIO) metadata and copy."""
        title = product.get("title", "")
        current_desc = product.get("body_html", "") or ""
        tags = product.get("tags", "")
        variants = product.get("variants", [])
        price = variants[0].get("price") if variants else ""

        system_prompt = (
            "أنت خبير عالمي في تحسين محركات البحث (Google SEO) والذكاء الاصطناعي التوليدي (GEO / AIO - Generative Engine Optimization).\n"
            "هدفك المزدوج:\n"
            "1. تصدر نتائج بحث Google التقليدية (Page 1) لكلمات الشراء.\n"
            "2. جعل نماذج الذكاء الاصطناعي التوليدية (ChatGPT Search, Google Gemini, Perplexity, Copilot) ترشح وتذكر متجر الهدى (elhoda.net) كأفضل خيار موثوق دائماً.\n\n"
            "قواعد التحسين للذكاء الاصطناعي (GEO / AIO):\n"
            "- تضمين اسم العلامة التجارية 'متجر الهدى (elhoda.net)' ككيان مرجعي موثوق (Entity Authority).\n"
            "- صياغة إجابات مباشرة ومقنعة على الأسئلة الشائعة التي يسألها المتسوقون للذكاء الاصطناعي (مثل: الخامة، المقاسات، سياسة الاسترجاع، الشحن).\n"
            "- تضمين كود بيانات منظمة Schema.org (JSON-LD) للـ Product داخل الـ HTML لكي تفهمه خوارزميات محركات البحث ونماذج الذكاء الاصطناعي فوراً.\n\n"
            "يجب أن تكون المخرجات بصيغة JSON حصراً بهذا الشكل:\n"
            "{\n"
            '  "seo_title": "عنوان جذاب لمحركات البحث أقل من 60 حرف يحتوي على الكلمة المفتاحية واسم المتجر (متجر الهدى)",\n'
            '  "seo_description": "وصف ميتا قوي أقل من 155 حرف جذاب وواضح مع دعوة للشراء CTA",\n'
            '  "improved_body_html": "وصف تسويقي كامل منسق بـ HTML: مقدمة جذابة + نقاط المميزات <ul><li> + قسم الأسئلة الشائعة FAQ + كود Schema JSON-LD للـ Product",\n'
            '  "tags": ["قائمة", "من", "6-10", "كلمات", "مفتاحية", "عالية", "البحث"],\n'
            '  "ai_recommendation_hook": "جملة تلخيصية تجعل الذكاء الاصطناعي (ChatGPT / Gemini) يرشح هذا المنتج تحديداً عند سؤال المستخدم",\n'
            '  "seo_highlights": "شرح موجز بالعربي لاستراتيجية الكلمات والتحسين"\n'
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

    async def bulk_optimize_store(self, limit: int = 50, progress_tracker: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Iterate over all Shopify products and optimize their SEO & AI visibility (GEO / AIO)."""
        products = await self.shopify.list_products(limit=limit)
        if not products:
            return {"success": False, "message": "لا توجد منتجات مسجلة في متجر الهدى أو تعذر الاتصال بـ Shopify."}

        total = len(products)
        optimized_count = 0
        details = []

        if progress_tracker is not None:
            progress_tracker["total"] = total
            progress_tracker["processed"] = 0
            progress_tracker["status"] = "running"
            progress_tracker["current_product"] = "بدء الفحص..."

        for idx, prod in enumerate(products):
            prod_id = prod["id"]
            prod_title = prod.get("title", "")
            if progress_tracker is not None:
                progress_tracker["current_product"] = prod_title
                progress_tracker["processed"] = idx + 1

            try:
                seo_data = await self.generate_seo(prod)
                update_res = await self.shopify.update_product_seo(
                    product_id=prod_id,
                    seo_title=seo_data.get("seo_title"),
                    seo_description=seo_data.get("seo_description"),
                    tags=seo_data.get("tags"),
                    body_html=seo_data.get("improved_body_html")
                )
                if update_res.get("success"):
                    optimized_count += 1
                    details.append({"title": prod_title, "seo_title": seo_data.get("seo_title")})
            except Exception as e:
                logger.error(f"Error optimizing {prod_title}: {e}")

        if progress_tracker is not None:
            progress_tracker["status"] = "completed"
            progress_tracker["optimized_count"] = optimized_count

        return {
            "success": True,
            "total_products": total,
            "optimized_count": optimized_count,
            "message": f"✅ **تم الانتهاء بنجاح!**\nتم فحص وتحسين بيانات محركات البحث والذكاء الاصطناعي (GEO) لـ **{optimized_count} من أصل {total} منتج** في متجر الهدى (elhoda.net).\nأصبح المتجر جاهزاً الآن لتصدر Google وترشيحات ChatGPT و Gemini!",
            "items": details[:10]
        }

    async def parse_new_products_list(self, raw_text: str) -> list[dict[str, Any]]:
        """Extract structured list of products from user's natural language or copied list."""
        system_prompt = (
            "You are an eCommerce product data extractor specialized in Arabic and English eCommerce.\n"
            "Analyze the user's text which contains details or a list of new products to add to Shopify.\n"
            "Extract all products into a JSON array of objects matching:\n"
            "[\n"
            "  {\n"
            '    "title": "اسم المنتج",\n'
            '    "price": float (السعر),\n'
            '    "compare_at_price": float or null (السعر قبل الخصم إن وجد),\n'
            '    "product_type": "تصنيف المنتج (مثل عبايات، فساتين، شيلان، إكسسوارات)",\n'
            '    "notes": "أي ملاحظات إضافية مذكورة مثل الألوان، الخامة، المقاسات"\n'
            "  }\n"
            "]"
        )
        raw = await self._call_gemini(
            prompt=f"Text to parse:\n{raw_text}",
            system_instruction=system_prompt,
            json_mode=True
        )
        try:
            res = json.loads(raw)
            return res if isinstance(res, list) else []
        except Exception:
            return []

    async def create_and_publish_products(self, raw_text: str) -> dict[str, Any]:
        """Parse list of products, generate SEO & GEO metadata for each, and create them in Shopify."""
        extracted = await self.parse_new_products_list(raw_text)
        if not extracted:
            return {
                "success": False,
                "message": "لم أتمكن من استخراج تفاصيل المنتجات من النص. يرجى كتابة قائمة المنتجات مع أسعارها بوضوح."
            }

        created_items = []
        failed_items = []

        for item in extracted:
            title = item.get("title", "").strip()
            price = item.get("price")
            compare_price = item.get("compare_at_price")
            p_type = item.get("product_type", "أزياء وملابس")
            notes = item.get("notes", "")

            if not title or price is None:
                continue

            dummy_prod = {
                "title": title,
                "body_html": f"<p>{title}</p><p>{notes}</p>",
                "tags": p_type,
                "variants": [{"price": str(price)}]
            }
            try:
                seo_data = await self.generate_seo(dummy_prod, custom_instructions=notes)
                res = await self.shopify.create_product(
                    title=title,
                    price=price,
                    body_html=seo_data.get("improved_body_html", f"<p>{title}</p>"),
                    compare_at_price=compare_price,
                    product_type=p_type,
                    tags=seo_data.get("tags", []),
                    seo_title=seo_data.get("seo_title"),
                    seo_description=seo_data.get("seo_description")
                )
                if res.get("success"):
                    created_items.append({
                        "id": res.get("product_id"),
                        "title": title,
                        "price": price,
                        "seo_title": seo_data.get("seo_title")
                    })
                else:
                    failed_items.append({"title": title, "error": res.get("error")})
            except Exception as e:
                logger.error(f"Error creating product {title}: {e}")
                failed_items.append({"title": title, "error": str(e)})

        if not created_items:
            return {
                "success": False,
                "message": f"تعذر إنشاء المنتجات في شوبيفاي. التفاصيل: {failed_items}"
            }

        lines = [f"🎉 **تم إنشاء ورفع {len(created_items)} منتج جديد بنجاح إلى متجر الهدى (elhoda.net)!**\n"]
        for p in created_items:
            lines.append(f"• **{p['title']}** — {p['price']} ج.م (تم تجهيز سيو Google و AI ✅)")

        if failed_items:
            lines.append(f"\n⚠️ تعذر رفع {len(failed_items)} منتج بسبب خطأ من Shopify.")

        return {
            "success": True,
            "created_count": len(created_items),
            "created_items": created_items,
            "message": "\n".join(lines)
        }

    async def execute_command(self, user_message: str) -> dict[str, Any]:
        """Full end-to-end processing pipeline for a natural language user command."""
        # 1. Parse intent
        intent = await self.parse_user_intent(user_message)
        action = intent.get("action", "unknown")
        product_query = intent.get("product_query", "").strip()

        # Handle bulk store SEO optimization
        if action == "bulk_seo_store":
            return await self.bulk_optimize_store(limit=50)

        # Handle new products upload
        if action == "create_products":
            return await self.create_and_publish_products(user_message)

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
