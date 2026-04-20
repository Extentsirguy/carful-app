-- CARFul Database Schema
-- OECD CARF XML v2.0 Compatible
-- Generated: 2026-02-01

-- ============================================================================
-- ISO 3166-1 Alpha-2 Country Codes Lookup Table
-- ============================================================================
-- This table enables CHECK constraints via foreign key relationships
-- and provides the authoritative list of valid country codes.

CREATE TABLE IF NOT EXISTS country_codes (
    code TEXT PRIMARY KEY CHECK(length(code) = 2),
    name TEXT NOT NULL,
    is_active INTEGER DEFAULT 1  -- Some codes are reserved/deprecated
);

-- ============================================================================
-- Message Header Table
-- ============================================================================
-- Stores metadata for each CARF submission message.
-- Maps to: CARF_Message/MessageHeader

CREATE TABLE IF NOT EXISTS message_header (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Sending/Receiving Jurisdictions
    sending_comp_auth TEXT NOT NULL
        REFERENCES country_codes(code),
    receiving_comp_auth TEXT NOT NULL
        REFERENCES country_codes(code),

    -- Message Identification
    message_type TEXT NOT NULL DEFAULT 'CARF'
        CHECK(message_type = 'CARF'),
    message_type_indic TEXT NOT NULL
        CHECK(message_type_indic IN ('CARF701', 'CARF702', 'CARF703')),
    message_ref_id TEXT NOT NULL UNIQUE,

    -- Reporting Period (calendar year)
    reporting_period_start TEXT NOT NULL,  -- YYYY-MM-DD
    reporting_period_end TEXT NOT NULL,    -- YYYY-MM-DD

    -- Timestamps
    timestamp TEXT NOT NULL,  -- ISO 8601: YYYY-MM-DDTHH:mm:ssZ
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Constraints
    CHECK(date(reporting_period_start) IS NOT NULL),
    CHECK(date(reporting_period_end) IS NOT NULL),
    CHECK(reporting_period_end >= reporting_period_start)
);

-- ============================================================================
-- RCASP Table (Reporting Crypto-Asset Service Provider)
-- ============================================================================
-- Stores information about the reporting entity.
-- Maps to: CARFBody/ReportingGroup/RCASP

CREATE TABLE IF NOT EXISTS rcasp (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL
        REFERENCES message_header(id) ON DELETE CASCADE,

    -- Document Specification (for corrections)
    doc_type_indic TEXT NOT NULL DEFAULT 'OECD1'
        CHECK(doc_type_indic IN ('OECD1', 'OECD2', 'OECD3')),
    doc_ref_id TEXT NOT NULL,
    corr_doc_ref_id TEXT,  -- For corrections/deletions only

    -- Entity Identification
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'Entity'
        CHECK(entity_type IN ('Entity', 'Individual')),

    -- Tax Identification
    tin TEXT,  -- Tax Identification Number (jurisdiction-specific format)
    tin_issued_by TEXT
        REFERENCES country_codes(code),

    -- Address (JSON-encoded for flexibility)
    address_type TEXT DEFAULT 'OECD303',  -- Business address
    address_json TEXT NOT NULL,  -- JSON: {street, city, postal_code, country_code, etc.}
    country_code TEXT NOT NULL
        REFERENCES country_codes(code),

    -- Nexus Information
    nexus_type TEXT NOT NULL
        CHECK(nexus_type IN (
            'CARF801',  -- Jurisdiction of tax residence
            'CARF802',  -- Jurisdiction of incorporation
            'CARF803',  -- Jurisdiction of management
            'CARF804',  -- Jurisdiction of regular place of business
            'CARF805'   -- Other nexus
        )),

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Unique constraint per message
    UNIQUE(message_id, doc_ref_id)
);

-- ============================================================================
-- User Table (Reportable Crypto Users)
-- ============================================================================
-- Stores information about reportable users/account holders.
-- Maps to: CARFBody/ReportingGroup/CryptoUser

CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rcasp_id INTEGER NOT NULL
        REFERENCES rcasp(id) ON DELETE CASCADE,

    -- Document Specification
    doc_type_indic TEXT NOT NULL DEFAULT 'OECD1'
        CHECK(doc_type_indic IN ('OECD1', 'OECD2', 'OECD3')),
    doc_ref_id TEXT NOT NULL,
    corr_doc_ref_id TEXT,

    -- User Type
    user_type TEXT NOT NULL DEFAULT 'Individual'
        CHECK(user_type IN ('Individual', 'Entity')),

    -- Identification
    first_name TEXT,      -- For individuals
    middle_name TEXT,     -- For individuals
    last_name TEXT,       -- For individuals
    entity_name TEXT,     -- For entities
    name_type TEXT,       -- OECD naming convention

    -- Tax Identification
    tin TEXT,             -- TIN or 'NOTIN'
    tin_unknown INTEGER DEFAULT 0,  -- Set to 1 if TIN unavailable
    tin_issued_by TEXT
        REFERENCES country_codes(code),

    -- Tax Residency (can have multiple - primary stored here)
    tax_residency TEXT NOT NULL
        REFERENCES country_codes(code),

    -- Address
    address_json TEXT,    -- JSON-encoded address object
    address_country TEXT
        REFERENCES country_codes(code),

    -- Birth Information (for individuals)
    birth_date TEXT,      -- YYYY-MM-DD
    birth_city TEXT,
    birth_country TEXT
        REFERENCES country_codes(code),

    -- Account Information
    account_number TEXT,  -- Internal identifier
    account_number_type TEXT,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    source_row INTEGER,   -- Original CSV row for error tracking

    -- Constraints
    UNIQUE(rcasp_id, doc_ref_id),
    CHECK(
        (user_type = 'Individual' AND (first_name IS NOT NULL OR last_name IS NOT NULL))
        OR
        (user_type = 'Entity' AND entity_name IS NOT NULL)
    )
);

