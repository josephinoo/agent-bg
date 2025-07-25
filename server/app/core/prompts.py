# app/core/prompts.py
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
import json
import logging

logger = logging.getLogger(__name__)

class ConversationStep(Enum):
    """Enum para los pasos de la conversación"""
    GREETING = "greeting"
    COLLECT_BUDGET = "collect_budget"
    COLLECT_INCOME = "collect_income"
    COLLECT_EMPLOYMENT = "collect_employment"
    COLLECT_AMOUNT = "collect_amount"
    PRESENT_OFFER = "present_offer"
    AWAITING_DECISION = "awaiting_decision"
    HANDLE_OBJECTION = "handle_objection"
    REQUEST_CLARIFICATION = "request_clarification"
    CLOSE_POSITIVE = "close_positive"
    CLOSE_NEGATIVE = "close_negative"
    COMPLETED = "completed"
    ERROR = "error"

class ProductType(Enum):
    """Enum para tipos de productos"""
    CREDIT_CARD = "credit_card"
    PERSONAL_CREDIT = "credit"
    INSURANCE = "insurance"
    SAVINGS = "savings"
    MORTGAGE = "mortgage"
    INVESTMENT = "investment"

class CustomerSegment(Enum):
    """Enum para segmentos de clientes"""
    PREMIUM = "premium"
    STANDARD = "standard"
    BASIC = "basic"
    YOUTH = "youth"
    SENIOR = "senior"

class IntentType(Enum):
    """Enum para tipos de intención"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    REQUEST_INFO = "request_info"
    OBJECTION = "objection"
    UNCLEAR = "unclear"

@dataclass
class PromptContext:
    """Contexto para la generación de prompts"""
    user_name: str
    product_type: ProductType
    customer_segment: CustomerSegment
    current_step: ConversationStep
    collected_data: Dict[str, Any]
    session_metadata: Optional[Dict[str, Any]] = None
    user_preferences: Optional[Dict[str, Any]] = None

class BasePromptTemplate:
    """Clase base para templates de prompts"""
    
    def __init__(self, template: str, required_vars: List[str] = None):
        self.template = template
        self.required_vars = required_vars or []
    
    def render(self, **kwargs) -> str:
        """Renderiza el template con las variables proporcionadas"""
        try:
            # Validar variables requeridas
            missing_vars = [var for var in self.required_vars if var not in kwargs]
            if missing_vars:
                logger.warning(f"Variables faltantes en template: {missing_vars}")
            
            return self.template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Error renderizando template: variable {e} no encontrada")
            return self.template
        except Exception as e:
            logger.error(f"Error inesperado renderizando template: {e}")
            return self.template

class SystemPromptBuilder:
    """Constructor especializado para prompts del sistema"""
    
    BASE_TEMPLATE = """
Eres un asistente bancario profesional especializado en {product_type_display}. 

🎯 CONTEXTO: Detectamos que {user_name} mostró interés en nuestros productos basado en su comportamiento digital.

📋 TU OBJETIVO:
1. Confirmar su interés de manera natural y empática
2. Recolectar información necesaria (UNA pregunta a la vez)
3. Presentar la mejor opción personalizada
4. Guiar hacia la conversión con confianza

✅ REGLAS DE COMPORTAMIENTO:
• Usa emojis estratégicamente (máximo 2 por mensaje)
• Haz UNA pregunta específica por vez
• Mantén respuestas de 2-3 líneas máximo
• Adapta el lenguaje al segmento {customer_segment_display}
• Sé empático, profesional pero conversacional
• Usa el nombre del cliente cuando sea natural

❌ RESTRICCIONES:
• NUNCA solicites datos sensibles (cuentas, contraseñas, PIN)
• Si dice "no" claramente, despídete sin insistir
• No hagas preguntas múltiples consecutivas
• Evita jerga técnica excesiva

👤 PERFIL DEL CLIENTE:
- Nombre: {user_name}
- Segmento: {customer_segment_display}
- Producto objetivo: {product_type_display}
- Propensión estimada: {propensity_score}%

