-- Social Media CRM - Phase-1a Database Schema
-- PostgreSQL Schema for Interactions, Tickets, Users, Platforms, and Audit Logs

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- 1. PLATFORM CONFIGURATION
-- ============================================================================
CREATE TABLE platforms (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    icon_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    api_base_url VARCHAR(500),
    max_message_length INT,
    supports_media BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 2. USER & AUTHENTICATION
-- ============================================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(500) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role VARCHAR(50) NOT NULL, -- 'admin', 'team_leader', 'agent'
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    language_preference VARCHAR(20) DEFAULT 'en',
    timezone VARCHAR(100) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    CHECK (role IN ('admin', 'team_leader', 'agent'))
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role ON users(role);

-- ============================================================================
-- 3. PLATFORM CREDENTIALS & INTEGRATION
-- ============================================================================
CREATE TABLE platform_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform_id UUID NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    admin_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    business_account_id VARCHAR(255) NOT NULL,
    business_account_name VARCHAR(255),
    access_token VARCHAR(2000),
    refresh_token VARCHAR(2000),
    token_expires_at TIMESTAMP,
    scope VARCHAR(1000),
    is_active BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMP,
    sync_status VARCHAR(50), -- 'active', 'paused', 'error'
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform_id, business_account_id)
);

CREATE INDEX idx_platform_creds_platform ON platform_credentials(platform_id);
CREATE INDEX idx_platform_creds_admin ON platform_credentials(admin_id);

-- ============================================================================
-- 4. CUSTOMERS
-- ============================================================================
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform_user_id VARCHAR(500) NOT NULL,
    platform_id UUID NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    display_name VARCHAR(255),
    avatar_url VARCHAR(500),
    profile_url VARCHAR(500),
    follower_count INT DEFAULT 0,
    is_verified_on_platform BOOLEAN DEFAULT FALSE,
    sentiment_history JSONB, -- {negative: 0, neutral: 0, positive: 0}
    metadata JSONB,
    first_interaction_at TIMESTAMP,
    last_interaction_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform_user_id, platform_id)
);

CREATE INDEX idx_customers_platform ON customers(platform_id);
CREATE INDEX idx_customers_platform_user ON customers(platform_user_id);
CREATE INDEX idx_customers_last_interaction ON customers(last_interaction_at DESC);

-- ============================================================================
-- 5. INTERACTIONS (Raw Social Media Posts/Comments/Messages)
-- ============================================================================
CREATE TABLE interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform_id UUID NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    platform_interaction_id VARCHAR(500) NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    interaction_type VARCHAR(50) NOT NULL, -- 'comment', 'message', 'mention', 'review', 'post'
    content TEXT,
    media_urls TEXT[], -- Array of media attachment URLs
    parent_interaction_id UUID REFERENCES interactions(id) ON DELETE SET NULL, -- For nested comments
    post_url VARCHAR(500),
    is_public BOOLEAN DEFAULT TRUE,
    platform_metadata JSONB, -- Store platform-specific data
    captured_at TIMESTAMP NOT NULL,
    is_processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform_id, platform_interaction_id)
);

CREATE INDEX idx_interactions_platform ON interactions(platform_id);
CREATE INDEX idx_interactions_customer ON interactions(customer_id);
CREATE INDEX idx_interactions_type ON interactions(interaction_type);
CREATE INDEX idx_interactions_processed ON interactions(is_processed);
CREATE INDEX idx_interactions_created ON interactions(created_at DESC);
CREATE INDEX idx_interactions_content ON interactions USING gin(to_tsvector('english', content));

-- ============================================================================
-- 6. TICKETS
-- ============================================================================
CREATE TABLE tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_number VARCHAR(50) NOT NULL UNIQUE,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    primary_interaction_id UUID NOT NULL REFERENCES interactions(id) ON DELETE RESTRICT,
    platform_id UUID NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    assigned_to_agent_id UUID REFERENCES users(id) ON DELETE SET NULL,
    assigned_to_team_lead_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'open', -- 'open', 'in_progress', 'pending', 'resolved', 'closed'
    priority VARCHAR(20) DEFAULT 'medium', -- 'low', 'medium', 'high', 'urgent'
    subject VARCHAR(500),
    description TEXT,
    tags VARCHAR(100)[],
    internal_notes TEXT,
    resolution_summary TEXT,
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of_ticket_id UUID REFERENCES tickets(id) ON DELETE SET NULL,
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    first_response_at TIMESTAMP,
    resolved_at TIMESTAMP,
    closed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_customer ON tickets(customer_id);
CREATE INDEX idx_tickets_platform ON tickets(platform_id);
CREATE INDEX idx_tickets_assigned_agent ON tickets(assigned_to_agent_id);
CREATE INDEX idx_tickets_priority ON tickets(priority);
CREATE INDEX idx_tickets_created ON tickets(created_at DESC);
CREATE INDEX idx_tickets_opened ON tickets(opened_at DESC);

