# conversation_agent.py
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional
import logging

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from app.models.schemas import ConversationState
from app.core.prompts import PromptBuilder, ConversationFlowManager
from app.config import settings

logger = logging.getLogger(__name__)

class ConversationAgent:
    def __init__(self, conversation_repo, lead_repo=None, user_repo=None):
        self.conversation_repo = conversation_repo
        self.lead_repo = lead_repo
        self.user_repo = user_repo
        self.prompt_builder = PromptBuilder()
        self.flow_manager = ConversationFlowManager(self.prompt_builder)
        
        # Configurar LLM con mejores parámetros
        self.llm = ChatOpenAI(
            openai_api_key=settings.openai_api_key,
            model=settings.openai_model,
            temperature=0.3,  # Más determinístico para conversaciones bancarias
            max_tokens=200,   # Respuestas más concisas
            timeout=30,       # Timeout para evitar bloqueos
        )
        
        # Crear workflow mejorado
        workflow = StateGraph(ConversationState)
        workflow.add_node("analyze_message", self.analyze_message)
        workflow.add_node("generate_response", self.generate_response)
        workflow.add_node("save_conversation", self.save_conversation)
        
        workflow.set_entry_point("analyze_message")
        workflow.add_edge("analyze_message", "generate_response")
        workflow.add_edge("generate_response", "save_conversation")
        workflow.add_edge("save_conversation", END)
        
        self.graph = workflow.compile()
    
    async def analyze_message(self, state: ConversationState) -> ConversationState:
        """Analiza el mensaje del usuario usando el PromptBuilder mejorado"""

        try:
            # Asegurar que existe el conversation log
            await self.conversation_repo.save_conversation_log(state)
            
            user_message = state["messages"][-1]["content"]
            current_step = state.get("current_step", "greeting")
            product_type = state.get("product_type", "credit_card")
            customer_segment = state.get("customer_segment", "standard")
            
            logger.info(f"Analizando mensaje: '{user_message}' en paso: {current_step}")
            
            # Analizar intención usando el nuevo PromptBuilder
            intent = self.prompt_builder.analyze_intent(
            message=state.get("messages")[-1]["content"],
            current_step=state.get("current_step"),
            product_type=state.get("product_type"),
            customer_segment=state.get("customer_segment"),
            user_name=state.get("user_name")
        )
            
            # Mapear intención a intent_confirmed para compatibilidad
            if intent == "positive":
                state["intent_confirmed"] = True
            elif intent == "negative":
                state["intent_confirmed"] = False
            else:
                state["intent_confirmed"] = None
            
            state["detected_intent"] = intent
            
            # Extraer datos según el paso actual
            collected_data = state.get("collected_data", {})
            
            if current_step == "collect_income":
                income = self.prompt_builder.extract_data(user_message, "income")
                if income:
                    collected_data["monthly_income"] = income
                    logger.info(f"Ingreso extraído: {income}")
            
            elif current_step == "collect_employment":
                employment = self.prompt_builder.extract_data(user_message, "employment")
                if employment:
                    collected_data["employment_type"] = employment
                    logger.info(f"Empleo extraído: {employment}")
            
            elif current_step == "collect_amount":
                amount = self.prompt_builder.extract_data(user_message, "amount")
                if amount:
                    collected_data["requested_amount"] = amount
                    logger.info(f"Monto extraído: {amount}")
            
            # Fallback: extracción básica con regex (para compatibilidad)
            if not collected_data.get("monthly_income") and current_step in ["collect_income", "collect_budget"]:
                numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d{2})?', user_message.replace(',', ''))
                if numbers:
                    try:
                        amount = float(numbers[0])
                        if current_step == "collect_budget":
                            collected_data["budget"] = amount
                        else:
                            collected_data["monthly_income"] = amount
                        logger.info(f"Número extraído con regex: {amount}")
                    except ValueError:
                        pass
            
            state["collected_data"] = collected_data
            
            # Guardar mensaje del usuario
            await self.conversation_repo.save_message(
                state["session_id"], "user", user_message, current_step
            )
            
        except Exception as e:
            logger.error(f"Error en analyze_message: {e}")
            # En caso de error, mantener estado actual
            state["detected_intent"] = "unclear"
        
        return state
    
    
    async def generate_response(self, state: ConversationState) -> ConversationState:
        """Genera respuesta usando el PromptBuilder mejorado"""
        try:

            current_step = state.get("current_step", "greeting")
            intent = state.get("detected_intent", "unclear")
            collected_data = state.get("collected_data", {})
            user_name = state.get("user_name", "Cliente")
            product_type = state.get("product_type", "credit_card")
            customer_segment = state.get("customer_segment", "standard")
            needs_retry = state.get("needs_retry", False)
            
            logger.info(f"Generando respuesta para paso: {current_step}, intención: {intent}")
            
            next_step = self.flow_manager.get_next_step(current_step, intent, collected_data)
            
            # Generar respuesta apropiada
            if intent == "negative" and current_step != "greeting":
                response = self._generate_negative_response(user_name)
                next_step = "close_negative"
            
            elif current_step == "present_offer" and intent == "positive":
                next_step = "close_positive"
                response = await self._generate_llm_response(
                    step="close_positive",
                    user_name=user_name,
                    product_type=product_type,
                    customer_segment=customer_segment,
                    collected_data=collected_data
                )
            
            elif next_step == "present_offer":
                # Usar el ProductPromptBuilder para generar oferta
                offer_details = self.prompt_builder.build_product_offer(
                    product_type=product_type,
                    collected_data=collected_data,
                    customer_segment=customer_segment,
                    user_name=user_name
                )
                response = await self._generate_llm_response(
                    step="present_offer",
                    user_name=user_name,
                    product_type=product_type,
                    customer_segment=customer_segment,
                    collected_data=collected_data,
                    offer_details=offer_details
                )
            
            else:
                # Generar respuesta estándar para el paso
                response = await self._generate_llm_response(
                    step=next_step if not needs_retry else current_step,
                    user_name=user_name,
                    product_type=product_type,
                    customer_segment=customer_segment,
                    collected_data=collected_data
                )
            
            # Limpiar y validar respuesta
            response = self._clean_response(response)
            
            # Agregar respuesta a los mensajes
            state["messages"].append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat()
            })
            
            state["current_step"] = next_step
            
            # Guardar mensaje del agente
            await self.conversation_repo.save_message(
                state["session_id"], "agent", response, next_step
            )
            
            logger.info(f"Respuesta generada. Siguiente paso: {next_step}")
            
        except Exception as e:
            logger.error(f"Error en generate_response: {e}")
            fallback = "Disculpa, hubo un error técnico. ¿Podemos continuar?"
            
            state["messages"].append({
                "role": "assistant", 
                "content": fallback,
                "timestamp": datetime.now().isoformat()
            })
            
            # No cambiar el paso en caso de error
            await self.conversation_repo.save_message(
                state["session_id"], "agent", fallback, state.get("current_step", "error")
            )
  
        return state
    
    async def _generate_llm_response(self, step: str, user_name: str, product_type: str, 
                                   customer_segment: str, collected_data: Dict[str, Any],
                                   **extra_kwargs) -> str:
        """Genera respuesta usando el LLM con el PromptBuilder"""
        try:
            # Construir prompt del sistema
            system_prompt = self.prompt_builder.build_system_prompt(
                user_name=user_name,
                product_type=product_type,
                customer_segment=customer_segment,
                current_step=step,
                collected_data=collected_data
            )
            
            # Construir prompt del paso
            step_prompt = self.prompt_builder.build_step_prompt(
                step=step,
                user_name=user_name,
                product_type=product_type,
                customer_segment=customer_segment,
                collected_data=collected_data,
                **extra_kwargs
            )
            
            # Generar respuesta con el LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Genera la respuesta apropiada para: {step_prompt}")
            ]
            
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
            
        except Exception as e:
            logger.error(f"Error generando respuesta LLM: {e}")
            # Fallback: usar respuesta del PromptBuilder sin LLM
            return self.prompt_builder.build_step_prompt(
                step=step,
                user_name=user_name,
                product_type=product_type,
                customer_segment=customer_segment,
                collected_data=collected_data,
                **extra_kwargs
            )
    
    def _generate_negative_response(self, user_name: str) -> str:
        """Genera respuesta para intención negativa"""
        responses = [
            f"Entiendo perfectamente, {user_name}. Gracias por tu tiempo.",
            f"No hay problema, {user_name}. Si cambias de opinión, aquí estaré.",
            f"Comprendo, {user_name}. ¡Que tengas un excelente día!"
        ]
        return responses[0]  # Usar la primera por consistencia
    
    def _clean_response(self, response: str) -> str:
        """Limpia y valida la respuesta generada"""
        if not response or not isinstance(response, str):
            return "¿En qué puedo ayudarte?"
        
        # Limpiar caracteres extraños y normalizar
        cleaned = response.strip()
        
        # Limitar longitud máxima
        if len(cleaned) > 500:
            cleaned = cleaned[:497] + "..."
        
        # Asegurar que termine con puntuación apropiada
        if cleaned and not cleaned[-1] in ".!?":
            cleaned += "."
        
        return cleaned
    
    async def save_conversation(self, state: ConversationState) -> ConversationState:
        """Guarda el estado de la conversación con métricas adicionales"""
        try:
            # Calcular progreso de la conversación
            progress = self.flow_manager.get_conversation_progress(
                state.get("current_step", "greeting"),
                state.get("collected_data", {})
            )
            
            state["conversation_progress"] = progress
            
            # Guardar estado completo
            await self.conversation_repo.save_conversation_log(state)
            
            # Si completó la conversación exitosamente, crear lead
            if (state["current_step"] == "close_positive" and 
                state.get("intent_confirmed") and 
                self.lead_repo and 
                progress.get("data_completeness", 0) >= 75):  # Al menos 75% de datos completos
                
                try:
                    lead_id = await self.lead_repo.save_lead(state)
                    state["lead_generated"] = True
                    state["lead_id"] = lead_id
                    logger.info(f"Lead generado exitosamente: {lead_id}")
                except Exception as e:
                    logger.error(f"Error creando lead: {e}")
                    state["lead_generated"] = False
            
        except Exception as e:
            logger.error(f"Error en save_conversation: {e}")
        
        return state
    
    async def process_message(self, state: ConversationState) -> ConversationState:
        """Procesa un mensaje completo a través del workflow mejorado"""
        try:
            logger.info(f"Procesando mensaje para sesión: {state.get('session_id')}")
            result = await self.graph.ainvoke(state)
            logger.info(f"Mensaje procesado exitosamente")
            return result
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
            
            # Respuesta de error más informativa
            error_message = "Disculpa, tengo un problema técnico momentáneo. ¿Podrías repetir tu mensaje?"
            
            state["messages"].append({
                "role": "assistant",
                "content": error_message,
                "timestamp": datetime.now().isoformat()
            })
            state["current_step"] = "error"
            
            # Intentar guardar el error
            try:
                await self.conversation_repo.save_message(
                    state["session_id"], "agent", error_message, "error"
                )
            except:
                pass  # Si no puede guardar, al menos retornar el estado
            
            return state
    
    async def create_initial_state(self, phone: str, user_data: Dict[str, Any], message: str) -> ConversationState:
        """Crea el estado inicial de la conversación con validaciones mejoradas"""
        
        # Validar datos de entrada
        if not phone or not user_data or not message:
            raise ValueError("phone, user_data y message son requeridos")
        
        # Obtener o crear session_id
        session_id = await self._get_or_create_session_id(phone)
        
        # Obtener paso actual (si existe conversación previa)
        current_step = await self.conversation_repo.get_current_step(session_id)
        
        # Obtener datos previamente recolectados
        previous_data = await self._get_previous_collected_data(session_id)
        
        # Crear estado inicial
        state = self._build_conversation_state(
            phone, user_data, message, session_id, current_step, previous_data
        )
        
        # Guardar estado inicial
        await self._save_initial_state(state)
        
        logger.info(f"Estado inicial creado para sesión: {session_id}")
        
        return state
    
    async def _get_or_create_session_id(self, phone: str) -> str:
        """Obtiene session_id existente o crea uno nuevo"""
        try:
            session_id = await self.conversation_repo.get_session_id(phone)
            
            if not session_id:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                clean_phone = phone.replace('+', '').replace('-', '').replace(' ', '')
                session_id = f"session_{clean_phone}_{timestamp}"
                logger.info(f"Nuevo session_id creado: {session_id}")
            else:
                logger.info(f"Session_id existente encontrado: {session_id}")
            
            return session_id
        except Exception as e:
            logger.error(f"Error obteniendo session_id: {e}")
            # Fallback: crear session_id temporal
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            return f"session_temp_{timestamp}"
    
    async def _get_previous_collected_data(self, session_id: str) -> Dict[str, Any]:
        """Obtiene datos previamente recolectados en la conversación"""
        try:
            previous_state = await self.conversation_repo.get_conversation_state(session_id)
            return previous_state.get("collected_data", {}) if previous_state else {}
        except Exception as e:
            logger.error(f"Error obteniendo datos previos: {e}")
            return {}
    
    def _build_conversation_state(self, phone: str, user_data: Dict[str, Any], 
                                message: str, session_id: str, current_step: Optional[str],
                                previous_data: Dict[str, Any] = None) -> ConversationState:
        """Construye el objeto ConversationState con validaciones"""
        
        # Valores por defecto seguros
        defaults = {
            "user_id": "unknown",
            "campaign_id": "default",
            "product_type": "credit_card",
            "propensity_score": 0.5,
            "first_name": "Cliente",
            "customer_segment": "standard"
        }
        
        # Merge con defaults
        safe_user_data = {**defaults, **user_data}
        
        return ConversationState(
            phone=phone,
            user_id=safe_user_data["user_id"],
            campaign_id=safe_user_data["campaign_id"],
            product_type=safe_user_data["product_type"],
            current_step=current_step or "greeting",
            collected_data=previous_data or {},
            messages=[{
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat()
            }],
            intent_confirmed=None,
            session_id=session_id,
            propensity_score=safe_user_data["propensity_score"],
            user_name=safe_user_data["first_name"],
            customer_segment=safe_user_data["customer_segment"]
        )
    
    async def _save_initial_state(self, state: ConversationState) -> None:
        """Guarda el estado inicial en el repositorio con manejo de errores"""
        try:
            await self.conversation_repo.save_conversation_log(state)
            logger.info(f"Estado inicial guardado para sesión: {state['session_id']}")
        except Exception as e:
            logger.error(f"Error guardando estado inicial: {e}")
            # No hacer raise aquí para no bloquear la conversación
    
    def get_conversation_metrics(self, state: ConversationState) -> Dict[str, Any]:
        """Obtiene métricas de la conversación actual"""
        try:
            progress = self.flow_manager.get_conversation_progress(
                state.get("current_step", "greeting"),
                state.get("collected_data", {})
            )
            
            return {
                "session_id": state.get("session_id"),
                "current_step": state.get("current_step"),
                "progress_percentage": progress.get("progress_percentage", 0),
                "data_completeness": progress.get("data_completeness", 0),
                "message_count": len(state.get("messages", [])),
                "intent_confirmed": state.get("intent_confirmed"),
                "detected_intent": state.get("detected_intent"),
                "lead_generated": state.get("lead_generated", False),
                "conversation_started": state.get("messages", [{}])[0].get("timestamp") if state.get("messages") else None
            }
        except Exception as e:
            logger.error(f"Error calculando métricas: {e}")
            return {"error": str(e)}

