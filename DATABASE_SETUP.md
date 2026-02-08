# Database Setup Instructions

## Current Issue

The database connection is failing with:
```
password authentication failed for user "tebra_user"
```

## Quick Fix

### Option 1: Run the fix script (if you have postgres superuser access)

```bash
./scripts/fix_db_credentials.sh
```

### Option 2: Manual Setup

Connect to PostgreSQL as a superuser and run:

```sql
-- Connect as postgres
psql -U postgres

-- Create user if it doesn't exist
CREATE USER tebra_user WITH PASSWORD 'tebra_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE tebra_dw TO tebra_user;

-- Connect to the database
\c tebra_dw

-- Grant schema privileges
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO tebra_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO tebra_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO tebra_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO tebra_user;
```

### Option 3: Verify Current Credentials

If the user already exists, verify the password:

```bash
# Test connection
PGPASSWORD=tebra_password psql -h localhost -U tebra_user -d tebra_dw -c "SELECT version();"
```

If this fails, the password might be different. Reset it:

```sql
ALTER USER tebra_user WITH PASSWORD 'tebra_password';
```

## After Setup

Once the credentials are fixed, run the training:

```bash
export DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw"
python3 scripts/train_model_with_env.py --days-back 365 --model-type lightgbm --tune --n-trials 50
```

## Alternative: Use Different Credentials

If you have different credentials that work, update the DATABASE_URL:

```bash
export DATABASE_URL="postgresql+asyncpg://YOUR_USER:YOUR_PASSWORD@localhost:5432/tebra_dw"
```