📊 ESTADO ACTUAL:
- Paso: {current_step_display}
- Datos recolectados: {collected_data_summary}
"""

    SEGMENT_ADAPTATIONS = {
        CustomerSegment.PREMIUM: {
            "tone": "más formal y sofisticado",
            "language": "técnico preciso",
            "focus": "beneficios exclusivos y personalizados"
        },
        CustomerSegment.STANDARD: {
            "tone": "profesional pero amigable",
            "language": "claro y directo",
            "focus": "valor y beneficios prácticos"
        },
        CustomerSegment.BASIC: {
            "tone": "muy amigable y simple",
            "language": "sencillo y accesible",
            "focus": "simplicidad y apoyo"
        },
        CustomerSegment.YOUTH: {
            "tone": "casual y dinámico",
            "language": "moderno y digital",
            "focus": "innovación y facilidad de uso"
        },
        CustomerSegment.SENIOR: {
            "tone": "respetuoso y paciente",
            "language": "claro y sin prisa",
            "focus": "seguridad y acompañamiento"
        }
    }

    @classmethod
    def build(cls, context: PromptContext) -> str:
        """Construye el prompt del sistema"""
        adaptation = cls.SEGMENT_ADAPTATIONS.get(
            context.customer_segment, 
            cls.SEGMENT_ADAPTATIONS[CustomerSegment.STANDARD]
        )
        
        return cls.BASE_TEMPLATE.format(
            user_name=context.user_name,
            product_type_display=cls._get_product_display(context.product_type),
            customer_segment_display=cls._get_segment_display(context.customer_segment),
            current_step_display=cls._get_step_display(context.current_step),
            collected_data_summary=cls._format_collected_data(context.collected_data),
            propensity_score=int(context.session_metadata.get("propensity_score", 75) * 100) if context.session_metadata else 75,
            **adaptation
        )
    
    @staticmethod
    def _get_product_display(product_type: ProductType) -> str:
        display_map = {
            ProductType.CREDIT_CARD: "Tarjetas de Crédito",
            ProductType.PERSONAL_CREDIT: "Créditos Personales",
            ProductType.INSURANCE: "Seguros",
            ProductType.SAVINGS: "Cuentas de Ahorro",
            ProductType.MORTGAGE: "Créditos Hipotecarios",
            ProductType.INVESTMENT: "Inversiones"
        }
        return display_map.get(product_type, str(product_type.value))
    
    @staticmethod
    def _get_segment_display(segment: CustomerSegment) -> str:
        display_map = {
            CustomerSegment.PREMIUM: "Premium",
            CustomerSegment.STANDARD: "Estándar", 
            CustomerSegment.BASIC: "Básico",
            CustomerSegment.YOUTH: "Joven",
            CustomerSegment.SENIOR: "Senior"
        }
        return display_map.get(segment, str(segment.value))
    
    @staticmethod
    def _get_step_display(step: ConversationStep) -> str:
        display_map = {
            ConversationStep.GREETING: "Saludo inicial",
            ConversationStep.COLLECT_BUDGET: "Recolección de presupuesto",
            ConversationStep.COLLECT_INCOME: "Recolección de ingresos",
            ConversationStep.COLLECT_EMPLOYMENT: "Información laboral",
            ConversationStep.COLLECT_AMOUNT: "Monto solicitado",
            ConversationStep.PRESENT_OFFER: "Presentación de oferta",
            ConversationStep.AWAITING_DECISION: "Esperando decisión",
            ConversationStep.HANDLE_OBJECTION: "Manejo de objeciones",
            ConversationStep.REQUEST_CLARIFICATION: "Solicitud de aclaración"
        }
        return display_map.get(step, str(step.value))
    
    @staticmethod
    def _format_collected_data(data: Dict[str, Any]) -> str:
        if not data:
            return "Ninguno aún"
        
        formatted = []
        key_map = {
            "budget": "Presupuesto",
            "monthly_income": "Ingresos mensuales",
            "employment_type": "Tipo de empleo",
            "requested_amount": "Monto solicitado"
        }
        
        for key, value in data.items():
            display_key = key_map.get(key, key)
            if isinstance(value, (int, float)):
                formatted.append(f"{display_key}: ${value:,}")
            else:
                formatted.append(f"{display_key}: {value}")
        
        return ", ".join(formatted)

class StepPromptBuilder:
    """Constructor para prompts específicos de cada paso"""
    
    STEP_TEMPLATES = {
        ConversationStep.GREETING: BasePromptTemplate(
            """¡Hola {user_name}! 👋 
            
Vi que estuviste consultando opciones de {product_type_display}. {segment_greeting}

¿Te gustaría que te ayude a encontrar la mejor opción para tu perfil?""",
            required_vars=["user_name", "product_type_display"]
        ),
        
        ConversationStep.COLLECT_INCOME: BasePromptTemplate(
            """{confirmation_phrase} Para recomendarte las mejores opciones disponibles, ¿podrías contarme cuáles son tus ingresos mensuales aproximados?

{income_context}""",
            required_vars=["confirmation_phrase"]
        ),
        
        ConversationStep.COLLECT_EMPLOYMENT: BasePromptTemplate(
            """Perfecto, con ${monthly_income:,} mensuales tienes buenas opciones. 💪

¿Trabajas como empleado en una empresa o tienes tu propio negocio?""",
            required_vars=["monthly_income"]
        ),
        
        ConversationStep.COLLECT_AMOUNT: BasePromptTemplate(
            """Excelente información. {employment_acknowledgment}

