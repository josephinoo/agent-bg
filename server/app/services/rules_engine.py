# app/services/rules_engine.py
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging

from app.database.connection import DatabaseManager
from app.database.repository import UserRepository, ConversationRepository
from app.services.builderbot_service import BuilderBotService
from app.core.utils import calculate_propensity_score, get_ecuadorian_datetime
from app.config import settings

logger = logging.getLogger(__name__)

class RulesEngine:
    """
    Motor de reglas que emula Azure Data Factory
    Evalúa eventos de usuarios y activa el agente cuando corresponde
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.user_repo = UserRepository(db_manager)
        self.conversation_repo = ConversationRepository(db_manager)
        self.builderbot = BuilderBotService()
        self.is_running = False
        
    async def start_monitoring(self, interval_seconds: int = 30):
        """Inicia el monitoreo continuo de eventos"""
        self.is_running = True
        logger.info(f"🔍 Iniciando monitoreo de reglas cada {interval_seconds} segundos")
        
        while self.is_running:
            try:
                await self.process_pending_events()
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logger.error(f"❌ Error en ciclo de monitoreo: {e}")
                await asyncio.sleep(interval_seconds)
    
    async def stop_monitoring(self):
        """Detiene el monitoreo"""
        self.is_running = False
        logger.info("⏹️ Monitoreo de reglas detenido")
    
    async def process_pending_events(self):
        """Procesa eventos pendientes y evalúa reglas"""
        try:
            # 1. Obtener eventos recientes (últimos 5 minutos)
            recent_events = await self._get_recent_events()
            
            if not recent_events:
                logger.debug("No hay eventos recientes para procesar")
                return
            
            logger.info(f"📊 Procesando {len(recent_events)} eventos recientes")
            
            # 2. Agrupar eventos por usuario
            events_by_user = self._group_events_by_user(recent_events)
            
            # 3. Evaluar reglas para cada usuario
            activations = []
            for user_id, user_events in events_by_user.items():
                user_activations = await self._evaluate_user_rules(user_id, user_events)
                activations.extend(user_activations)
            
            # 4. Procesar activaciones
            if activations:
                logger.info(f"🎯 Procesando {len(activations)} activaciones de reglas")
                await self._process_activations(activations)
            
        except Exception as e:
            logger.error(f"❌ Error procesando eventos: {e}")
    
    async def _get_recent_events(self, minutes_ago: int = 5) -> List[Dict[str, Any]]:
        """Obtiene eventos de usuarios de los últimos X minutos"""
        
        query = """
        SELECT ue.*, cu.campaign_id, cu.customer_segment
        FROM user_events ue
        JOIN campaign_users cu ON ue.user_id = cu.user_id
        JOIN campaigns c ON cu.campaign_id = c.id
        WHERE ue.timestamp >= NOW() - INTERVAL '1 minute' * $1
          AND c.status = 'active'
          AND cu.status = 'active'
          AND c.start_date <= NOW()
          AND c.end_date >= NOW()
        ORDER BY ue.timestamp DESC
        """
        
        try:
            rows = await self.db_manager.execute_query(query, minutes_ago)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error obteniendo eventos recientes: {e}")
            return []
    
    def _group_events_by_user(self, events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Agrupa eventos por user_id"""
        grouped = {}
        for event in events:
            user_id = event['user_id']
            if user_id not in grouped:
                grouped[user_id] = []
            grouped[user_id].append(event)
        return grouped
    
    async def _evaluate_user_rules(self, user_id: str, user_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Evalúa todas las reglas activas para un usuario específico"""
        
        if not user_events:
            return []
        
        # Obtener campaña del usuario
        campaign_id = user_events[0]['campaign_id']
        
        # Obtener reglas activas para la campaña
        rules = await self._get_active_rules(campaign_id)
        
        if not rules:
            return []
        
        activations = []
        
        for rule in rules:
            try:
                # Verificar cooldown de la regla
                if not await self._check_rule_cooldown(user_id, rule['id'], rule['cooldown_hours']):
                    continue
                
                # Evaluar condición de la regla (simplificado)
                rule_triggered = await self._evaluate_simple_rule(user_id, rule, user_events)
                
                if rule_triggered:
                    # Calcular score de propensión simple
                    propensity_score = 0.75  # Score fijo para simplicidad
                    
                    # Verificar score mínimo
                    if propensity_score >= rule['min_propensity_score']:
                        # Verificar guardrails básicos
                        guardrails_passed = await self._check_basic_guardrails(user_id, campaign_id)
                        
                        if guardrails_passed:
                            activation = {
                                'rule_id': rule['id'],
                                'rule_name': rule['rule_name'],
                                'user_id': user_id,
                                'campaign_id': campaign_id,
                                'trigger_event': user_events[-1]['event_type'],
                                'propensity_score': propensity_score,
                                'priority': rule['priority']
                            }
                            activations.append(activation)
                            
                            logger.info(f"✅ Regla activada: {rule['rule_name']} para usuario {user_id}")
                        else:
                            logger.info(f"🚫 Regla bloqueada por guardrails")
                    else:
                        logger.info(f"📉 Score bajo para regla {rule['rule_name']}")
                        
            except Exception as e:
                logger.error(f"Error evaluando regla {rule['id']}: {e}")
        
        return activations
    
    async def _get_active_rules(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Obtiene reglas activas para una campaña"""
        
        query = """
        SELECT id, rule_name, rule_type, condition_sql, priority,
               min_propensity_score, cooldown_hours, max_activations_per_day
        FROM activation_rules
        WHERE campaign_id = $1 
          AND is_active = true
        ORDER BY priority ASC
        """
        
        try:
            rows = await self.db_manager.execute_query(query, campaign_id)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error obteniendo reglas activas: {e}")
            return []
    
    async def _check_rule_cooldown(self, user_id: str, rule_id: str, cooldown_hours: int) -> bool:
        """Verifica si la regla está en período de cooldown"""
        
        query = """
        SELECT MAX(timestamp) as last_activation
        FROM rule_activations
        WHERE user_id = $1 AND rule_id = $2
        """
        
        try:
            row = await self.db_manager.execute_single(query, user_id, str(rule_id))
            
            if row and row['last_activation']:
                time_since_last = datetime.now() - row['last_activation']
                hours_passed = time_since_last.total_seconds() / 3600
                return hours_passed >= cooldown_hours
            
            return True  # No hay activaciones previas
            
        except Exception as e:
            logger.error(f"Error verificando cooldown: {e}")
            return False
    
    async def _evaluate_simple_rule(self, user_id: str, rule: Dict[str, Any], 
                                   recent_events: List[Dict[str, Any]]) -> bool:
        """Evalúa reglas de forma simplificada"""
        
        rule_type = rule['rule_type']
        condition_sql = rule['condition_sql']
        
        try:
            # Reglas de intención: verificar evento específico
            if rule_type == 'intent':
                for event in recent_events:
                    if 'credit_application_start' in condition_sql and event['event_type'] == 'credit_application_start':
                        return True
                    elif 'credit_card_application_start' in condition_sql and event['event_type'] == 'credit_card_application_start':
                        return True
                return False
            
            # Reglas de frecuencia: contar eventos
            elif rule_type == 'frequency':
                if 'login' in condition_sql and 'COUNT(*) >= 3' in condition_sql:
                    return await self._count_events_today(user_id, 'login') >= 3
                elif 'account_movements_view' in condition_sql and 'COUNT(*) >= 10' in condition_sql:
                    return await self._count_events_today(user_id, 'account_movements_view') >= 10
                return False
            
            # Reglas de comportamiento: patrones simples
            elif rule_type == 'behavioral':
                if 'transaction' in condition_sql:
                    return await self._check_high_value_transactions(user_id)
                return False
                
            return False
                
        except Exception as e:
            logger.error(f"Error evaluando regla simple {rule['id']}: {e}")
            return False
    
    async def _count_events_today(self, user_id: str, event_type: str) -> int:
        """Cuenta eventos de un tipo específico hoy"""
        
        query = """
        SELECT COUNT(*) as count
        FROM user_events
        WHERE user_id = $1 
          AND event_type = $2 
          AND DATE(timestamp) = CURRENT_DATE
        """
        
        try:
            row = await self.db_manager.execute_single(query, user_id, event_type)
            return row['count'] if row else 0
        except Exception as e:
            logger.error(f"Error contando eventos: {e}")
            return 0
    
    async def _check_high_value_transactions(self, user_id: str) -> bool:
        """Verifica transacciones de alto valor"""
        
        query = """
        SELECT COUNT(*) as count
        FROM user_events
        WHERE user_id = $1 
          AND event_type = 'transaction'
          AND (metadata->>'amount')::numeric > 1000
          AND timestamp >= CURRENT_DATE - INTERVAL '7 days'
        """
        
        try:
            row = await self.db_manager.execute_single(query, user_id)
            return (row['count'] if row else 0) > 0
        except Exception as e:
            logger.error(f"Error verificando transacciones: {e}")
            return False
    
    async def _check_basic_guardrails(self, user_id: str, campaign_id: str) -> bool:
        """Verificación básica de guardrails"""
        try:
            # Verificar último contacto (7 días)
            query = """
            SELECT MAX(timestamp) as last_contact
            FROM rule_activations
            WHERE user_id = $1 AND action_taken = 'whatsapp_sent'
            """
            
            row = await self.db_manager.execute_single(query, user_id)
            
            if row and row['last_contact']:
                days_since = (datetime.now() - row['last_contact']).days
                if days_since < 7:
                    return False
            
            # Verificar contactos hoy (máximo 1)
            query_today = """
            SELECT COUNT(*) as contacts_today
            FROM rule_activations
            WHERE user_id = $1 
              AND action_taken = 'whatsapp_sent'
              AND DATE(timestamp) = CURRENT_DATE
            """
            
            row_today = await self.db_manager.execute_single(query_today, user_id)
            contacts_today = row_today['contacts_today'] if row_today else 0
            
            return contacts_today == 0
            
        except Exception as e:
            logger.error(f"Error verificando guardrails: {e}")
            return False
    
    async def _process_activations(self, activations: List[Dict[str, Any]]):
        """Procesa las activaciones de reglas"""
        
        # Ordenar por prioridad
        activations.sort(key=lambda x: x['priority'])
        
        for activation in activations:
            try:
                await self._trigger_agent(activation)
                await asyncio.sleep(1)  # Espaciar activaciones
            except Exception as e:
                logger.error(f"Error procesando activación: {e}")
    
    async def _trigger_agent(self, activation: Dict[str, Any]):
        """Activa el agente para un usuario específico"""
        
        user_id = activation['user_id']
        campaign_id = activation['campaign_id']
        
        try:
            # Obtener teléfono del usuario
            query = """
            SELECT phone FROM campaign_users 
            WHERE user_id = $1 AND campaign_id = $2
            """
            row = await self.db_manager.execute_single(query, user_id, campaign_id)
            
            if not row:
                logger.error(f"No se encontró teléfono para usuario {user_id}")
                return
            
            phone = row['phone']
            
            # Trigger conversación en BuilderBot
            success = await self.builderbot.trigger_flow(
                phone,
                "AGENT_FLOW",
                {
                    "campaign_id": campaign_id,
                    "trigger_rule": activation['rule_name']
                }
            )
            
            # Registrar activación
            await self._record_activation(activation, success)
            
            if success:
                logger.info(f"🚀 Agente activado para {phone} - Regla: {activation['rule_name']}")
            else:
                logger.error(f"❌ Error activando agente para {phone}")
                
        except Exception as e:
            logger.error(f"Error triggering agente: {e}")
            await self._record_activation(activation, False, str(e))
    
    async def _record_activation(self, activation: Dict[str, Any], success: bool, error: str = None):
        """Registra la activación de una regla"""
        
        query = """
        INSERT INTO rule_activations (
            rule_id, user_id, campaign_id, event_type, propensity_score,
            guardrails_passed, action_taken, block_reason, timestamp
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """
        
        try:
            await self.db_manager.execute_command(
                query,
                activation['rule_id'],
                activation['user_id'],
                activation['campaign_id'],
                activation['trigger_event'],
                activation['propensity_score'],
                success,
                'whatsapp_sent' if success else 'failed',
                error,
                datetime.now()
            )
        except Exception as e:
            logger.error(f"Error registrando activación: {e}")


# ============================================
# SIMULADOR DE EVENTOS (SIMPLIFICADO)
# ============================================

class EventSimulator:
    """Simulador de eventos de usuario para testing"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    async def simulate_user_behavior(self, user_id: str, behavior_type: str = "high_activity"):
        """Simula comportamiento de usuario"""
        
        events_to_create = []
        
        if behavior_type == "high_activity":
            # Simular 3 logins en poco tiempo
            for i in range(3):
                events_to_create.append({
                    'user_id': user_id,
                    'event_type': 'login',
                    'timestamp': datetime.now() - timedelta(minutes=i*2),
                    'session_id': f'sim_session_{i}',
                    'metadata': {'device': 'mobile', 'simulation': True}
                })
        
        elif behavior_type == "credit_interest":
            # Simular interés en crédito
            events_to_create.append({
                'user_id': user_id,
                'event_type': 'credit_application_start',
                'timestamp': datetime.now(),
                'session_id': 'sim_credit_session',
                'page_url': '/credit/apply',
                'metadata': {'product_interest': 'personal_credit', 'simulation': True}
            })
        
        elif behavior_type == "financial_anxiety":
            # Simular múltiples consultas de movimientos
            for i in range(12):
                events_to_create.append({
                    'user_id': user_id,
                    'event_type': 'account_movements_view',
                    'timestamp': datetime.now() - timedelta(minutes=i*5),
                    'session_id': f'sim_movements_{i}',
                    'page_url': '/movements',
                    'metadata': {'filters_applied': ['last_30_days'], 'simulation': True}
                })
        
        # Insertar eventos
        for event in events_to_create:
            await self._insert_event(event)
        
        logger.info(f"✅ Simulados {len(events_to_create)} eventos para usuario {user_id}")
    
    async def _insert_event(self, event_data: Dict[str, Any]):
        """Inserta un evento simulado"""
        
        query = """
        INSERT INTO user_events (
            user_id, event_type, timestamp, session_id, 
            page_url, metadata, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        
        try:
            await self.db_manager.execute_command(
                query,
                event_data['user_id'],
                event_data['event_type'],
                event_data['timestamp'],
                event_data.get('session_id'),
                event_data.get('page_url'),
                json.dumps(event_data.get('metadata', {})),
                datetime.now()
            )
        except Exception as e:
            logger.error(f"Error insertando evento simulado: {e}")
    
    async def create_test_scenario(self, phone: str) -> str:
        """Crea un escenario completo de testing"""
        
        # Buscar usuario por teléfono
        user_repo = UserRepository(self.db_manager)
        user_data = await user_repo.get_user_by_phone(phone)
        
        if not user_data:
            logger.error(f"Usuario con teléfono {phone} no encontrado")
            return "Usuario no encontrado"
        
        user_id = user_data.user_id
        
        # Simular diferentes comportamientos
        await self.simulate_user_behavior(user_id, "high_activity")
        await asyncio.sleep(2)
        await self.simulate_user_behavior(user_id, "credit_interest")
        
        return f"Escenario creado para usuario {user_id}"


# ============================================
# EJECUCIÓN PRINCIPAL
# ============================================

async def main():
    """Función principal para ejecutar el motor de reglas"""
    from app.database.connection import DatabaseManager
    
    try:
        # Inicializar conexión a base de datos
        db_manager = DatabaseManager()
        await db_manager.connect()
        
        logger.info("🚀 Iniciando motor de reglas...")
        
        # Crear instancia del motor de reglas
        rules_engine = RulesEngine(db_manager)
        
        # Crear simulador para testing
        simulator = EventSimulator(db_manager)
        
        # Simular algunos eventos de prueba
        logger.info("📊 Creando escenario de prueba...")
        test_result = await simulator.create_test_scenario("+593991234567")
        logger.info(f"✅ {test_result}")
        
        # Iniciar monitoreo
        logger.info("🔍 Iniciando monitoreo de reglas...")
        await rules_engine.start_monitoring(interval_seconds=30)
        
    except KeyboardInterrupt:
        logger.info("⏹️ Deteniendo motor de reglas...")
        if 'rules_engine' in locals():
            await rules_engine.stop_monitoring()
    except Exception as e:
        logger.error(f"❌ Error en ejecución principal: {e}")
    finally:
        if 'db_manager' in locals():
            await db_manager.close()
        logger.info("🏁 Motor de reglas detenido")

if __name__ == "__main__":
    import asyncio
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Ejecutar motor de reglas
    asyncio.run(main())
    


