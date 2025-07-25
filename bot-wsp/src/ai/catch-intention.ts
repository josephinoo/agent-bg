// ai/catch-intention.ts
import { z } from "zod";
import { ChatOpenAI } from "@langchain/openai";
import { ChatPromptTemplate } from "@langchain/core/prompts";

export const openAI = new ChatOpenAI({
    modelName: 'gpt-4o-mini',
    openAIApiKey: process.env.OPENAI_API_KEY,
    temperature: 0.3
});

const SYSTEM_STRUCT = `Eres un experto en detectar intenciones de clientes bancarios. 
Analiza el mensaje del usuario y categoriza su intención basándote en:

COMPORTAMIENTO DETECTADO: El cliente ha estado navegando productos bancarios en la web/app
CONTEXTO: Cliente de Banco Guayaquil interesado en productos financieros

Mensaje del usuario: {question}
Historia de conversación: {history}`;

export const PROMPT_STRUCT = ChatPromptTemplate.fromMessages([
    ["system", SYSTEM_STRUCT],
    ["human", "{question}"]
]);

const catchIntention = z.object({
    intention: z.enum([
        'GREETING',           // Saludo inicial
        'INTEREST_CONFIRM',   // Confirma interés en producto  
        'INTEREST_DECLINE',   // Rechaza ayuda
        'ASKING_INFO',        // Pregunta sobre productos
        'PROVIDING_DATA',     // Da información personal (sueldo, empresa, etc)
        'CHANGING_PRODUCT',   // Quiere cambiar de producto
        'COMPLAINT',          // Reclamo o molestia
        'CLOSURE',           // Despedida
        'UNKNOWN'            // No está claro
    ]).describe('Categoriza la intención del mensaje del cliente bancario'),
    
    confidence: z.number().min(0).max(1)
        .describe('Nivel de confianza en la detección (0-1)'),
    
    product_interest: z.enum([
        'credito_personal',
        'credito_hipotecario', 
        'credito_vehicular',
        'tarjeta_credito',
        'cuenta_ahorros',
        'inversion',
        'none'
    ]).describe('Producto que menciona o parece interesar al cliente'),
    
    emotion: z.enum(['positive', 'neutral', 'negative', 'frustrated'])
        .describe('Tono emocional del mensaje'),
        
    next_action: z.string()
        .describe('Sugerencia de próxima acción para el bot')
        
}).describe('Análisis completo de la intención del cliente bancario');

const llmWithToolsCatchIntention = openAI.withStructuredOutput(catchIntention, {
    name: "BankIntentionAnalysis",
});

export interface IntentionResult {
    intention: string;
    confidence: number;
    product_interest: string;
    emotion: string;
    next_action: string;
}

export const getIntention = async (text: string, conversationHistory: string = ""): Promise<IntentionResult> => {
    try {
        const result = await PROMPT_STRUCT.pipe(llmWithToolsCatchIntention).invoke({
            question: text,
            history: conversationHistory
        });

        return {
            intention: result.intention.toLowerCase(),
            confidence: result.confidence,
            product_interest: result.product_interest,
            emotion: result.emotion,
            next_action: result.next_action
        };
    } catch (error) {
        console.error('Error en detección de intención:', error);
        return {
            intention: 'unknown',
            confidence: 0,
            product_interest: 'none',
            emotion: 'neutral',
            next_action: 'Continuar con flujo normal'
        };
    }
};

// Función auxiliar para construir historial de conversación
export const buildConversationHistory = (userStates: Map<string, any>, userId: string): string => {
    const state = userStates.get(userId);
    if (!state) return "Nueva conversación";
    
    let history = `Cliente: ${state.name || 'Usuario'}\n`;
    history += `Paso actual: ${state.step}\n`;
    
    if (state.selectedProduct) {
        history += `Producto de interés: ${state.selectedProduct}\n`;
    }
    
    if (state.salary) history += `Sueldo: $${state.salary}\n`;
    if (state.company) history += `Empresa: ${state.company}\n`;
    if (state.amount) history += `Monto solicitado: $${state.amount}\n`;
    
    return history;
};