-- ============================================================================
-- 7. TICKET INTERACTIONS (Link interactions to tickets)
-- ============================================================================
CREATE TABLE ticket_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    interaction_id UUID NOT NULL REFERENCES interactions(id) ON DELETE CASCADE,
    sequence_number INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticket_id, interaction_id)
);

CREATE INDEX idx_ticket_interactions_ticket ON ticket_interactions(ticket_id);
CREATE INDEX idx_ticket_interactions_interaction ON ticket_interactions(interaction_id);

-- ============================================================================
-- 8. RESPONSES (Agent responses sent back to customers)
-- ============================================================================
CREATE TABLE responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    platform_id UUID NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    responding_to_interaction_id UUID NOT NULL REFERENCES interactions(id) ON DELETE RESTRICT,
    content TEXT NOT NULL,
    media_urls TEXT[],
    response_type VARCHAR(50) DEFAULT 'manual', -- 'manual', 'template', 'ai_suggested'
    platform_post_id VARCHAR(500),
    status VARCHAR(50) NOT NULL DEFAULT 'draft', -- 'draft', 'submitted', 'published', 'failed'
    is_private_message BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP,
    platform_response JSONB, -- Store API response from platform
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_responses_ticket ON responses(ticket_id);
CREATE INDEX idx_responses_agent ON responses(agent_id);
CREATE INDEX idx_responses_status ON responses(status);
CREATE INDEX idx_responses_platform ON responses(platform_id);
CREATE INDEX idx_responses_created ON responses(created_at DESC);

-- ============================================================================
-- 9. AUDIT LOG
-- ============================================================================
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(255) NOT NULL,
    entity_type VARCHAR(100),
    entity_id VARCHAR(500),
    old_values JSONB,
    new_values JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);

-- ============================================================================
-- 10. SYSTEM SETTINGS
-- ============================================================================
CREATE TABLE system_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    setting_key VARCHAR(255) NOT NULL,
    setting_value TEXT,
    setting_type VARCHAR(50), -- 'string', 'boolean', 'integer', 'json'
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(admin_id, setting_key)
);

-- Refresh/access token revocation for local logout and refresh rotation.
CREATE TABLE revoked_tokens (
    jti VARCHAR(36) PRIMARY KEY,
    expires_at TIMESTAMP NOT NULL
);

-- ============================================================================
-- 11. INITIAL DATA
-- ============================================================================
INSERT INTO platforms (name, display_name, icon_url, is_active, max_message_length, supports_media) VALUES
('facebook', 'Facebook', 'https://www.facebook.com/favicon.ico', TRUE, 63206, TRUE),
('instagram', 'Instagram', 'https://www.instagram.com/favicon.ico', TRUE, 2200, TRUE),
('twitter', 'X (Twitter)', 'https://twitter.com/favicon.ico', FALSE, 280, TRUE),
('youtube', 'YouTube', 'https://www.youtube.com/favicon.ico', FALSE, 10000, TRUE),
('linkedin', 'LinkedIn', 'https://www.linkedin.com/favicon.ico', FALSE, 3000, TRUE)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 12. HELPER FUNCTIONS
-- ============================================================================

-- Function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to tables with updated_at column
CREATE TRIGGER update_users_timestamp BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER update_customers_timestamp BEFORE UPDATE ON customers FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER update_tickets_timestamp BEFORE UPDATE ON tickets FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER update_responses_timestamp BEFORE UPDATE ON responses FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER update_platform_creds_timestamp BEFORE UPDATE ON platform_credentials FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER update_system_settings_timestamp BEFORE UPDATE ON system_settings FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- ============================================================================
-- 13. VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Active interactions for dashboard
CREATE VIEW v_active_interactions AS
SELECT 
    i.id,
    i.platform_id,
    p.display_name as platform_name,
    c.display_name as customer_name,
    i.interaction_type,
    i.content,
    i.captured_at,
    t.id as ticket_id,
    t.status as ticket_status,
    t.assigned_to_agent_id
FROM interactions i
JOIN platforms p ON i.platform_id = p.id
JOIN customers c ON i.customer_id = c.id
LEFT JOIN ticket_interactions ti ON i.id = ti.interaction_id
LEFT JOIN tickets t ON ti.ticket_id = t.id
WHERE i.is_processed = FALSE
ORDER BY i.captured_at DESC;

-- Ticket summary with agent info
CREATE VIEW v_ticket_summary AS
SELECT 
    t.id,
    t.ticket_number,
    c.display_name as customer_name,
    p.display_name as platform_name,
    u.username as assigned_agent,
    t.status,
    t.priority,
    t.subject,
    t.opened_at,
    t.first_response_at,
    EXTRACT(EPOCH FROM (COALESCE(t.first_response_at, NOW()) - t.opened_at)) / 60 as response_time_minutes
FROM tickets t
JOIN customers c ON t.customer_id = c.id
JOIN platforms p ON t.platform_id = p.id
LEFT JOIN users u ON t.assigned_to_agent_id = u.id
ORDER BY t.opened_at DESC;
