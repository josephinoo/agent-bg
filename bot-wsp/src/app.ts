import 'dotenv/config'
import { createBot, createProvider, createFlow, addKeyword } from '@builderbot/bot'
import { PostgreSQLAdapter as Database } from '@builderbot/database-postgres'
import { BaileysProvider as Provider } from '@builderbot/provider-baileys'
import OpenAI from 'openai'
import axios from 'axios'
import { getIntention, buildConversationHistory, IntentionResult } from './ai/catch-intention'

// --- Configuración ---
const openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY,
});

const PORT = process.env.PORT ?? 3008
const EXTERNAL_API_URL = process.env.EXTERNAL_API_URL ?? 'http://localhost:8000'

interface UserState {
    step: string;
    name?: string;
    salary?: string;
    company?: string;
    selectedProduct?: string;
    amount?: string;
    additionalInfo?: string;
    conversationHistory?: string[];
    retryCount?: number;
    clientData?: any;
    campaignData?: any;
}

const userStates = new Map<string, UserState>()

/**
 * Consultar información del cliente desde API externa
 */
const getClientInfo = async (phoneNumber: string): Promise<any> => {
    try {
        console.log(`🔍 Consultando información del cliente: ${phoneNumber}`)
        
        const cleanPhone = phoneNumber.replace(/[^\d+]/g, '')
        const response = await axios.get(`${EXTERNAL_API_URL}/client/${cleanPhone}`, {
            timeout: 10000,
            headers: {
                'Content-Type': 'application/json'
            }
        })
        
        console.log(`✅ Información del cliente obtenida:`, response.data)
        return response.data
        
    } catch (error: any) {
        console.log(`❌ Error consultando cliente: ${error.message}`)
        return null
    }
}

/**
 * Consultar campañas activas para el cliente
 */
const getCampaignInfo = async (phoneNumber: string): Promise<any> => {
    try {
        console.log(`🎯 Consultando campañas para: ${phoneNumber}`)
        
        const cleanPhone = phoneNumber.replace(/[^\d+]/g, '')
        const response = await axios.get(`${EXTERNAL_API_URL}/campanas/${cleanPhone}`, {
            timeout: 10000,
            headers: {
                'Content-Type': 'application/json'
            }
        })
        
        console.log(`✅ Campañas obtenidas:`, response.data)
        return response.data
        
    } catch (error: any) {
        console.log(`❌ Error consultando campañas: ${error.message}`)
        return null
    }
}

/**
 * Enviar lead aceptado a API externa
 */
const sendLeadAccepted = async (phoneNumber: string, leadData: any): Promise<boolean> => {
    try {
        console.log(`📤 Enviando lead aceptado: ${phoneNumber}`)
        
        const cleanPhone = phoneNumber.replace(/[^\d+]/g, '')
        const response = await axios.post(`${EXTERNAL_API_URL}/lead/${cleanPhone}`, leadData, {
            timeout: 15000,
            headers: {
                'Content-Type': 'application/json'
            }
        })
        
        console.log(`✅ Lead enviado exitosamente:`, response.data)
        return true
        
    } catch (error: any) {
        console.log(`❌ Error enviando lead: ${error.message}`)
        return false
    }
}

/**
 * Sistema de saludos variados basado en contexto real del cliente
 */
