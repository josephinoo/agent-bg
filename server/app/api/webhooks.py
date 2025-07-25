# app/api/webhooks.py
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any
import logging
from datetime import datetime
import json

from app.models.schemas import BuilderBotMessage, AgentResponse, ErrorResponse
from app.database.connection import get_database, DatabaseManager
from app.database.repository import UserRepository, ConversationRepository, LeadRepository
from app.services.langraph_agent import ConversationAgent
from app.services.builderbot_service import BuilderBotService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhooks"])

# ============================================
# DEPENDENCY INJECTION
# ============================================

async def get_repositories(db: DatabaseManager = Depends(get_database)):
    """Obtiene repositorios necesarios"""
    user_repo = UserRepository(db)
    conversation_repo = ConversationRepository(db)
    lead_repo = LeadRepository(db)
    return user_repo, conversation_repo, lead_repo

async def get_agent(repos = Depends(get_repositories)):
    """Obtiene instancia del agente conversacional"""
    user_repo, conversation_repo, lead_repo = repos
    return ConversationAgent(conversation_repo, lead_repo, user_repo)

async def get_builderbot_service():
    """Obtiene servicio de BuilderBot"""
    return BuilderBotService()

# ============================================
# ENDPOINTS PRINCIPALES
# ============================================

@router.post("/builderbot", response_model=AgentResponse)
async def handle_builderbot_message(
    message: BuilderBotMessage,
    background_tasks: BackgroundTasks,
    repos = Depends(get_repositories),
    agent: ConversationAgent = Depends(get_agent),
    builderbot: BuilderBotService = Depends(get_builderbot_service)
):
    try:
        user_repo, conversation_repo, lead_repo = repos
        
        logger.info(f"📱 Mensaje recibido de {message.phone}: {message.message}")
        
        # 1. Verificar si el usuario está en alguna campaña activa
        user_data = await user_repo.get_user_by_phone(message.phone)
        
        if not user_data:
            logger.warning(f"Usuario {message.phone} no está en ninguna campaña activa")
            return AgentResponse(
                status="no_campaign",
                response="Gracias por contactarnos. En este momento atendemos consultas específicas de nuestros clientes en campañas activas.",
                step="not_eligible",
                session_id="",
                intent_confirmed=False,
                collected_data={}
            )
        
        logger.info(f"✅ Usuario encontrado: {user_data.user_id} en campaña {user_data.campaign_id}")
        
        # 2. Crear estado inicial
        state = await agent.create_initial_state(
            phone=message.phone,
            user_data=user_data.dict(),
            message=message.message
        )
        
        logger.info(f"🤖 Procesando mensaje con agente...")
        logger.info(f"Type of state: {type(state)}, value: {state}")
        result_state = await agent.process_message(state)
        
        # 5. Obtener la respuesta generada (debe ser exactamente UNA)
        agent_messages = [msg for msg in result_state["messages"] if msg["role"] == "assistant"]
        
        if not agent_messages:
            logger.error("❌ No se generó respuesta del agente")
            return AgentResponse(
                status="error",
                response="Disculpa, tengo problemas técnicos. ¿Podrías intentar más tarde?",
                step=result_state["current_step"],
                session_id=result_state["session_id"],
                intent_confirmed=result_state.get("intent_confirmed"),
                collected_data=result_state.get("collected_data", {})
            )
        
        # Obtener la ÚLTIMA respuesta del agente (la que acabamos de generar)
        latest_response = agent_messages[-1]["content"]
        
        logger.info(f"✅ Procesamiento completo para {message.phone}")
        logger.info(f"📤 Respuesta: {latest_response[:100]}...")
        
        # CORREGIR: Manejar collected_data correctamente
        collected_data = result_state.get("collected_data", {})
     
        return AgentResponse(
            status="success",
            response=latest_response,
            step=result_state["current_step"],
            session_id=result_state["session_id"],
            intent_confirmed=result_state.get("intent_confirmed"),
            collected_data={}
        )
        
    except Exception as e:
        logger.error(f"❌ Error procesando mensaje de {message.phone}: {e}")
        
        # Respuesta de error
        error_response = "Disculpa, tengo problemas técnicos en este momento. ¿Podrías intentar más tarde? 2"
        
        # Intentar enviar respuesta de error a BuilderBot
        try:
            builderbot_service = await get_builderbot_service()
            background_tasks.add_task(
                send_response_to_builderbot,
                builderbot_service,
                message.phone,
                error_response,
                "error_session"
            )
        except:
            pass  # Si falla el envío, al menos loggear
        
        return AgentResponse(
            status="error",
            response=error_response,
            step="error",
            session_id="",
            intent_confirmed=False,
            collected_data={}
        )

