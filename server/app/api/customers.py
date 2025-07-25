# app/api/customers.py - VERSIÓN CORREGIDA
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from decimal import Decimal
import logging

from app.database.connection import db_manager
from app.database.repository import UserRepository, CampaignRepository, LeadRepository, ConversationRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["customers"])

# Dependency para obtener repositorios
async def get_repositories():
    return {
        "user_repo": UserRepository(db_manager),
        "campaign_repo": CampaignRepository(db_manager),
        "lead_repo": LeadRepository(db_manager),
        "conversation_repo": ConversationRepository(db_manager)
    }

@router.get("/client/{phone}")
async def get_customer_info(
    phone: str,
    repos: Dict = Depends(get_repositories)
):
    """
    Obtiene información completa del cliente por número de teléfono
    """
    try:
        user_repo = repos["user_repo"]
        conversation_repo = repos["conversation_repo"]
        
        # Obtener datos del usuario
        user_data = await user_repo.get_user_by_phone(phone)
        
        if not user_data:
            # Verificar si existe en la tabla pero sin campaña activa
            debug_query = """
            SELECT cu.*, c.status as campaign_status, c.name as campaign_name
            FROM campaign_users cu
            LEFT JOIN campaigns c ON cu.campaign_id = c.id
            WHERE cu.phone = $1 OR cu.phone = $2
            ORDER BY cu.added_at DESC
            LIMIT 1
            """
            clean_phone = _clean_phone(phone)
            debug_row = await db_manager.execute_single(debug_query, phone, clean_phone)
            
            if debug_row:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "Cliente encontrado pero sin campaña activa",
                        "campaign_status": debug_row.get('campaign_status'),
                        "campaign_name": debug_row.get('campaign_name'),
                        "phone": phone
                    }
                )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Cliente con teléfono {phone} no encontrado en el sistema"
                )
        
        # Obtener historial de conversaciones para comportamiento
        conversation_history = await conversation_repo.get_unified_history(phone, limit=10)
        
        # Calcular comportamiento reciente
        page_visits = len(conversation_history)
        last_action = None
        if conversation_history:
            last_message = conversation_history[0]
            last_action = last_message.get('message_text', 'sin_actividad')[:50]
        
        # Construir respuesta
        customer_info = {
            "id": user_data.user_id,
            "name": f"{user_data.first_name} {user_data.last_name}".strip(),
            "last_login": conversation_history[0]['timestamp'].isoformat() if conversation_history else None,
            "products": user_data.current_products or [],
            "score": user_data.credit_score or 0,
            "behavior": {
                "page_visits": page_visits,
                "last_action": last_action or "sin_actividad"
            },
            "customer_segment": user_data.customer_segment,
            "monthly_income": safe_decimal_to_float(user_data.monthly_income),
            "phone": user_data.phone,
            "campaign_id": user_data.campaign_id,
            "product_type": user_data.product_type
        }
        
        return customer_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo información del cliente {phone}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor al obtener información del cliente"
        )

