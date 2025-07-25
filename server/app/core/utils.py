# app/core/utils.py
import re
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from decimal import Decimal
import hashlib
import random
import string

# ============================================
# UTILIDADES DE TELÉFONO
# ============================================

def clean_phone_number(phone: str) -> str:
    """Limpia y estandariza número de teléfono a formato internacional"""
    if not phone:
        return ""
    
    # Remover caracteres no numéricos excepto +
    clean = re.sub(r'[^\d+]', '', phone)
    
    # Si no tiene código de país, agregar +593 (Ecuador)
    if not clean.startswith('+'):
        if clean.startswith('593'):
            clean = '+' + clean
        elif clean.startswith('09') or clean.startswith('9'):
            clean = '+593' + clean.lstrip('0')
        else:
            clean = '+593' + clean
    
    return clean

def is_valid_phone_number(phone: str) -> bool:
    """Valida formato de número de teléfono"""
    clean_phone = clean_phone_number(phone)
    
    # Validar formato ecuatoriano: +593 seguido de 9 dígitos
    pattern = r'^\+593[0-9]{9}$'
    return bool(re.match(pattern, clean_phone))

def mask_phone_number(phone: str) -> str:
    """Enmascara número de teléfono para logging"""
    if len(phone) < 8:
        return phone
    
    return phone[:4] + "*" * (len(phone) - 8) + phone[-4:]

# ============================================
# UTILIDADES DE TEXTO
# ============================================

def extract_numbers_from_text(text: str) -> List[float]:
    """Extrae números de un texto"""
    if not text:
        return []
    
    # Pattern para números con decimales
    pattern = r'\d+(?:\.\d+)?'
    matches = re.findall(pattern, text)
    
    try:
        return [float(match) for match in matches]
    except ValueError:
        return []

def extract_emails_from_text(text: str) -> List[str]:
    """Extrae emails de un texto"""
    if not text:
        return []
    
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(pattern, text)

def sanitize_text_for_logging(text: str, max_length: int = 100) -> str:
    """Sanitiza texto para logging seguro"""
    if not text:
        return ""
    
    # Remover información potencialmente sensible
    sensitive_patterns = [
        (r'\b\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b', '[CARD]'),  # Números de tarjeta
        (r'\b\d{2,4}[-/]\d{2,4}[-/]\d{2,4}\b', '[DATE]'),   # Fechas
        (r'\b\d{3,4}\b', '[CVV]'),                           # CVV
    ]
    
    sanitized = text
    for pattern, replacement in sensitive_patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    
    # Truncar si es muy largo
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."
    
    return sanitized

def normalize_text(text: str) -> str:
    """Normaliza texto para comparaciones"""
    if not text:
        return ""
    
    # Convertir a minúsculas, remover acentos básicos y espacios extra
    normalized = text.lower().strip()
    
    # Reemplazos básicos de acentos
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ñ': 'n', 'ü': 'u'
    }
    
    for accented, normal in replacements.items():
        normalized = normalized.replace(accented, normal)
    
    # Remover espacios múltiples
    normalized = re.sub(r'\s+', ' ', normalized)
    
    return normalized

# ============================================
# UTILIDADES DE FECHA Y TIEMPO
# ============================================

def get_ecuadorian_datetime() -> datetime:
    """Obtiene fecha/hora actual en zona horaria de Ecuador (UTC-5)"""
    from datetime import datetime, timedelta
    utc_now = datetime.utcnow()
    ecuador_time = utc_now - timedelta(hours=5)
    return ecuador_time

def is_business_hours() -> bool:
    """Verifica si estamos en horario comercial (9 AM - 6 PM, Ecuador)"""
    ecuador_time = get_ecuadorian_datetime()
    
    # Lunes a Viernes, 9 AM a 6 PM
    if ecuador_time.weekday() >= 5:  # Sábado (5) y Domingo (6)
        return False
    
    hour = ecuador_time.hour
    return 9 <= hour < 18

def format_datetime_for_display(dt: datetime) -> str:
    """Formatea datetime para mostrar al usuario"""
    ecuador_time = dt - timedelta(hours=5) if dt.tzinfo is None else dt
    return ecuador_time.strftime("%d/%m/%Y %H:%M")

