import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from pydantic import BaseModel

from src.config import settings
from src.shopify_client import ShopifyClient
from src.ai_agent import AIAgent
from src.telegram_bot import TelegramBotService
from src.database import (
    authenticate_user,
    get_user_by_username,
    list_users,
    create_user,
    delete_user,
    log_activity,
    get_activity_logs
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML_PATH = BASE_DIR / "dashboard" / "templates" / "index.html"
LOGIN_HTML_PATH = BASE_DIR / "dashboard" / "templates" / "login.html"

# Active sessions store in memory: token -> username
SESSIONS: dict[str, str] = {}

def get_current_user(request: Request) -> Optional[dict[str, Any]]:
    token = request.cookies.get("session_token")
    if not token or token not in SESSIONS:
        return None
    username = SESSIONS[token]
    user = get_user_by_username(username)
    return user

def require_auth(request: Request) -> dict[str, Any]:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user

shopify_client = ShopifyClient()
ai_agent = AIAgent(shopify_client)
telegram_service = TelegramBotService()
telegram_task: Optional[asyncio.Task] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_task
    logger.info("Starting Shopify AI Agent Server...")
    
    # Start Telegram Bot if configured
    if settings.TELEGRAM_BOT_TOKEN and "123456" not in settings.TELEGRAM_BOT_TOKEN:
        try:
            tg_app = telegram_service.build_application()
            await tg_app.initialize()
            await tg_app.start()
            telegram_task = asyncio.create_task(tg_app.updater.start_polling())
            logger.info("Telegram Bot started successfully.")
        except Exception as e:
            logger.error(f"Failed to start Telegram Bot: {e}")
    else:
        logger.info("Telegram Bot token is not configured or is a placeholder. Skipping Telegram.")

    yield

    if telegram_service.app and telegram_service.app.updater:
        logger.info("Stopping Telegram Bot...")
        await telegram_service.app.updater.stop()
        await telegram_service.app.stop()
        await telegram_service.app.shutdown()
    logger.info("Server shutdown complete.")

app = FastAPI(title="Shopify AI Agent - elhoda.net", lifespan=lifespan)

# Request Models
class LoginRequest(BaseModel):
    username: str
    password: str

class SettingsUpdateRequest(BaseModel):
    shopify_store_url: Optional[str] = None
    shopify_token: Optional[str] = None
    gemini_key: Optional[str] = None
    telegram_token: Optional[str] = None
    admin_password: Optional[str] = None
    admin_username: Optional[str] = None

class AICommandRequest(BaseModel):
    prompt: str

class UpdatePriceRequest(BaseModel):
    product_id: int | str
    new_price: float | str
    compare_at_price: Optional[float | str] = None

class OptimizeSeoRequest(BaseModel):
    product_id: int | str
    custom_instructions: Optional[str] = None

class UserCreateReq(BaseModel):
    username: str
    password: str
    name: str
    role: str = "staff"

# Routes
@app.get("/login")
async def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=302)
    return FileResponse(LOGIN_HTML_PATH)

@app.post("/api/login")
async def api_login(req: LoginRequest, response: Response):
    user = authenticate_user(req.username, req.password)
    if user:
        token = secrets.token_urlsafe(32)
        SESSIONS[token] = user["username"]
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 7 # 7 days
        )
        log_activity(user["username"], "تسجيل دخول", f"تسجيل دخول ناجح للمستخدم {user['name']} ({user['role']})")
        return {"success": True, "username": user["username"], "name": user["name"], "role": user["role"]}
    return {"success": False, "message": "اسم المستخدم أو كلمة المرور غير صحيحة"}

@app.get("/logout")
async def logout_view(request: Request):
    user = get_current_user(request)
    if user:
        log_activity(user["username"], "تسجيل خروج", f"قام المستخدم {user['name']} بتسجيل الخروج")
    token = request.cookies.get("session_token")
    if token and token in SESSIONS:
        del SESSIONS[token]
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie("session_token")
    return resp

@app.get("/api/me")
async def me_view(request: Request):
    user = get_current_user(request)
    if not user:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "id": user.get("id"),
        "username": user.get("username"),
        "name": user.get("name"),
        "role": user.get("role", "staff")
    }

@app.get("/api/users")
async def get_users_list(request: Request):
    user = require_auth(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="صلاحية المدير فقط")
    return {"success": True, "users": list_users()}