@router.get("/campanas/{phone}")
async def get_active_campaigns_for_customer(
    phone: str,
    repos: Dict = Depends(get_repositories)
):
    """
    Obtiene campañas activas disponibles para un cliente específico
    """
    try:
        user_repo = repos["user_repo"]
        campaign_repo = repos["campaign_repo"]
        
        # Verificar si el usuario existe
        user_data = await user_repo.get_user_by_phone(phone)
        if not user_data:
            raise HTTPException(
                status_code=404,
                detail=f"Cliente con teléfono {phone} no encontrado"
            )
        
        # Obtener campañas activas
        active_campaigns = await campaign_repo.get_active_campaigns()
        
        # Verificar que no sea None
        if active_campaigns is None:
            active_campaigns = []
        
        # Filtrar y enriquecer campañas según el perfil del cliente
        available_campaigns = []
        
        for campaign in active_campaigns:
            try:
                # Convertir valores a tipos seguros
                credit_score = safe_int(user_data.credit_score)
                monthly_income = safe_decimal_to_float(user_data.monthly_income)
                product_type = campaign['product_type']
                
                # Calcular monto máximo
                max_amount = calculate_max_amount(credit_score, monthly_income, product_type)
                
                # Manejar valores None de la base de datos
                budget_total = safe_decimal_to_float(campaign['budget_total'])
                budget_spent = safe_decimal_to_float(campaign['budget_spent'])
                
                campaign_info = {
                    "id": str(campaign['id']),
                    "name": campaign['name'],
                    "product": campaign['product_type'],
                    "max_amount": max_amount,
                    "status": campaign['status'],
                    "budget_available": budget_total - budget_spent,
                    "end_date": campaign['end_date'].isoformat() if campaign['end_date'] else None
                }
                
                available_campaigns.append(campaign_info)
                
            except Exception as campaign_error:
                logger.warning(f"Error procesando campaña {campaign.get('id', 'unknown')}: {campaign_error}")
                continue
        
        return {
            "customer_id": user_data.user_id,
            "customer_segment": user_data.customer_segment,
            "active_campaigns": available_campaigns,
            "total_campaigns": len(available_campaigns)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo campañas para cliente {phone}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor al obtener campañas"
        )

@router.post("/lead/{phone}")
async def create_lead_for_customer(
    phone: str,
    lead_data: Optional[Dict[str, Any]] = None,
    repos: Dict = Depends(get_repositories)
):
    """
    Crea un nuevo lead para un cliente específico
    """
    try:
        user_repo = repos["user_repo"]
        lead_repo = repos["lead_repo"]
        conversation_repo = repos["conversation_repo"]
        
        # Verificar que el usuario existe
        user_data = await user_repo.get_user_by_phone(phone)
        if not user_data:
            raise HTTPException(
                status_code=404,
                detail=f"Cliente con teléfono {phone} no encontrado"
            )
        
        # Crear sesión de conversación si no existe
        session_id = await conversation_repo.get_session_id(phone)
        if not session_id:
            session_id = f"lead_{user_data.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Preparar datos del estado de conversación
        collected_data = {}
        if lead_data:
            collected_data.update(lead_data)
        
        # Crear estado de conversación para el lead
        conversation_state = {
            "session_id": session_id,
            "user_id": user_data.user_id,
            "campaign_id": user_data.campaign_id,
            "phone": user_data.phone,
            "user_name": f"{user_data.first_name} {user_data.last_name}".strip(),
            "product_type": lead_data.get("product_type", user_data.product_type) if lead_data else user_data.product_type,
            "current_step": "completed",
            "intent_confirmed": True,
            "collected_data": collected_data,
            "messages": [],
            "propensity_score": calculate_propensity_score(user_data, collected_data)
        }
        
        # Guardar el lead
        lead_id = await lead_repo.save_lead(conversation_state)
        
        # Guardar log de conversación
        await conversation_repo.save_conversation_log(conversation_state)
        
        # Actualizar estado del usuario en campaña
        await user_repo.update_user_status(
            user_data.user_id, 
            user_data.campaign_id, 
            "lead_generated"
        )
        
        return {
            "lead_id": lead_id,
            "status": "accepted",
            "timestamp": datetime.now().isoformat(),
            "customer_id": user_data.user_id,
            "session_id": session_id,
            "product_type": conversation_state["product_type"],
            "propensity_score": conversation_state["propensity_score"],
            "message": "Lead creado exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando lead para cliente {phone}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor al crear lead"
        )

# Funciones auxiliares mejoradas
def safe_decimal_to_float(value: Union[Decimal, float, int, None]) -> float:
    """Convierte de forma segura Decimal/int/None a float"""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0

def safe_int(value: Union[int, float, Decimal, None]) -> int:
    """Convierte de forma segura cualquier número a int"""
    if value is None:
        return 0
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0

