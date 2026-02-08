#!/bin/bash
# Script to help fix database credentials

echo "🔧 Database Credential Setup"
echo ""
echo "The database connection is failing. Let's verify and fix it."
echo ""

# Try to connect as postgres user (usually has admin access)
echo "Attempting to connect as 'postgres' user..."
echo "If this works, we can create/fix the tebra_user account."
echo ""

# Check if we can connect as postgres
if psql -h localhost -U postgres -d postgres -c "\q" 2>/dev/null; then
    echo "✅ Connected as postgres user"
    echo ""
    echo "Creating/updating tebra_user..."
    psql -h localhost -U postgres -d postgres <<EOF
-- Create user if it doesn't exist
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'tebra_user') THEN
        CREATE USER tebra_user WITH PASSWORD 'tebra_password';
        RAISE NOTICE 'User tebra_user created';
    ELSE
        RAISE NOTICE 'User tebra_user already exists';
    END IF;
END
\$\$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE tebra_dw TO tebra_user;
\c tebra_dw
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO tebra_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO tebra_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO tebra_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO tebra_user;

-- Update password (in case it was wrong)
ALTER USER tebra_user WITH PASSWORD 'tebra_password';
EOF
    
    echo ""
    echo "✅ User setup complete. Testing connection..."
    PGPASSWORD=tebra_password psql -h localhost -U tebra_user -d tebra_dw -c "SELECT 'Connection successful!' as status;" 2>&1
    
else
    echo "❌ Cannot connect as postgres user"
    echo ""
    echo "Please run this manually:"
    echo ""
    echo "1. Connect to PostgreSQL as superuser:"
    echo "   psql -U postgres"
    echo ""
    echo "2. Create/update the user:"
    echo "   CREATE USER tebra_user WITH PASSWORD 'tebra_password';"
    echo "   GRANT ALL PRIVILEGES ON DATABASE tebra_dw TO tebra_user;"
    echo "   \\c tebra_dw"
    echo "   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO tebra_user;"
    echo ""
    echo "3. Or if user exists, just update password:"
    echo "   ALTER USER tebra_user WITH PASSWORD 'tebra_password';"
fi