@app.post("/api/users")
async def create_user_endpoint(req: UserCreateReq, request: Request):
    user = require_auth(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="صلاحية المدير فقط")
    
    ok = create_user(req.username, req.password, req.name, req.role)
    if ok:
        log_activity(user["username"], "إضافة مستخدم", f"تم إنشاء مستخدم جديد: {req.username} ({req.name}) بصلاحية {req.role}")
        return {"success": True, "message": "تمت إضافة المستخدم بنجاح"}
    return {"success": False, "message": "اسم المستخدم موجود مسبقاً، يرجى اختيار اسم آخر"}

@app.delete("/api/users/{user_id}")
async def delete_user_endpoint(user_id: int, request: Request):
    user = require_auth(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="صلاحية المدير فقط")
    
    ok = delete_user(user_id)
    if ok:
        log_activity(user["username"], "حذف مستخدم", f"تم حذف المستخدم ذو المعرف رقم {user_id}")
        return {"success": True, "message": "تم حذف المستخدم بنجاح"}
    return {"success": False, "message": "تعذر حذف المستخدم"}

@app.get("/api/logs")
async def get_logs_endpoint(request: Request, user_filter: Optional[str] = None, limit: int = 100):
    user = require_auth(request)
    # Admin can view all, staff sees only their own
    username_filter = user_filter if user.get("role") == "admin" else user["username"]
    logs = get_activity_logs(limit=limit, username_filter=username_filter)
    return {"success": True, "logs": logs}

@app.get("/")
async def dashboard_view(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return FileResponse(INDEX_HTML_PATH)

@app.get("/api/settings")
async def get_settings_status():
    """Return status of configured credentials."""
    return {
        "shopify_store_url": settings.clean_store_domain(),
        "has_shopify_token": bool(settings.SHOPIFY_ADMIN_ACCESS_TOKEN and "shpat_" in settings.SHOPIFY_ADMIN_ACCESS_TOKEN),
        "has_gemini_key": bool(settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY) > 10),
        "has_telegram_token": bool(settings.TELEGRAM_BOT_TOKEN and ":" in settings.TELEGRAM_BOT_TOKEN)
    }

@app.post("/api/settings")
async def update_settings_endpoint(req: SettingsUpdateRequest):
    """Save credentials to .env file and reload runtime configuration."""
    env_path = BASE_DIR.parent / ".env"
    
    # Read existing .env lines
    existing_lines = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    env_map = {}
    for line in existing_lines:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env_map[k.strip()] = v.strip()

    if req.shopify_store_url:
        env_map["SHOPIFY_STORE_URL"] = req.shopify_store_url.strip()
        settings.SHOPIFY_STORE_URL = req.shopify_store_url.strip()

    if req.shopify_token:
        env_map["SHOPIFY_ADMIN_ACCESS_TOKEN"] = req.shopify_token.strip()
        settings.SHOPIFY_ADMIN_ACCESS_TOKEN = req.shopify_token.strip()

    if req.gemini_key:
        env_map["GEMINI_API_KEY"] = req.gemini_key.strip()
        settings.GEMINI_API_KEY = req.gemini_key.strip()

    if req.telegram_token:
        env_map["TELEGRAM_BOT_TOKEN"] = req.telegram_token.strip()
        settings.TELEGRAM_BOT_TOKEN = req.telegram_token.strip()

    if req.admin_password and req.admin_username:
        new_users_str = f"{req.admin_username.strip()}:{req.admin_password.strip()}"
        env_map["DASHBOARD_USERS"] = new_users_str
        settings.DASHBOARD_USERS = new_users_str

    # Recreate clients with new credentials
    global shopify_client, ai_agent
    shopify_client = ShopifyClient()
    ai_agent = AIAgent(shopify_client)

    # Save to .env
    output_lines = [
        f"SHOPIFY_STORE_URL={env_map.get('SHOPIFY_STORE_URL', 'elhoda.net')}",
        f"SHOPIFY_ADMIN_ACCESS_TOKEN={env_map.get('SHOPIFY_ADMIN_ACCESS_TOKEN', '')}",
        f"SHOPIFY_API_VERSION={env_map.get('SHOPIFY_API_VERSION', '2024-04')}",
        f"GEMINI_API_KEY={env_map.get('GEMINI_API_KEY', '')}",
        f"TELEGRAM_BOT_TOKEN={env_map.get('TELEGRAM_BOT_TOKEN', '')}",
        f"TELEGRAM_ALLOWED_USER_IDS={env_map.get('TELEGRAM_ALLOWED_USER_IDS', '')}",
        f"DASHBOARD_USERS={env_map.get('DASHBOARD_USERS', 'admin:elhoda@2026')}",
        f"SECRET_KEY={env_map.get('SECRET_KEY', 'elhoda-super-secret-key-2026')}",
        f"HOST={env_map.get('HOST', '127.0.0.1')}",
        f"PORT={env_map.get('PORT', '8000')}"
    ]
    env_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")

    return {
        "success": True,
        "message": "تم حفظ الإعدادات بنجاح وتفعيل الربط الفوري!",
        "status": await get_settings_status()
    }

