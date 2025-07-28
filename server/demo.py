import requests
import json

# Lista de contactos con números y mensajes personalizados
contacts = [
    # {
    #     "number": "+593981134169",
    #     "message": "Hola Jhon 🚀"
    # },
    # {
    #     "number": "+593995093295", 
    #     "message": "Hola Diego 🚀"
    # },
    # {
    #     "number": "+593994370212",
    #     "message": "Hola Marlon 🚀"
    # },
    # {
    #     "number": "+593996999151",
    #     "message": "Hola Victor 🚀"
    # },
    {
        "number": "+593967655522",
        "message": "Hola Jeremy 🚀"
    },
       {
        "number": "+593967655522",
        "message": "Hola Jeremy 🚀"
    },
       {
        "number": "+593967655522",
        "message": "Hola Jeremy 🚀"
    },
    
]



# URL del endpoint
url = "http://localhost:3008/send-message"

# Función para enviar mensajes
def send_whatsapp_messages():
    for contact in contacts:
        try:
            # Realizar POST request
            response = requests.post(
                url, 
                json=contact,
                headers={'Content-Type': 'application/json'}
            )
   

            # Verificar respuesta
            if response.status_code == 200:
                print(f"✅ Mensaje enviado exitosamente a {contact['number']}")
                print(f"   Respuesta: {response.text}")
            else:
                print(f"❌ Error enviando mensaje a {contact['number']}")
                print(f"   Status Code: {response.status_code}")
                print(f"   Respuesta: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error de conexión enviando a {contact['number']}: {e}")
        
        print("-" * 50)

# Ejecutar el envío de mensajes
if __name__ == "__main__":
    print("🚀 Iniciando envío de mensajes WhatsApp...")
    print("=" * 50)
    send_whatsapp_messages()
    print("✨ Proceso completado!")