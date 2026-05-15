#!/usr/bin/env python3
"""
Скрипт для додавання нових колонок до таблиці opportunities
Запустіть: python migrate_db.py
"""

import sqlite3
import os

DB_PATH = "p2p_arbitrage.db"


def migrate():
    """Додає нові колонки до таблиці opportunities"""

    if not os.path.exists(DB_PATH):
        print(f"❌ Файл бази даних {DB_PATH} не знайдено!")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Отримуємо список існуючих колонок
    cursor.execute("PRAGMA table_info(opportunities)")
    existing_columns = [col[1] for col in cursor.fetchall()]

    print(f"📋 Існуючі колонки: {existing_columns}")
    print("-" * 50)

    # Список нових колонок для додавання
    new_columns = [
        ("buy_status", "TEXT", "unknown"),
        ("sell_status", "TEXT", "unknown"),
        ("buy_is_recommended", "INTEGER", "0"),
        ("sell_is_recommended", "INTEGER", "0")
    ]

    added = []
    skipped = []

    for col_name, col_type, default_value in new_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE opportunities ADD COLUMN {col_name} {col_type} DEFAULT {default_value}")
                added.append(col_name)
                print(f"✅ Додано колонку: {col_name} ({col_type})")
            except Exception as e:
                print(f"❌ Помилка при додаванні {col_name}: {e}")
        else:
            skipped.append(col_name)
            print(f"⏭ Колонка вже існує: {col_name}")

    if added:
        conn.commit()
        print("-" * 50)
        print(f"✅ Успішно додано колонки: {added}")
    else:
        print("ℹ️ Всі колонки вже існують. Нічого не додано.")

    # Перевіряємо результат
    cursor.execute("PRAGMA table_info(opportunities)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"\n📋 Підсумкові колонки: {columns}")

    conn.close()
    return True


def reset_database():
    """Повне скидання БД (якщо потрібно)"""
    if os.path.exists(DB_PATH):
        confirm = input(f"⚠️ Видалити {DB_PATH}? (yes/no): ")
        if confirm.lower() == 'yes':
            os.remove(DB_PATH)
            print(f"🗑 Файл {DB_PATH} видалено")
            return True
    return False


if __name__ == "__main__":
    print("=" * 50)
    print("🏦 Міграція бази даних P2P Arbitrage Bot")
    print("=" * 50)
    print()

    # Питаємо користувача
    print("1. Додати нові колонки до існуючої БД")
    print("2. Повністю скинути БД (ВСІ ДАНІ БУДУТЬ ВТРАЧЕНІ)")
    print("3. Вийти")

    choice = input("\nВиберіть опцію (1/2/3): ").strip()

    if choice == "1":
        migrate()
    elif choice == "2":
        if reset_database():
            print("✅ Базу даних скинуто. При наступному запуску бот створить нову БД з усіма колонками.")
        else:
            print("❌ Скидання скасовано")
    else:
        print("👋 Вихід")