def calculate_session_expiry(minutes: int = 30) -> datetime:
    """Calcula tiempo de expiración de sesión"""
    return datetime.utcnow() + timedelta(minutes=minutes)

# ============================================
# UTILIDADES DE DATOS
# ============================================

def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """Carga JSON de manera segura"""
    if not json_str:
        return default
    
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default

def safe_json_dumps(data: Any, default: str = "{}") -> str:
    """Convierte a JSON de manera segura"""
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return default

def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Merge dos diccionarios de manera segura"""
    if not dict1:
        return dict2.copy() if dict2 else {}
    if not dict2:
        return dict1.copy()
    
    result = dict1.copy()
    result.update(dict2)
    return result

def extract_dict_fields(data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    """Extrae campos específicos de un diccionario"""
    return {field: data.get(field) for field in fields if field in data}

# ============================================
# UTILIDADES DE VALIDACIÓN
# ============================================

def validate_email(email: str) -> bool:
    """Valida formato de email"""
    if not email:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_income(income: Any) -> bool:
    """Valida que el ingreso sea un número válido"""
    try:
        value = float(income)
        return 0 < value <= 1000000  # Entre 0 y 1M
    except (ValueError, TypeError):
        return False

def validate_amount(amount: Any) -> bool:
    """Valida que el monto sea válido"""
    try:
        value = float(amount)
        return 0 < value <= 500000  # Entre 0 y 500k
    except (ValueError, TypeError):
        return False

def validate_employment_type(employment: str) -> bool:
    """Valida tipo de empleo"""
    valid_types = ["employee", "business_owner", "freelancer", "retired", "student", "unemployed", "other"]
    return employment in valid_types

# ============================================
# UTILIDADES DE SEGURIDAD
# ============================================

def generate_session_id(prefix: str = "session") -> str:
    """Genera ID de sesión único"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}_{timestamp}_{random_suffix}"

def hash_sensitive_data(data: str) -> str:
    """Hashea datos sensibles para logging"""
    return hashlib.sha256(data.encode()).hexdigest()[:16]

def mask_sensitive_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """Enmascara información sensible en diccionarios"""
    sensitive_fields = ['phone', 'email', 'user_id', 'campaign_id']
    
    masked = data.copy()
    for field in sensitive_fields:
        if field in masked and masked[field]:
            if field == 'phone':
                masked[field] = mask_phone_number(str(masked[field]))
            elif field == 'email':
                email = str(masked[field])
                if '@' in email:
                    local, domain = email.split('@', 1)
                    masked[field] = f"{local[:2]}***@{domain}"
            else:
                value = str(masked[field])
                masked[field] = f"{value[:4]}***{value[-4:]}" if len(value) > 8 else "***"
    
    return masked

# ============================================
# UTILIDADES DE LOGGING
# ============================================