const generateVariedGreeting = (clientData: any, campaignData: any, userName: string): string => {
    const hasActiveCampaigns = campaignData && campaignData.active_campaigns && campaignData.active_campaigns.length > 0
    const campaign = hasActiveCampaigns ? campaignData.active_campaigns[0] : null
    const productType = campaign?.product || 'general'
    const maxAmount = campaign?.max_amount || 0
    const customerSegment = clientData?.customer_segment || 'standard'
    const creditScore = clientData?.score || 0
    const monthlyIncome = clientData?.monthly_income || 0
    
    const greetingTemplates = {
        'credit_card': [
            `¡Hola ${userName}! 🎯 Soy tu asesor de Banco Guayaquil. Vi que has consultado sobre tarjetas de crédito y quiero ofrecerte algo especial. ¿Conversamos?`,
            `${userName}, ¡qué tal! 👋 Te escribo porque detecté tu interés en tarjetas de crédito. Tengo una propuesta personalizada para ti. ¿Te interesa?`,
            `¡Buenas ${userName}! 💳 Desde Banco Guayaquil te contacto porque vi tu actividad sobre tarjetas. Tengo condiciones exclusivas que podrían gustarte. ¿Hablamos?`,
            `Hola ${userName} 😊 Tu asesor de Banco Guayaquil aquí. Noté que buscas una tarjeta de crédito y puedo ayudarte con algo mejor de lo que imaginabas. ¿Te parece si vemos opciones?`
        ],
        'credito_personal': [
            `¡Hola ${userName}! 💰 Soy de Banco Guayaquil y vi que necesitas un crédito personal. Tengo opciones que podrían encajar perfecto con tu perfil. ¿Te cuento?`,
            `${userName}, ¡buenas! 🚀 Te contacto porque detectamos tu interés en financiamiento personal. Hay algo interesante que ofrecerte. ¿Conversamos?`,
            `¡Qué tal ${userName}! 👋 Desde Banco Guayaquil te escribo por tu consulta sobre créditos. Creo que puedo sorprenderte con las condiciones. ¿Te interesa escuchar?`,
            `Hola ${userName} 😊 Tu asesor bancario aquí. Vi tu búsqueda de crédito personal y tengo propuestas que van a gustarte. ¿Dedicamos unos minutos?`
        ],
        'credito_vehicular': [
            `¡Hola ${userName}! 🚗 Te contacto de Banco Guayaquil porque vi tu interés en financiar un vehículo. Tengo tasas especiales que deberías conocer. ¿Hablamos?`,
            `${userName}, ¡buenas! 🎯 Soy tu asesor de Banco Guayaquil. Detecté que buscas crédito vehicular y puedo ofrecerte condiciones preferenciales. ¿Te interesa?`,
            `¡Qué tal ${userName}! 🚀 Desde el banco te escribo por tu consulta sobre financiamiento de autos. Hay algo bueno que mostrarte. ¿Conversamos?`,
            `Hola ${userName} 👋 Tu asesor bancario aquí. Vi que planeas comprar un vehículo y tengo propuestas que podrían facilitarte todo. ¿Te cuento?`
        ],
        'credito_hipotecario': [
            `¡Hola ${userName}! 🏠 Te contacto de Banco Guayaquil por tu interés en crédito hipotecario. Tengo condiciones especiales para tu casa soñada. ¿Conversamos?`,
            `${userName}, ¡buenas! 🎯 Soy de Banco Guayaquil y vi tu búsqueda de crédito para vivienda. Puedo ofrecerte algo muy competitivo. ¿Te interesa?`,
            `¡Qué tal ${userName}! 🚀 Desde el banco te escribo porque detecté tu proyecto inmobiliario. Hay financiamiento que te va a convenir. ¿Hablamos?`,
            `Hola ${userName} 😊 Tu asesor hipotecario aquí. Vi tu interés en financiar vivienda y tengo propuestas que podrían sorprenderte. ¿Te cuento?`
        ],
        'general': [
            `¡Hola ${userName}! 👋 Soy tu asesor de Banco Guayaquil. Vi tu actividad y quiero ofrecerte productos que se ajusten a tu perfil. ¿Conversamos?`,
            `${userName}, ¡buenas! 🎯 Te contacto porque detectamos tu interés en nuestros servicios financieros. Tengo algo personalizado para ti. ¿Te interesa?`,
            `¡Qué tal ${userName}! 💫 Desde Banco Guayaquil te escribo para ofrecerte opciones que podrían interesarte según tu perfil. ¿Hablamos?`,
            `Hola ${userName} 😊 Tu asesor bancario aquí. Quiero mostrarte productos financieros que van perfectos con lo que buscas. ¿Te parece si conversamos?`
        ]
    }
    
    const templates = greetingTemplates[productType] || greetingTemplates['general']
    
    let templateIndex = 0
    
    if (customerSegment === 'premium' && creditScore > 750) {
        templateIndex = 0
    } else if (monthlyIncome > 2000) {
        templateIndex = 1
    } else if (creditScore > 600) {
        templateIndex = 2
    } else {
        templateIndex = 3
    }
    
    templateIndex = templateIndex % templates.length
    
    let greeting = templates[templateIndex]
    
    if (hasActiveCampaigns && maxAmount > 0) {
        const amountText = maxAmount >= 10000 ? 
            `hasta $${Math.floor(maxAmount/1000)}k` : 
            `hasta $${maxAmount.toLocaleString()}`
        
        if (productType === 'credit_card') {
            greeting += ` Límites ${amountText} disponibles.`
        } else if (productType.includes('credito')) {
            greeting += ` Montos ${amountText} con excelentes tasas.`
        }
    }
    
    return greeting
}

