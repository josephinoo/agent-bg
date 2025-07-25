import 'dotenv/config'
import { createBot, createProvider, createFlow, addKeyword } from '@builderbot/bot'
import { PostgreSQLAdapter as Database } from '@builderbot/database-postgres'
import { BaileysProvider as Provider } from '@builderbot/provider-baileys'
import axios from 'axios'

const PORT = process.env.PORT ?? 3008
const AGENT_API_URL = process.env.AGENT_API_URL ?? 'http://localhost:8000'

// Envío al webhook del agente
const sendToAgent = async (phone: string, message: string): Promise<string | null> => {
    try {
        const cleanPhone = phone.replace(/[^\d+]/g, '')
        const formattedPhone = cleanPhone.startsWith('+') ? cleanPhone : 
                              cleanPhone.startsWith('593') ? `+${cleanPhone}` : 
                              `+593${cleanPhone.replace(/^0+/, '')}`

        const response = await axios.post(`${AGENT_API_URL}/webhook/builderbot`, {
            phone: formattedPhone,
            message: message.trim()
        }, {
            headers: { 'Content-Type': 'application/json' },
            timeout: 15000
        })

        if (response.data?.response && typeof response.data.response === 'string') {
            return response.data.response
        }
        
        return null

    } catch (error) {
        console.log(`❌ Error enviando al agente: ${error.message}`)
        return null
    }
}

// Flujo para recibir mensajes
const mainFlow = addKeyword<Provider, Database>('')
    .addAction(async (ctx, { flowDynamic, endFlow }) => {
        console.log(`📨 Mensaje recibido de ${ctx.from}: ${ctx.body}`)
        
        // Enviar al agente
        const agentResponse = await sendToAgent(ctx.from, ctx.body)
        
        // Si hay respuesta del agente, enviarla
        if (agentResponse) {
            await flowDynamic(agentResponse)
        }
        
        return endFlow()
    })

const main = async () => {
    const adapterFlow = createFlow([mainFlow])
    const adapterProvider = createProvider(Provider)

    const adapterDB = new Database({
        host: process.env.POSTGRES_DB_HOST,
        port: parseInt(process.env.POSTGRES_DB_PORT ?? '5432'),
        user: process.env.POSTGRES_DB_USER,
        password: process.env.POSTGRES_DB_PASSWORD,
        database: process.env.POSTGRES_DB_NAME
    })

    const { httpServer, handleCtx } = await createBot({
        flow: adapterFlow,
        provider: adapterProvider,
        database: adapterDB
    })

    // Endpoint para enviar mensajes
    adapterProvider.server.post('/send-message', handleCtx(async (bot, req, res) => {
        const { number, message } = req.body
        
        if (!number || !message) {
            res.writeHead(400, { 'Content-Type': 'application/json' })
            return res.end(JSON.stringify({ 
                status: 'error', 
                error: 'Faltan parámetros: number y message son requeridos' 
            }))
        }

        try {
            await bot.sendMessage(number, message, {})
            console.log(`✅ Mensaje enviado a ${number}`)
            
            res.writeHead(200, { 'Content-Type': 'application/json' })
            return res.end(JSON.stringify({ 
                status: 'sent', 
                number, 
                message 
            }))
            
        } catch (error) {
            console.log(`❌ Error enviando mensaje: ${error.message}`)
            
            res.writeHead(500, { 'Content-Type': 'application/json' })
            return res.end(JSON.stringify({ 
                status: 'error', 
                error: error.message 
            }))
        }
    }))

    // Endpoint para disparar agente (opcional)
    adapterProvider.server.post('/trigger-agent', handleCtx(async (bot, req, res) => {
        const { number, message } = req.body
        console.log(`🤖 Trigger agent: ${number} - ${message}`)
        
        res.writeHead(200, { 'Content-Type': 'application/json' })
        return res.end(JSON.stringify({ status: 'success' }))
    }))

    // Health check
    adapterProvider.server.get('/health', handleCtx(async (bot, req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' })
        return res.end(JSON.stringify({
            status: 'healthy',
            service: 'BuilderBot WhatsApp',
            timestamp: new Date().toISOString()
        }))
    }))

    // Iniciar servidor
    httpServer(+PORT)
    console.log(`✅ BuilderBot iniciado en puerto ${PORT}`)
}

main().catch(err => {
    console.error('❌ Error:', err.message)
    process.exit(1)
})