{amount_question}""",
            required_vars=["amount_question"]
        ),
        
        ConversationStep.PRESENT_OFFER: BasePromptTemplate(
            """¡Tengo la opción perfecta para ti! 🎯

{offer_details}

¿Te gustaría que te envíe más información detallada o tienes alguna pregunta específica?""",
            required_vars=["offer_details"]
        ),
        
        ConversationStep.AWAITING_DECISION: BasePromptTemplate(
            """{decision_prompt}

¿Te interesa proceder con esta opción?""",
            required_vars=["decision_prompt"]
        ),
        
        ConversationStep.CLOSE_POSITIVE: BasePromptTemplate(
            """¡Excelente decisión, {user_name}! 🙌

Un asesor especializado se contactará contigo en las próximas 24-48 horas para finalizar tu {product_type_display}.

¡Gracias por confiar en nosotros!""",
            required_vars=["user_name", "product_type_display"]
        ),
        
        ConversationStep.CLOSE_NEGATIVE: BasePromptTemplate(
            """Entiendo perfectamente, {user_name}. 

Gracias por tu tiempo. Si en el futuro cambias de opinión, estaré aquí para ayudarte.

¡Que tengas un excelente día! 👋""",
            required_vars=["user_name"]
        ),
        
        ConversationStep.HANDLE_OBJECTION: BasePromptTemplate(
            """Entiendo tu preocupación sobre {objection_topic}. {objection_response}

¿Hay algo más específico que te gustaría saber?""",
            required_vars=["objection_topic", "objection_response"]
        ),
        
        ConversationStep.REQUEST_CLARIFICATION: BasePromptTemplate(
            """No entendí bien tu mensaje, ¿podrías darme más detalles? 

{clarification_examples}