-- ============================================================================
-- Transaction Table (Relevant Transactions)
-- ============================================================================
-- Stores all reportable crypto transactions.
-- Maps to: CryptoUser/RelevantTransactions/*

CREATE TABLE IF NOT EXISTS "transaction" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL
        REFERENCES user(id) ON DELETE CASCADE,

    -- Transaction Classification
    transaction_category TEXT NOT NULL
        CHECK(transaction_category IN (
            'Exchange',           -- Crypto-to-crypto or crypto-to-fiat
            'TransferIn',         -- Inbound transfers
            'TransferOut',        -- Outbound transfers
            'RetailPayment'       -- Retail payment transactions
        )),

    -- CARF Transaction Type Codes
    transaction_type TEXT NOT NULL
        CHECK(transaction_type IN (
            -- Exchange types (CARF4xx)
            'CARF401',  -- Staking
            'CARF402',  -- Crypto Loan
            'CARF403',  -- Wrapping
            'CARF404',  -- Collateral

            -- Transfer In types (CARF5xx)
            'CARF501',  -- Airdrop
            'CARF502',  -- Staking Income
            'CARF503',  -- Mining Income
            'CARF504',  -- Crypto Loan (received)
            'CARF505',  -- Transfer from RCASP
            'CARF506',  -- Sale of Goods/Services
            'CARF507',  -- Collateral (received)
            'CARF508',  -- Other
            'CARF509',  -- Unknown

            -- Transfer Out types (CARF6xx)
            'CARF601',  -- Transfer to RCASP
            'CARF602',  -- Crypto Loan (given)
            'CARF603',  -- Purchase of Goods/Services
            'CARF604',  -- Collateral (posted)
            'CARF605',  -- Other
            'CARF606'   -- Unknown
        )),

    -- Asset Information
    asset_type TEXT NOT NULL,     -- Crypto asset identifier (BTC, ETH, etc.)
    asset_name TEXT,              -- Full name if available

    -- Amounts (stored as TEXT for Decimal precision - up to 20 decimals)
    amount TEXT NOT NULL,         -- Quantity of crypto asset
    amount_fiat TEXT,             -- Fiat equivalent value
    fiat_currency TEXT,           -- ISO 4217 currency code (USD, EUR, etc.)

    -- For Exchange Transactions
    acquired_asset_type TEXT,     -- Asset received in exchange
    acquired_amount TEXT,         -- Amount received
    disposed_asset_type TEXT,     -- Asset disposed
    disposed_amount TEXT,         -- Amount disposed

    -- Transaction Details
    transaction_id TEXT,          -- Blockchain/exchange transaction ID
    timestamp TEXT NOT NULL,      -- ISO 8601: YYYY-MM-DDTHH:mm:ssZ

    -- Aggregation Support
    is_aggregated INTEGER DEFAULT 0,
    aggregation_count INTEGER DEFAULT 1,

    -- Source Tracking
    source_row INTEGER,           -- Original CSV row for error tracking
    source_file TEXT,             -- Original filename

    -- Validation Status
    validation_status TEXT DEFAULT 'pending'
        CHECK(validation_status IN ('pending', 'validated', 'error', 'suggested')),
    validation_notes TEXT,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Date validation
    CHECK(datetime(timestamp) IS NOT NULL)
);

-- ============================================================================
-- Controlling Person Table (for Entity Users)
-- ============================================================================
-- Stores controlling persons of entity users.
-- Maps to: CryptoUser/ControllingPerson

CREATE TABLE IF NOT EXISTS controlling_person (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL
        REFERENCES user(id) ON DELETE CASCADE,

    -- Identification
    first_name TEXT NOT NULL,
    middle_name TEXT,
    last_name TEXT NOT NULL,

    -- Tax Information
    tin TEXT,
    tin_unknown INTEGER DEFAULT 0,
    tin_issued_by TEXT
        REFERENCES country_codes(code),
    tax_residency TEXT NOT NULL
        REFERENCES country_codes(code),

    -- Address
    address_json TEXT,
    address_country TEXT
        REFERENCES country_codes(code),

    -- Birth Information
    birth_date TEXT,
    birth_city TEXT,
    birth_country TEXT
        REFERENCES country_codes(code),

    -- Control Type
    control_type TEXT,  -- Beneficial owner, director, etc.

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    source_row INTEGER
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_rcasp_message
    ON rcasp(message_id);

CREATE INDEX IF NOT EXISTS idx_user_rcasp
    ON user(rcasp_id);

CREATE INDEX IF NOT EXISTS idx_user_tax_residency
    ON user(tax_residency);

CREATE INDEX IF NOT EXISTS idx_transaction_user
    ON "transaction"(user_id);

CREATE INDEX IF NOT EXISTS idx_transaction_type
    ON "transaction"(transaction_type);

CREATE INDEX IF NOT EXISTS idx_transaction_timestamp
    ON "transaction"(timestamp);

CREATE INDEX IF NOT EXISTS idx_transaction_asset
    ON "transaction"(asset_type);

CREATE INDEX IF NOT EXISTS idx_transaction_category
    ON "transaction"(transaction_category);

CREATE INDEX IF NOT EXISTS idx_controlling_person_user
    ON controlling_person(user_id);

-- ============================================================================
-- Views for Common Queries
-- ============================================================================

-- User transactions summary
CREATE VIEW IF NOT EXISTS v_user_transaction_summary AS
SELECT
    u.id AS user_id,
    COALESCE(u.first_name || ' ' || u.last_name, u.entity_name) AS user_name,
    u.tax_residency,
    t.transaction_type,
    t.asset_type,
    COUNT(*) AS transaction_count,
    SUM(CAST(t.amount AS REAL)) AS total_amount
FROM user u
LEFT JOIN "transaction" t ON u.id = t.user_id
GROUP BY u.id, t.transaction_type, t.asset_type;

-- RCASP reporting summary
CREATE VIEW IF NOT EXISTS v_rcasp_summary AS
SELECT
    r.id AS rcasp_id,
    r.name AS rcasp_name,
    r.country_code,
    COUNT(DISTINCT u.id) AS user_count,
    COUNT(t.id) AS transaction_count
FROM rcasp r
LEFT JOIN user u ON r.id = u.rcasp_id
LEFT JOIN "transaction" t ON u.id = t.user_id
GROUP BY r.id;
