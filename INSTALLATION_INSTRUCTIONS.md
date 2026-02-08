# OpenMP Installation - Quick Start

## ⚡ Quick Installation

**Run this command in your terminal** (it will prompt for your password):

```bash
cd /Users/ssnesargi/Documents/Code/denial-models
./RUN_THIS_TO_INSTALL.sh
```

The script will:
1. Fix Homebrew permissions (requires your password)
2. Install OpenMP runtime
3. Install XGBoost and LightGBM Python packages
4. Verify everything works

## 📋 Manual Installation (if script doesn't work)

If you prefer to run commands manually:

```bash
# 1. Fix Homebrew permissions
sudo chown -R $(whoami) /opt/homebrew

# 2. Install OpenMP
brew install libomp

# 3. Activate virtual environment
source venv/bin/activate

# 4. Install Python packages
pip install --upgrade xgboost>=2.0 lightgbm>=4.1

# 5. Verify
python -c "import xgboost; print('✅ XGBoost OK')"
python -c "import lightgbm; print('✅ LightGBM OK')"
```

## ✅ After Installation

Once installation is complete, you can train models:

```bash
# Quick test
python scripts/train_model.py --days-back 90 --limit 500 --model-type lightgbm

# Full training with hyperparameter tuning
python scripts/train_model.py \
    --days-back 180 \
    --limit 1000 \
    --model-type lightgbm \
    --tune \
    --n-trials 100
```

## 🐛 Troubleshooting

### "Library not loaded: @rpath/libomp.dylib"

This means OpenMP isn't found. Make sure:
1. OpenMP is installed: `brew list libomp`
2. Library exists: `ls -la /opt/homebrew/opt/libomp/lib/libomp.dylib`

### "Permission denied" errors

Run the permission fix:
```bash
sudo chown -R $(whoami) /opt/homebrew
```

### Python packages won't import

Try reinstalling after OpenMP is installed:
```bash
pip uninstall xgboost lightgbm
pip install xgboost>=2.0 lightgbm>=4.1
```