def create_log_context(session_id: str, user_id: str = None, phone: str = None) -> Dict[str, Any]:
    """Crea contexto para logging estructurado"""
    context = {
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if user_id:
        context["user_id"] = hash_sensitive_data(user_id)
    
    if phone:
        context["phone"] = mask_phone_number(phone)
    
    return context

def log_conversation_event(event_type: str, session_id: str, details: Dict[str, Any] = None):
    """Logging estructurado para eventos de conversación"""
    import logging
    logger = logging.getLogger("conversation")
    
    log_data = {
        "event_type": event_type,
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if details:
        # Enmascarar datos sensibles antes de logging
        safe_details = mask_sensitive_info(details)
        log_data.update(safe_details)
    
    logger.info(json.dumps(log_data, ensure_ascii=False))

# ============================================
# UTILIDADES DE ANÁLISIS
# ============================================

def calculate_propensity_score(user_data: Dict[str, Any], collected_data: Dict[str, Any]) -> float:
    """Calcula score de propensión simple basado en datos"""
    score = 0.5  # Base score
    
    # Ajustar por segmento de cliente
    segment = user_data.get('customer_segment', 'standard')
    segment_multipliers = {
        'premium': 1.3,
        'standard': 1.0, 
        'basic': 0.8
    }
    score *= segment_multipliers.get(segment, 1.0)
    
    # Ajustar por ingresos
    monthly_income = collected_data.get('monthly_income')
    if monthly_income:
        if monthly_income > 5000:
            score *= 1.2
        elif monthly_income > 2000:
            score *= 1.1
        elif monthly_income < 1000:
            score *= 0.8
    
    # Ajustar por tipo de empleo
    employment = collected_data.get('employment_type')
    employment_multipliers = {
        'employee': 1.1,
        'business_owner': 1.2,
        'freelancer': 0.9,
        'retired': 0.8
    }
    if employment in employment_multipliers:
        score *= employment_multipliers[employment]
    
    # Mantener score entre 0.1 y 1.0
    return max(0.1, min(1.0, score))

def analyze_conversation_completion(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analiza el nivel de completitud de una conversación"""
    if not messages:
        return {"completion_rate": 0.0, "status": "not_started"}
    
    user_messages = [msg for msg in messages if msg.get("role") == "user"]
    agent_messages = [msg for msg in messages if msg.get("role") == "assistant"]
    
    analysis = {
        "total_messages": len(messages),
        "user_messages": len(user_messages),
        "agent_messages": len(agent_messages),
        "avg_message_length": sum(len(msg.get("content", "")) for msg in messages) / len(messages),
        "conversation_duration": None
    }
    
    # Calcular duración si hay timestamps
    if messages and "timestamp" in messages[0] and "timestamp" in messages[-1]:
        try:
            start = datetime.fromisoformat(messages[0]["timestamp"].replace('Z', '+00:00'))
            end = datetime.fromisoformat(messages[-1]["timestamp"].replace('Z', '+00:00'))
            analysis["conversation_duration"] = (end - start).total_seconds()
        except:
            pass
    
    # Determinar completion rate basado en número de intercambios
    if len(user_messages) >= 4 and len(agent_messages) >= 4:
        analysis["completion_rate"] = 1.0
        analysis["status"] = "completed"
    elif len(user_messages) >= 2:
        analysis["completion_rate"] = 0.7
        analysis["status"] = "partial"
    else:
        analysis["completion_rate"] = 0.3
        analysis["status"] = "early_stage"
    
    return analysis

# ============================================
# UTILIDADES DE CONFIGURACIÓN
# ============================================

def get_product_config(product_type: str) -> Dict[str, Any]:
    """Obtiene configuración específica por tipo de producto"""
    configs = {
        "credit_card": {
            "max_limit": 50000,
            "min_income": 500,
            "approval_threshold": 0.6,
            "required_fields": ["monthly_income", "employment_type", "requested_amount"]
        },
        "credit": {
            "max_amount": 200000,
            "min_income": 800,
            "approval_threshold": 0.7,
            "required_fields": ["monthly_income", "employment_type", "requested_amount"]
        },
        "insurance": {
            "max_premium": 1000,
            "min_income": 300,
            "approval_threshold": 0.5,
            "required_fields": ["monthly_income", "employment_type", "coverage_type"]
        },
        "savings": {
            "min_amount": 50,
            "min_income": 200,
            "approval_threshold": 0.4,
            "required_fields": ["monthly_income", "savings_goal"]
        }
    }
    
    return configs.get(product_type, configs["credit_card"])

def validate_collected_data(collected_data: Dict[str, Any], product_type: str) -> Dict[str, Any]:
    """Valida datos recolectados contra configuración del producto"""
    config = get_product_config(product_type)
    validation_result = {
        "is_valid": True,
        "missing_fields": [],
        "invalid_fields": [],
        "warnings": []
    }
    
    # Verificar campos requeridos
    required_fields = config.get("required_fields", [])
    for field in required_fields:
        if field not in collected_data or not collected_data[field]:
            validation_result["missing_fields"].append(field)
    
    # Validar valores específicos
    if "monthly_income" in collected_data:
        income = collected_data["monthly_income"]
        min_income = config.get("min_income", 0)
        
        if not validate_income(income):
            validation_result["invalid_fields"].append("monthly_income")
        elif float(income) < min_income:
            validation_result["warnings"].append(f"Income below minimum: {min_income}")
    
    # Determinar validez general
    validation_result["is_valid"] = (
        len(validation_result["missing_fields"]) == 0 and 
        len(validation_result["invalid_fields"]) == 0
    )
    
    return validation_result