/**
 * Sistema de saludos por hora del día
 */
const generateTimeBasedGreeting = (clientData: any, campaignData: any, userName: string): string => {
    const hour = new Date().getHours()
    const campaign = campaignData?.active_campaigns?.[0]
    const productType = campaign?.product || 'general'
    
    let timeGreeting = ''
    if (hour < 12) {
        timeGreeting = 'Buenos días'
    } else if (hour < 18) {
        timeGreeting = 'Buenas tardes'
    } else {
        timeGreeting = 'Buenas noches'
    }
    
    const contextualMessages = {
        'credit_card': `${timeGreeting} ${userName} 💳 Te contacto de Banco Guayaquil porque vi tu interés en tarjetas de crédito. ¿Te parece si revisamos las mejores opciones para ti?`,
        'credito_personal': `${timeGreeting} ${userName} 💰 Soy tu asesor de Banco Guayaquil. Detecté que buscas un crédito personal y tengo propuestas interesantes. ¿Conversamos?`,
        'credito_vehicular': `${timeGreeting} ${userName} 🚗 Te escribo de Banco Guayaquil por tu consulta sobre crédito vehicular. Hay condiciones que podrían gustarte. ¿Hablamos?`,
        'credito_hipotecario': `${timeGreeting} ${userName} 🏠 Desde Banco Guayaquil te contacto por tu interés hipotecario. Tengo financiamiento especial para tu proyecto. ¿Te cuento?`,
        'general': `${timeGreeting} ${userName} 👋 Soy de Banco Guayaquil y quiero ofrecerte productos financieros que se ajusten a tu perfil. ¿Te interesa conversar?`
    }
    
    return contextualMessages[productType] || contextualMessages['general']
}

/**
 * Selector principal de saludo
 */
const generatePersonalizedGreeting = (clientData: any, campaignData: any, userName: string): string => {
    const greetingStyles = [
        () => generateVariedGreeting(clientData, campaignData, userName)
    ]
    
    const styleIndex = Math.floor(Date.now() / 1000) % greetingStyles.length
    
    return greetingStyles[styleIndex]()
}

/**
 * Validación inteligente con IA
 */
