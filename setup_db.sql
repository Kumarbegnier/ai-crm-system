CREATE DATABASE crm_ai;

\c crm_ai;

CREATE TABLE users (
    id                        SERIAL PRIMARY KEY,

    -- Basic Info
    name                      VARCHAR(255) NOT NULL,
    email                     VARCHAR(255) UNIQUE NOT NULL,
    phone                     VARCHAR(20),

    -- Role & Access
    role                      VARCHAR(50)  NOT NULL DEFAULT 'sales_rep', -- sales_rep, manager, admin
    designation               VARCHAR(100),

    -- Territory / Region Mapping
    region                    VARCHAR(100),
    city                      VARCHAR(100),

    -- Authentication
    password_hash             TEXT,
    is_active                 BOOLEAN      DEFAULT TRUE,

    -- AI / CRM Metrics
    total_interactions_logged INT          DEFAULT 0,
    last_active_at            TIMESTAMP,

    -- Audit
    created_at                TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at                TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_users_email  ON users(LOWER(email));
CREATE INDEX        idx_users_role   ON users(role);
CREATE INDEX        idx_users_region ON users(region);

CREATE TABLE hcps (
    id                    SERIAL PRIMARY KEY,

    -- Basic Info
    name                  VARCHAR(255) NOT NULL,
    specialty             VARCHAR(100),
    sub_specialty         VARCHAR(100),
    qualification         VARCHAR(100),

    -- Organization Info
    organization          VARCHAR(255),
    department            VARCHAR(100),

    -- Contact Info
    phone                 VARCHAR(20),
    email                 VARCHAR(255) UNIQUE,

    -- Location Info
    city                  VARCHAR(100),
    state                 VARCHAR(100),
    country               VARCHAR(100) DEFAULT 'India',
    normalized_name       VARCHAR(255) UNIQUE,

    -- CRM Intelligence Fields
    engagement_score      FLOAT        DEFAULT 0,
    total_interactions    INT          DEFAULT 0,
    last_interaction_date TIMESTAMP,

    -- Segmentation
    priority              VARCHAR(50)  DEFAULT 'medium',  -- high / medium / low
    status                VARCHAR(50)  DEFAULT 'active',

    -- Audit Fields
    created_by            VARCHAR(100),
    created_at            TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_hcps_name ON hcps(LOWER(name));
CREATE UNIQUE INDEX idx_hcps_normalized_name ON hcps(LOWER(normalized_name));

CREATE TABLE appointments (
    id           SERIAL PRIMARY KEY,
    hcp_id       INT  NOT NULL REFERENCES hcps(id) ON DELETE CASCADE,
    date         DATE NOT NULL,
    time         TEXT NOT NULL,
    status       TEXT DEFAULT 'scheduled',
    notes        TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(hcp_id, date, time)
);

CREATE INDEX idx_appointments_hcp_date ON appointments(hcp_id, date);
CREATE INDEX idx_appointments_status   ON appointments(status);

CREATE TABLE interactions (
    id                  SERIAL PRIMARY KEY,

    -- Relationship
    hcp_id              INT  NOT NULL REFERENCES hcps(id) ON DELETE CASCADE,
    user_id             INT  REFERENCES users(id),

    -- Interaction Details
    interaction_type    VARCHAR(50)  NOT NULL DEFAULT 'call',  -- call, visit, meeting, email
    interaction_channel VARCHAR(50),                           -- in-person, phone, video, email
    interaction_date    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Content
    notes               TEXT         NOT NULL,

    -- AI-First Design
    raw_input           TEXT,
    ai_summary          TEXT,
    ai_entities         JSONB,        -- extracted structured data (drug, followup, etc.)
    sentiment           VARCHAR(20),  -- positive / neutral / negative

    -- Business Context
    product_discussed   VARCHAR(255),
    outcome             VARCHAR(100), -- interested, not_interested, follow_up_required

    -- Follow-up Intelligence
    follow_up_required  BOOLEAN      DEFAULT FALSE,
    follow_up_date      TIMESTAMP,

    -- Audit
    created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_interactions_hcp_id  ON interactions(hcp_id);
CREATE INDEX idx_interactions_date    ON interactions(interaction_date DESC);
CREATE INDEX idx_interactions_followup ON interactions(follow_up_required, follow_up_date)
    WHERE follow_up_required = TRUE;

CREATE TABLE interaction_metadata (
    id                SERIAL PRIMARY KEY,

    interaction_id    INT NOT NULL
        REFERENCES interactions(id) ON DELETE CASCADE,

    -- Key-Value Storage
    key               VARCHAR(100) NOT NULL,
    value             TEXT,

    -- Data typing (important for AI + filtering)
    value_type        VARCHAR(50) DEFAULT 'string', -- string, number, date, boolean, json

    -- Source tracking
    source            VARCHAR(50) DEFAULT 'llm',    -- llm / user / system

    confidence_score  FLOAT,                        -- 0 to 1 (LLM confidence)

    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metadata_interaction_id ON interaction_metadata(interaction_id);
CREATE INDEX idx_metadata_key            ON interaction_metadata(key);
CREATE INDEX idx_metadata_source         ON interaction_metadata(source);

-- Tags Master Table
CREATE TABLE tags (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE NOT NULL,
    category    VARCHAR(100), -- behavior, specialty, priority, product
    description TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_tags_name ON tags(LOWER(name));
CREATE INDEX idx_tags_category    ON tags(category);

-- HCP ↔ Tags Mapping Table
CREATE TABLE hcp_tags (
    id               SERIAL PRIMARY KEY,
    hcp_id           INT NOT NULL
        REFERENCES hcps(id) ON DELETE CASCADE,
    tag_id           INT NOT NULL
        REFERENCES tags(id) ON DELETE CASCADE,
    confidence_score FLOAT, -- 0 to 1
    source           VARCHAR(50) DEFAULT 'llm', -- llm / user / system
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (hcp_id, tag_id)
);

CREATE INDEX idx_hcp_tags_hcp_id ON hcp_tags(hcp_id);
CREATE INDEX idx_hcp_tags_tag_id ON hcp_tags(tag_id);
