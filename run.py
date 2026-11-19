import uvicorn
from src.config import settings

if __name__ == "__main__":
    print("=" * 60)
    print(f"🚀 بدء تشغيل مساعد الذكاء الاصطناعي لمتجر الهدى ({settings.clean_store_domain()})")
    print(f"🌐 لوحة التحكم متاحة على: http://{settings.HOST}:{settings.PORT}")
    print("=" * 60)
    uvicorn.run("src.main:app", host=settings.HOST, port=settings.PORT, reload=True)
