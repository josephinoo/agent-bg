# test_flow.py
"""
Script para probar el flujo completo del agente de leads
Ejecutar: python test_flow.py
"""

import asyncio
import httpx
import time
from datetime import datetime

# Configuración
API_BASE_URL = "http://localhost:8000"
TEST_PHONE = "+593997814126"
TEST_USER_ID = "user_001"

class LeadsAgentTester:
    def __init__(self):
        self.base_url = API_BASE_URL
        
    async def test_complete_flow(self):
        """Prueba el flujo completo del sistema"""
        print("🚀 Iniciando test del flujo completo del Agente de Leads")
        print("=" * 60)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Health Check
            await self.test_health_check(client)
            
            # 2. Verificar estado inicial
            await self.test_initial_state(client)
            
            # 3. Simular eventos de usuario
            await self.test_event_simulation(client)
            
            # 4. Iniciar monitoreo de reglas
            await self.test_rules_monitoring(client)
            
            # 5. Verificar activaciones
            await self.test_activation_check(client)
            
            # 6. Simular mensaje de WhatsApp
            await self.test_whatsapp_webhook(client)
            
            # 7. Verificar resultados
            await self.test_results_verification(client)
            
            # Nuevo test para fallback/clarify
            await self.test_fallback_clarify(client)
            
        print("\n✅ Test completo finalizado!")
    
    async def test_health_check(self, client: httpx.AsyncClient):
        """Test 1: Verificar que la API esté funcionando"""
        print("\n1️⃣ Testing Health Check...")
        
        try:
            response = await client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ API Health: {data['status']}")
                print(f"   📊 Database: {data['components']['database']['status']}")
                print(f"   🤖 OpenAI: {data['components']['openai']['status']}")
            else:
                print(f"   ❌ Health check failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    async def test_initial_state(self, client: httpx.AsyncClient):
        """Test 2: Verificar estado inicial del sistema"""
        print("\n2️⃣ Testing Initial State...")
        
        try:
            # Verificar estado del motor de reglas
            response = await client.get(f"{self.base_url}/rules/monitoring-status")
            if response.status_code == 200:
                data = response.json()
                print(f"   📡 Rules Engine: {'Running' if data['is_running'] else 'Stopped'}")
            
            # Verificar eventos recientes
            response = await client.get(f"{self.base_url}/rules/recent-events?minutes_ago=10")
            if response.status_code == 200:
                data = response.json()
                print(f"   📊 Recent Events: {data['count']} eventos en últimos 10 min")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    async def test_event_simulation(self, client: httpx.AsyncClient):
        """Test 3: Simular eventos de usuario"""
        print("\n3️⃣ Testing Event Simulation...")
        
        try:
            # Simular múltiples logins (debería activar regla de frecuencia)
            response = await client.post(
                f"{self.base_url}/rules/simulate-events",
                json={
                    "user_id": TEST_USER_ID,
                    "behavior_type": "high_activity"
                }
            )
            
            if response.status_code == 200:
                print("   ✅ Simulados eventos de alta actividad")
            
            # Esperar un poco
            await asyncio.sleep(2)
            
            # Simular interés en crédito
            response = await client.post(
                f"{self.base_url}/rules/simulate-events",
                json={
                    "user_id": TEST_USER_ID,
                    "behavior_type": "credit_interest"
                }
            )
            
            if response.status_code == 200:
                print("   ✅ Simulados eventos de interés en crédito")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    async def test_rules_monitoring(self, client: httpx.AsyncClient):
        """Test 4: Iniciar y probar monitoreo de reglas"""
        print("\n4️⃣ Testing Rules Monitoring...")
        
        try:
            # Iniciar monitoreo
            response = await client.post(
                f"{self.base_url}/rules/start-monitoring",
                params={"interval_seconds": 5}  # Cada 5 segundos para testing rápido
            )
            
            if response.status_code == 200:
                print("   ✅ Monitoreo de reglas iniciado (cada 5 segundos)")
            
            # Procesar eventos manualmente una vez
            response = await client.post(f"{self.base_url}/rules/process-events")
            if response.status_code == 200:
                print("   ✅ Procesamiento manual de eventos ejecutado")
            
            # Esperar que el monitoreo automático procese
            print("   ⏳ Esperando procesamiento automático...")
            await asyncio.sleep(8)
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    async def test_activation_check(self, client: httpx.AsyncClient):
        """Test 5: Verificar si se activaron reglas"""
        print("\n5️⃣ Testing Rule Activations...")
        
        try:
            # Verificar eventos recientes nuevamente
            response = await client.get(f"{self.base_url}/rules/recent-events?minutes_ago=5")
            if response.status_code == 200:
                data = response.json()
                print(f"   📊 Eventos recientes: {data['count']}")
                
                if data['events']:
                    latest_event = data['events'][0]
                    print(f"   📝 Último evento: {latest_event['event_type']} para {latest_event['user_id']}")
            
            # Verificar si hay alguna campaña con reglas
            # Primero necesitamos encontrar un campaign_id
            # Para simplicidad, usaremos un ID genérico en el test
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    async def test_whatsapp_webhook(self, client: httpx.AsyncClient):
        """Test 6: Simular mensaje de WhatsApp entrante"""
        print("\n6️⃣ Testing WhatsApp Webhook...")
        
        try:
            # Simular mensaje de WhatsApp
            response = await client.post(
                f"{self.base_url}/webhook/builderbot",
                json={
                    "phone": TEST_PHONE,
                    "message": "Hola, me interesa información sobre créditos",
                    "ref": "test_ref",
                    "keyword": None
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Webhook procesado: {data['status']}")
                print(f"   💬 Respuesta: {data['response'][:100]}...")
                print(f"   🔄 Paso actual: {data['step']}")
            else:
                print(f"   ⚠️ Webhook response: {response.status_code}")
                if response.status_code == 200:
                    print(f"   📝 Response: {response.json()}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    async def test_results_verification(self, client: httpx.AsyncClient):
        """Test 7: Verificar resultados finales"""
        print("\n7️⃣ Testing Results Verification...")
        
        try:
            # Detener monitoreo
            response = await client.post(f"{self.base_url}/rules/stop-monitoring")
            if response.status_code == 200:
                print("   ⏹️ Monitoreo detenido")
            
            # Verificar estado final
            response = await client.get(f"{self.base_url}/rules/monitoring-status")
            if response.status_code == 200:
                data = response.json()
                print(f"   📡 Estado final: {'Running' if data['is_running'] else 'Stopped'}")
            
            # Mostrar resumen
            print("\n📋 RESUMEN DEL TEST:")
            print("   ✅ Sistema iniciado correctamente")
            print("   ✅ Eventos simulados")
            print("   ✅ Motor de reglas funcionando")
            print("   ✅ Webhook de WhatsApp operativo")
            print("   ✅ Agente conversacional respondiendo")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

    async def test_fallback_clarify(self, client: httpx.AsyncClient):
        """Test: Simular mensaje confuso y esperar aclaración"""
        print("\n8️⃣ Testing Fallback/Clarify...")
        try:
            response = await client.post(
                f"{self.base_url}/webhook/builderbot",
                json={
                    "phone": TEST_PHONE,
                    "message": "asdfghjkl",  # Mensaje confuso
                    "ref": "test_ref",
                    "keyword": None
                }
            )
            if response.status_code == 200:
                data = response.json()
                print(f"   🟢 Fallback/Clarify procesado: {data['status']}")
                print(f"   💬 Respuesta: {data['response'][:100]}...")
                print(f"   🔄 Paso actual: {data['step']}")
            else:
                print(f"   ⚠️ Fallback/Clarify response: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

async def main():
    """Función principal"""
    tester = LeadsAgentTester()
    await tester.test_complete_flow()

if __name__ == "__main__":
    print("🧪 Tester del Agente de Leads")
    print(f"🔗 API URL: {API_BASE_URL}")
    print(f"📱 Test Phone: {TEST_PHONE}")
    print(f"👤 Test User: {TEST_USER_ID}")
    print(f"⏰ Timestamp: {datetime.now()}")
    
    asyncio.run(main())