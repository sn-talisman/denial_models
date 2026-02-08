#!/bin/bash
# Quick installation script for OpenMP and ML dependencies

set -e

echo "🔧 Installing OpenMP and ML dependencies..."
echo ""

# Step 1: Install OpenMP
echo "📦 Step 1: Installing OpenMP runtime..."
if command -v brew &> /dev/null; then
    echo "   Fixing Homebrew permissions (requires sudo password)..."
    sudo chown -R $(whoami) /opt/homebrew 2>/dev/null || true
    
    echo "   Installing libomp..."
    brew install libomp
    echo "   ✅ OpenMP installed"
else
    echo "   ❌ Homebrew not found. Please install Homebrew first:"
    echo "      /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi

# Step 2: Verify OpenMP
echo ""
echo "🔍 Step 2: Verifying OpenMP installation..."
if [ -f "/opt/homebrew/opt/libomp/lib/libomp.dylib" ] || [ -f "/usr/local/opt/libomp/lib/libomp.dylib" ]; then
    echo "   ✅ OpenMP found"
else
    echo "   ⚠️  OpenMP not found in standard locations"
    echo "   Please check installation manually"
fi

# Step 3: Install Python packages
echo ""
echo "🐍 Step 3: Installing Python ML packages..."
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "   Virtual environment activated"
    
    echo "   Installing xgboost and lightgbm..."
    pip install xgboost>=2.0 lightgbm>=4.1
    
    echo "   ✅ Python packages installed"
else
    echo "   ⚠️  Virtual environment not found"
    echo "   Please create venv first: python3 -m venv venv"
    exit 1
fi

# Step 4: Verify Python packages
echo ""
echo "🧪 Step 4: Testing installation..."
python -c "import xgboost; print('   ✅ XGBoost OK')" || echo "   ❌ XGBoost failed"
python -c "import lightgbm; print('   ✅ LightGBM OK')" || echo "   ❌ LightGBM failed"

echo ""
echo "🎉 Installation complete!"
echo ""
echo "You can now run model training:"
echo "  python scripts/train_model.py --days-back 90 --model-type lightgbm"

