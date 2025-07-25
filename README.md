# 🤖 Agent-BG: Sistema de Agente Conversacional Bancario

Un sistema completo de agente conversacional inteligente para captación de leads bancarios, integrando WhatsApp con IA avanzada y gestión de campañas.

## 📋 Descripción

Agent-BG es una solución integral que combina:
- **Bot de WhatsApp** con BuilderBot y Baileys
- **API Backend** con FastAPI y PostgreSQL
- **Motor de IA** con OpenAI GPT-4
- **Sistema de Campañas** con reglas de activación y guardrails

## 🏗️ Arquitectura del Proyecto

```
agent-bg/
├── bot-wsp/          # Bot de WhatsApp (TypeScript/Node.js)
├── server/           # API Backend (Python/FastAPI)
└── sql/             # Esquemas de base de datos
```

## 🚀 Componentes Principales

### 1. Bot de WhatsApp (`bot-wsp/`)

**Tecnologías:**
- TypeScript + Node.js
- BuilderBot Framework
- Baileys Provider
- OpenAI GPT-4
- PostgreSQL

**Características:**
- Conversaciones inteligentes con IA
- Integración con API externa
- Validación de datos con IA
- Respuestas personalizadas
- Gestión de estados de usuario

### 2. API Backend (`server/`)

**Tecnologías:**
- FastAPI (Python)
- PostgreSQL
- OpenAI
- LangChain
- Pydantic

**Características:**
- Gestión de clientes y campañas
- Webhooks para integración
- Motor de reglas de negocio
- Sistema de guardrails
- Logging avanzado

### 3. Base de Datos (`sql/`)

**Esquemas principales:**
- `campaigns` - Gestión de campañas
- `campaign_users` - Usuarios en campañas
- `activation_rules` - Reglas de activación
- `campaign_guardrails` - Protecciones de campaña
- `user_events` - Eventos de usuarios

## 🛠️ Instalación y Configuración

### Prerrequisitos

- Node.js 18+
- Python 3.9+
- PostgreSQL 13+
- Cuenta de OpenAI

### 1. Configurar el Bot de WhatsApp

```bash
cd bot-wsp
npm install
```

Crear archivo `.env`:
```env
OPENAI_API_KEY=tu_api_key_de_openai
EXTERNAL_API_URL=http://localhost:8000
PORT=3008
```

### 2. Configurar el Servidor Backend

```bash
cd server
pip install -r requirements.txt
```

Crear archivo `.env`:
```env
SUPABASE_DATABASE_URL=postgresql://usuario:password@localhost:5432/database
OPENAI_API_KEY=tu_api_key_de_openai
BUILDERBOT_URL=http://localhost:3008
```

### 3. Configurar Base de Datos

```bash
# Ejecutar el script SQL
psql -d tu_database -f sql/tables.sql
```

## 🚀 Ejecución

### 1. Iniciar el Servidor Backend

```bash
cd server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Iniciar el Bot de WhatsApp

```bash
cd bot-wsp
npm run dev
```

## 📡 API Endpoints

### Backend (`http://localhost:8000`)

- `GET /` - Información del servicio
- `GET /health` - Estado de salud
- `GET /client/{phone}` - Información del cliente
- `GET /campanas/{phone}` - Campañas del cliente
- `POST /lead/{phone}` - Enviar lead aceptado

### Webhooks

- `POST /webhook/builderbot` - Webhook para BuilderBot
- `POST /webhook/campaign` - Webhook para campañas

## 🤖 Flujo de Conversación

1. **Recepción de mensaje** - Bot recibe mensaje en WhatsApp
2. **Análisis de intención** - IA analiza la intención del usuario
3. **Consulta de datos** - Se consulta información del cliente
4. **Personalización** - Respuesta adaptada al perfil del cliente
5. **Recolección de datos** - Captura de información del lead
6. **Validación** - Validación de datos con IA
7. **Envío de lead** - Envío a sistema externo

## 🎯 Características Avanzadas

### Sistema de Campañas
- Gestión de múltiples campañas
- Segmentación de usuarios
- Reglas de activación personalizadas
- Guardrails de protección

### IA Inteligente
- Análisis de intención en tiempo real
- Respuestas personalizadas
- Validación de datos con IA
- Generación de saludos contextuales

### Seguridad y Control
- Guardrails de frecuencia
- Límites de presupuesto
- Cooldowns automáticos
- Validación de datos

## 🔧 Desarrollo

### Scripts Disponibles

**Bot de WhatsApp:**
```bash
npm run dev      # Desarrollo con hot reload
npm run build    # Compilar para producción
npm start        # Ejecutar en producción
npm run lint     # Linting
```

**Servidor Backend:**
```bash
# Ejecutar con uvicorn
uvicorn app.main:app --reload

# Ejecutar tests
python -m pytest app/test/
```

## 📊 Monitoreo

### Logs
- `bot-wsp/core.class.log` - Logs del bot
- `bot-wsp/queue.class.log` - Logs de cola
- `server/rules_engine.log` - Logs del motor de reglas

### Métricas
- Estado de salud en `/health`
- Información del servicio en `/info`
- Logs estructurados en ambos componentes

## 🐳 Docker

### Bot de WhatsApp
```bash
cd bot-wsp
docker build -t agent-bg-bot .
docker run -p 3008:3008 agent-bg-bot
```

### Servidor Backend
```bash
cd server
docker build -t agent-bg-server .
docker run -p 8000:8000 agent-bg-server
```

## 📝 Variables de Entorno

### Bot de WhatsApp
- `OPENAI_API_KEY` - API Key de OpenAI
- `EXTERNAL_API_URL` - URL del servidor backend
- `PORT` - Puerto del bot (default: 3008)

### Servidor Backend
- `SUPABASE_DATABASE_URL` - URL de conexión a PostgreSQL
- `OPENAI_API_KEY` - API Key de OpenAI
- `BUILDERBOT_URL` - URL del bot de WhatsApp

## 🤝 Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia ISC.

## 🆘 Soporte

- **Documentación:** Revisa los READMEs específicos en cada carpeta
- **Issues:** Reporta problemas en GitHub Issues
- **Discord:** Únete a la comunidad de BuilderBot

---

**Desarrollado con ❤️ para automatizar la captación de leads bancarios** 
