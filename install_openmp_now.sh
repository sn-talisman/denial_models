#!/bin/bash
# Installation script for OpenMP - run this manually

set -e

echo "🔧 Installing OpenMP and ML dependencies..."
echo ""

# Step 1: Fix Homebrew permissions
echo "📦 Step 1: Fixing Homebrew permissions..."
echo "   (You'll be prompted for your password)"
sudo chown -R $(whoami) /opt/homebrew /opt/homebrew/share/man/man8 /opt/homebrew/share/zsh /opt/homebrew/share/zsh/site-functions /opt/homebrew/var/homebrew/locks /opt/homebrew/var/log

# Step 2: Install OpenMP
echo ""
echo "📦 Step 2: Installing OpenMP runtime..."
brew install libomp

# Step 3: Verify OpenMP
echo ""
echo "🔍 Step 3: Verifying OpenMP installation..."
if [ -f "/opt/homebrew/opt/libomp/lib/libomp.dylib" ]; then
    echo "   ✅ OpenMP found at /opt/homebrew/opt/libomp/lib/libomp.dylib"
elif [ -f "/usr/local/opt/libomp/lib/libomp.dylib" ]; then
    echo "   ✅ OpenMP found at /usr/local/opt/libomp/lib/libomp.dylib"
else
    echo "   ⚠️  OpenMP not found in standard locations"
    exit 1
fi

# Step 4: Install Python packages
echo ""
echo "🐍 Step 4: Installing Python ML packages..."
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "   Virtual environment activated"
    
    echo "   Installing xgboost and lightgbm..."
    pip install --upgrade xgboost>=2.0 lightgbm>=4.1
    
    echo "   ✅ Python packages installed"
else
    echo "   ⚠️  Virtual environment not found"
    echo "   Creating venv..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install xgboost>=2.0 lightgbm>=4.1
fi

# Step 5: Verify Python packages
echo ""
echo "🧪 Step 5: Testing installation..."
if python -c "import xgboost; print('   ✅ XGBoost OK')" 2>/dev/null; then
    echo "   XGBoost imported successfully"
else
    echo "   ❌ XGBoost import failed"
    exit 1
fi

if python -c "import lightgbm; print('   ✅ LightGBM OK')" 2>/dev/null; then
    echo "   LightGBM imported successfully"
else
    echo "   ❌ LightGBM import failed"
    exit 1
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "You can now run model training:"
echo "  python scripts/train_model.py --days-back 90 --model-type lightgbm"

