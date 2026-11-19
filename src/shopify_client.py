import logging
from typing import Any, Optional
import httpx
from src.config import settings

logger = logging.getLogger("shopify_client")

class ShopifyClient:
    def __init__(self, store_url: Optional[str] = None, token: Optional[str] = None):
        domain = store_url or settings.clean_store_domain()
        self.base_url = f"https://{domain}/admin/api/{settings.SHOPIFY_API_VERSION}"
        self.token = token or settings.SHOPIFY_ADMIN_ACCESS_TOKEN
        self.headers = {
            "X-Shopify-Access-Token": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self.headers, timeout=20.0)

    async def test_connection(self) -> dict[str, Any]:
        """Test API credentials against Shopify shop endpoint."""
        async with self._client() as client:
            url = f"{self.base_url}/shop.json"
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json().get("shop", {})
                return {
                    "success": True,
                    "name": data.get("name"),
                    "domain": data.get("domain"),
                    "myshopify_domain": data.get("myshopify_domain"),
                    "currency": data.get("currency")
                }
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text
            }

    async def list_products(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch list of products with variants and images."""
        async with self._client() as client:
            url = f"{self.base_url}/products.json?limit={limit}"
            response = await client.get(url)
            if response.status_code == 200:
                return response.json().get("products", [])
            logger.error(f"Error fetching products: {response.text}")
            return []

    async def search_products(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search products by title or keywords."""
        query = query.strip()
        async with self._client() as client:
            # First try exact/partial title search
            url = f"{self.base_url}/products.json?title={query}&limit={limit}"
            response = await client.get(url)
            products = []
            if response.status_code == 200:
                products = response.json().get("products", [])

            # If no direct match, fetch latest and filter locally
            if not products:
                all_prods = await self.list_products(limit=50)
                q_lower = query.lower()
                products = [
                    p for p in all_prods
                    if q_lower in p.get("title", "").lower()
                    or any(q_lower in tag.lower() for tag in p.get("tags", "").split(","))
                ][:limit]

            return products

    async def get_product(self, product_id: int | str) -> Optional[dict[str, Any]]:
        """Get full product details by ID."""
        async with self._client() as client:
            url = f"{self.base_url}/products/{product_id}.json"
            response = await client.get(url)
            if response.status_code == 200:
                return response.json().get("product")
            return None

    async def update_variant_price(
        self,
        variant_id: int | str,
        price: float | str,
        compare_at_price: Optional[float | str] = None
    ) -> bool:
        """Update price for a specific variant."""
        async with self._client() as client:
            url = f"{self.base_url}/variants/{variant_id}.json"
            payload: dict[str, Any] = {
                "variant": {
                    "id": variant_id,
                    "price": f"{float(price):.2f}"
                }
            }
            if compare_at_price is not None:
                payload["variant"]["compare_at_price"] = f"{float(compare_at_price):.2f}"

            response = await client.put(url, json=payload)
            if response.status_code == 200:
                return True
            logger.error(f"Failed to update variant price {variant_id}: {response.text}")
            return False

    async def update_product_price(
        self,
        product_id: int | str,
        new_price: float | str,
        compare_at_price: Optional[float | str] = None,
        variant_id: Optional[int | str] = None
    ) -> dict[str, Any]:
        """Update price on specific variant or all variants of a product."""
        product = await self.get_product(product_id)
        if not product:
            return {"success": False, "error": f"Product {product_id} not found."}

        variants = product.get("variants", [])
        if not variants:
            return {"success": False, "error": "No variants found on product."}

        updated_count = 0
        old_prices = []

        for v in variants:
            v_id = v.get("id")
            old_prices.append({"id": v_id, "title": v.get("title"), "old_price": v.get("price")})
            if variant_id is None or str(variant_id) == str(v_id):
                ok = await self.update_variant_price(v_id, new_price, compare_at_price)
                if ok:
                    updated_count += 1

        return {
            "success": updated_count > 0,
            "product_id": product_id,
            "product_title": product.get("title"),
            "new_price": new_price,
            "compare_at_price": compare_at_price,
            "variants_updated": updated_count,
            "history": old_prices
        }

    async def update_product_seo(
        self,
        product_id: int | str,
        seo_title: Optional[str] = None,
        seo_description: Optional[str] = None,
        tags: Optional[list[str] | str] = None,
        body_html: Optional[str] = None
    ) -> dict[str, Any]:
        """Update SEO title, meta description, tags, and product body."""
        async with self._client() as client:
            url = f"{self.base_url}/products/{product_id}.json"
            product_data: dict[str, Any] = {"id": product_id}

            if seo_title:
                product_data["metafields_global_title_tag"] = seo_title
            if seo_description:
                product_data["metafields_global_description_tag"] = seo_description
            if tags:
                if isinstance(tags, list):
                    product_data["tags"] = ", ".join(tags)
                else:
                    product_data["tags"] = tags
            if body_html:
                product_data["body_html"] = body_html

            response = await client.put(url, json={"product": product_data})
            if response.status_code == 200:
                updated = response.json().get("product", {})
                return {
                    "success": True,
                    "product_id": product_id,
                    "title": updated.get("title"),
                    "seo_title": updated.get("metafields_global_title_tag"),
                    "seo_description": updated.get("metafields_global_description_tag"),
                    "tags": updated.get("tags")
                }
            logger.error(f"Failed to update SEO for product {product_id}: {response.text}")
            return {"success": False, "error": response.text}