def _clean_phone(phone: str) -> str:
    """Limpia el formato del teléfono"""
    import re
    clean = re.sub(r'[^\d+]', '', phone)
    
    if not clean.startswith('+'):
        if clean.startswith('593'):
            clean = '+' + clean
        elif clean.startswith('09') or clean.startswith('9'):
            clean = '+593' + clean.lstrip('0')
        else:
            clean = '+593' + clean
    
    return clean

def calculate_max_amount(credit_score: int, monthly_income: float, product_type: str) -> int:
    """Calcula el monto máximo según el perfil del cliente - VERSIÓN CORREGIDA"""
    if not credit_score or not monthly_income:
        return 5000  # Monto base
    
    # Factores base según producto
    product_factors = {
        "credito_personal": 5.0,  # Asegurar que sea float
        "credito_vehicular": 15.0,
        "credito_hipotecario": 100.0,
        "tarjeta_credito": 3.0
    }
    
    base_factor = product_factors.get(product_type, 5.0)
    
    # Ajuste por score crediticio
    if credit_score >= 800:
        score_multiplier = 1.5
    elif credit_score >= 700:
        score_multiplier = 1.2
    elif credit_score >= 600:
        score_multiplier = 1.0
    else:
        score_multiplier = 0.7
    
    # Asegurar que monthly_income sea float
    monthly_income_float = float(monthly_income)
    
    # Calcular con tipos compatibles
    max_amount = int(monthly_income_float * base_factor * score_multiplier)
    
    # Límites por producto
    limits = {
        "credito_personal": (1000, 50000),
        "credito_vehicular": (5000, 200000),
        "credito_hipotecario": (20000, 500000),
        "tarjeta_credito": (500, 15000)
    }
    
    min_limit, max_limit = limits.get(product_type, (1000, 50000))
    
    return max(min_limit, min(max_amount, max_limit))

def calculate_propensity_score(user_data, collected_data: Dict) -> float:
    """Calcula el score de propensión basado en datos del usuario"""
    score = 0.0
    
    # Score base por segmento
    segment_scores = {
        "premium": 0.8,
        "standard": 0.6,
        "basic": 0.4
    }
    score += segment_scores.get(user_data.customer_segment, 0.5)
    
    # Ajuste por score crediticio
    if user_data.credit_score:
        credit_score = safe_int(user_data.credit_score)
        if credit_score >= 800:
            score += 0.2
        elif credit_score >= 700:
            score += 0.1
        elif credit_score < 600:
            score -= 0.1
    
    # Ajuste por ingresos
    monthly_income = safe_decimal_to_float(user_data.monthly_income)
    if monthly_income > 1500:
        score += 0.1
    
    # Ajuste por productos actuales
    if user_data.current_products and len(user_data.current_products) > 0:
        score += 0.1
    
    return min(1.0, max(0.0, score))

# Endpoint de debugging
@router.get("/debug/cliente/{phone}")
async def debug_customer(phone: str):
    """Endpoint para debugging - verificar por qué un cliente no se encuentra"""
    try:
        clean_phone = _clean_phone(phone)
        
        # Buscar en campaign_users
        user_query = """
        SELECT cu.*, c.status as campaign_status, c.name as campaign_name,
               c.start_date, c.end_date, c.budget_total, c.budget_spent
        FROM campaign_users cu
        LEFT JOIN campaigns c ON cu.campaign_id = c.id
        WHERE cu.phone = $1 OR cu.phone = $2
        ORDER BY cu.added_at DESC
        """
        
        rows = await db_manager.execute_query(user_query, phone, clean_phone)
        users = [dict(row) for row in rows] if rows else []
        
        return {
            "original_phone": phone,
            "clean_phone": clean_phone,
            "found_users": len(users),
            "users": users
        }
        
    except Exception as e:
        logger.error(f"Error en debug para {phone}: {e}")
        return {"error": str(e)}