@router.post("/start-chat", response_model=AgentResponse)
async def start_chat(
    start_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    repos = Depends(get_repositories),
    agent: ConversationAgent = Depends(get_agent),
    builderbot: BuilderBotService = Depends(get_builderbot_service)
):
    try:
        phone = start_data.get("phone")
        campaign_id = start_data.get("campaign_id")
        user_info = start_data.get("user_data", {})
        
        if not phone or not campaign_id:
            raise HTTPException(
                status_code=400, 
                detail="Se requieren 'phone' y 'campaign_id'"
            )
        
        logger.info(f"🚀 Iniciando chat proactivo con {phone} - Campaña: {campaign_id}")
        
        user_repo, conversation_repo, lead_repo = repos
        
        # 1. Verificar si el usuario ya existe en esta campaña
        existing_user = await user_repo.get_user_by_phone(phone)
        
        if existing_user and existing_user.campaign_id == campaign_id:
            logger.info(f"👤 Usuario {phone} ya existe en campaña {campaign_id}")
            user_data = existing_user.dict()
        else:
            # 2. Crear/actualizar usuario en la campaña
            user_data = {
                "user_id": f"user_{phone.replace('+', '').replace(' ', '')}_{campaign_id}",
                "campaign_id": campaign_id,
                "phone": phone,
                "first_name": user_info.get("first_name", ""),
                "last_name": user_info.get("last_name", ""),
                "product_type": user_info.get("product_type", "credit_card"),
                "customer_segment": user_info.get("customer_segment", "standard"),
                "created_at": datetime.now().isoformat()
            }
            
            await user_repo.create_or_update_user(user_data)
            logger.info(f"✅ Usuario {phone} agregado a campaña {campaign_id}")
        
        # 3. CAMBIO PRINCIPAL: Crear saludo personalizado directo
        user_name = user_data.get("first_name", "").strip() or "Cliente"
        product_type = user_data.get("product_type", "credit_card")
        
        # Saludo personalizado según el producto
        greeting_messages = {
            "credit_card": f"¡Hola {user_name}! 👋 Soy tu asesor financiero virtual. Tengo una excelente oportunidad de tarjeta de crédito para ti. ¿Cuál es tu presupuesto mensual aproximado?",
            "personal_loan": f"¡Hola {user_name}! 👋 Te contacto porque tenemos préstamos personales con tasas preferenciales. ¿Qué presupuesto manejas mensualmente?",
            "mortgage": f"¡Hola {user_name}! 👋 Tenemos opciones de crédito hipotecario que te pueden interesar. ¿Cuáles son tus ingresos mensuales aproximados?"
        }
        
        agent_response = greeting_messages.get(product_type, 
            f"¡Hola {user_name}! 👋 Tengo información financiera importante para ti. ¿Cuál es tu presupuesto mensual?")
        
        # 4. Crear estado inicial simple
        session_id = f"session_{phone.replace('+', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        state = {
            "phone": phone,
            "user_id": user_data["user_id"],
            "campaign_id": campaign_id,
            "product_type": product_type,
            "current_step": "collect_budget",  # Empezar directamente preguntando presupuesto
            "collected_data": {},
            "messages": [{
                "role": "assistant",
                "content": agent_response,
                "timestamp": datetime.now().isoformat()
            }],
            "intent_confirmed": None,
            "session_id": session_id,
            "user_name": user_name,
            "customer_segment": user_data.get("customer_segment", "standard")
        }
        
        # 5. Guardar estado inicial
        try:
            await conversation_repo.save_conversation_log(state)
            await conversation_repo.save_message(session_id, "agent", agent_response, "greeting")
        except Exception as e:
            logger.error(f"Error guardando estado inicial: {e}")
        
        # 6. Enviar mensaje a BuilderBot
        background_tasks.add_task(
            send_response_to_builderbot,
            builderbot,
            phone,
            agent_response,
            session_id
        )
        
        logger.info(f"✅ Chat iniciado exitosamente con {phone}")
        logger.info(f"📤 Saludo: {agent_response}")
        
        return AgentResponse(
            status="chat_started",
            response=agent_response,
            step="collect_budget",
            session_id=session_id,
            intent_confirmed=None,
            collected_data={}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error iniciando chat con {phone}: {e}")
        
        return AgentResponse(
            status="error",
            response="Error interno al iniciar conversación",
            step="error",
            session_id="",
            intent_confirmed=False,
            collected_data={}
        )


# ============================================
# ENDPOINTS DE GESTIÓN
# ============================================

@router.get("/conversations/{session_id}")
async def get_conversation_details(
    session_id: str,
    agent: ConversationAgent = Depends(get_agent)
):
    """Obtiene detalles de una conversación específica"""
    try:
        summary = await agent.get_conversation_summary(session_id)
        return summary
    except Exception as e:
        logger.error(f"Error obteniendo conversación {session_id}: {e}")
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

@router.get("/user/{phone}/conversations")
async def get_user_conversations(
    phone: str,
    repos = Depends(get_repositories)
):
    """Obtiene historial de conversaciones de un usuario"""
    try:
        user_repo, conversation_repo, lead_repo = repos
        
        # Obtener historial de BuilderBot
        user_data = await user_repo.get_user_by_phone(phone)
        history = await conversation_repo.get_builderbot_history(phone, limit=20)
        
        # Verificar si está en campaña
        
        
        return {
            "phone": phone,
            "in_active_campaign": user_data is not None,
            "campaign_info": user_data.dict() if user_data else None,
            "conversation_history": history
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo conversaciones de {phone}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# FUNCIONES AUXILIARES
# ============================================

async def send_response_to_builderbot(
    builderbot_service: BuilderBotService, 
    phone: str, 
    message: str, 
    session_id: str
):
    """Envía respuesta a BuilderBot en background con logging mejorado"""
    try:
        logger.info(f"📤 Enviando a BuilderBot: {phone} - {message[:50]}...")
        success = await builderbot_service.send_message(phone, message)
        
        if success:
            logger.info(f"✅ Mensaje enviado exitosamente a {phone}")
        else:
            logger.error(f"❌ Falló envío a BuilderBot para {phone}")
            
    except Exception as e:
        logger.error(f"❌ Error crítico enviando a BuilderBot: {e}")

# ============================================
# HEALTH CHECK ESPECÍFICO
# ============================================

@router.get("/health")
async def webhook_health_check(
    repos = Depends(get_repositories)
):
    """Health check específico para webhooks"""
    try:
        user_repo, conversation_repo, lead_repo = repos
        
        # Verificar conexión a DB haciendo una query simple
        test_campaigns = await user_repo.db.execute_query(
            "SELECT COUNT(*) as count FROM campaigns LIMIT 1"
        )
        
        return {
            "status": "healthy",
            "webhook_service": "online",
            "database": "connected",
            "total_campaigns": test_campaigns[0]["count"] if test_campaigns else 0,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Webhook health check failed: {e}")
        return {
            "status": "unhealthy", 
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }