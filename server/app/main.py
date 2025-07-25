
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from datetime import datetime
from app.api import webhooks, customers 

from app.config import settings
from app.database.connection import db_manager
from app.api import webhooks


# ============================================
# CONFIGURACIÓN DE LOGGING
# ============================================

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# ============================================
# LIFECYCLE EVENTS
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manejo del ciclo de vida de la aplicación"""
    
    # Startup
    logger.info("🚀 Iniciando Agente de Leads Bancario...")
    
    try:
        # Conectar a la base de datos
        await db_manager.connect()
        logger.info("✅ Base de datos conectada")
        
        # Verificar configuración
        logger.info(f"✅ Configuración cargada - Modo: {'DEBUG' if settings.debug else 'PRODUCTION'}")
        logger.info(f"✅ OpenAI configurado - Modelo: {settings.openai_model}")
        logger.info(f"✅ BuilderBot URL: {settings.builderbot_url}")
        
    except Exception as e:
        logger.error(f"❌ Error durante startup: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("👋 Cerrando Agente de Leads Bancario...")
    try:
        await db_manager.disconnect()
        logger.info("✅ Conexiones de DB cerradas")
    except Exception as e:
        logger.error(f"❌ Error durante shutdown: {e}")

# ============================================
# CREACIÓN DE LA APLICACIÓN
# ============================================

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="API para agente conversacional de captación de leads bancarios",
    lifespan=lifespan,
    debug=settings.debug
)

# ============================================
# MIDDLEWARE
# ============================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# ROUTERS
# ============================================

# Incluir routers de API
app.include_router(webhooks.router)
app.include_router(customers.router)  


# ============================================
# ENDPOINTS PRINCIPALES
# ============================================

@app.get("/")
async def root():
    """Endpoint raíz con información básica"""
    return {
        "service": settings.api_title,
        "version": settings.api_version,
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "webhook_builderbot": "✅ Integración WhatsApp",
            "langraph_agent": "✅ Conversaciones inteligentes", 
            "rules_engine": "✅ Motor de reglas automático",
            "event_simulation": "✅ Simulador para testing"
        },
        "endpoints": {
            "health": "/health",
            "webhook": "/webhook/builderbot",
            "rules": "/rules/*",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    """Health check completo del sistema"""
    try:
        health_status = {
            "status": "healthy",
            "service": settings.api_title,
            "version": settings.api_version,
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }
        
        # Verificar base de datos
        try:
            db_healthy = await db_manager.health_check()
            health_status["components"]["database"] = {
                "status": "healthy" if db_healthy else "unhealthy",
                "details": "Connected" if db_healthy else "Connection failed"
            }
        except Exception as e:
            health_status["components"]["database"] = {
                "status": "unhealthy",
                "details": str(e)
            }
        
        # Verificar configuración OpenAI
        health_status["components"]["openai"] = {
            "status": "configured" if settings.openai_api_key else "not_configured",
            "model": settings.openai_model
        }
        
        # Verificar BuilderBot (opcional)
        try:
            from app.services.builderbot_service import BuilderBotService
            builderbot = BuilderBotService()
            bb_healthy = await builderbot.health_check()
            health_status["components"]["builderbot"] = {
                "status": "healthy" if bb_healthy else "unreachable",
                "url": settings.builderbot_url
            }
        except Exception as e:
            health_status["components"]["builderbot"] = {
                "status": "error",
                "details": str(e)
            }
        
        # Determinar estado general
        component_statuses = [comp["status"] for comp in health_status["components"].values()]
        if "unhealthy" in component_statuses:
            health_status["status"] = "degraded"
        elif all(status in ["healthy", "configured"] for status in component_statuses):
            health_status["status"] = "healthy"
        else:
            health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error en health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/info")
async def service_info():
    """Información detallada del servicio"""
    return {
        "service": {
            "name": settings.api_title,
            "version": settings.api_version,
            "debug_mode": settings.debug
        },
        "configuration": {
            "openai_model": settings.openai_model,
            "openai_temperature": settings.openai_temperature,
            "openai_max_tokens": settings.openai_max_tokens,
            "builderbot_url": settings.builderbot_url,
            "session_timeout_minutes": settings.session_timeout_minutes
        },
        "features": {
            "langraph_agent": "✅ Conversaciones paso a paso",
            "builderbot_integration": "✅ WhatsApp bidireccional",
            "conversation_logging": "✅ Trazabilidad completa",
            "lead_generation": "✅ Captación inteligente",
            "rules_engine": "✅ Evaluación automática de reglas",
            "event_simulation": "✅ Testing y debugging",
            "guardrails": "✅ Validaciones de negocio"
        },
        "endpoints": {
            "webhook_builderbot": "/webhook/builderbot",
            "webhook_health": "/webhook/health",
            "rules_start": "/rules/start-monitoring",
            "rules_simulate": "/rules/simulate-events",
            "test_message": "/webhook/test-message",
            "health_check": "/health",
            "documentation": "/docs"
        }
    }

# ============================================
# MANEJO DE ERRORES GLOBAL
# ============================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Manejo global de excepciones"""
    logger.error(f"Error no manejado en {request.url}: {exc}")
    
    return {
        "error": "Internal server error",
        "detail": "Ha ocurrido un error interno. Por favor contacta al administrador.",
        "timestamp": datetime.now().isoformat(),
        "path": str(request.url)
    }

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Manejo de excepciones HTTP"""
    logger.warning(f"HTTP Exception {exc.status_code} en {request.url}: {exc.detail}")
    
    return {
        "error": f"HTTP {exc.status_code}",
        "detail": exc.detail,
        "timestamp": datetime.now().isoformat(),
        "path": str(request.url)
    }

# ============================================
# INICIALIZACIÓN
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"🚀 Iniciando servidor en {settings.api_host}:{settings.api_port}")
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )