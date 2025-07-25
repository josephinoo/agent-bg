# app/services/builderbot_service.py
import httpx
import logging
from typing import Dict, Any, Optional
from app.config import settings
import uuid

logger = logging.getLogger(__name__)

def make_json_serializable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(v) for v in obj]
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    return obj

class BuilderBotService:
    """Servicio para comunicación con BuilderBot"""
    
    def __init__(self):
        self.base_url = settings.builderbot_url
        self.timeout = settings.builderbot_timeout
    
    async def send_message(self, phone: str, message: str, media_url: Optional[str] = None) -> bool:
        """Envía mensaje a través de BuilderBot"""

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "number": phone,
                    "message": message
                }
                
                if media_url:
                    payload["urlMedia"] = media_url
                
                response = await client.post(
                    f"{self.base_url}/send-message",
                    json=payload
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Mensaje enviado a {phone}: {message[:50]}...")
                    return True
                else:
                    logger.error(f"❌ Error enviando mensaje a {phone}: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error conectando con BuilderBot: {e}")
            return False
    
    async def trigger_flow(self, phone: str, flow_name: str, data: Dict[str, Any] = None) -> bool:
        """Trigger un flujo específico en BuilderBot"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "number": phone,
                    "name": flow_name
                }
                
                if data:
                    payload.update(make_json_serializable(data))
                
                endpoint_map = {
                    "REGISTER_FLOW": "/v1/register",
                    "AGENT_FLOW": "/trigger-agent"
                }
                
                endpoint = endpoint_map.get(flow_name, "/v1/register")
                
                response = await client.post(
                    f"{self.base_url}{endpoint}",
                    json=payload
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Flujo {flow_name} activado para {phone}")
                    return True
                else:
                    logger.error(f"❌ Error activando flujo {flow_name}: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error triggering flujo {flow_name}: {e}")
            return False
    
    async def add_to_blacklist(self, phone: str) -> bool:
        """Agrega número a blacklist de BuilderBot"""
        return await self._manage_blacklist(phone, "add")
    
    async def remove_from_blacklist(self, phone: str) -> bool:
        """Remueve número de blacklist de BuilderBot"""
        return await self._manage_blacklist(phone, "remove")
    
    async def _manage_blacklist(self, phone: str, action: str) -> bool:
        """Gestiona blacklist de BuilderBot"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "number": phone,
                    "intent": action
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/blacklist",
                    json=payload
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ {action} blacklist para {phone}")
                    return True
                else:
                    logger.error(f"❌ Error {action} blacklist para {phone}: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error {action} blacklist para {phone}: {e}")
            return False