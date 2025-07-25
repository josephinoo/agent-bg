# app/database/repository.py
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from decimal import Decimal
import logging

from app.database.connection import DatabaseManager
from app.models.schemas import UserData, ConversationState, ConversationLog

logger = logging.getLogger(__name__)

class UserRepository:
    """Repositorio para operaciones de usuarios"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def _clean_phone(self, phone: str) -> str:
        """Limpia el formato del teléfono"""
        clean = re.sub(r'[^\d+]', '', phone)
        
        if not clean.startswith('+'):
            if clean.startswith('593'):
                clean = '+' + clean
            elif clean.startswith('09') or clean.startswith('9'):
                clean = '+593' + clean.lstrip('0')
            else:
                clean = '+593' + clean
        
        return clean
    
    async def get_user_by_phone(self, phone: str) -> Optional[UserData]:
        """Obtiene usuario por teléfono desde campaign_users"""
        clean_phone = self._clean_phone(phone)
        print("clean_phone", clean_phone)
        query = """
        SELECT cu.*, c.id as campaign_id, c.product_type, c.name as campaign_name,
               c.budget_total, c.budget_spent
        FROM campaign_users cu
        JOIN campaigns c ON cu.campaign_id = c.id
        WHERE (cu.phone = $1 OR cu.phone = $2) 
          AND c.status = 'active' 

          AND c.start_date <= NOW()
          AND c.end_date >= NOW()
          AND c.budget_spent < c.budget_total
        ORDER BY c.created_at DESC
        LIMIT 1
        """


        
        try:
        
            row = await self.db.execute_single(query, phone, clean_phone)
    
   
            if not row:
                return None
            current_products = []
            if row['current_products']:
                try:
                    current_products = json.loads(row['current_products'])
                except (json.JSONDecodeError, TypeError):
                    # If parsing fails, default to empty list
                    current_products = []
            
            return UserData(
                user_id=row['user_id'],
                campaign_id=str(row['campaign_id']),
                product_type=row['product_type'],
                first_name=row['first_name'] or '',
                last_name=row['last_name'] or '',
                phone=row['phone'],
                customer_segment=row['customer_segment'] or 'standard',
                current_products=current_products,
                credit_score=row['credit_score'],
                monthly_income=row['monthly_income']
            )
        except Exception as e:
            logger.error(f"Error obteniendo usuario por teléfono {phone}: {e}")
            return None
    
    async def check_user_in_campaign(self, phone: str) -> bool:
        """Verifica si un usuario está en alguna campaña activa"""
        user = await self.get_user_by_phone(phone)
        return user is not None
    
    async def update_user_status(self, user_id: str, campaign_id: str, status: str):
        """Actualiza el estado del usuario en la campaña"""
        query = """
        UPDATE campaign_users 
        SET status = $3
        WHERE user_id = $1 AND campaign_id = $2
        """
        
        try:
            await self.db.execute_command(query, user_id, campaign_id, status)
            logger.info(f"Estado actualizado para usuario {user_id}: {status}")
        except Exception as e:
            logger.error(f"Error actualizando estado de usuario: {e}")
            raise

class ConversationRepository:
    """Repositorio para operaciones de conversaciones de campañas"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def get_campaign_conversation_history(self, session_id: str) -> List[Dict]:
        """Obtiene historial de conversación de campaña específica"""
        query = """
        SELECT cm.*, cl.campaign_id, cl.product_type
        FROM conversation_messages cm
        JOIN conversation_logs cl ON cm.session_id = cl.session_id
        WHERE cm.session_id = $1
        ORDER BY cm.timestamp ASC
        """
        
        try:
            rows = await self.db.execute_query(query, session_id)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error obteniendo historial de campaña {session_id}: {e}")
            return []
    
    async def get_builderbot_history(self, phone: str, limit: int = 10) -> List[Dict]:
        """Obtiene historial de BuilderBot para contexto"""
        clean_phone = self._clean_phone(phone)
        
        query = """
        SELECT h.answer, h.created_at, h.keyword, h.options, h.phone,
               c.values as contact_values
        FROM history h
        LEFT JOIN contact c ON h.contact_id = c.id
        WHERE (h.phone = $1 OR h.phone = $2)
        ORDER BY h.created_at DESC
        LIMIT $3
        """
        
        try:
            rows = await self.db.execute_query(query, phone, clean_phone, limit)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error obteniendo historial BuilderBot para {phone}: {e}")
            return []
    
    async def get_unified_history(self, phone: str, limit: int = 20) -> List[Dict]:
        """Obtiene historial unificado (BuilderBot + Campañas) usando la vista"""
        clean_phone = self._clean_phone(phone)
        
        query = """
        SELECT * FROM unified_conversation_history
        WHERE phone = $1 OR phone = $2
        ORDER BY timestamp DESC
        LIMIT $3
        """
        
        try:
            rows = await self.db.execute_query(query, phone, clean_phone, limit)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error obteniendo historial unificado para {phone}: {e}")
            return []
    
    async def save_conversation_log(self, state: ConversationState) -> str:
        """Guarda o actualiza log de conversación de campaña"""
        query = """
        INSERT INTO conversation_logs (
            session_id, user_id, campaign_id, status, current_step,
            product_type, phone_number, intent_confirmed, collected_data,
            total_messages, started_at, last_activity_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        ON CONFLICT (session_id) 
        DO UPDATE SET 
            current_step = EXCLUDED.current_step,
            intent_confirmed = EXCLUDED.intent_confirmed,
            collected_data = EXCLUDED.collected_data,
            total_messages = EXCLUDED.total_messages,
            last_activity_at = EXCLUDED.last_activity_at,
            status = CASE 
                WHEN EXCLUDED.current_step = 'completed' THEN 'completed'
                ELSE conversation_logs.status
            END
        RETURNING id
        """
        
        try:
            row = await self.db.execute_single(
                query,
                state["session_id"],
                state["user_id"], 
                state["campaign_id"],
                "active" if state["current_step"] != "completed" else "completed",
                state["current_step"],
                state["product_type"],
                state["phone"],
                state["intent_confirmed"],
                json.dumps(state["collected_data"]),
                len(state["messages"]),
                datetime.now(),
                datetime.now()
            )
            return str(row["id"])
        except Exception as e:
            logger.error(f"Error guardando log de conversación: {e}")
            raise
    
    async def save_message(self, session_id: str, sender: str, message: str, 
                          intent: Optional[str] = None, confidence: Optional[float] = None,
                          agent_step: Optional[str] = None, metadata: Optional[Dict] = None) -> str:
        """Guarda mensaje individual de campaña"""
        query = """
        INSERT INTO conversation_messages (
            session_id, sender, message_text, intent_detected, 
            confidence_score, agent_step, timestamp, metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """
        
        try:
            row = await self.db.execute_single(
                query,
                session_id, sender, message, intent, 
                confidence, agent_step, datetime.now(),
                json.dumps(metadata or {})
            )
            return str(row["id"])
        except Exception as e:
            logger.error(f"Error guardando mensaje: {e}")
            raise
    
    async def get_current_step(self, session_id: str) -> str:
        """Obtiene el paso actual de la conversación"""
        query = """
        SELECT current_step FROM conversation_logs WHERE session_id = $1
        """
        row = await self.db.execute_single(query, session_id)
        return row["current_step"] if row else "greeting"
    
    async def get_session_id(self, phone: str) -> str:
        """Obtiene el ID de la sesión"""
        query = """
        SELECT session_id FROM conversation_logs WHERE phone_number = $1
        """
        row = await self.db.execute_single(query, phone)
        return row["session_id"] if row else None
    


    
    async def create_builderbot_mapping(self, phone: str, campaign_user_id: str, 
                                      session_id: str) -> str:
        """Crea mapeo entre BuilderBot y sistema de campañas"""
        clean_phone = self._clean_phone(phone)
        
        # Buscar contact_id de BuilderBot
        contact_query = """
        SELECT id FROM contact WHERE phone = $1 OR phone = $2 LIMIT 1
        """
        contact_row = await self.db.execute_single(contact_query, phone, clean_phone)
        
        # Crear mapeo
        mapping_query = """
        INSERT INTO builderbot_campaign_mapping (
            phone, builderbot_contact_id, campaign_user_id, session_id
        ) VALUES ($1, $2, $3, $4)
        RETURNING id
        """
        
        try:
            row = await self.db.execute_single(
                mapping_query,
                clean_phone,
                contact_row['id'] if contact_row else None,
                campaign_user_id,
                session_id
            )
            return str(row["id"])
        except Exception as e:
            logger.error(f"Error creando mapeo BuilderBot-Campaign: {e}")
            raise
    
    def _clean_phone(self, phone: str) -> str:
        """Limpia el formato del teléfono"""
        clean = re.sub(r'[^\d+]', '', phone)
        
        if not clean.startswith('+'):
            if clean.startswith('593'):
                clean = '+' + clean
            elif clean.startswith('09') or clean.startswith('9'):
                clean = '+593' + clean.lstrip('0')
            else:
                clean = '+593' + clean
        
        return clean
    
    async def get_collected_data(self, session_id: str) -> Dict[str, Any]:
        """Obtiene los datos recopilados de una sesión"""
        query = """
        SELECT collected_data FROM conversation_logs WHERE session_id = $1
        """
        row = await self.db.execute_single(query, session_id)
        return row["collected_data"] if row else {}

