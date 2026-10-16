from wardrobe_ai import config

def main() -> int:
    print("Hello world")
    print(config.PROJECT_ROOT)
    print(config.DATA_DIR)
    print(config.DB_PATH)
    return 0