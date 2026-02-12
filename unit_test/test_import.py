import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

try:
    from src.core.config_loader import get_config_loader
    print("✅ Successfully imported config_loader")
    
    # Try to initialize config loader
    # loader = get_config_loader()
    # print("✅ Successfully initialized config_loader")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