¡Gracias por tu paciencia! 😊""",
            required_vars=["clarification_examples"]
        )
    }

    SEGMENT_GREETINGS = {
        CustomerSegment.PREMIUM: "Como cliente preferencial, quiero asegurarme de ofrecerte las mejores condiciones.",
        CustomerSegment.STANDARD: "Me encantaría ayudarte a encontrar algo que se ajuste perfectamente a tus necesidades.",
        CustomerSegment.BASIC: "Estoy aquí para ayudarte de manera sencilla y sin complicaciones.",
        CustomerSegment.YOUTH: "¡Perfecto timing! Tenemos opciones geniales para personas como tú.",
        CustomerSegment.SENIOR: "Será un placer ayudarte con toda la información que necesites."
    }

    @classmethod
    def build(cls, context: PromptContext, **extra_vars) -> str:
        """Construye el prompt para un paso específico"""
        template = cls.STEP_TEMPLATES.get(context.current_step)
        if not template:
            logger.warning(f"No hay template para el paso: {context.current_step}")
            return "Continúa la conversación apropiadamente."
        
        # Preparar variables base
        variables = {
            "user_name": context.user_name,
            "product_type_display": SystemPromptBuilder._get_product_display(context.product_type),
            "segment_greeting": cls.SEGMENT_GREETINGS.get(
                context.customer_segment, 
                cls.SEGMENT_GREETINGS[CustomerSegment.STANDARD]
            ),
            **context.collected_data,
            **extra_vars
        }
        
        # Agregar variables específicas del paso
        variables.update(cls._get_step_specific_vars(context))
        
        return template.render(**variables)
    
    @classmethod
    def _get_step_specific_vars(cls, context: PromptContext) -> Dict[str, Any]:
        """Obtiene variables específicas para cada paso"""
        step_vars = {}
        
        if context.current_step == ConversationStep.COLLECT_INCOME:
            step_vars["confirmation_phrase"] = cls._get_confirmation_phrase(context)
            step_vars["income_context"] = cls._get_income_context(context.product_type)
        
        elif context.current_step == ConversationStep.COLLECT_EMPLOYMENT:
            employment = context.collected_data.get("employment_type", "")
            if employment == "employee":
                step_vars["employment_acknowledgment"] = "Es genial que tengas un empleo estable."
            elif employment == "business_owner":
                step_vars["employment_acknowledgment"] = "¡Excelente que tengas tu propio negocio!"
            else:
                step_vars["employment_acknowledgment"] = ""
        
        elif context.current_step == ConversationStep.COLLECT_AMOUNT:
            step_vars["amount_question"] = ProductPromptBuilder.get_amount_question(context.product_type)
        
        elif context.current_step == ConversationStep.PRESENT_OFFER:
            step_vars["offer_details"] = ProductPromptBuilder.build_offer(context)
        
        return step_vars
    
    @staticmethod
    def _get_confirmation_phrase(context: PromptContext) -> str:
        confirmations = {
            CustomerSegment.PREMIUM: "Perfecto.",
            CustomerSegment.STANDARD: "Excelente.",
            CustomerSegment.BASIC: "¡Muy bien!",
            CustomerSegment.YOUTH: "¡Genial!",
            CustomerSegment.SENIOR: "Muy bien."
        }
        return confirmations.get(context.customer_segment, "Perfecto.")
    
    @staticmethod
    def _get_income_context(product_type: ProductType) -> str:
        contexts = {
            ProductType.CREDIT_CARD: "Esto me ayuda a calcular el límite ideal para ti.",
            ProductType.PERSONAL_CREDIT: "Con esta info puedo mostrarte los montos disponibles.",
            ProductType.INSURANCE: "Así puedo sugerirte coberturas acordes a tu perfil.",
            ProductType.SAVINGS: "Para recomendarte el mejor plan de ahorro.",
            ProductType.MORTGAGE: "Es fundamental para evaluar tu capacidad de financiamiento.",
            ProductType.INVESTMENT: "Necesario para armar una estrategia de inversión adecuada."
        }
        return contexts.get(product_type, "Esto me ayuda a darte la mejor recomendación.")

class ProductPromptBuilder:
    """Constructor especializado para prompts específicos de productos"""
    
    PRODUCT_CONFIGS = {
        ProductType.CREDIT_CARD: {
            "benefits": [
                "Sin anualidad el primer año",
                "Cashback en compras diarias",
                "Meses sin intereses en tiendas afiliadas",
                "Programa de puntos canjeables",
                "Seguro de compras incluido",
                "App móvil avanzada"
            ],
            "amount_question": "¿Qué límite de crédito te gustaría tener en tu tarjeta?",
            "calculation": lambda income: min(income * 5, 15000)
        },
        
        ProductType.PERSONAL_CREDIT: {
            "benefits": [
                "Tasas preferenciales desde 8.9%",
                "Plazos flexibles hasta 60 meses",
                "Aprobación en 24 horas",
                "Sin comisiones por apertura",
                "Pagos fijos mensuales",
                "Opción de prepago sin penalización"
            ],
            "amount_question": "¿Qué monto de crédito necesitas aproximadamente?",
            "calculation": lambda income: min(income * 12, 100000)
        },
        
        ProductType.INSURANCE: {
            "benefits": [
                "Cobertura integral",
                "Primas competitivas",
                "Atención 24/7 en emergencias",
                "Red de proveedores nacional",
                "Deducibles preferenciales",
                "App para reportar siniestros"
            ],
            "amount_question": "¿Qué tipo de cobertura buscas: vida, hogar, auto o familiar?",
            "calculation": lambda income: income * 0.05  # 5% del ingreso como prima sugerida
        },
        
        ProductType.SAVINGS: {
            "benefits": [
                "Rendimientos hasta 6.5% anual",
                "Sin monto mínimo de apertura",
                "Retiros ilimitados",
                "Banca digital completa",
                "Transferencias gratuitas",
                "Estado de cuenta digital"
            ],
            "amount_question": "¿Qué monto te gustaría ahorrar mensualmente?",
            "calculation": lambda income: income * 0.15  # 15% del ingreso sugerido
        }
    }

    @classmethod
    def build_offer(cls, context: PromptContext) -> str:
        """Construye una oferta personalizada"""
        config = cls.PRODUCT_CONFIGS.get(context.product_type)
        if not config:
            return "Te tengo una excelente opción que será perfecta para ti."
        
        monthly_income = context.collected_data.get("monthly_income", 0)
        if not monthly_income:
            return "Necesito conocer tus ingresos para darte la mejor recomendación."
        
        # Calcular valores recomendados
        recommended_value = config["calculation"](monthly_income)
        
        # Seleccionar beneficios top 3
        benefits = config["benefits"][:3]
        benefits_text = ", ".join(benefits[:-1]) + f" y {benefits[-1]}"
        
        # Construir oferta específica
        if context.product_type == ProductType.CREDIT_CARD:
            product_name = cls._get_card_type(monthly_income)
            return f"Con tus ingresos de ${monthly_income:,}, te recomiendo nuestra {product_name} con límite de hasta ${int(recommended_value):,}, que incluye {benefits_text}."
        
        elif context.product_type == ProductType.PERSONAL_CREDIT:
            monthly_payment = recommended_value / 36  # 36 meses promedio
            return f"Puedo ofrecerte un crédito de hasta ${int(recommended_value):,} con cuotas desde ${int(monthly_payment):,} mensuales, que incluye {benefits_text}."
        
        elif context.product_type == ProductType.INSURANCE:
            return f"Te recomiendo nuestro seguro integral con prima mensual desde ${int(recommended_value):,}, que incluye {benefits_text}."
        
        elif context.product_type == ProductType.SAVINGS:
            annual_earnings = recommended_value * 12 * 0.065  # 6.5% anual
            return f"Tu cuenta de ahorros con ${int(recommended_value):,} mensuales generaría aproximadamente ${int(annual_earnings):,} al año, e incluye {benefits_text}."
        
        return f"Te tengo una excelente opción con {benefits_text}."
    
    @classmethod
    def get_amount_question(cls, product_type: ProductType) -> str:
        """Obtiene la pregunta sobre monto para un producto"""
        config = cls.PRODUCT_CONFIGS.get(product_type)
        return config["amount_question"] if config else "¿Qué monto te interesa?"
    
    @staticmethod
    def _get_card_type(income: float) -> str:
        """Determina el tipo de tarjeta según ingresos"""
        if income >= 5000:
            return "Tarjeta Platinum"
        elif income >= 2500:
            return "Tarjeta Gold"
        else:
            return "Tarjeta Classic"

class IntentAnalyzer:
    """Analizador de intenciones del usuario"""
    
    POSITIVE_KEYWORDS = [
        "sí", "si", "ok", "acepto", "me interesa", "perfecto", "excelente",
        "genial", "claro", "por supuesto", "dale", "vamos", "quiero"
    ]
    
    NEGATIVE_KEYWORDS = [
        "no", "nah", "no gracias", "no me interesa", "paso", "mejor no",
        "ahora no", "tal vez después", "no estoy seguro", "déjame pensarlo"
    ]
    
    INFO_REQUEST_KEYWORDS = [
        "información", "detalles", "explica", "cómo", "qué", "cuál",
        "cuánto", "cuándo", "dónde", "por qué", "más info", "dime más"
    ]
    
    OBJECTION_KEYWORDS = [
        "pero", "sin embargo", "aunque", "el problema es", "me preocupa",
        "no estoy convencido", "dudas", "riesgo", "caro", "costoso"
    ]

    EMPLOYMENT_KEYWORDS = [
        "empleado", "trabajo", "empresa", "empleada", "oficina", "sueldo",
        "negocio", "propio", "empresario", "comercio", "dueño", "independiente",
        "freelance", "independiente", "por mi cuenta", "proyectos",
        "jubilado", "pensionado", "retirado", "tercera edad",
        "estudiante", "estudio", "universidad", "carrera",
        "desempleado", "sin trabajo", "buscando trabajo", "cesante"
    ]
    
    @classmethod
    def analyze(cls, message: str, context: PromptContext) -> IntentType:
        """Analiza la intención del mensaje del usuario"""
        message_lower = message.lower().strip()
    
        # Análisis por keywords
        if any(word in message_lower for word in cls.POSITIVE_KEYWORDS):
            return IntentType.POSITIVE
        
        if any(word in message_lower for word in cls.NEGATIVE_KEYWORDS):
            return IntentType.NEGATIVE
        
        if any(word in message_lower for word in cls.INFO_REQUEST_KEYWORDS):
    
            return IntentType.REQUEST_INFO
        
        if any(word in message_lower for word in cls.OBJECTION_KEYWORDS):
            return IntentType.OBJECTION
        
        # Análisis contextual según el paso actual
        if context.current_step in [
            ConversationStep.COLLECT_INCOME, 
            ConversationStep.COLLECT_AMOUNT
        ]:
            # Si proporciona datos numéricos o informativos, es neutral
            if any(char.isdigit() for char in message):
                return IntentType.NEUTRAL
        
        if any(word in message_lower for word in cls.EMPLOYMENT_KEYWORDS):
            return IntentType.NEUTRAL
        
        # Si no se puede determinar claramente
        return IntentType.UNCLEAR

class DataExtractor:
    """Extractor de datos específicos del mensaje del usuario"""
    
    @staticmethod
    def extract_income(message: str) -> Optional[float]:
        """Extrae ingreso mensual del mensaje"""
        import re
        
        # Buscar números en el mensaje
        numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d{2})?', message.replace(',', ''))
        
        if not numbers:
            return None
        
        # Si hay múltiples números, buscar contexto
        message_lower = message.lower()
        
        if "entre" in message_lower and len(numbers) >= 2:
            # "entre 2000 y 3000" -> promedio
            return (float(numbers[0]) + float(numbers[1])) / 2
        
        # Tomar el primer número encontrado
        return float(numbers[0])
    
    @staticmethod
    def extract_employment(message: str) -> Optional[str]:
        """Extrae tipo de empleo del mensaje"""
        message_lower = message.lower()
        
        employment_keywords = {
            "employee": ["empleado", "trabajo", "empresa", "empleada", "oficina", "sueldo"],
            "business_owner": ["negocio", "propio", "empresario", "comercio", "dueño", "independiente"],
            "freelancer": ["freelance", "independiente", "por mi cuenta", "proyectos"],
            "retired": ["jubilado", "pensionado", "retirado", "tercera edad"],
            "student": ["estudiante", "estudio", "universidad", "carrera"],
            "unemployed": ["desempleado", "sin trabajo", "buscando trabajo", "cesante"]
        }
        
        for employment_type, keywords in employment_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                return employment_type
        
        return None
    
    @staticmethod
    def extract_amount(message: str) -> Optional[float]:
        """Extrae monto solicitado del mensaje"""
        import re
        
        numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d{2})?', message.replace(',', ''))
        
        if not numbers:
            return None
        
        message_lower = message.lower()
        
        if "entre" in message_lower and len(numbers) >= 2:
            # Tomar el número mayor del rango
            return max(float(numbers[0]), float(numbers[1]))
        
        return float(numbers[0])

class PromptBuilder:
    """Clase principal del constructor de prompts mejorado"""
    
    def __init__(self):
        self.system_builder = SystemPromptBuilder()
        self.step_builder = StepPromptBuilder()
        self.product_builder = ProductPromptBuilder()
        self.intent_analyzer = IntentAnalyzer()
        self.data_extractor = DataExtractor()
    
    def build_system_prompt(self, user_name: str, product_type: str, customer_segment: str,
                          current_step: str, collected_data: Dict[str, Any],
                          session_metadata: Dict[str, Any] = None) -> str:
        """Construye el prompt del sistema"""
        try:
            context = PromptContext(
                user_name=user_name,
                product_type=ProductType(product_type),
                customer_segment=CustomerSegment(customer_segment),
                current_step=ConversationStep(current_step),
                collected_data=collected_data,
                session_metadata=session_metadata or {}
            )
            return self.system_builder.build(context)
        except (ValueError, KeyError) as e:
            logger.error(f"Error construyendo system prompt: {e}")
            return f"Eres un asistente bancario profesional ayudando a {user_name}."
    
    def build_step_prompt(self, step: str, user_name: str = "Cliente", 
                         product_type: str = "credit_card", customer_segment: str = "standard",
                         collected_data: Dict[str, Any] = None, **kwargs) -> str:
        """Construye prompt específico para un paso"""
        try:
            context = PromptContext(
                user_name=user_name,
                product_type=ProductType(product_type),
                customer_segment=CustomerSegment(customer_segment),
                current_step=ConversationStep(step),
                collected_data=collected_data or {}
            )
            return self.step_builder.build(context, **kwargs)
        except (ValueError, KeyError) as e:
            logger.error(f"Error construyendo step prompt: {e}")
            return f"Continúa la conversación apropiadamente para el paso: {step}"
    
    def analyze_intent(self, message: str, current_step: str = "greeting",
                      product_type: str = "credit_card", customer_segment: str = "standard", user_name: str = "Cliente") -> str:
        """Analiza la intención del mensaje del usuario"""

        context = PromptContext(
                user_name=user_name,
                product_type=ProductType(product_type),
                customer_segment=CustomerSegment(customer_segment),
                current_step=ConversationStep(current_step),
                collected_data={}
            )
        intent = self.intent_analyzer.analyze(message, context)
        print("x"*20)
        print("intent", intent.value)
        print("x"*20)

        return intent.value

    
    def extract_data(self, message: str, data_type: str) -> Any:
        """Extrae datos específicos del mensaje"""
        try:
            if data_type == "income":
                return self.data_extractor.extract_income(message)
            elif data_type == "employment":
                return self.data_extractor.extract_employment(message)
            elif data_type == "amount":
                return self.data_extractor.extract_amount(message)
            else:
                logger.warning(f"Tipo de datos no soportado: {data_type}")
                return None
        except Exception as e:
            logger.error(f"Error extrayendo datos {data_type}: {e}")
            return None
    
    def build_product_offer(self, product_type: str, collected_data: Dict[str, Any],
                           customer_segment: str = "standard", user_name: str = "Cliente") -> str:
        """Construye oferta específica por producto"""
        try:
            context = PromptContext(
                user_name=user_name,
                product_type=ProductType(product_type),
                customer_segment=CustomerSegment(customer_segment),
                current_step=ConversationStep.PRESENT_OFFER,
                collected_data=collected_data
            )
            return self.product_builder.build_offer(context)
        except Exception as e:
            logger.error(f"Error construyendo oferta de producto: {e}")
            return "Te tengo una excelente opción que será perfecta para ti."
    
    def get_validation_rules(self, step: str) -> Dict[str, Any]:
        """Obtiene reglas de validación para un paso específico"""
        validation_rules = {
            ConversationStep.COLLECT_INCOME.value: {
                "required_data": ["monthly_income"],
                "data_type": "numeric",
                "min_value": 500,
                "max_value": 50000,
                "error_message": "Por favor, proporciona un ingreso mensual válido entre $500 y $50,000."
            },
            ConversationStep.COLLECT_EMPLOYMENT.value: {
                "required_data": ["employment_type"],
                "data_type": "categorical",
                "valid_values": ["employee", "business_owner", "freelancer", "retired", "student", "unemployed"],
                "error_message": "Por favor, especifica tu situación laboral actual."
            },
            ConversationStep.COLLECT_AMOUNT.value: {
                "required_data": ["requested_amount"],
                "data_type": "numeric",
                "min_value": 100,
                "max_value": 100000,
                "error_message": "Por favor, indica el monto que te interesa."
            }
        }
        
        return validation_rules.get(step, {})
    
    def validate_collected_data(self, step: str, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Valida los datos recolectados según las reglas del paso"""
        rules = self.get_validation_rules(step)
        
        if not rules:
            return {"valid": True, "message": None}
        
        required_data = rules.get("required_data", [])
        
        # Verificar que todos los datos requeridos estén presentes
        missing_data = [field for field in required_data if field not in collected_data or collected_data[field] is None]
        
        if missing_data:
            return {
                "valid": False,
                "message": rules.get("error_message", "Faltan datos requeridos."),
                "missing_fields": missing_data
            }
        
        # Validaciones específicas por tipo de dato
        data_type = rules.get("data_type")
        
        if data_type == "numeric":
            for field in required_data:
                value = collected_data.get(field)
                if not isinstance(value, (int, float)):
                    return {
                        "valid": False,
                        "message": f"El valor de {field} debe ser numérico."
                    }
                
                min_val = rules.get("min_value")
                max_val = rules.get("max_value")
                
                if min_val and value < min_val:
                    return {
                        "valid": False,
                        "message": f"El valor mínimo para {field} es {min_val}."
                    }
                
                if max_val and value > max_val:
                    return {
                        "valid": False,
                        "message": f"El valor máximo para {field} es {max_val}."
                    }
        
        elif data_type == "categorical":
            valid_values = rules.get("valid_values", [])
            for field in required_data:
                value = collected_data.get(field)
                if value not in valid_values:
                    return {
                        "valid": False,
                        "message": f"Valor no válido para {field}. Valores permitidos: {', '.join(valid_values)}"
                    }
        
        return {"valid": True, "message": "Datos válidos"}

