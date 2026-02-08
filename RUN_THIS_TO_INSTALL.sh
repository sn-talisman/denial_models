#!/bin/bash
# Run this script in your terminal to install OpenMP
# It will prompt for your password when needed

cd "$(dirname "$0")"

echo "🔧 Installing OpenMP and ML dependencies..."
echo ""

# Step 1: Fix Homebrew permissions
echo "📦 Step 1: Fixing Homebrew permissions (requires password)..."
sudo chown -R $(whoami) /opt/homebrew /opt/homebrew/share/man/man8 /opt/homebrew/share/zsh /opt/homebrew/share/zsh/site-functions /opt/homebrew/var/homebrew/locks /opt/homebrew/var/log

# Step 2: Install OpenMP
echo ""
echo "📦 Step 2: Installing OpenMP runtime..."
brew install libomp

# Step 3: Verify OpenMP
echo ""
echo "🔍 Step 3: Verifying OpenMP installation..."
if [ -f "/opt/homebrew/opt/libomp/lib/libomp.dylib" ]; then
    echo "   ✅ OpenMP found"
else
    echo "   ⚠️  OpenMP not found"
    exit 1
fi

# Step 4: Install Python packages
echo ""
echo "🐍 Step 4: Installing Python ML packages..."
source venv/bin/activate
pip install --upgrade xgboost>=2.0 lightgbm>=4.1

# Step 5: Verify
echo ""
echo "🧪 Step 5: Testing..."
python -c "import xgboost; print('✅ XGBoost OK')"
python -c "import lightgbm; print('✅ LightGBM OK')"

echo ""
echo "🎉 Installation complete!"