const validateDataWithAI = async (data: string, dataType: 'salary' | 'company' | 'amount', userName: string): Promise<{isValid: boolean, message?: string, extractedValue?: string}> => {
    try {
        let prompt = ''
        
        if (dataType === 'salary') {
            prompt = `
            El cliente ${userName} dice que su sueldo es: "${data}"
            
            VALIDA si esto es un sueldo válido:
            - Debe ser un número positivo
            - Puede incluir palabras como "dólares", "mil", "k"  
            - Ejemplo válido: "2500", "2,500", "2500 dólares", "2.5k", "dos mil quinientos"
            - Ejemplo inválido: "no tengo", "mucho", "poco", "-500", "0", números negativos
            
            Si es válido, extrae SOLO el número en formato limpio.
            Si no es válido, explica por qué de forma amigable y humana.
            
            Responde en formato JSON:
            {"isValid": true/false, "extractedValue": "número_limpio", "message": "explicación_humana"}
            `
        } else if (dataType === 'company') {
            prompt = `
            El cliente ${userName} dice que trabaja en: "${data}"
            
            VALIDA si esto es una empresa/trabajo válido:
            - Debe ser un nombre de empresa, institución o tipo de trabajo
            - Ejemplo válido: "Banco Guayaquil", "Google", "soy independiente", "trabajo por mi cuenta"
            - Ejemplo inválido: "no trabajo", "desempleado", "nada", respuestas vagas
            
            Si es válido, limpia el texto.
            Si no es válido, pregunta de forma empática.
            
            Responde en formato JSON:
            {"isValid": true/false, "extractedValue": "empresa_limpia", "message": "explicación_humana"}
            `
        } else if (dataType === 'amount') {
            prompt = `
            El cliente ${userName} solicita un monto de: "${data}"
            
            VALIDA si esto es un monto válido:
            - Debe ser un número positivo mayor a $1,000
            - Puede incluir palabras como "dólares", "mil", "k"
            - Ejemplo válido: "15000", "15,000", "15k", "quince mil"
            - Ejemplo inválido: "mucho", "poco", "no sé", "100" (muy bajo), "-5000"
            
            Si es válido, extrae el número limpio.
            Si no es válido, sugiere rangos típicos de forma amigable.
            
            Responde en formato JSON:
            {"isValid": true/false, "extractedValue": "número_limpio", "message": "explicación_humana"}
            `
        }

        const completion = await openai.chat.completions.create({
            model: "gpt-4o-mini",
            messages: [
                {
                    role: "system",
                    content: "Eres un asesor bancario humano y empático. IMPORTANTE: Responde ÚNICAMENTE con JSON válido puro, sin ```json ni markdown. Solo el objeto JSON limpio."
                },
                {
                    role: "user",
                    content: prompt
                }
            ],
            temperature: 0.3,
        });

        let response = completion.choices[0].message.content || '{"isValid": false, "message": "No pude procesar tu respuesta"}'
        
        response = response.replace(/```json\s*/g, '').replace(/```\s*/g, '').trim()
        
        const parsed = JSON.parse(response)
        
        return {
            isValid: parsed.isValid,
            message: parsed.message,
            extractedValue: parsed.extractedValue
        }
        
    } catch (error) {
        console.error('Error en validación:', error)
        return {
            isValid: false,
            message: "Disculpa, no entendí bien tu respuesta. ¿Podrías repetirla de forma más clara?"
        }
    }
}

/**
 * Respuesta humana y empática
 */
const generateHumanResponse = async (situation: string, userName: string, userMessage: string): Promise<string> => {
    try {
        const prompt = `
        El cliente ${userName} está en esta situación: ${situation}
        Su mensaje fue: "${userMessage}"
        
        Genera una respuesta MUY humana y empática como si fueras un asesor real del banco que:
        1. Entiende su situación particular
        2. Le da confianza y tranquilidad
        3. Le ofrece alternativas o soluciones
        4. Mantiene un tono cálido pero profesional
        
        Máximo 80 palabras. Que suene natural y humano.
        `

        const completion = await openai.chat.completions.create({
            model: "gpt-4o-mini",
            messages: [
                {
                    role: "system",
                    content: "Eres un asesor bancario con 15 años de experiencia. Respondes con mucha humanidad y empatía."
                },
                {
                    role: "user",
                    content: prompt
                }
            ],
            temperature: 0.7,
        });

        return completion.choices[0].message.content || "Entiendo tu situación. Estoy aquí para ayudarte de la mejor manera posible."
        
    } catch (error) {
        return "Comprendo perfectamente. Cada situación es única y estoy aquí para encontrar la mejor solución para ti."
    }
}

// --- Flujos del Bot ---