class LeadRepository:
    """Repositorio para operaciones de leads"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def save_lead(self, state: ConversationState) -> str:
        """Guarda un nuevo lead"""
        collected = state["collected_data"]
        
        query = """
        INSERT INTO leads (
            user_id, campaign_id, session_id, first_name, last_name, 
            email, phone, product_type, monthly_income, employment_type, 
            requested_amount, channel, propensity_score, status, priority,
            marketing_consent, data_processing_consent, whatsapp_consent
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
        RETURNING id
        """
        
        try:
            row = await self.db.execute_single(
                query,
                state["user_id"], state["campaign_id"], state["session_id"],
                collected.get("first_name", state["user_name"]), 
                collected.get("last_name", ""),
                collected.get("email", ""), state["phone"], 
                state["product_type"], 
                collected.get("monthly_income"), 
                collected.get("employment_type"),
                collected.get("requested_amount"), 
                "whatsapp", state["propensity_score"], 
                "qualified" if state["intent_confirmed"] else "new",
                "high" if state["propensity_score"] > 0.7 else "medium",
                True, True, True  # Consentimientos
            )
            return str(row["id"])
        except Exception as e:
            logger.error(f"Error guardando lead: {e}")
            raise
    
    async def get_leads_by_campaign(self, campaign_id: str, limit: int = 100) -> List[Dict]:
        """Obtiene leads por campaña"""
        query = """
        SELECT * FROM leads 
        WHERE campaign_id = $1 
        ORDER BY created_at DESC 
        LIMIT $2
        """
        
        try:
            rows = await self.db.execute_query(query, campaign_id, limit)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error obteniendo leads de campaña {campaign_id}: {e}")
            return []
    
    async def update_lead_status(self, lead_id: str, status: str):
        """Actualiza el estado de un lead"""
        query = """
        UPDATE leads 
        SET status = $2, updated_at = NOW()
        WHERE id = $1
        """
        
        try:
            await self.db.execute_command(query, lead_id, status)
            logger.info(f"Lead {lead_id} actualizado a estado: {status}")
        except Exception as e:
            logger.error(f"Error actualizando lead {lead_id}: {e}")
            raise

class CampaignRepository:
    """Repositorio para operaciones de campañas"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def get_campaign_stats(self, campaign_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de una campaña"""
        query = """
        SELECT 
            c.id, c.name, c.product_type, c.budget_total, c.budget_spent,
            c.budget_total - c.budget_spent as budget_remaining,
            COUNT(cu.id) as total_users,
            COUNT(CASE WHEN cu.status = 'active' THEN 1 END) as active_users,
            COUNT(CASE WHEN cu.status = 'contacted' THEN 1 END) as contacted_users,
            COUNT(l.id) as total_leads,
            COUNT(CASE WHEN l.status = 'converted' THEN 1 END) as converted_leads,
            COALESCE(AVG(l.propensity_score), 0) as avg_propensity_score
        FROM campaigns c
        LEFT JOIN campaign_users cu ON c.id = cu.campaign_id
        LEFT JOIN leads l ON c.id = l.campaign_id
        WHERE c.id = $1
        GROUP BY c.id, c.name, c.product_type, c.budget_total, c.budget_spent
        """
        
        try:
            row = await self.db.execute_single(query, campaign_id)
            if not row:
                return {}
            
            stats = dict(row)
            
            # Calcular conversion rate
            contacted = stats.get('contacted_users', 0)
            converted = stats.get('converted_leads', 0)
            stats['conversion_rate'] = (converted / contacted * 100) if contacted > 0 else 0
            
            return stats
        except Exception as e:
            logger.error(f"Error obteniendo stats de campaña {campaign_id}: {e}")
            return {}
    
    
# Agregar este método completo a la clase CampaignRepository en app/database/repository.py

    async def get_active_campaigns(self) -> List[Dict]:
        """Obtiene todas las campañas activas"""
        query = """
        SELECT id, name, product_type, status, budget_total, budget_spent,
            start_date, end_date, created_at
        FROM campaigns
        WHERE status = 'active' 
        AND start_date <= NOW() 
        AND end_date >= NOW()
        AND budget_spent < budget_total
        ORDER BY created_at DESC
        """
        
        try:
            rows = await self.db.execute_query(query)
            return [dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Error obteniendo campañas activas: {e}")
            return []  # Retornar lista vacía en lugar de None
    
    
    