
try:
    print("Importing app...")
    from app import app
    print("App imported successfully.")
except Exception as e:
    print(f"Failed to import app: {e}")
except ImportError as e:
    print(f"Import error: {e}")
