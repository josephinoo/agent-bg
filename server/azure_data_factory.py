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

class AzureDataFactory:
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
        self._cycle_count = 0
        
    async def verify_database_setup(self) -> bool:
        """Verifica que la base de datos tenga los datos necesarios"""
        try:
            # Verificar campaña activa
            campaigns_query = "SELECT COUNT(*) as count FROM campaigns WHERE status = 'active'"
            campaigns_result = await self.db_manager.execute_single(campaigns_query)
            campaigns_count = campaigns_result['count'] if campaigns_result else 0
            
            # Verificar usuarios de campaña
            users_query = "SELECT COUNT(*) as count FROM campaign_users WHERE status = 'active'"
            users_result = await self.db_manager.execute_single(users_query)
            users_count = users_result['count'] if users_result else 0
            
            # Verificar reglas activas
            rules_query = "SELECT COUNT(*) as count FROM activation_rules WHERE is_active = true"
            rules_result = await self.db_manager.execute_single(rules_query)
            rules_count = rules_result['count'] if rules_result else 0
            
            logger.info(f"📊 Estado de BD: {campaigns_count} campañas, {users_count} usuarios, {rules_count} reglas")
            
            if campaigns_count == 0:
                logger.warning("⚠️ No hay campañas activas")
                return False
            
            if users_count == 0:
                logger.warning("⚠️ No hay usuarios en campañas")
                return False
                
            if rules_count == 0:
                logger.warning("⚠️ No hay reglas de activación")
                return False
            
            logger.info("✅ Base de datos configurada correctamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error verificando BD: {e}")
            return False
    
    async def start_monitoring(self, interval_seconds: int = 3):
        """Inicia el monitoreo continuo de eventos"""
        
        # Verificar setup de BD antes de iniciar
        if not await self.verify_database_setup():
            logger.error("❌ Base de datos no está configurada. Ejecuta los scripts SQL de prueba primero.")
            return
        
        self.is_running = True
        self._cycle_count = 0
        logger.info(f"🔍 Iniciando monitoreo de reglas cada {interval_seconds} segundos")
        
        try:
            while self.is_running:
                self._cycle_count += 1
                logger.info(f"🔄 Ejecutando ciclo #{self._cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                try:
                    await self.process_pending_events()
                except Exception as e:
                    logger.error(f"❌ Error en proceso de eventos (ciclo #{self._cycle_count}): {e}")
                
                # SIEMPRE esperar el intervalo, sin importar si hay errores
                logger.debug(f"⏱️ Esperando {interval_seconds} segundos...")
                await asyncio.sleep(interval_seconds)
                
        except asyncio.CancelledError:
            logger.info("🛑 Monitoreo cancelado")
        except Exception as e:
            logger.error(f"❌ Error crítico en start_monitoring: {e}")
        finally:
            self.is_running = False
            logger.info(f"⏹️ Monitoreo finalizado después de {self._cycle_count} ciclos")
    
    async def stop_monitoring(self):
        """Detiene el monitoreo"""
        logger.info("🛑 Solicitando detención del monitoreo...")
        self.is_running = False
    
    async def process_pending_events(self):
        """Procesa eventos pendientes y evalúa reglas"""
        # 1. Obtener eventos recientes
        recent_events = await self._get_recent_events()
        
        if not recent_events:
            logger.debug(f"📭 Sin eventos recientes (ciclo #{self._cycle_count})")
            return
        
        logger.info(f"📊 Procesando {len(recent_events)} eventos recientes")
        
        # 2. Agrupar eventos por usuario
        events_by_user = self._group_events_by_user(recent_events)
        logger.info(f"👥 Eventos de {len(events_by_user)} usuarios distintos")
        
        # 3. Evaluar reglas para cada usuario
        all_activations = []
        for user_id, user_events in events_by_user.items():
            try:
                activations = await self._evaluate_user_rules(user_id, user_events)
                all_activations.extend(activations)
            except Exception as e:
                logger.error(f"Error evaluando usuario {user_id}: {e}")
        
        # 4. Procesar activaciones
        if all_activations:
            logger.info(f"🎯 Procesando {len(all_activations)} activaciones")
            await self._process_activations(all_activations)
        else:
            logger.debug("🚫 No se generaron activaciones")

    async def _get_recent_events(self, minutes_ago: int = 2) -> List[Dict[str, Any]]:
        """Obtiene eventos de usuarios de los últimos X minutos"""
        
        query = """
        SELECT ue.*, cu.campaign_id, cu.customer_segment, cu.phone
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
            result = [dict(row) for row in rows]
            
            if result:
                logger.debug(f"🔍 Encontrados {len(result)} eventos recientes:")
                for event in result[:3]:  # Solo mostrar primeros 3
                    logger.debug(f"  - {event['event_type']} | {event['user_id']} | {event['timestamp']}")
            
            return result
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
        
        campaign_id = user_events[0]['campaign_id']
        phone = user_events[0]['phone']
        
        # Obtener reglas activas
        rules = await self._get_active_rules(campaign_id)
        
        if not rules:
            logger.debug(f"📋 Sin reglas activas para campaña {campaign_id}")
            return []
        
        logger.debug(f"📋 Evaluando {len(rules)} reglas para usuario {user_id}")
        activations = []
        
        for rule in rules:
            try:
                # Verificar cooldown
                if not await self._check_rule_cooldown(user_id, rule['id'], rule.get('cooldown_hours', 24)):
                    logger.debug(f"⏰ Regla {rule['rule_name']} en cooldown")
                    continue
                
                # Evaluar regla
                rule_triggered = await self._evaluate_simple_rule(user_id, rule, user_events)
                
                if rule_triggered:
                    propensity_score = 0.85  # Score alto para testing
                    
                    if propensity_score >= rule.get('min_propensity_score', 0.5):
                        # Verificar guardrails
                        if await self._check_basic_guardrails(user_id, campaign_id):
                            activation = {
                                'rule_id': rule['id'],
                                'rule_name': rule['rule_name'],
                                'user_id': user_id,
                                'campaign_id': campaign_id,
                                'phone': phone,
                                'trigger_event': user_events[-1]['event_type'],
                                'propensity_score': propensity_score,
                                'priority': rule.get('priority', 5)
                            }
                            activations.append(activation)
                            logger.info(f"✅ REGLA ACTIVADA: {rule['rule_name']} para {phone}")
                        else:
                            logger.info(f"🚫 Regla bloqueada por guardrails: {rule['rule_name']}")
                    else:
                        logger.debug(f"📉 Score insuficiente: {propensity_score}")
                        
            except Exception as e:
                logger.error(f"Error evaluando regla {rule.get('id', 'unknown')}: {e}")
        
        return activations
    
    async def _get_active_rules(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Obtiene reglas activas para una campaña"""
        
        query = """
        SELECT id, rule_name, rule_type, condition_sql, priority,
               min_propensity_score, cooldown_hours
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
        """Verifica cooldown de regla"""
        
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
            
            return True
            
        except Exception as e:
            logger.error(f"Error verificando cooldown: {e}")
            return True  # En caso de error, permitir
    
    async def _evaluate_simple_rule(self, user_id: str, rule: Dict[str, Any], 
                                   recent_events: List[Dict[str, Any]]) -> bool:
        """Evalúa reglas de forma simplificada"""
        
        rule_type = rule.get('rule_type', '')
        condition_sql = rule.get('condition_sql', '')
        
        try:
            # Reglas de intención
            if rule_type == 'intent':
                for event in recent_events:
                    if 'credit_application_start' in condition_sql and event['event_type'] == 'credit_application_start':
                        logger.debug(f"✅ Intent rule triggered: credit_application_start")
                        return True
                    elif 'credit_card_application_start' in condition_sql and event['event_type'] == 'credit_card_application_start':
                        logger.debug(f"✅ Intent rule triggered: credit_card_application_start")
                        return True
            
            # Reglas de frecuencia
            elif rule_type == 'frequency':
                if 'login' in condition_sql and 'COUNT(*) >= 3' in condition_sql:
                    count = await self._count_events_today(user_id, 'login')
                    logger.debug(f"Login count today: {count}")
                    return count >= 3
                elif 'account_movements_view' in condition_sql and 'COUNT(*) >= 10' in condition_sql:
                    count = await self._count_events_today(user_id, 'account_movements_view')
                    logger.debug(f"Movements view count today: {count}")
                    return count >= 10
            
            # Reglas de comportamiento
            elif rule_type == 'behavioral':
                if 'transaction' in condition_sql:
                    result = await self._check_high_value_transactions(user_id)
                    logger.debug(f"High value transactions: {result}")
                    return result
                    
            return False
                
        except Exception as e:
            logger.error(f"Error evaluando regla {rule.get('id')}: {e}")
            return False
    
    async def _count_events_today(self, user_id: str, event_type: str) -> int:
        """Cuenta eventos de hoy"""
        
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
            # Verificar contactos en las últimas 4 horas (más permisivo para testing)
            query = """
            SELECT COUNT(*) as recent_contacts
            FROM rule_activations
            WHERE user_id = $1 
              AND action_taken = 'whatsapp_sent'
              AND timestamp >= NOW() - INTERVAL '4 hours'
            """
            
            row = await self.db_manager.execute_single(query, user_id)
            recent_contacts = row['recent_contacts'] if row else 0
            
            if recent_contacts > 0:
                logger.debug(f"🚫 Guardrail: {recent_contacts} contactos recientes")
                return False
            
            # Verificar contactos hoy (máximo 2 para testing)
            query_today = """
            SELECT COUNT(*) as contacts_today
            FROM rule_activations
            WHERE user_id = $1 
              AND action_taken = 'whatsapp_sent'
              AND DATE(timestamp) = CURRENT_DATE
            """
            
            row_today = await self.db_manager.execute_single(query_today, user_id)
            contacts_today = row_today['contacts_today'] if row_today else 0
            
            if contacts_today >= 2:
                logger.debug(f"🚫 Guardrail: ya se enviaron {contacts_today} mensajes hoy")
                return False
            
            logger.debug(f"✅ Guardrails OK: {contacts_today} contactos hoy")
            return True
            
        except Exception as e:
            logger.error(f"Error verificando guardrails: {e}")
            return False
    
    async def _process_activations(self, activations: List[Dict[str, Any]]):
        """Procesa las activaciones de reglas"""
        
        # Ordenar por prioridad
        activations.sort(key=lambda x: x.get('priority', 5))
        
        for activation in activations:
            try:
                success = await self._trigger_agent(activation)
                await self._record_activation(activation, success)
                
                if success:
                    logger.info(f"🚀 MENSAJE ENVIADO a {activation['phone']} - Regla: {activation['rule_name']}")
                else:
                    logger.error(f"❌ FALLO AL ENVIAR a {activation['phone']}")
                
                # Esperar entre envíos
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error procesando activación: {e}")
                await self._record_activation(activation, False, str(e))
    
    async def _trigger_agent(self, activation: Dict[str, Any]) -> bool:
        """Activa el agente enviando mensaje por WhatsApp"""
        
        phone = activation['phone']
        
        try:
            # Enviar mensaje por BuilderBot
            success = await self.builderbot.trigger_flow(
                phone,
                "AGENT_FLOW",
                {
                    "campaign_id": activation['campaign_id'],
                    "trigger_rule": activation['rule_name'],
                    "propensity_score": activation['propensity_score']
                }
            )
            
            if success:
                logger.info(f"✅ BuilderBot activado exitosamente para {phone}")
            else:
                logger.error(f"❌ BuilderBot falló para {phone}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error triggering BuilderBot para {phone}: {e}")
            return False
    
    async def _record_activation(self, activation: Dict[str, Any], success: bool, error: str = None):
        """Registra la activación de una regla"""
        
        # Primero verificar si la tabla existe, si no, crearla
        create_table_query = """
        CREATE TABLE IF NOT EXISTS rule_activations (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            rule_id uuid NOT NULL,
            user_id character varying NOT NULL,
            campaign_id uuid NOT NULL,
            event_type character varying,
            propensity_score numeric,
            guardrails_passed boolean DEFAULT false,
            action_taken character varying,
            block_reason text,
            timestamp timestamp with time zone DEFAULT now(),
            created_at timestamp with time zone DEFAULT now(),
            CONSTRAINT rule_activations_pkey PRIMARY KEY (id)
        )
        """
        
        insert_query = """
        INSERT INTO rule_activations (
            rule_id, user_id, campaign_id, event_type, propensity_score,
            guardrails_passed, action_taken, block_reason, timestamp
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """
        
        try:
            # Crear tabla si no existe
            await self.db_manager.execute_command(create_table_query)
            
            # Insertar registro
            await self.db_manager.execute_command(
                insert_query,
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
            logger.debug(f"📝 Activación registrada en BD")
        except Exception as e:
            logger.error(f"Error registrando activación: {e}")
            # No re-raise para que el sistema continúe


# ============================================
# SIMULADOR DE EVENTOS MEJORADO
# ============================================

class EventSimulator:
    """Simulador de eventos de usuario para testing"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    async def simulate_user_behavior(self, user_id: str, behavior_type: str = "high_activity"):
        """Simula comportamiento de usuario"""
        
        events_to_create = []
        current_time = datetime.now()
        
        if behavior_type == "high_activity":
            # Simular múltiples logins recientes
            for i in range(4):
                events_to_create.append({
                    'user_id': user_id,
                    'event_type': 'login',
                    'timestamp': current_time - timedelta(minutes=i*3),
                    'session_id': f'sim_session_{i}_{current_time.timestamp()}',
                    'metadata': {'device': 'mobile', 'simulation': True, 'ip': '192.168.1.1'}
                })
        
        elif behavior_type == "credit_interest":
            events_to_create.append({
                'user_id': user_id,
                'event_type': 'credit_application_start',
                'timestamp': current_time,
                'session_id': f'sim_credit_{current_time.timestamp()}',
                'page_url': '/credit/apply',
                'metadata': {'product_interest': 'personal_credit', 'simulation': True}
            })
        
        elif behavior_type == "financial_anxiety":
            # Múltiples consultas de movimientos
            for i in range(12):
                events_to_create.append({
                    'user_id': user_id,
                    'event_type': 'account_movements_view',
                    'timestamp': current_time - timedelta(minutes=i*2),
                    'session_id': f'sim_movements_{i}_{current_time.timestamp()}',
                    'page_url': '/movements',
                    'metadata': {'filters_applied': ['last_3_days'], 'simulation': True}
                })
        
        # Insertar eventos
        for event in events_to_create:
            await self._insert_event(event)
        
        logger.info(f"✅ Simulados {len(events_to_create)} eventos '{behavior_type}' para usuario {user_id}")
    
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
        
        user_repo = UserRepository(self.db_manager)
        user_data = await user_repo.get_user_by_phone(phone)
        
        if not user_data:
            logger.error(f"Usuario con teléfono {phone} no encontrado")
            return "Usuario no encontrado"
        
        user_id = user_data.user_id
        
        # Simular diferentes comportamientos
        logger.info(f"🎭 Creando escenario de testing para {phone}")
        
        await self.simulate_user_behavior(user_id, "high_activity")
        await asyncio.sleep(1)
        await self.simulate_user_behavior(user_id, "credit_interest")
        await asyncio.sleep(1)
        await self.simulate_user_behavior(user_id, "financial_anxiety")
        
        return f"Escenario completo creado para usuario {user_id}"


# ============================================
# EJECUCIÓN PRINCIPAL
# ============================================

async def main():
    """Función principal mejorada"""
    from app.database.connection import DatabaseManager
    
    db_manager = None
    rules_engine = None
    
    try:
        # Inicializar BD
        db_manager = DatabaseManager()
        await db_manager.connect()
        logger.info("🔌 Conexión a BD establecida")
        
        # Crear motor de reglas
        rules_engine = AzureDataFactory(db_manager)
        
        # Crear simulador
        simulator = EventSimulator(db_manager)
        
        # Simular eventos de prueba
        logger.info("🎭 Creando escenario de prueba...")
        test_result = await simulator.create_test_scenario("+593997814126")
        logger.info(f"✅ {test_result}")
        
        # Dar tiempo para que se inserten los eventos
        await asyncio.sleep(2)
        
        # Iniciar monitoreo continuo
        logger.info("🚀 INICIANDO MOTOR DE REGLAS...")
        await rules_engine.start_monitoring(interval_seconds=5)
        
    except KeyboardInterrupt:
        logger.info("\n⏹️ CTRL+C detectado - Deteniendo motor...")
    except Exception as e:
        logger.error(f"❌ Error crítico: {e}")
    finally:
        # Cleanup
        if rules_engine:
            await rules_engine.stop_monitoring()
        if db_manager:
            await db_manager.close()
        logger.info("🏁 Motor de reglas completamente detenido")

if __name__ == "__main__":
    # Configurar logging más detallado
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('rules_engine.log')
        ]
    )
    
    # Ejecutar
    asyncio.run(main())