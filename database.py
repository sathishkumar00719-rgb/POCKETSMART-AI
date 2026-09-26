import sqlite3

DATABASE = "pocketsmart.db"


def get_db_connection():
    conn = sqlite3.connect(DATABASE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_db():
    conn = get_db_connection()

    # =========================================
    # USERS TABLE
    # =========================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT,
            hashed_password TEXT NOT NULL,
            email_verified INTEGER DEFAULT 0,
            disabled INTEGER DEFAULT 0,
            otp_hash TEXT,
            otp_expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    # =========================================
    # PENDING USERS TABLE
    # Used during registration OTP verification
    # =========================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT,
            hashed_password TEXT NOT NULL,
            otp_hash TEXT NOT NULL,
            otp_expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    # =========================================
    # PASSWORD RESET OTP TABLE
    # Used for Forgot Password
    # =========================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            otp_hash TEXT NOT NULL,
            otp_expires_at TIMESTAMP NOT NULL,
            verified INTEGER DEFAULT 0,
            reset_token_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    conn.commit()
    conn.close()