@app.get("/api/products")
async def get_products():
    """List products from Shopify store."""
    if not settings.SHOPIFY_ADMIN_ACCESS_TOKEN or "shpat_" not in settings.SHOPIFY_ADMIN_ACCESS_TOKEN:
        return {
            "success": False,
            "message": "لم يتم إدخال مفتاح Shopify Admin API Access Token بعد في ملف .env",
            "products": []
        }
    try:
        products = await shopify_client.list_products(limit=50)
        return {"success": True, "products": products}
    except Exception as e:
        logger.exception("Error listing products")
        return {"success": False, "message": str(e), "products": []}

@app.post("/api/ai-command")
async def execute_ai_command(req: AICommandRequest, request: Request):
    """Execute natural language command via AI Agent."""
    user = require_auth(request)
    try:
        result = await ai_agent.execute_command(req.prompt)
        log_activity(
            username=user["username"],
            action="أمر ذكاء اصطناعي",
            details=f"طلب: {req.prompt} ➔ النتيجة: {result.get('message', '')[:120]}",
            product_id=str(result.get("product_id") or ""),
            product_title=result.get("product_title")
        )
        return result
    except Exception as e:
        logger.exception("Error executing AI command")
        log_activity(
            username=user["username"],
            action="أمر ذكاء اصطناعي (فشل)",
            details=f"فشل تنفيذ الطلب '{req.prompt}': {str(e)}"
        )
        return {"success": False, "message": str(e)}

@app.post("/api/update-price")
async def update_price(req: UpdatePriceRequest, request: Request):
    """Directly update product price."""
    user = require_auth(request)
    try:
        res = await shopify_client.update_product_price(
            product_id=req.product_id,
            new_price=req.new_price,
            compare_at_price=req.compare_at_price
        )
        if res.get("success"):
            log_activity(
                username=user["username"],
                action="تعديل سعر",
                details=f"تعديل سعر منتج ({res.get('product_title')}) إلى {req.new_price} ج.م" + (f" (قبل الخصم: {req.compare_at_price})" if req.compare_at_price else ""),
                product_id=str(req.product_id),
                product_title=res.get("product_title")
            )
        return res
    except Exception as e:
        logger.exception("Error updating price")
        return {"success": False, "error": str(e)}

@app.post("/api/optimize-seo")
async def optimize_seo(req: OptimizeSeoRequest, request: Request):
    """Generate and apply AI SEO optimization for a product."""
    user = require_auth(request)
    try:
        product = await shopify_client.get_product(req.product_id)
        if not product:
            return {"success": False, "error": "المنتج غير موجود."}

        seo_data = await ai_agent.generate_seo(product, req.custom_instructions or "")
        update_res = await shopify_client.update_product_seo(
            product_id=req.product_id,
            seo_title=seo_data.get("seo_title"),
            seo_description=seo_data.get("seo_description"),
            tags=seo_data.get("tags"),
            body_html=seo_data.get("improved_body_html")
        )
        if update_res.get("success"):
            log_activity(
                username=user["username"],
                action="تحسين SEO",
                details=f"تحسين سيو منتج: {product.get('title')} | العنوان: {seo_data.get('seo_title')}",
                product_id=str(req.product_id),
                product_title=product.get("title")
            )
        return {
            "success": update_res.get("success", False),
            "seo": seo_data,
            "update_response": update_res
        }
    except Exception as e:
        logger.exception("Error optimizing SEO")
        return {"success": False, "error": str(e)}

@app.get("/health")
async def health():
    return {"status": "ok", "store": settings.clean_store_domain()}
