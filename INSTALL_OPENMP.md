# Installing OpenMP Runtime

## Prerequisites

OpenMP is required for XGBoost and LightGBM to work. You need to install it **before** installing the Python packages.

## Step-by-Step Installation

### Step 1: Install OpenMP Runtime

**macOS (using Homebrew):**

```bash
# Fix Homebrew permissions (if needed - requires sudo password)
sudo chown -R $(whoami) /opt/homebrew

# Install OpenMP
brew install libomp
```

**Note:** You'll need to enter your password for the `sudo` command.

### Step 2: Verify OpenMP Installation

```bash
# Check if libomp.dylib exists
ls -la /opt/homebrew/opt/libomp/lib/libomp.dylib
```

If the file exists, OpenMP is installed correctly.

### Step 3: Install Python Packages

After OpenMP is installed, install the ML packages:

```bash
# Activate your virtual environment
source venv/bin/activate

# Install XGBoost and LightGBM
pip install xgboost>=2.0 lightgbm>=4.1

# Or install all dependencies from pyproject.toml
pip install -e .
```

### Step 4: Verify Installation

Test that everything works:

```bash
# Test XGBoost
python -c "import xgboost; print('✅ XGBoost OK')"

# Test LightGBM  
python -c "import lightgbm; print('✅ LightGBM OK')"
```

If both commands succeed, you're ready to train models!

### Option 2: Manual Installation

If Homebrew isn't available or you prefer manual installation:

1. **Download OpenMP:**
   - Visit: https://www.openmp.org/resources/openmp-compilers-tools/
   - Or use: `brew install libomp` (if Homebrew works)

2. **Verify Installation:**
   ```bash
   # Check if libomp.dylib exists
   ls -la /opt/homebrew/opt/libomp/lib/libomp.dylib
   # or
   ls -la /usr/local/opt/libomp/lib/libomp.dylib
   ```

### Verification

After installation, verify that XGBoost/LightGBM work:

```bash
# Activate your virtual environment
source venv/bin/activate

# Test XGBoost
python -c "import xgboost; print('✅ XGBoost OK')"

# Test LightGBM
python -c "import lightgbm; print('✅ LightGBM OK')"
```

### Alternative: Use scikit-learn

If you can't install OpenMP, you can temporarily use scikit-learn models:

```python
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier

# These don't require OpenMP
model = GradientBoostingClassifier()
```

However, XGBoost/LightGBM generally perform better for this use case.

## Troubleshooting

### "Library not loaded: @rpath/libomp.dylib"

This means OpenMP isn't found. Solutions:

1. **Install via Homebrew:**
   ```bash
   brew install libomp
   ```

2. **Set library path (temporary):**
   ```bash
   export DYLD_LIBRARY_PATH=/opt/homebrew/opt/libomp/lib:$DYLD_LIBRARY_PATH
   ```

3. **Reinstall XGBoost/LightGBM after installing OpenMP:**
   ```bash
   pip uninstall xgboost lightgbm
   pip install xgboost lightgbm
   ```

### Permission Issues with Homebrew

If you get permission errors:

```bash
# Fix ownership
sudo chown -R $(whoami) /opt/homebrew

# Fix permissions
chmod u+w /opt/homebrew
```

## Next Steps

Once OpenMP is installed, you can:

1. **Test the training pipeline:**
   ```bash
   python scripts/train_model.py --days-back 90 --limit 500 --model-type lightgbm
   ```

2. **Train with hyperparameter tuning:**
   ```bash
   python scripts/train_model.py \
       --days-back 180 \
       --limit 1000 \
       --model-type lightgbm \
       --tune \
       --n-trials 100
   ```