const mainFlow = addKeyword<Provider, Database>('')
    .addAction(async (ctx, { flowDynamic, gotoFlow }) => {
        const userId = ctx.from
        
        if (!userStates.has(userId)) {
            const userName = ctx.pushName || 'estimado cliente'
            
            const clientData = await getClientInfo(userId)
            const campaignData = await getCampaignInfo(userId)
            
            if (!clientData) {
                await flowDynamic('❌ No encontré tu información en nuestro sistema. ¿Podrías confirmar si eres cliente de Banco Guayaquil?')
                return
            }
            
            if (!campaignData || !campaignData.active_campaigns || campaignData.active_campaigns.length === 0) {
                await flowDynamic('ℹ️ No tienes campañas activas en este momento, pero igual puedo ayudarte con información general sobre nuestros productos. 😊')
            }
            
            userStates.set(userId, { 
                step: 'greeting', 
                name: userName,
                clientData,
                campaignData,
                conversationHistory: [],
                retryCount: 0
            })
            
            const greetingMessage = generatePersonalizedGreeting(clientData, campaignData, userName)
            await flowDynamic(greetingMessage)
            
            userStates.set(userId, { 
                step: 'waiting_interest', 
                name: userName,
                clientData,
                campaignData,
                conversationHistory: [greetingMessage],
                retryCount: 0
            })
            return
        }
        
        return gotoFlow(conversationFlow)
    })

