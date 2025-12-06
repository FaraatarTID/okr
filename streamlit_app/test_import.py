try:
    from utils.storage import start_timer
    print("Successfully imported start_timer")
except ImportError as e:
    print(f"Failed to import: {e}")
except Exception as e:
    print(f"Other error: {e}")
