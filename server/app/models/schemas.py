# app/models/schemas.py
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Any, Optional, TypedDict, Annotated
from datetime import datetime
from decimal import Decimal
import operator

# ============================================
# SCHEMAS DE ENTRADA
# ============================================

class BuilderBotMessage(BaseModel):
    """Mensaje recibido desde BuilderBot"""
    phone: str = Field(..., description="Número de teléfono con formato +593...")
    message: str = Field(..., description="Mensaje del usuario")
    ref: Optional[str] = None
    keyword: Optional[str] = None
    
    @validator('phone')
    def validate_phone(cls, v):
        if not v or len(v) < 10:
            raise ValueError('Teléfono debe tener al menos 10 dígitos')
        return v

class CampaignCreate(BaseModel):
    """Crear nueva campaña"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    product_type: str = Field(..., pattern="^(credit|credit_card|insurance|savings)$")
    budget_total: Decimal = Field(..., gt=0)
    max_leads_per_day: int = Field(default=100, ge=1)
    start_date: datetime
    end_date: datetime
    targeting_criteria: Optional[Dict[str, Any]] = None
    
    @validator('end_date')
    def validate_end_date(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v

class CampaignUser(BaseModel):
    """Usuario en campaña"""
    user_id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    customer_segment: str = Field(..., pattern="^(premium|standard|basic)$")
    current_products: List[str] = []
    credit_score: Optional[int] = Field(None, ge=300, le=850)
    monthly_income: Optional[Decimal] = Field(None, ge=0)

# ============================================
# SCHEMAS DE ESTADO
# ============================================

class ConversationState(TypedDict):
    """Estado de la conversación para LangGraph"""
    phone: str
    user_id: str
    campaign_id: str
    product_type: str
    current_step: str
    collected_data: Dict[str, Any]
    messages: Annotated[List[Dict], operator.add]
    intent_confirmed: Optional[bool]
    session_id: str
    propensity_score: float
    user_name: str
    customer_segment: str
    # Nuevos campos para el flujo extendido
    next_step: Optional[str]
    validation_error: Optional[str]
    can_retry: Optional[bool]
    lead_generated: Optional[bool]
    lead_id: Optional[str]
    save_error: Optional[str]
    retry_count: Optional[int]
    detected_intent: Optional[str]

class MessageData(BaseModel):
    """Datos de un mensaje"""
    role: str  # 'user' o 'assistant'
    content: str
    timestamp: str
    intent: Optional[str] = None
    confidence: Optional[float] = None

# ============================================
# SCHEMAS DE RESPUESTA
# ============================================

class AgentResponse(BaseModel):
    """Respuesta del agente"""
    status: str
    response: str
    step: str
    session_id: str
    intent_confirmed: Optional[bool] = None
    collected_data: Dict[str, Any] = {}
    
class HealthCheck(BaseModel):
    """Health check response"""
    status: str
    database: str
    llm: str
    timestamp: str
    error: Optional[str] = None

class LeadResponse(BaseModel):
    """Lead generado"""
    lead_id: str
    user_id: str
    campaign_id: str
    status: str
    collected_data: Dict[str, Any]
    created_at: datetime

class CampaignResponse(BaseModel):
    """Respuesta de campaña"""
    id: str
    name: str
    product_type: str
    status: str
    budget_total: float
    budget_spent: float
    budget_remaining: float
    stats: Dict[str, Any]

# ============================================
# SCHEMAS INTERNOS
# ============================================

class UserData(BaseModel):
    """Datos del usuario desde la base de datos"""
    user_id: str
    campaign_id: str
    product_type: str
    first_name: str
    last_name: str
    phone: str
    customer_segment: str
    current_products: List[str] = []
    credit_score: Optional[int] = None
    monthly_income: Optional[Decimal] = None

class ConversationLog(BaseModel):
    """Log de conversación"""
    session_id: str
    user_id: str
    campaign_id: str
    status: str
    current_step: str
    collected_data: Dict[str, Any]
    started_at: datetime
    completed_at: Optional[datetime] = None

class IntentAnalysis(BaseModel):
    """Resultado del análisis de intención"""
    intent: str  # 'positive', 'negative', 'neutral', 'request_info'
    confidence: float
    extracted_data: Dict[str, Any] = {}

# ============================================
# SCHEMAS DE ERROR
# ============================================

class ErrorResponse(BaseModel):
    """Respuesta de error estándar"""
    error: str
    detail: str
    timestamp: str
    path: Optional[str] = None

class ValidationError(BaseModel):
    """Error de validación"""
    field: str
    message: str
    value: Any

# ============================================
# SCHEMAS DE CONFIGURACIÓN
# ============================================

class AgentConfig(BaseModel):
    """Configuración del agente"""
    max_retries: int = 3
    timeout_seconds: int = 30
    temperature: float = 0.7
    max_tokens: int = 500
    
class CampaignStats(BaseModel):
    """Estadísticas de campaña"""
    total_users: int = 0
    active_users: int = 0
    contacted_users: int = 0
    converted_users: int = 0
    conversion_rate: float = 0.0
    avg_propensity_score: float = 0.0

# ============================================
# SCHEMAS DE LEAD
# ============================================

class LeadCreate(BaseModel):
    product_type: Optional[str] = None
    requested_amount: Optional[float] = None
    employment_type: Optional[str] = None
    monthly_income: Optional[float] = None
    email: Optional[str] = None

class LeadResponse(BaseModel):
    lead_id: str
    status: str
    timestamp: str
    customer_id: str
    session_id: str
    product_type: str
    propensity_score: float
    message: str