const conversationFlow = addKeyword<Provider, Database>('')
    .addAction(async (ctx, { flowDynamic }) => {
        const userId = ctx.from
        const userMessage = ctx.body
        const userState = userStates.get(userId) || { step: 'greeting', name: 'Usuario', retryCount: 0 }
        
        const updatedHistory = [...(userState.conversationHistory || []), `Usuario: ${userMessage}`]
        userStates.set(userId, { ...userState, conversationHistory: updatedHistory })
        
        const conversationHistoryText = buildConversationHistory(userStates, userId)
        const intention: IntentionResult = await getIntention(userMessage, conversationHistoryText)
        
        console.log(`🧠 Intención detectada: ${intention.intention} (${intention.confidence}) - Emoción: ${intention.emotion}`)
        
        if (intention.emotion === 'negative' || intention.emotion === 'frustrated') {
            const empathicResponse = await generateHumanResponse('cliente molesto o frustrado', userState.name!, userMessage)
            await flowDynamic(empathicResponse)
            await flowDynamic('¿Hay algo específico que te preocupa? Estoy aquí para escucharte y ayudarte. 😊')
            return
        }
        
        switch (userState.step) {
            case 'waiting_interest': {
                if (intention.intention === 'interest_confirm' || userMessage.toLowerCase().includes('si') || userMessage.toLowerCase().includes('sí')) {
                    await flowDynamic('¡Excelente! Me da mucha satisfacción poder ayudarte con esto.')
                    await flowDynamic('Para ofrecerte las mejores condiciones, necesito conocer tu situación financiera actual.')
                    await flowDynamic('¿Podrías decirme cuál es tu sueldo mensual? Puedes escribirlo como prefieras: números, con palabras, etc. 💰')
                    userStates.set(userId, { ...userState, step: 'waiting_salary', retryCount: 0 })
                } else if (intention.intention === 'interest_decline' || userMessage.toLowerCase().includes('no')) {
                    const humanResponse = await generateHumanResponse('cliente declina ayuda', userState.name!, userMessage)
                    await flowDynamic(humanResponse)
                    await flowDynamic('¿Hay alguna información específica que te gustaría conocer? Estoy aquí para cualquier duda. 🤔')
                    userStates.set(userId, { ...userState, step: 'waiting_questions' })
                } else {
                    await flowDynamic('Entiendo que puedas tener dudas. Es completamente normal.')
                    await flowDynamic('¿Te gustaría que te cuente más sobre nuestras opciones, o prefieres que te ayude directamente con una solicitud? 😊')
                }
                break
            }

            case 'waiting_salary': {
                const validation = await validateDataWithAI(userMessage, 'salary', userState.name!)
                
                if (validation.isValid && validation.extractedValue) {
                    const salary = validation.extractedValue
                    await flowDynamic(`¡Perfecto! Ingreso de $${salary} mensuales registrado. ✅`)
                    await flowDynamic('Excelente situación financiera. Ahora, ¿podrías decirme en qué empresa trabajas o a qué te dedicas? 🏢')
                    userStates.set(userId, { ...userState, step: 'waiting_company', salary, retryCount: 0 })
                } else {
                    const retryCount = (userState.retryCount || 0) + 1
                    
                    if (retryCount >= 3) {
                        const humanResponse = await generateHumanResponse('cliente con dificultades para proporcionar sueldo', userState.name!, userMessage)
                        await flowDynamic(humanResponse)
                        await flowDynamic('¿Te gustaría que un asesor especializado te llame para conversar sobre tu situación específica? 📞')
                        userStates.set(userId, { ...userState, step: 'waiting_human_contact' })
                    } else {
                        await flowDynamic(validation.message || 'No logré entender tu sueldo.')
                        if (retryCount === 1) {
                            await flowDynamic('Por ejemplo, puedes escribir: "2500", "2,500 dólares", "dos mil quinientos", etc.')
                        }
                        userStates.set(userId, { ...userState, retryCount })
                    }
                }
                break
            }
                
            case 'waiting_company': {
                const validation = await validateDataWithAI(userMessage, 'company', userState.name!)
                
                if (validation.isValid && validation.extractedValue) {
                    const company = validation.extractedValue
                    await flowDynamic(`¡Excelente! ${company} es una muy buena referencia. ✅`)
                    await flowDynamic('Con tu perfil laboral, podemos ofrecerte condiciones muy atractivas.')
                    await flowDynamic('¿Qué monto de crédito personal necesitas para tu proyecto? 💰')
                    userStates.set(userId, { ...userState, step: 'waiting_amount', company, retryCount: 0 })
                } else {
                    const retryCount = (userState.retryCount || 0) + 1
                    
                    if (retryCount >= 3) {
                        const humanResponse = await generateHumanResponse('dificultades con información laboral', userState.name!, userMessage)
                        await flowDynamic(humanResponse)
                        await flowDynamic('Entiendo que cada situación laboral es única. ¿Te gustaría que conversemos por teléfono? 📞')
                        userStates.set(userId, { ...userState, step: 'waiting_human_contact' })
                    } else {
                        await flowDynamic(validation.message || 'No logré entender dónde trabajas.')
                        if (retryCount === 1) {
                            await flowDynamic('Puedes escribir el nombre de tu empresa, "independiente", "por cuenta propia", etc.')
                        }
                        userStates.set(userId, { ...userState, retryCount })
                    }
                }
                break
            }
                
            case 'waiting_amount': {
                const validation = await validateDataWithAI(userMessage, 'amount', userState.name!)
                
                if (validation.isValid && validation.extractedValue) {
                    const amount = validation.extractedValue
                    await flowDynamic(`¡Perfecto! Solicitud de ${amount} recibida. ✅`)
                    
                    await flowDynamic('📋 Resumen de tu solicitud:')
                    await flowDynamic(`• *Nombre:* ${userState.name}\n• *Sueldo:* ${userState.salary}\n• *Empresa:* ${userState.company}\n• *Monto:* ${amount}`)

                    await flowDynamic('📤 Enviando tu solicitud a nuestro sistema...')
                    
                    const leadData = {
                        name: userState.name,
                        salary: userState.salary,
                        company: userState.company,
                        amount: amount,
                        product: userState.selectedProduct || 'credito_personal',
                        timestamp: new Date().toISOString(),
                        source: 'whatsapp_bot',
                        client_data: userState.clientData,
                        campaign_data: userState.campaignData
                    }
                    
                    const leadSent = await sendLeadAccepted(userId, leadData)
                    
                    if (leadSent) {
                        await flowDynamic('✅ Tu solicitud ha sido procesada exitosamente.')
                        
                        const aiMessage = await generateHumanResponse('solicitud procesada exitosamente', userState.name!, `Solicitud: ${amount}`)
                        
                        await new Promise(resolve => setTimeout(resolve, 3000))
                        await flowDynamic(aiMessage)
                        await flowDynamic('📞 Un especialista te contactará en los próximos 10 minutos.')
                        await flowDynamic('¡Gracias por confiar en Banco Guayaquil! 🎉')
                        
                    } else {
                        await flowDynamic('⚠️ Hubo un inconveniente al procesar tu solicitud.')
                        await flowDynamic('Un asesor te contactará en breve para continuar manualmente.')
                        await flowDynamic('¡No te preocupes, tu información está segura! 😊')
                    }
                    
                    userStates.delete(userId)
                } else {
                    const retryCount = (userState.retryCount || 0) + 1
                    
                    if (retryCount >= 3) {
                        await flowDynamic('Comprendo que definir el monto exacto puede ser complejo.')
                        await flowDynamic('¿Te gustaría que un asesor te llame para ayudarte a calcular el monto ideal para tu proyecto? 📞')
                        userStates.set(userId, { ...userState, step: 'waiting_human_contact' })
                    } else {
                        await flowDynamic(validation.message || 'No logré entender el monto que necesitas.')
                        if (retryCount === 1) {
                            await flowDynamic('Por ejemplo: "15000", "15,000", "quince mil dólares", etc.')
                        }
                        userStates.set(userId, { ...userState, retryCount })
                    }
                }
                break
            }

            case 'waiting_human_contact': {
                if (userMessage.toLowerCase().includes('si') || userMessage.toLowerCase().includes('sí')) {
                    await flowDynamic('¡Perfecto! Un asesor especializado te contactará en los próximos 15 minutos.')
                    await flowDynamic('Mientras tanto, puedes preparar cualquier documento que tengas a mano.')
                    await flowDynamic('¡Gracias por tu paciencia y confianza en Banco Guayaquil! 🎉')
                    userStates.delete(userId)
                } else {
                    await flowDynamic('Entiendo perfectamente. Cuando te sientas listo, estaré aquí para ayudarte.')
                    await flowDynamic('¿Hay algo más en lo que pueda asistirte hoy? 😊')
                    userStates.set(userId, { ...userState, step: 'waiting_interest' })
                }
                break
            }
                
            default: {
                const humanResponse = await generateHumanResponse('mensaje no entendido', userState.name!, userMessage)
                await flowDynamic(humanResponse)
                await flowDynamic('¿Te gustaría que te ayude con tu solicitud o tienes alguna pregunta específica? 😊')
                userStates.set(userId, { ...userState, step: 'waiting_interest' })
                break
            }
        }
    })