class ConversationFlowManager:
    """Gestor del flujo de conversación"""
    
    def __init__(self, prompt_builder: PromptBuilder):
        self.prompt_builder = prompt_builder
    
    def get_next_step(self, current_step: str, intent: str, collected_data: Dict[str, Any]) -> str:
        """Determina el siguiente paso en la conversación"""
        try:
            current = ConversationStep(current_step)
            intent_type = IntentType(intent)
            
            # Si el usuario rechaza en cualquier momento
            if intent_type == IntentType.NEGATIVE:
                return ConversationStep.CLOSE_NEGATIVE.value
            
            # Flujo principal según el paso actual
            if current == ConversationStep.GREETING:
                if intent_type == IntentType.POSITIVE:
                    return ConversationStep.COLLECT_INCOME.value
                else:
                    return ConversationStep.REQUEST_CLARIFICATION.value
            
            elif current == ConversationStep.COLLECT_INCOME:
                if self._has_valid_income(collected_data):
                    return ConversationStep.COLLECT_EMPLOYMENT.value
                else:
                    return ConversationStep.COLLECT_INCOME.value  # Repetir hasta obtener datos válidos
            
            elif current == ConversationStep.COLLECT_EMPLOYMENT:
                if self._has_valid_employment(collected_data):
                    return ConversationStep.COLLECT_AMOUNT.value
                else:
                    return ConversationStep.COLLECT_EMPLOYMENT.value
            
            elif current == ConversationStep.COLLECT_AMOUNT:
                if self._has_valid_amount(collected_data):
                    return ConversationStep.PRESENT_OFFER.value
                else:
                    return ConversationStep.COLLECT_AMOUNT.value
            
            elif current == ConversationStep.PRESENT_OFFER:
                if intent_type == IntentType.POSITIVE:
                    return ConversationStep.AWAITING_DECISION.value
                elif intent_type == IntentType.REQUEST_INFO:
                    return ConversationStep.PRESENT_OFFER.value  # Proporcionar más info
                elif intent_type == IntentType.OBJECTION:
                    return ConversationStep.HANDLE_OBJECTION.value
                else:
                    return ConversationStep.REQUEST_CLARIFICATION.value
            
            elif current == ConversationStep.AWAITING_DECISION:
                if intent_type == IntentType.POSITIVE:
                    return ConversationStep.CLOSE_POSITIVE.value
                elif intent_type == IntentType.NEGATIVE:
                    return ConversationStep.CLOSE_NEGATIVE.value
                else:
                    return ConversationStep.AWAITING_DECISION.value
            
            elif current == ConversationStep.HANDLE_OBJECTION:
                if intent_type == IntentType.POSITIVE:
                    return ConversationStep.AWAITING_DECISION.value
                elif intent_type == IntentType.REQUEST_INFO:
                    return ConversationStep.PRESENT_OFFER.value
                else:
                    return ConversationStep.CLOSE_NEGATIVE.value
            
            elif current == ConversationStep.REQUEST_CLARIFICATION:
                # Volver al paso anterior o continuar según el contexto
                return self._get_clarification_next_step(collected_data)
            
            else:
                return ConversationStep.ERROR.value
        
        except (ValueError, KeyError) as e:
            logger.error(f"Error determinando siguiente paso: {e}")
            return ConversationStep.ERROR.value
    
    def _has_valid_income(self, data: Dict[str, Any]) -> bool:
        """Verifica si hay ingresos válidos"""
        income = data.get("monthly_income")
        return isinstance(income, (int, float)) and 500 <= income <= 50000
    
    def _has_valid_employment(self, data: Dict[str, Any]) -> bool:
        """Verifica si hay información de empleo válida"""
        employment = data.get("employment_type")
        valid_types = ["employee", "business_owner", "freelancer", "retired", "student", "unemployed"]
        return employment in valid_types
    
    def _has_valid_amount(self, data: Dict[str, Any]) -> bool:
        """Verifica si hay monto válido"""
        amount = data.get("requested_amount")
        return isinstance(amount, (int, float)) and amount > 0
    
    def _get_clarification_next_step(self, data: Dict[str, Any]) -> str:
        """Determina el siguiente paso después de una aclaración"""
        if not self._has_valid_income(data):
            return ConversationStep.COLLECT_INCOME.value
        elif not self._has_valid_employment(data):
            return ConversationStep.COLLECT_EMPLOYMENT.value
        elif not self._has_valid_amount(data):
            return ConversationStep.COLLECT_AMOUNT.value
        else:
            return ConversationStep.PRESENT_OFFER.value
    
    def is_conversation_complete(self, current_step: str) -> bool:
        """Verifica si la conversación ha terminado"""
        terminal_steps = [
            ConversationStep.CLOSE_POSITIVE.value,
            ConversationStep.CLOSE_NEGATIVE.value,
            ConversationStep.COMPLETED.value,
            ConversationStep.ERROR.value
        ]
        return current_step in terminal_steps
    
    def get_conversation_progress(self, current_step: str, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Obtiene el progreso actual de la conversación"""
        try:
            step = ConversationStep(current_step)
            
            # Definir orden de pasos
            step_order = [
                ConversationStep.GREETING,
                ConversationStep.COLLECT_INCOME,
                ConversationStep.COLLECT_EMPLOYMENT,
                ConversationStep.COLLECT_AMOUNT,
                ConversationStep.PRESENT_OFFER,
                ConversationStep.AWAITING_DECISION,
                ConversationStep.CLOSE_POSITIVE
            ]
            
            try:
                current_index = step_order.index(step)
                progress_percentage = int((current_index / len(step_order)) * 100)
            except ValueError:
                # Si el paso no está en el orden principal (ej: manejo de objeciones)
                progress_percentage = 50  # Estimación
            
            # Calcular completitud de datos
            required_fields = ["monthly_income", "employment_type", "requested_amount"]
            completed_fields = sum(1 for field in required_fields if collected_data.get(field) is not None)
            data_completeness = int((completed_fields / len(required_fields)) * 100)
            
            return {
                "current_step": current_step,
                "progress_percentage": progress_percentage,
                "data_completeness": data_completeness,
                "is_complete": self.is_conversation_complete(current_step),
                "collected_fields": completed_fields,
                "total_fields": len(required_fields)
            }
        
        except Exception as e:
            logger.error(f"Error calculando progreso: {e}")
            return {
                "current_step": current_step,
                "progress_percentage": 0,
                "data_completeness": 0,
                "is_complete": False,
                "error": str(e)
            }

# Funciones de utilidad para retrocompatibilidad
def build_system_prompt(user_name: str, product_type: str, customer_segment: str,
                       current_step: str, collected_data: Dict[str, Any]) -> str:
    """Función de compatibilidad con la interfaz anterior"""
    builder = PromptBuilder()
    return builder.build_system_prompt(
        user_name=user_name,
        product_type=product_type,
        customer_segment=customer_segment,
        current_step=current_step,
        collected_data=collected_data
    )

def build_step_prompt(step: str, **kwargs) -> str:
    """Función de compatibilidad con la interfaz anterior"""
    builder = PromptBuilder()
    return builder.build_step_prompt(step=step, **kwargs)

