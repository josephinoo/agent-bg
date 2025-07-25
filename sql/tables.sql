-- TABLA DE CAMPAÑAS
CREATE TABLE campaigns (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    product_type VARCHAR(100) NOT NULL, -- 'credit', 'credit_card', 'insurance'
    status VARCHAR(50) DEFAULT 'draft', -- 'draft', 'active', 'paused', 'completed'
    
    budget_total DECIMAL(10,2) NOT NULL,
    budget_spent DECIMAL(10,2) DEFAULT 0,
    max_leads_per_day INTEGER DEFAULT 100,
    
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    targeting_criteria JSONB -- Criterios de segmentación
);

-- TABLA DE USUARIOS EN CAMPAÑA
CREATE TABLE campaign_users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    user_id VARCHAR(100) NOT NULL,
    
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(20),
    
    customer_segment VARCHAR(50), -- 'premium', 'standard', 'basic'
    current_products JSONB, -- ["cuenta_corriente", "cuenta_ahorros"]
    credit_score INTEGER,
    monthly_income DECIMAL(10,2),
    
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'contacted', 'converted'
    added_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(campaign_id, user_id)
);

-- TABLA DE REGLAS DE ACTIVACIÓN
CREATE TABLE activation_rules (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    
    rule_name VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50) NOT NULL, -- 'behavioral', 'frequency', 'intent'
    condition_sql TEXT NOT NULL, -- "event_type = 'login' AND count >= 3"
    
    priority INTEGER DEFAULT 1,
    min_propensity_score DECIMAL(3,2) DEFAULT 0.5,
    cooldown_hours INTEGER DEFAULT 24,
    is_active BOOLEAN DEFAULT true,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TABLA DE GUARDRAILS
CREATE TABLE campaign_guardrails (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    
    guardrail_type VARCHAR(50) NOT NULL, -- 'frequency', 'budget', 'timing'
    config JSONB NOT NULL, -- {"max_contacts_per_day": 1, "cooldown_days": 7}
    is_active BOOLEAN DEFAULT true,
    error_message TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TABLA DE EVENTOS DIGITALES
CREATE TABLE user_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL, -- 'login', 'credit_application_start', etc.
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    session_id VARCHAR(100),
    
    -- Metadata del evento
    page_url TEXT,
    user_agent TEXT,
    ip_address INET,
    metadata JSONB, -- Datos adicionales específicos del evento
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para optimizar consultas
CREATE INDEX idx_user_events_user_id ON user_events(user_id);
CREATE INDEX idx_user_events_type ON user_events(event_type);
CREATE INDEX idx_user_events_timestamp ON user_events(timestamp);
CREATE INDEX idx_user_events_session ON user_events(session_id);