const main = async () => {
    const adapterFlow = createFlow([mainFlow, conversationFlow])
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

    // Endpoints HTTP
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
            res.writeHead(200, { 'Content-Type': 'application/json' })
            return res.end(JSON.stringify({ status: 'sent', number, message }))
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error'
            res.writeHead(500, { 'Content-Type': 'application/json' })
            return res.end(JSON.stringify({ status: 'error', error: errorMessage }))
        }
    }))

    adapterProvider.server.get('/health', handleCtx(async (bot, req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' })
        return res.end(JSON.stringify({ 
            status: 'healthy', 
            service: 'BuilderBot con APIs Externas - Banco Guayaquil', 
            timestamp: new Date().toISOString(),
            activeConversations: userStates.size,
            features: ['Validación IA', 'APIs Externas', 'Detección emocional', 'Respuestas humanas'],
            external_api: EXTERNAL_API_URL
        }))
    }))
    
    httpServer(+PORT)
    console.log(`✅ BuilderBot con APIs Externas iniciado en puerto ${PORT}`)
    console.log(`🧠 Características activas:`)
    console.log(`   ✓ Consulta información del cliente: GET ${EXTERNAL_API_URL}/client/:number`)
    console.log(`   ✓ Consulta campañas activas: GET ${EXTERNAL_API_URL}/campanas/:number`)
    console.log(`   ✓ Envía leads aceptados: POST ${EXTERNAL_API_URL}/lead/:number`)
    console.log(`   ✓ Detección de intenciones con LangChain`)
    console.log(`   ✓ Validación inteligente de datos`)
    console.log(`   ✓ Respuestas empáticas y humanas`)
    console.log(`   ✓ Manejo de emociones negativas`)
    console.log(`   ✓ Reintentos inteligentes`)
}

main().catch(err => {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error'
    console.error('❌ Error al iniciar:', errorMessage)
    process.exit(1)
})