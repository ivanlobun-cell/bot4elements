import os
import threading
from flask import Flask
import telebot
import sqlite3
import re
import random
import time
import math
from datetime import datetime, timedelta

# ========== ТОКЕН (из переменной окружения) ==========
TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("Токен не найден! Установите переменную TELEGRAM_TOKEN")

bot = telebot.TeleBot(TOKEN)

# ========== БАЗА ДАННЫХ ==========
conn = sqlite3.connect('game.db', check_same_thread=False)
cursor = conn.cursor()

# Таблица игроков
cursor.execute('''
CREATE TABLE IF NOT EXISTS players (
    user_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    nation TEXT NOT NULL,
    level INTEGER DEFAULT 1,
    exp INTEGER DEFAULT 0,
    hp INTEGER DEFAULT 100,
    max_hp INTEGER DEFAULT 100,
    attack INTEGER DEFAULT 10,
    defense INTEGER DEFAULT 5,
    location TEXT DEFAULT 'start',
    energy INTEGER DEFAULT 50,
    max_energy INTEGER DEFAULT 50,
    skill_points INTEGER DEFAULT 0,
    stat_points INTEGER DEFAULT 0,
    gold INTEGER DEFAULT 0,
    weapon_slot INTEGER DEFAULT 0,
    armor_slot INTEGER DEFAULT 0,
    helmet_slot INTEGER DEFAULT 0,
    accessory_slot INTEGER DEFAULT 0,
    last_daily_quest TIMESTAMP,
    daily_quest TEXT,
    daily_quest_progress INTEGER DEFAULT 0,
    last_raid TIMESTAMP,
    pvp_wins INTEGER DEFAULT 0,
    pvp_losses INTEGER DEFAULT 0
)
''')
conn.commit()

# Добавление новых столбцов, если их нет
cursor.execute("PRAGMA table_info(players)")
cols = [c[1] for c in cursor.fetchall()]
for col in ['last_daily_quest', 'daily_quest', 'daily_quest_progress', 'last_raid', 'pvp_wins', 'pvp_losses']:
    if col not in cols:
        cursor.execute(f"ALTER TABLE players ADD COLUMN {col} DEFAULT NULL")
conn.commit()

# Таблица предметов
cursor.execute('''
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,  -- 'weapon','armor','helmet','accessory','potion_hp','potion_energy'
    rarity TEXT NOT NULL,
    description TEXT,
    attack_bonus INTEGER DEFAULT 0,
    defense_bonus INTEGER DEFAULT 0,
    hp_bonus INTEGER DEFAULT 0,
    energy_bonus INTEGER DEFAULT 0,
    effect_percent INTEGER DEFAULT 0,
    price_buy INTEGER DEFAULT 0,
    price_sell INTEGER DEFAULT 0
)
''')
conn.commit()

# Проверка столбцов в items (миграция)
cursor.execute("PRAGMA table_info(items)")
item_cols = [c[1] for c in cursor.fetchall()]
for col in ['attack_bonus', 'defense_bonus', 'hp_bonus', 'energy_bonus', 'effect_percent']:
    if col not in item_cols:
        cursor.execute(f"ALTER TABLE items ADD COLUMN {col} INTEGER DEFAULT 0")
conn.commit()

# Таблица инвентаря
cursor.execute('''
CREATE TABLE IF NOT EXISTS inventory (
    user_id INTEGER,
    item_id INTEGER,
    quantity INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, item_id)
)
''')
conn.commit()

# Таблица способностей игрока
cursor.execute('''
CREATE TABLE IF NOT EXISTS player_abilities (
    user_id INTEGER,
    ability_id INTEGER,
    level INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, ability_id)
)
''')
conn.commit()

# Таблица способностей (описания)
cursor.execute('''
CREATE TABLE IF NOT EXISTS abilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    nation TEXT NOT NULL,
    description TEXT,
    base_damage INTEGER DEFAULT 0,
    base_heal INTEGER DEFAULT 0,
    energy_cost INTEGER DEFAULT 10,
    unlock_level INTEGER DEFAULT 5,
    upgrade_multiplier REAL DEFAULT 1.1
)
''')
conn.commit()

# Заполнение способностей (если пусто)
cursor.execute("SELECT COUNT(*) FROM abilities")
if cursor.fetchone()[0] == 0:
    abilities_data = [
        # Вода
        ('Ледяная стрела', 'Вода', 'Наносит урон', 15, 0, 10, 5, 1.15),
        ('Исцеление', 'Вода', 'Восстанавливает HP', 0, 20, 15, 10, 1.2),
        ('Ледяной щит', 'Вода', 'Увеличивает защиту на 2 боя', 0, 0, 10, 15, 1.0),
        ('Цунами', 'Вода', 'Мощная атака', 30, 0, 20, 20, 1.1),
        ('Призыв духа', 'Вода', 'Лечит и атакует', 10, 15, 25, 25, 1.15),
        ('Ледяная буря', 'Вода', 'Сильная атака', 45, 0, 30, 30, 1.1),
        # Земля
        ('Каменный кулак', 'Земля', 'Наносит урон', 18, 0, 10, 5, 1.15),
        ('Земляная броня', 'Земля', 'Увеличивает защиту', 0, 0, 15, 10, 1.0),
        ('Дрожь земли', 'Земля', 'Атака по области', 25, 0, 15, 15, 1.1),
        ('Каменная стена', 'Земля', 'Сильно увеличивает защиту на бой', 0, 0, 20, 20, 1.0),
        ('Гнев земли', 'Земля', 'Мощная атака', 35, 0, 20, 20, 1.15),
        ('Землетрясение', 'Земля', 'Огромный урон', 55, 0, 30, 30, 1.1),
        # Огонь
        ('Огненный шар', 'Огонь', 'Наносит урон', 20, 0, 10, 5, 1.15),
        ('Огненный щит', 'Огонь', 'Увеличивает атаку на 2 боя', 0, 0, 15, 10, 1.0),
        ('Пламя', 'Огонь', 'Атака с поджогом', 28, 0, 15, 15, 1.1),
        ('Огненный дождь', 'Огонь', 'Атака по области', 35, 0, 20, 20, 1.15),
        ('Вспышка', 'Огонь', 'Критическая атака', 40, 0, 25, 25, 1.1),
        ('Пепельный вихрь', 'Огонь', 'Огромный урон', 60, 0, 30, 30, 1.1),
        # Воздух
        ('Воздушный удар', 'Воздух', 'Наносит урон', 15, 0, 8, 5, 1.15),
        ('Ветряной щит', 'Воздух', 'Увеличивает уклонение', 0, 0, 12, 10, 1.0),
        ('Ураган', 'Воздух', 'Атака по области', 25, 0, 15, 15, 1.1),
        ('Порыв ветра', 'Воздух', 'Атака и снижение защиты врага', 30, 0, 20, 20, 1.15),
        ('Шторм', 'Воздух', 'Мощная атака', 40, 0, 25, 25, 1.1),
        ('Ветряной смерч', 'Воздух', 'Огромный урон', 55, 0, 30, 30, 1.1),
    ]
    for ab in abilities_data:
        cursor.execute('''
        INSERT INTO abilities (name, nation, description, base_damage, base_heal, energy_cost, unlock_level, upgrade_multiplier)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ab)
    conn.commit()

# Заполнение предметов (если пусто)
cursor.execute("SELECT COUNT(*) FROM items")
if cursor.fetchone()[0] == 0:
    items_data = [
        # Оружие
        ('Деревянный меч', 'weapon', 'обычный', 'Простой меч', 3, 0, 0, 0, 0, 15, 7),
        ('Стальной меч', 'weapon', 'необычный', 'Крепкий клинок', 6, 0, 0, 0, 0, 40, 20),
        ('Огненный клинок', 'weapon', 'редкий', 'Пылающий меч', 12, 0, 0, 0, 0, 100, 50),
        ('Ледяной клинок', 'weapon', 'редкий', 'Меч из льда', 10, 2, 0, 0, 0, 120, 60),
        ('Молния-меч', 'weapon', 'эпический', 'Заряжен молниями', 18, 3, 0, 0, 0, 200, 100),
        # Броня
        ('Кожаный доспех', 'armor', 'обычный', 'Лёгкая броня', 0, 3, 0, 0, 0, 20, 10),
        ('Кольчуга', 'armor', 'необычный', 'Кольчужная рубаха', 0, 6, 0, 0, 0, 50, 25),
        ('Латный доспех', 'armor', 'редкий', 'Тяжёлая броня', 0, 12, 0, 0, 0, 120, 60),
        ('Доспех дракона', 'armor', 'эпический', 'Чешуя дракона', 0, 20, 10, 0, 0, 250, 125),
        # Шлемы
        ('Кожаный шлем', 'helmet', 'обычный', 'Лёгкий шлем', 0, 1, 5, 0, 0, 10, 5),
        ('Стальной шлем', 'helmet', 'необычный', 'Стальной шлем', 0, 3, 10, 0, 0, 30, 15),
        ('Шлем стража', 'helmet', 'редкий', 'Защитный шлем', 0, 5, 20, 0, 0, 80, 40),
        ('Корона мага', 'helmet', 'эпический', '+энергия и HP', 0, 2, 15, 10, 0, 150, 75),
        # Аксессуары
        ('Кольцо силы', 'accessory', 'необычный', '+2 атака', 2, 0, 0, 0, 0, 35, 17),
        ('Амулет защиты', 'accessory', 'необычный', '+2 защита', 0, 2, 0, 0, 0, 35, 17),
        ('Ожерелье жизни', 'accessory', 'редкий', '+30 HP', 0, 0, 30, 0, 0, 90, 45),
        ('Кольцо мага', 'accessory', 'редкий', '+20 энергии', 0, 0, 0, 20, 0, 90, 45),
        ('Артефакт мощи', 'accessory', 'эпический', '+5 атаки, +5 защиты', 5, 5, 0, 0, 0, 200, 100),
        # Зелья
        ('Малое зелье лечения', 'potion_hp', 'обычный', '25% HP', 0, 0, 0, 0, 25, 10, 5),
        ('Большое зелье лечения', 'potion_hp', 'необычный', '50% HP', 0, 0, 0, 0, 50, 30, 15),
        ('Зелье энергии', 'potion_energy', 'обычный', '30% энергии', 0, 0, 0, 0, 30, 15, 7),
    ]
    for item in items_data:
        cursor.execute('''
        INSERT INTO items (name, type, rarity, description, attack_bonus, defense_bonus, hp_bonus, energy_bonus, effect_percent, price_buy, price_sell)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', item)
    conn.commit()

# ========== КАРТА МИРА ==========
locations = {
    'start': {'name': 'Перекрёсток', 'desc': 'Центральный перекрёсток.', 'exits': ['south_pole','omashu','fire_capital','western_temple','spirit_forest','death_mountain']},
    'south_pole': {'name': 'Южный полюс', 'desc': 'Вечные льды.', 'exits': ['start']},
    'omashu': {'name': 'Омашу', 'desc': 'Город Земли.', 'exits': ['start'], 'has_shop': True, 'has_npc': True, 'npc_name': 'Торговец Бао'},
    'fire_capital': {'name': 'Столица Огня', 'desc': 'Сердце Огня.', 'exits': ['start'], 'has_shop': True, 'has_npc': True, 'npc_name': 'Оружейник Чжо'},
    'western_temple': {'name': 'Храм Западного ветра', 'desc': 'Воздушный храм.', 'exits': ['start']},
    'spirit_forest': {'name': 'Лес духов', 'desc': 'Мистический лес.', 'exits': ['start']},
    'death_mountain': {'name': 'Гора Смерти', 'desc': 'Опасная гора.', 'exits': ['start']}
}

# ========== МОНСТРЫ ==========
monster_templates = {
    'ice_spirit': {'name': 'Ледяной дух', 'hp': 45, 'attack': 12, 'defense': 5, 'exp': 25, 'ability': 'Ледяное дыхание', 'ability_damage': 18, 'locations': ['south_pole'], 'loot': [{'item_name': 'Малое зелье лечения', 'chance': 0.3}, {'item_name': 'Зелье энергии', 'chance': 0.2}, {'item_name': 'Кожаный шлем', 'chance': 0.02}, {'item_name': 'Кольцо силы', 'chance': 0.01}], 'gold_min': 5, 'gold_max': 15},
    'snow_wolf': {'name': 'Снежный волк', 'hp': 35, 'attack': 15, 'defense': 3, 'exp': 20, 'ability': 'Смертельный укус', 'ability_damage': 22, 'locations': ['south_pole'], 'loot': [{'item_name': 'Малое зелье лечения', 'chance': 0.25}, {'item_name': 'Кожаный доспех', 'chance': 0.02}], 'gold_min': 3, 'gold_max': 10},
    'earth_guardian': {'name': 'Страж земли', 'hp': 55, 'attack': 10, 'defense': 10, 'exp': 30, 'ability': 'Каменный кулак', 'ability_damage': 20, 'locations': ['omashu'], 'loot': [{'item_name': 'Большое зелье лечения', 'chance': 0.2}, {'item_name': 'Стальной меч', 'chance': 0.02}, {'item_name': 'Стальной шлем', 'chance': 0.02}], 'gold_min': 10, 'gold_max': 25},
    'sand_scorpion': {'name': 'Песчаный скорпион', 'hp': 30, 'attack': 18, 'defense': 2, 'exp': 22, 'ability': 'Ядовитое жало', 'ability_damage': 25, 'locations': ['omashu'], 'loot': [{'item_name': 'Зелье энергии', 'chance': 0.3}, {'item_name': 'Амулет защиты', 'chance': 0.01}], 'gold_min': 5, 'gold_max': 12},
    'fire_salamander': {'name': 'Огненная саламандра', 'hp': 50, 'attack': 20, 'defense': 6, 'exp': 28, 'ability': 'Огненный шар', 'ability_damage': 30, 'locations': ['fire_capital'], 'loot': [{'item_name': 'Малое зелье лечения', 'chance': 0.3}, {'item_name': 'Огненный клинок', 'chance': 0.01}, {'item_name': 'Кольчуга', 'chance': 0.02}], 'gold_min': 8, 'gold_max': 20},
    'ash_wraith': {'name': 'Пепельный призрак', 'hp': 40, 'attack': 22, 'defense': 4, 'exp': 35, 'ability': 'Пепельный вихрь', 'ability_damage': 28, 'locations': ['fire_capital'], 'loot': [{'item_name': 'Большое зелье лечения', 'chance': 0.25}, {'item_name': 'Ожерелье жизни', 'chance': 0.01}], 'gold_min': 12, 'gold_max': 30},
    'wind_serpent': {'name': 'Ветряной змей', 'hp': 35, 'attack': 16, 'defense': 7, 'exp': 25, 'ability': 'Ураганный порыв', 'ability_damage': 24, 'locations': ['western_temple'], 'loot': [{'item_name': 'Зелье энергии', 'chance': 0.3}, {'item_name': 'Кольцо мага', 'chance': 0.01}], 'gold_min': 6, 'gold_max': 14},
    'cloud_guardian': {'name': 'Облачный страж', 'hp': 60, 'attack': 12, 'defense': 12, 'exp': 40, 'ability': 'Грозовой разряд', 'ability_damage': 35, 'locations': ['western_temple'], 'loot': [{'item_name': 'Ледяной клинок', 'chance': 0.005}, {'item_name': 'Артефакт мощи', 'chance': 0.005}], 'gold_min': 15, 'gold_max': 35},
    'spirit_guardian': {'name': 'Хранитель леса', 'hp': 70, 'attack': 18, 'defense': 8, 'exp': 45, 'ability': 'Духовный удар', 'ability_damage': 32, 'locations': ['spirit_forest'], 'loot': [{'item_name': 'Большое зелье лечения', 'chance': 0.3}, {'item_name': 'Латный доспех', 'chance': 0.01}, {'item_name': 'Корона мага', 'chance': 0.005}], 'gold_min': 20, 'gold_max': 40},
    'lava_beast': {'name': 'Лавовый зверь', 'hp': 80, 'attack': 25, 'defense': 5, 'exp': 50, 'ability': 'Лавовый плевок', 'ability_damage': 40, 'locations': ['death_mountain'], 'loot': [{'item_name': 'Молния-меч', 'chance': 0.005}, {'item_name': 'Доспех дракона', 'chance': 0.005}, {'item_name': 'Кольцо мага', 'chance': 0.01}], 'gold_min': 25, 'gold_max': 50}
}

raid_boss = {
    'name': 'Древний дракон',
    'hp': 200,
    'attack': 35,
    'defense': 15,
    'exp': 150,
    'ability': 'Дыхание дракона',
    'ability_damage': 50,
    'gold_min': 50, 'gold_max': 100,
    'loot': [{'item_name': 'Доспех дракона', 'chance': 0.1}, {'item_name': 'Артефакт мощи', 'chance': 0.1}]
}

def get_monster_for_location(location_id):
    possible = [m for m in monster_templates.values() if location_id in m.get('locations', [])]
    if not possible:
        return {'name': 'Дикое создание', 'hp': 30, 'attack': 10, 'defense': 3, 'exp': 15, 'ability': 'Дикий рывок', 'ability_damage': 15, 'rank': 'Обычный', 'loot': [{'item_name': 'Малое зелье лечения', 'chance': 0.1}], 'gold_min': 2, 'gold_max': 8}
    monster = random.choice(possible).copy()
    roll = random.random()
    if roll < 0.6:
        rank, mult = 'Обычный', 1.0
    elif roll < 0.9:
        rank, mult = 'Элитный', 1.8
    else:
        rank, mult = 'Босс', 3.0
    monster['hp'] = int(monster['hp'] * mult)
    monster['attack'] = int(monster['attack'] * mult)
    monster['defense'] = int(monster['defense'] * mult)
    monster['exp'] = int(monster['exp'] * mult)
    monster['rank'] = rank
    monster['gold_min'] = int(monster.get('gold_min', 2) * mult)
    monster['gold_max'] = int(monster.get('gold_max', 8) * mult)
    return monster

# ========== СОСТОЯНИЯ ==========
registration_states = {}
battle_states = {}
pvp_duels = {}
restore_cooldowns = {}
pending_monsters = {}   # user_id -> монстр, ожидающий подтверждения боя

# ========== ФУНКЦИИ ИГРОКА ==========
def get_player(user_id):
    cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        columns = ['user_id','name','nation','level','exp','hp','max_hp','attack','defense','location','energy','max_energy',
                   'skill_points','stat_points','gold','weapon_slot','armor_slot','helmet_slot','accessory_slot',
                   'last_daily_quest','daily_quest','daily_quest_progress','last_raid','pvp_wins','pvp_losses']
        return dict(zip(columns, row))
    return None

def create_player(user_id, name, nation):
    if nation == 'Вода':
        atk, df = 8, 7
    elif nation == 'Земля':
        atk, df = 12, 10
    elif nation == 'Огонь':
        atk, df = 15, 5
    elif nation == 'Воздух':
        atk, df = 10, 8
    else:
        atk, df = 10, 5
    cursor.execute('''
    INSERT INTO players (user_id, name, nation, attack, defense, skill_points, stat_points, gold)
    VALUES (?, ?, ?, ?, ?, 0, 0, 0)
    ''', (user_id, name, nation, atk, df))
    conn.commit()

def save_player(user_id, **kwargs):
    for key, value in kwargs.items():
        cursor.execute(f"UPDATE players SET {key} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()

def gain_exp(user_id, amount):
    player = get_player(user_id)
    if not player:
        return False
    new_exp = player['exp'] + amount
    level_up = False
    while new_exp >= 100 * player['level']:
        new_exp -= 100 * player['level']
        player['level'] += 1
        player['max_hp'] += 10
        player['hp'] = player['max_hp']
        player['attack'] += 2
        player['defense'] += 1
        player['max_energy'] += 5
        player['energy'] = player['max_energy']
        player['skill_points'] += 1
        player['stat_points'] += 5
        level_up = True
    save_player(user_id,
                exp=new_exp, level=player['level'], max_hp=player['max_hp'], hp=player['hp'],
                attack=player['attack'], defense=player['defense'], max_energy=player['max_energy'],
                energy=player['energy'], skill_points=player['skill_points'], stat_points=player['stat_points'])
    return level_up

def heal_player(player, percent_hp=0.2, percent_energy=0.3):
    hp_heal = int(player['max_hp'] * percent_hp)
    energy_heal = int(player['max_energy'] * percent_energy)
    new_hp = min(player['hp'] + hp_heal, player['max_hp'])
    new_energy = min(player['energy'] + energy_heal, player['max_energy'])
    save_player(player['user_id'], hp=new_hp, energy=new_energy)
    return new_hp - player['hp'], new_energy - player['energy'], new_hp, new_energy

# ========== ЭКИПИРОВКА И СТАТЫ ==========
def get_item_info(item_id):
    cursor.execute('''
    SELECT id, name, type, rarity, description, attack_bonus, defense_bonus, hp_bonus, energy_bonus, effect_percent, price_buy, price_sell
    FROM items WHERE id = ?
    ''', (item_id,))
    return cursor.fetchone()

def get_total_stats(player):
    base_atk = player['attack']
    base_def = player['defense']
    base_hp = player['max_hp']
    base_en = player['max_energy']
    bonus_atk = bonus_def = bonus_hp = bonus_en = 0
    for slot in ['weapon_slot','armor_slot','helmet_slot','accessory_slot']:
        item_id = player[slot]
        if item_id > 0:
            item = get_item_info(item_id)
            if item:
                bonus_atk += item[5]
                bonus_def += item[6]
                bonus_hp += item[7]
                bonus_en += item[8]
    return {
        'attack': base_atk + bonus_atk,
        'defense': base_def + bonus_def,
        'max_hp': base_hp + bonus_hp,
        'max_energy': base_en + bonus_en,
        'bonus_attack': bonus_atk,
        'bonus_defense': bonus_def,
        'bonus_hp': bonus_hp,
        'bonus_energy': bonus_en
    }

def equip_item(user_id, item_id):
    item = get_item_info(item_id)
    if not item:
        return False, "Предмет не найден."
    typ = item[2]
    if typ not in ['weapon','armor','helmet','accessory']:
        return False, "Этот предмет нельзя экипировать."
    slot_map = {'weapon':'weapon_slot','armor':'armor_slot','helmet':'helmet_slot','accessory':'accessory_slot'}
    slot = slot_map[typ]
    player = get_player(user_id)
    old = player[slot]
    if old > 0:
        cursor.execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND item_id = ?", (user_id, old))
    cursor.execute("UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    cursor.execute("DELETE FROM inventory WHERE user_id = ? AND item_id = ? AND quantity <= 0", (user_id, item_id))
    conn.commit()
    save_player(user_id, **{slot: item_id})
    return True, f"Экипировано {item[1]}"

def unequip_item(user_id, slot):
    slot_map = {'weapon':'weapon_slot','armor':'armor_slot','helmet':'helmet_slot','accessory':'accessory_slot'}
    db_slot = slot_map.get(slot)
    if not db_slot:
        return False, "Неверный слот."
    player = get_player(user_id)
    item_id = player[db_slot]
    if item_id == 0:
        return False, "Слот пуст."
    cursor.execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    conn.commit()
    save_player(user_id, **{db_slot: 0})
    item = get_item_info(item_id)
    return True, f"Снято {item[1]}"

def add_item_to_inventory(user_id, item_name, quantity=1):
    cursor.execute("SELECT id FROM items WHERE name = ?", (item_name,))
    row = cursor.fetchone()
    if not row:
        return False
    item_id = row[0]
    cursor.execute("INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, ?) "
                   "ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = quantity + ?",
                   (user_id, item_id, quantity, quantity))
    conn.commit()
    return True

def get_inventory(user_id):
    cursor.execute('''
    SELECT items.id, items.name, items.type, items.rarity, items.description,
           items.attack_bonus, items.defense_bonus, items.hp_bonus, items.energy_bonus,
           items.effect_percent, inventory.quantity
    FROM inventory
    JOIN items ON inventory.item_id = items.id
    WHERE inventory.user_id = ?
    ''', (user_id,))
    return cursor.fetchall()

# ========== СПОСОБНОСТИ ==========
def get_player_abilities(user_id):
    cursor.execute('''
    SELECT a.id, a.name, a.nation, a.description, a.base_damage, a.base_heal, a.energy_cost, a.unlock_level, a.upgrade_multiplier, p.level
    FROM abilities a
    LEFT JOIN player_abilities p ON a.id = p.ability_id AND p.user_id = ?
    WHERE a.nation = (SELECT nation FROM players WHERE user_id = ?)
    AND a.unlock_level <= (SELECT level FROM players WHERE user_id = ?)
    ''', (user_id, user_id, user_id))
    return cursor.fetchall()

def get_ability_damage(ability, player_level):
    base = ability[4]
    upgrade_level = ability[9] if ability[9] else 1
    multiplier = ability[8] ** (upgrade_level - 1)
    return int(base * multiplier)

def get_ability_heal(ability, player_level):
    base = ability[5]
    upgrade_level = ability[9] if ability[9] else 1
    multiplier = ability[8] ** (upgrade_level - 1)
    return int(base * multiplier)

def upgrade_ability(user_id, ability_id):
    cursor.execute("SELECT level FROM player_abilities WHERE user_id = ? AND ability_id = ?", (user_id, ability_id))
    row = cursor.fetchone()
    if row:
        new_level = row[0] + 1
        cursor.execute("UPDATE player_abilities SET level = ? WHERE user_id = ? AND ability_id = ?", (new_level, user_id, ability_id))
    else:
        new_level = 2
        cursor.execute("INSERT INTO player_abilities (user_id, ability_id, level) VALUES (?, ?, ?)", (user_id, ability_id, 2))
    conn.commit()
    return new_level

# ========== ЕЖЕДНЕВНЫЕ КВЕСТЫ ==========
def generate_daily_quest():
    quests = [
        {'desc': 'Убейте 5 монстров в Южном полюсе', 'target': 'south_pole', 'count': 5, 'reward_exp': 30, 'reward_gold': 20},
        {'desc': 'Убейте 3 монстров в Омашу', 'target': 'omashu', 'count': 3, 'reward_exp': 25, 'reward_gold': 15},
        {'desc': 'Убейте 4 монстров в Столице Огня', 'target': 'fire_capital', 'count': 4, 'reward_exp': 30, 'reward_gold': 25},
        {'desc': 'Убейте 3 монстров в Лесу духов', 'target': 'spirit_forest', 'count': 3, 'reward_exp': 35, 'reward_gold': 30},
        {'desc': 'Убейте 2 монстров на Горе Смерти', 'target': 'death_mountain', 'count': 2, 'reward_exp': 40, 'reward_gold': 40},
    ]
    return random.choice(quests)

def check_daily_quest(user_id):
    player = get_player(user_id)
    if not player:
        return None
    now = datetime.now()
    if player['last_daily_quest']:
        last = datetime.strptime(player['last_daily_quest'], '%Y-%m-%d %H:%M:%S')
        if (now - last).days >= 1:
            quest = generate_daily_quest()
            save_player(user_id, daily_quest=quest['desc'], daily_quest_progress=0, last_daily_quest=now.strftime('%Y-%m-%d %H:%M:%S'))
            return quest
        else:
            if player['daily_quest']:
                return {'desc': player['daily_quest'], 'progress': player['daily_quest_progress']}
            else:
                quest = generate_daily_quest()
                save_player(user_id, daily_quest=quest['desc'], daily_quest_progress=0, last_daily_quest=now.strftime('%Y-%m-%d %H:%M:%S'))
                return quest
    else:
        quest = generate_daily_quest()
        save_player(user_id, daily_quest=quest['desc'], daily_quest_progress=0, last_daily_quest=now.strftime('%Y-%m-%d %H:%M:%S'))
        return quest

def update_daily_quest(user_id, location):
    player = get_player(user_id)
    if not player or not player['daily_quest']:
        return False, None
    import re
    numbers = re.findall(r'\d+', player['daily_quest'])
    if numbers:
        target = int(numbers[0])
        if location in player['daily_quest']:
            progress = player['daily_quest_progress'] + 1
            save_player(user_id, daily_quest_progress=progress)
            if progress >= target:
                reward_exp = 30
                reward_gold = 20
                gain_exp(user_id, reward_exp)
                player = get_player(user_id)
                save_player(user_id, gold=player['gold'] + reward_gold)
                save_player(user_id, daily_quest=None, daily_quest_progress=0)
                return True, f"Квест выполнен! Получено {reward_exp} опыта и {reward_gold} золота."
    return False, None

def can_raid(user_id):
    player = get_player(user_id)
    if not player:
        return False
    if not player['last_raid']:
        return True
    last = datetime.strptime(player['last_raid'], '%Y-%m-%d %H:%M:%S')
    return (datetime.now() - last).days >= 1

# ========== КЛАВИАТУРЫ ==========
def main_menu_keyboard():
    kb = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.add('👤 Профиль', '🗺️ Локация', '⚔️ Охота', '🚀 Переместиться')
    kb.add('💤 Восстановиться', '📈 Развитие', '🎒 Инвентарь', '⚔️ Экипировка')
    kb.add('🏪 Магазин', '📋 Ежедневный квест', '⚡ Способности', '👥 Дуэль')
    kb.add('🐉 Рейд')
    return kb

def battle_keyboard():
    kb = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.add('⚔️ Атаковать', '🛡️ Защита', '✨ Способность', '💤 Восстановление', '🧪 Зелье', '🏃 Сбежать')
    return kb

def battle_status_text(player, monster, total_stats, is_pvp=False):
    hp_label = "HP противника" if is_pvp else "HP монстра"
    return (f"❤️ Ваше HP: {player['hp']}/{total_stats['max_hp']}\n"
            f"⚡ Энергия: {player['energy']}/{total_stats['max_energy']}\n"
            f"❤️ {hp_label}: {monster['hp']}")

# ========== МЕНЮ СПОСОБНОСТЕЙ ==========
def abilities_menu(user_id):
    abilities = get_player_abilities(user_id)
    if not abilities:
        return "У вас пока нет доступных способностей. Повышайте уровень!", None
    text = "⚡ Ваши способности:\n\n"
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    for ab in abilities:
        ab_id, name, nation, desc, base_dmg, base_heal, cost, unlock, mult, level = ab
        if level is None:
            level = 1
        text += f"• {name} (ур. {level})\n"
        if base_dmg > 0:
            dmg = get_ability_damage(ab, 0)
            text += f"  Урон: {dmg}, стоимость: {cost} энергии\n"
        if base_heal > 0:
            heal = get_ability_heal(ab, 0)
            text += f"  Лечение: {heal}, стоимость: {cost} энергии\n"
        player = get_player(user_id)
        if player and player['skill_points'] > 0:
            keyboard.add(telebot.types.InlineKeyboardButton(f"Улучшить {name} (1 очко)", callback_data=f"upg_ability_{ab_id}"))
    keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    return text, keyboard

# ========== МАГАЗИН ==========
def shop_menu(user_id, category=None):
    player = get_player(user_id)
    if not player:
        return None
    categories = {
        'weapon': 'Оружие',
        'armor': 'Броня',
        'helmet': 'Шлемы',
        'accessory': 'Аксессуары',
        'potion_hp': 'Зелья HP',
        'potion_energy': 'Зелья энергии'
    }
    if category is None:
        text = "🏪 Выберите категорию:\n"
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        for key, label in categories.items():
            keyboard.add(telebot.types.InlineKeyboardButton(label, callback_data=f"shop_cat_{key}"))
        keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
        return text, keyboard
    else:
        cursor.execute('''
        SELECT id, name, type, rarity, description, attack_bonus, defense_bonus, hp_bonus, energy_bonus, price_buy
        FROM items WHERE type = ? AND price_buy > 0
        ''', (category,))
        items = cursor.fetchall()
        if not items:
            return "В этой категории нет товаров.", None
        text = f"🛒 Категория: {categories.get(category, category)}\nВаше золото: {player['gold']}\n\n"
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
        for item in items:
            item_id, name, typ, rarity, desc, atk, df, hp, en, price = item
            text += f"• {name} ({rarity})"
            if atk>0 or df>0 or hp>0 or en>0:
                text += f" [⚔️{atk} 🛡️{df} ❤️{hp} ⚡{en}]"
            text += f" — {price} золота\n"
            keyboard.add(telebot.types.InlineKeyboardButton(f"Купить {name} ({price})", callback_data=f"buy_{item_id}"))
        keyboard.add(telebot.types.InlineKeyboardButton("📤 Продать предмет", callback_data="sell_menu"))
        keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="shop_back"))
        return text, keyboard

def stats_menu(user_id):
    player = get_player(user_id)
    if not player:
        return None
    text = (f"📈 Развитие\nОчки навыков: {player['skill_points']}, Очки характеристик: {player['stat_points']}\n"
            f"⚔️ Атака: {player['attack']}\n🛡️ Защита: {player['defense']}\n"
            f"❤️ Макс. HP: {player['max_hp']}\n⚡ Макс. энергия: {player['max_energy']}")
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    if player['stat_points'] > 0:
        keyboard.add(telebot.types.InlineKeyboardButton("⚔️ +1 Атака", callback_data="stat_attack"))
        keyboard.add(telebot.types.InlineKeyboardButton("🛡️ +1 Защита", callback_data="stat_defense"))
        keyboard.add(telebot.types.InlineKeyboardButton("❤️ +10 HP", callback_data="stat_hp"))
        keyboard.add(telebot.types.InlineKeyboardButton("⚡ +5 Энергия", callback_data="stat_energy"))
    else:
        keyboard.add(telebot.types.InlineKeyboardButton("Нет очков характеристик", callback_data="noop"))
    keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    return text, keyboard

def inventory_menu(user_id):
    items = get_inventory(user_id)
    if not items:
        return "🎒 Инвентарь пуст.", None
    text = "🎒 Инвентарь:\n\n"
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    for item in items:
        item_id, name, typ, rarity, desc, atk, df, hp, en, effect, qty = item
        text += f"• {name} x{qty} ({rarity})"
        if atk>0 or df>0 or hp>0 or en>0:
            text += f" [⚔️{atk} 🛡️{df} ❤️{hp} ⚡{en}]"
        text += "\n"
        if typ in ['weapon','armor','helmet','accessory']:
            keyboard.add(telebot.types.InlineKeyboardButton(f"Экипировать {name}", callback_data=f"equip_{item_id}"))
        elif typ in ['potion_hp','potion_energy']:
            keyboard.add(telebot.types.InlineKeyboardButton(f"Использовать {name}", callback_data=f"use_item_{item_id}"))
    keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    return text, keyboard

def equipment_menu(user_id):
    player = get_player(user_id)
    if not player:
        return None
    total = get_total_stats(player)
    equipped = {}
    for slot in ['weapon','armor','helmet','accessory']:
        item_id = player[f'{slot}_slot']
        if item_id > 0:
            item = get_item_info(item_id)
            if item:
                equipped[slot] = item
    text = "⚔️ Экипировка:\n\n"
    slot_names = {'weapon':'Оружие','armor':'Броня','helmet':'Шлем','accessory':'Аксессуар'}
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    for slot_key, slot_name in slot_names.items():
        if slot_key in equipped:
            item = equipped[slot_key]
            text += f"▪ {slot_name}: {item[1]} ({item[3]})"
            if item[5]>0 or item[6]>0 or item[7]>0 or item[8]>0:
                text += f" [⚔️{item[5]} 🛡️{item[6]} ❤️{item[7]} ⚡{item[8]}]"
            text += "\n"
            keyboard.add(telebot.types.InlineKeyboardButton(f"Снять {item[1]}", callback_data=f"unequip_{slot_key}"))
        else:
            text += f"▪ {slot_name}: пусто\n"
    text += f"\nИтоговые статы:\n⚔️ {total['attack']} (база {player['attack']} + {total['bonus_attack']})\n"
    text += f"🛡️ {total['defense']} (база {player['defense']} + {total['bonus_defense']})\n"
    text += f"❤️ {total['max_hp']} (база {player['max_hp']} + {total['bonus_hp']})\n"
    text += f"⚡ {total['max_energy']} (база {player['max_energy']} + {total['bonus_energy']})"
    keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    return text, keyboard

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.chat.id
    player = get_player(user_id)
    if player:
        bot.send_message(user_id, f"С возвращением, {player['name']}!", reply_markup=main_menu_keyboard())
    else:
        bot.reply_to(message, "Добро пожаловать! Создайте персонажа командой /newgame")

@bot.message_handler(commands=['newgame'])
def new_game_cmd(message):
    user_id = message.chat.id
    if get_player(user_id):
        bot.reply_to(message, "У вас уже есть персонаж!")
        return
    registration_states[user_id] = {'step': 0, 'name': ''}
    bot.reply_to(message, "Введите имя (2–20 букв и пробелов):")

@bot.message_handler(commands=['profile'])
def profile_cmd(message):
    user_id = message.chat.id
    player = get_player(user_id)
    if not player:
        return
    total = get_total_stats(player)
    text = (f"👤 {player['name']} ({player['nation']})\n"
            f"Уровень: {player['level']}\n"
            f"Опыт: {player['exp']} / {100 * player['level']}\n"
            f"❤️ HP: {player['hp']}/{total['max_hp']}\n"
            f"⚔️ Атака: {total['attack']} (база {player['attack']} + {total['bonus_attack']})\n"
            f"🛡️ Защита: {total['defense']} (база {player['defense']} + {total['bonus_defense']})\n"
            f"⚡ Энергия: {player['energy']}/{total['max_energy']}\n"
            f"💰 Золото: {player['gold']}\n"
            f"🗺️ Локация: {locations.get(player['location'], {}).get('name', player['location'])}\n"
            f"📈 Очки навыков: {player['skill_points']}, Очки характеристик: {player['stat_points']}\n"
            f"🏆 PvP: побед {player['pvp_wins']}, поражений {player['pvp_losses']}")
    bot.reply_to(message, text)

@bot.message_handler(commands=['location'])
def location_cmd(message):
    user_id = message.chat.id
    player = get_player(user_id)
    if not player:
        return
    loc = locations.get(player['location'], locations['start'])
    text = f"🏠 {loc['name']}\n\n{loc['desc']}"
    if loc.get('has_shop'):
        text += "\n\n🛒 Здесь есть магазин!"
    if loc.get('has_npc'):
        text += f"\n👤 Здесь вы можете поговорить с {loc['npc_name']}."
    if loc['exits']:
        exits_names = [locations[eid]['name'] for eid in loc['exits'] if eid in locations]
        text += "\n\nМожно пойти: " + ", ".join(exits_names)
    bot.reply_to(message, text)

@bot.message_handler(commands=['stats'])
def stats_cmd(message):
    user_id = message.chat.id
    if not get_player(user_id):
        return
    result = stats_menu(user_id)
    if result:
        text, keyboard = result
        bot.reply_to(message, text, reply_markup=keyboard)

@bot.message_handler(commands=['reset'])
def reset_cmd(message):
    user_id = message.chat.id
    if not get_player(user_id):
        return
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton("Да, удалить", callback_data="confirm_reset"))
    keyboard.add(telebot.types.InlineKeyboardButton("Отмена", callback_data="cancel_reset"))
    bot.reply_to(message, "Удалить персонажа?", reply_markup=keyboard)

@bot.message_handler(commands=['inventory'])
def inventory_cmd(message):
    user_id = message.chat.id
    if not get_player(user_id):
        return
    result = inventory_menu(user_id)
    if result:
        text, keyboard = result
        bot.reply_to(message, text, reply_markup=keyboard)

@bot.message_handler(commands=['equip'])
def equip_cmd(message):
    user_id = message.chat.id
    if not get_player(user_id):
        return
    result = equipment_menu(user_id)
    if result:
        text, keyboard = result
        bot.reply_to(message, text, reply_markup=keyboard)

@bot.message_handler(commands=['abilities'])
def abilities_cmd(message):
    user_id = message.chat.id
    if not get_player(user_id):
        return
    result = abilities_menu(user_id)
    if result:
        text, keyboard = result
        bot.reply_to(message, text, reply_markup=keyboard)

@bot.message_handler(commands=['duel'])
def duel_cmd(message):
    user_id = message.chat.id
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Использование: /duel @username")
        return
    target_name = args[1].lstrip('@')
    cursor.execute("SELECT user_id, name FROM players WHERE name LIKE ?", (target_name,))
    row = cursor.fetchone()
    if not row:
        bot.reply_to(message, "Игрок не найден.")
        return
    target_id = row[0]
    if target_id == user_id:
        bot.reply_to(message, "Нельзя вызвать самого себя.")
        return
    if not get_player(target_id):
        bot.reply_to(message, "Игрок не найден.")
        return
    pvp_duels[target_id] = {'opponent': user_id, 'timestamp': time.time()}
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton("Принять дуэль", callback_data=f"accept_duel_{user_id}"))
    keyboard.add(telebot.types.InlineKeyboardButton("Отказаться", callback_data="decline_duel"))
    bot.send_message(target_id, f"⚔️ Игрок {get_player(user_id)['name']} вызывает вас на дуэль! Принять?", reply_markup=keyboard)
    bot.reply_to(message, "Вызов отправлен.")

@bot.message_handler(commands=['daily'])
def daily_cmd(message):
    user_id = message.chat.id
    quest = check_daily_quest(user_id)
    if isinstance(quest, dict) and 'desc' in quest:
        bot.reply_to(message, f"📋 Ежедневный квест:\n{quest['desc']}\nПрогресс: {quest.get('progress', 0)}")
    else:
        bot.reply_to(message, "Не удалось получить квест.")

@bot.message_handler(commands=['raid'])
def raid_cmd(message):
    user_id = message.chat.id
    if not can_raid(user_id):
        bot.reply_to(message, "Вы уже сражались с рейдовым боссом сегодня. Возвращайтесь завтра.")
        return
    battle_states[user_id] = {
        'monster': raid_boss.copy(),
        'defending': False,
        'restore_used': False,
        'turn': 'player',
        'is_raid': True
    }
    player = get_player(user_id)
    total = get_total_stats(player)
    bot.send_message(user_id, f"🐉 Вы вступаете в бой с {raid_boss['name']}!\n"
                              f"❤️ HP: {raid_boss['hp']}\n⚔️ Атака: {raid_boss['attack']}, 🛡️ Защита: {raid_boss['defense']}\n"
                              f"💥 {raid_boss['ability']} (урон {raid_boss['ability_damage']})\n"
                              f"{battle_status_text(player, raid_boss, total)}\n\n"
                              "Ваш ход!",
                     reply_markup=battle_keyboard())

# ========== ОБРАБОТЧИКИ ТЕКСТОВЫХ КНОПОК ==========
@bot.message_handler(func=lambda msg: msg.text == '👤 Профиль')
def profile_text(message): profile_cmd(message)
@bot.message_handler(func=lambda msg: msg.text == '🗺️ Локация')
def location_text(message): location_cmd(message)
@bot.message_handler(func=lambda msg: msg.text == '📈 Развитие')
def stats_text(message): stats_cmd(message)
@bot.message_handler(func=lambda msg: msg.text == '🎒 Инвентарь')
def inventory_text(message): inventory_cmd(message)
@bot.message_handler(func=lambda msg: msg.text == '⚔️ Экипировка')
def equip_text(message): equip_cmd(message)
@bot.message_handler(func=lambda msg: msg.text == '⚡ Способности')
def abilities_text(message): abilities_cmd(message)
@bot.message_handler(func=lambda msg: msg.text == '👥 Дуэль')
def duel_text(message):
    bot.reply_to(message, "Используйте команду /duel @username")
@bot.message_handler(func=lambda msg: msg.text == '📋 Ежедневный квест')
def daily_text(message): daily_cmd(message)
@bot.message_handler(func=lambda msg: msg.text == '🐉 Рейд')
def raid_text(message): raid_cmd(message)

@bot.message_handler(func=lambda msg: msg.text == '🏪 Магазин')
def shop_text(message):
    user_id = message.chat.id
    if not get_player(user_id):
        return
    result = shop_menu(user_id)
    if result:
        text, keyboard = result
        bot.reply_to(message, text, reply_markup=keyboard)

@bot.message_handler(func=lambda msg: msg.text == '⚔️ Охота')
def hunt_text(message):
    user_id = message.chat.id
    player = get_player(user_id)
    if not player:
        return
    if user_id in battle_states:
        bot.reply_to(message, "Вы уже в бою!")
        return
    # Генерируем монстра
    monster = get_monster_for_location(player['location'])
    # Сохраняем для дальнейшего использования
    pending_monsters[user_id] = monster
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(telebot.types.InlineKeyboardButton("⚔️ Сражаться!", callback_data="fight_confirm"))
    keyboard.add(telebot.types.InlineKeyboardButton("🏃 Убежать", callback_data="flee_encounter"))
    bot.send_message(user_id, f"⚔️ Вы встретили **{monster['rank']}** монстра **{monster['name']}**!\n"
                              f"❤️ HP: {monster['hp']}\n⚔️ Атака: {monster['attack']}, 🛡️ Защита: {monster['defense']}\n"
                              f"💥 Способность: {monster['ability']} (урон {monster['ability_damage']})\n\n"
                              "Что будете делать?",
                     reply_markup=keyboard, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == '🚀 Переместиться')
def go_text(message):
    user_id = message.chat.id
    player = get_player(user_id)
    if not player:
        return
    if user_id in battle_states:
        bot.reply_to(message, "Вы в бою! Нельзя перемещаться.")
        return
    loc = locations.get(player['location'])
    if not loc or not loc['exits']:
        bot.reply_to(message, "Отсюда никуда не уйти.")
        return
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    for eid in loc['exits']:
        exit_loc = locations.get(eid)
        if exit_loc:
            keyboard.add(telebot.types.InlineKeyboardButton(f"🚶 {exit_loc['name']}", callback_data=f"go_to_{eid}"))
    keyboard.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_go"))
    bot.reply_to(message, "Куда идём?", reply_markup=keyboard)

@bot.message_handler(func=lambda msg: msg.text == '💤 Восстановиться')
def restore_out_of_battle(message):
    user_id = message.chat.id
    player = get_player(user_id)
    if not player:
        return
    if user_id in battle_states:
        bot.reply_to(message, "Вы в бою. Используйте «Восстановление» в бою.")
        return
    now = time.time()
    last = restore_cooldowns.get(user_id, 0)
    if now - last < 60:
        remaining = int(60 - (now - last))
        bot.reply_to(message, f"💤 Вы недавно восстанавливались, попробуйте через {remaining} секунд.")
        return
    hp_heal, energy_heal, new_hp, new_energy = heal_player(player, 0.2, 0.3)
    restore_cooldowns[user_id] = now
    bot.reply_to(message, f"💤 Вы восстановили {hp_heal} HP и {energy_heal} энергии.\n"
                          f"❤️ Текущее HP: {new_hp}/{player['max_hp']}\n"
                          f"⚡ Текущая энергия: {new_energy}/{player['max_energy']}")

# ========== CALLBACK ОБРАБОТЧИКИ ==========
@bot.callback_query_handler(func=lambda call: call.data == 'back_to_menu')
def back_to_menu_callback(call):
    bot.edit_message_text("Возврат в главное меню.", chat_id=call.message.chat.id, message_id=call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'noop')
def noop_callback(call):
    bot.answer_callback_query(call.id, "Нет очков.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('stat_'))
def stat_callback(call):
    user_id = call.message.chat.id
    player = get_player(user_id)
    if not player:
        return
    if player['stat_points'] <= 0:
        bot.answer_callback_query(call.id, "Нет очков характеристик.")
        return
    if call.data == 'stat_attack':
        save_player(user_id, attack=player['attack']+1, stat_points=player['stat_points']-1)
        msg = "Атака +1"
    elif call.data == 'stat_defense':
        save_player(user_id, defense=player['defense']+1, stat_points=player['stat_points']-1)
        msg = "Защита +1"
    elif call.data == 'stat_hp':
        save_player(user_id, max_hp=player['max_hp']+10, hp=player['max_hp']+10, stat_points=player['stat_points']-1)
        msg = "HP +10, восстановлено"
    elif call.data == 'stat_energy':
        save_player(user_id, max_energy=player['max_energy']+5, energy=player['max_energy']+5, stat_points=player['stat_points']-1)
        msg = "Энергия +5, восстановлена"
    else:
        return
    bot.answer_callback_query(call.id, msg)
    result = stats_menu(user_id)
    if result:
        text, keyboard = result
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == 'fight_confirm')
def fight_confirm_callback(call):
    user_id = call.message.chat.id
    player = get_player(user_id)
    if not player:
        bot.answer_callback_query(call.id, "Ошибка персонажа.")
        return
    # Получаем монстра из хранилища
    if user_id not in pending_monsters:
        bot.answer_callback_query(call.id, "Монстр не найден. Начните охоту заново.")
        return
    monster = pending_monsters.pop(user_id)  # извлекаем и удаляем
    battle_states[user_id] = {'monster': monster, 'defending': False, 'restore_used': False, 'turn': 'player'}
    total = get_total_stats(player)
    bot.send_message(user_id, f"⚔️ Вы сражаетесь с {monster['rank']} монстром {monster['name']}!\n"
                              f"{battle_status_text(player, monster, total)}\n\nВаш ход.",
                     reply_markup=battle_keyboard())
    bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
    bot.answer_callback_query(call.id, "Бой начался!")

@bot.callback_query_handler(func=lambda call: call.data == 'flee_encounter')
def flee_encounter_callback(call):
    user_id = call.message.chat.id
    if user_id in pending_monsters:
        del pending_monsters[user_id]
    bot.edit_message_text("🏃 Вы убежали от монстра.", chat_id=call.message.chat.id, message_id=call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('go_to_') or call.data == 'cancel_go')
def go_callback(call):
    user_id = call.message.chat.id
    if user_id in battle_states:
        bot.answer_callback_query(call.id, "Вы в бою!")
        return
    player = get_player(user_id)
    if not player:
        return
    if call.data == 'cancel_go':
        bot.edit_message_text("Отмена.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    target = call.data.split('_', 2)[2]
    if target not in locations:
        bot.answer_callback_query(call.id, "Нет такой локации.")
        return
    if target not in locations.get(player['location'], {}).get('exits', []):
        bot.answer_callback_query(call.id, "Нет пути.")
        return
    save_player(user_id, location=target)
    loc = locations[target]
    bot.edit_message_text(f"Вы переместились в {loc['name']}.\n\n{loc['desc']}",
                          chat_id=call.message.chat.id, message_id=call.message.message_id)
    bot.answer_callback_query(call.id, f"Переход в {loc['name']}.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('equip_'))
def equip_callback(call):
    user_id = call.message.chat.id
    item_id = int(call.data.split('_')[1])
    success, msg = equip_item(user_id, item_id)
    bot.answer_callback_query(call.id, msg)
    if success:
        result = inventory_menu(user_id)
        if result:
            text, keyboard = result
            bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('unequip_'))
def unequip_callback(call):
    user_id = call.message.chat.id
    slot = call.data.split('_')[1]
    success, msg = unequip_item(user_id, slot)
    bot.answer_callback_query(call.id, msg)
    if success:
        result = equipment_menu(user_id)
        if result:
            text, keyboard = result
            bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('use_item_'))
def use_item_callback(call):
    user_id = call.message.chat.id
    item_id = int(call.data.split('_')[2])
    item = get_item_info(item_id)
    if not item:
        bot.answer_callback_query(call.id, "Предмет не найден.")
        return
    typ = item[2]
    player = get_player(user_id)
    if not player:
        return
    if typ == 'potion_hp':
        heal_percent = item[9] / 100.0
        hp_heal = int(player['max_hp'] * heal_percent)
        new_hp = min(player['hp'] + hp_heal, player['max_hp'])
        save_player(user_id, hp=new_hp)
        cursor.execute("UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_id = ?", (user_id, item_id))
        cursor.execute("DELETE FROM inventory WHERE user_id = ? AND item_id = ? AND quantity <= 0", (user_id, item_id))
        conn.commit()
        bot.answer_callback_query(call.id, f"Вы восстановили {new_hp - player['hp']} HP.")
    elif typ == 'potion_energy':
        heal_percent = item[9] / 100.0
        energy_heal = int(player['max_energy'] * heal_percent)
        new_energy = min(player['energy'] + energy_heal, player['max_energy'])
        save_player(user_id, energy=new_energy)
        cursor.execute("UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_id = ?", (user_id, item_id))
        cursor.execute("DELETE FROM inventory WHERE user_id = ? AND item_id = ? AND quantity <= 0", (user_id, item_id))
        conn.commit()
        bot.answer_callback_query(call.id, f"Вы восстановили {new_energy - player['energy']} энергии.")
    else:
        bot.answer_callback_query(call.id, "Этот предмет нельзя использовать.")
        return
    result = inventory_menu(user_id)
    if result:
        text, keyboard = result
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def buy_callback(call):
    user_id = call.message.chat.id
    item_id = int(call.data.split('_')[1])
    player = get_player(user_id)
    if not player:
        return
    item = get_item_info(item_id)
    if not item:
        return
    name, price = item[1], item[10]
    if player['gold'] < price:
        bot.answer_callback_query(call.id, f"Недостаточно золота! Нужно {price}.")
        return
    save_player(user_id, gold=player['gold'] - price)
    add_item_to_inventory(user_id, name, 1)
    bot.answer_callback_query(call.id, f"Куплено {name} за {price} золота.")
    result = shop_menu(user_id)
    if result:
        text, keyboard = result
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('shop_cat_'))
def shop_category_callback(call):
    user_id = call.message.chat.id
    category = call.data.split('_')[2]
    result = shop_menu(user_id, category)
    if result:
        text, keyboard = result
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'shop_back')
def shop_back_callback(call):
    user_id = call.message.chat.id
    result = shop_menu(user_id)
    if result:
        text, keyboard = result
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'sell_menu')
def sell_menu_callback(call):
    user_id = call.message.chat.id
    items = get_inventory(user_id)
    if not items:
        bot.answer_callback_query(call.id, "Нет предметов для продажи.")
        return
    text = "📤 Выберите предмет для продажи:\n"
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    for item in items:
        item_id, name, typ, rarity, desc, atk, df, hp, en, effect, qty = item
        cursor.execute("SELECT price_sell FROM items WHERE id = ?", (item_id,))
        price = cursor.fetchone()[0]
        text += f"• {name} x{qty} — {price} золота за шт.\n"
        keyboard.add(telebot.types.InlineKeyboardButton(f"Продать {name} (x{qty})", callback_data=f"sell_{item_id}"))
    keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="shop_back"))
    bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sell_'))
def sell_callback(call):
    user_id = call.message.chat.id
    item_id = int(call.data.split('_')[1])
    player = get_player(user_id)
    if not player:
        return
    cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    qty_row = cursor.fetchone()
    if not qty_row or qty_row[0] <= 0:
        bot.answer_callback_query(call.id, "Нет предмета.")
        return
    qty = qty_row[0]
    cursor.execute("SELECT price_sell FROM items WHERE id = ?", (item_id,))
    price = cursor.fetchone()[0]
    total_gold = price * qty
    save_player(user_id, gold=player['gold'] + total_gold)
    cursor.execute("DELETE FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    conn.commit()
    bot.answer_callback_query(call.id, f"Продано {qty} шт. за {total_gold} золота.")
    sell_menu_callback(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith('upg_ability_'))
def upgrade_ability_callback(call):
    user_id = call.message.chat.id
    ability_id = int(call.data.split('_')[2])
    player = get_player(user_id)
    if not player:
        bot.answer_callback_query(call.id, "Ошибка.")
        return
    if player['skill_points'] <= 0:
        bot.answer_callback_query(call.id, "Нет очков навыков.")
        return
    new_level = upgrade_ability(user_id, ability_id)
    save_player(user_id, skill_points=player['skill_points'] - 1)
    bot.answer_callback_query(call.id, f"Способность улучшена до уровня {new_level}.")
    result = abilities_menu(user_id)
    if result:
        text, keyboard = result
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard)

# ========== ПРИНЯТИЕ ДУЭЛИ ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_duel_'))
def accept_duel_callback(call):
    user_id = call.message.chat.id
    opponent_id = int(call.data.split('_')[2])
    
    if user_id not in pvp_duels or pvp_duels[user_id]['opponent'] != opponent_id:
        bot.answer_callback_query(call.id, "Вызов устарел.")
        return
    
    player1 = get_player(user_id)
    player2 = get_player(opponent_id)
    if not player1 or not player2:
        bot.answer_callback_query(call.id, "Ошибка: игрок не найден.")
        return
    
    total1 = get_total_stats(player1)
    total2 = get_total_stats(player2)
    
    monster_for_player1 = {
        'name': player2['name'],
        'hp': total2['max_hp'],
        'attack': total2['attack'],
        'defense': total2['defense'],
        'ability': 'Игрок',
        'ability_damage': 0,
        'rank': 'Игрок',
        'is_player': True,
        'real_user_id': opponent_id
    }
    monster_for_player2 = {
        'name': player1['name'],
        'hp': total1['max_hp'],
        'attack': total1['attack'],
        'defense': total1['defense'],
        'ability': 'Игрок',
        'ability_damage': 0,
        'rank': 'Игрок',
        'is_player': True,
        'real_user_id': user_id
    }
    
    battle_states[user_id] = {
        'monster': monster_for_player1,
        'defending': False,
        'restore_used': False,
        'turn': 'player',
        'is_pvp': True,
        'opponent_id': opponent_id
    }
    battle_states[opponent_id] = {
        'monster': monster_for_player2,
        'defending': False,
        'restore_used': False,
        'turn': 'player',
        'is_pvp': True,
        'opponent_id': user_id
    }
    
    if user_id in pvp_duels:
        del pvp_duels[user_id]
    
    bot.send_message(
        user_id,
        f"⚔️ Дуэль началась! Ваш противник — {player2['name']}.\n"
        f"{battle_status_text(player1, monster_for_player1, total1, is_pvp=True)}\n\n"
        "Ваш ход. Выберите действие:",
        reply_markup=battle_keyboard()
    )
    bot.send_message(
        opponent_id,
        f"⚔️ Дуэль началась! Ваш противник — {player1['name']}.\n"
        f"{battle_status_text(player2, monster_for_player2, total2, is_pvp=True)}\n\n"
        "Ваш ход. Выберите действие:",
        reply_markup=battle_keyboard()
    )
    
    bot.edit_message_text(
        "Дуэль принята! Бой начался.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'decline_duel')
def decline_duel_callback(call):
    user_id = call.message.chat.id
    if user_id in pvp_duels:
        del pvp_duels[user_id]
    bot.edit_message_text("Вы отклонили дуэль.", chat_id=call.message.chat.id, message_id=call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data in ['confirm_reset', 'cancel_reset'])
def reset_callback(call):
    user_id = call.message.chat.id
    if call.data == 'confirm_reset':
        cursor.execute("DELETE FROM players WHERE user_id = ?", (user_id,))
        conn.commit()
        if user_id in battle_states:
            del battle_states[user_id]
        if user_id in restore_cooldowns:
            del restore_cooldowns[user_id]
        bot.edit_message_text("Персонаж удалён.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id, "Удалено")
    else:
        bot.edit_message_text("Отмена.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id)

# ========== БОЕВАЯ СИСТЕМА ==========
@bot.message_handler(func=lambda msg: msg.text in ['⚔️ Атаковать', '🛡️ Защита', '✨ Способность', '💤 Восстановление', '🧪 Зелье', '🏃 Сбежать'])
def battle_action(message):
    user_id = message.chat.id
    if user_id not in battle_states:
        bot.reply_to(message, "Вы не в бою.", reply_markup=main_menu_keyboard())
        return
    action = message.text
    state = battle_states[user_id]
    monster = state['monster']
    player = get_player(user_id)
    if not player:
        if user_id in battle_states:
            del battle_states[user_id]
        return
    total = get_total_stats(player)
    atk = total['attack']
    df = total['defense']
    max_hp = total['max_hp']
    max_energy = total['max_energy']
    player['max_hp'] = max_hp
    player['max_energy'] = max_energy

    player_msg = ""
    if action == '⚔️ Атаковать':
        crit = random.random() < 0.15
        miss = random.random() < 0.10
        if miss:
            damage = 0
            player_msg = "😵 Вы промахнулись!"
        else:
            base = max(1, atk - monster['defense'] + random.randint(-2, 2))
            if crit:
                damage = int(base * 2)
                player_msg = f"💥 КРИТ! {damage} урона."
            else:
                damage = base
                player_msg = f"⚔️ {damage} урона."
        monster['hp'] -= damage
        state['defending'] = False

    elif action == '🛡️ Защита':
        state['defending'] = True
        player_msg = "🛡️ Защита."

    elif action == '✨ Способность':
        abilities = get_player_abilities(user_id)
        if not abilities:
            player_msg = "Нет доступных способностей."
        else:
            keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
            for ab in abilities:
                ab_id, name, nation, desc, base_dmg, base_heal, cost, unlock, mult, level = ab
                if level is None:
                    level = 1
                dmg = get_ability_damage(ab, player['level']) if base_dmg > 0 else 0
                heal = get_ability_heal(ab, player['level']) if base_heal > 0 else 0
                cost_energy = cost
                if player['energy'] < cost_energy:
                    continue
                label = f"{name} (ур.{level})"
                if dmg > 0:
                    label += f" урон {dmg}"
                if heal > 0:
                    label += f" лечение {heal}"
                label += f" [⚡{cost_energy}]"
                keyboard.add(telebot.types.InlineKeyboardButton(label, callback_data=f"use_ability_{ab_id}"))
            if keyboard.keyboard:
                bot.send_message(user_id, "Выберите способность:", reply_markup=keyboard)
                return
            else:
                player_msg = "Недостаточно энергии для способностей."

    elif action == '💤 Восстановление':
        if state.get('restore_used', False):
            player_msg = "Вы уже использовали восстановление в этом бою."
        else:
            hp_heal, energy_heal, new_hp, new_energy = heal_player(player, 0.2, 0.3)
            state['restore_used'] = True
            state['defending'] = False
            player['hp'] = new_hp
            player['energy'] = new_energy
            player_msg = f"💤 +{hp_heal} HP, +{energy_heal} энергии."

    elif action == '🧪 Зелье':
        inventory = get_inventory(user_id)
        potions = [item for item in inventory if item[2] in ['potion_hp','potion_energy']]
        if not potions:
            player_msg = "Нет зелий."
        else:
            keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
            for item in potions:
                item_id, name, typ, rarity, desc, atk_b, df_b, hp_b, en_b, effect, qty = item
                keyboard.add(telebot.types.InlineKeyboardButton(f"{name} x{qty}", callback_data=f"use_item_{item_id}"))
            keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_battle"))
            bot.send_message(user_id, "Выберите зелье:", reply_markup=keyboard)
            return

    elif action == '🏃 Сбежать':
        if random.random() < 0.6:
            if user_id in battle_states:
                del battle_states[user_id]
            bot.reply_to(message, "🏃 Вы сбежали!", reply_markup=main_menu_keyboard())
            return
        else:
            player_msg = "🏃 Не удалось сбежать!"

    if player_msg:
        bot.reply_to(message, player_msg)

    # Проверка смерти монстра
    if monster['hp'] <= 0:
        exp_gain = monster.get('exp', 20)
        gold_gain = random.randint(monster.get('gold_min', 2), monster.get('gold_max', 8))
        level_up = gain_exp(user_id, exp_gain)
        save_player(user_id, gold=player['gold'] + gold_gain)
        loot_msg = ""
        if 'loot' in monster:
            for loot_item in monster['loot']:
                if random.random() < loot_item['chance']:
                    add_item_to_inventory(user_id, loot_item['item_name'], 1)
                    loot_msg += f"\n🎁 + {loot_item['item_name']}!"
        if state.get('is_pvp', False):
            opponent_id = state.get('opponent_id')
            if opponent_id:
                save_player(user_id, pvp_wins=player['pvp_wins'] + 1)
                opp = get_player(opponent_id)
                if opp:
                    save_player(opponent_id, pvp_losses=opp['pvp_losses'] + 1)
                if opponent_id in battle_states:
                    del battle_states[opponent_id]
                bot.send_message(opponent_id, f"💔 Вы проиграли дуэль против {player['name']}.")
        if state.get('is_raid', False):
            save_player(user_id, last_raid=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            bot.send_message(user_id, "🐉 Рейдовый босс повержен! Возвращайтесь завтра.")
        player_loc = player['location']
        update_result = update_daily_quest(user_id, player_loc)
        if update_result and update_result[0]:
            bot.send_message(user_id, update_result[1])
        if user_id in battle_states:
            del battle_states[user_id]
        msg = f"🎉 Победа! {exp_gain} опыта, {gold_gain} золота." + loot_msg
        if level_up:
            msg += "\n🎊 Уровень повышен!"
        bot.reply_to(message, msg, reply_markup=main_menu_keyboard())
        return

    # Ход монстра (для PvP упрощённо)
    is_pvp = state.get('is_pvp', False)
    if not is_pvp:
        uses_ability = random.random() < 0.4
        if uses_ability and 'ability' in monster:
            ability_name = monster['ability']
            ability_damage = monster.get('ability_damage', 15)
            if state['defending']:
                damage = max(1, int(ability_damage * 0.5) + random.randint(-2, 2))
                state['defending'] = False
                monster_msg = f"💥 {monster['name']} использует {ability_name}! Урон {damage} (защита)."
            else:
                damage = max(1, ability_damage + random.randint(-3, 3))
                monster_msg = f"💥 {monster['name']} использует {ability_name}! Урон {damage}."
        else:
            crit = random.random() < 0.15
            miss = random.random() < 0.10
            if miss:
                damage = 0
                monster_msg = f"😵 {monster['name']} промахнулся!"
            else:
                base = max(1, monster['attack'] - df + random.randint(-2, 2))
                if crit:
                    damage = int(base * 2)
                    monster_msg = f"💥 КРИТ от {monster['name']}! Урон {damage}."
                else:
                    damage = base
                    monster_msg = f"⚔️ {monster['name']} атакует! Урон {damage}."
        player['hp'] -= damage
        save_player(user_id, hp=player['hp'])
        bot.reply_to(message, monster_msg)

        if player['hp'] <= 0:
            if user_id in battle_states:
                del battle_states[user_id]
            exp_loss = int(player['exp'] * 0.1)
            new_exp = max(0, player['exp'] - exp_loss)
            save_player(user_id, hp=max_hp, exp=new_exp, location='start')
            bot.reply_to(message, f"💀 Вы погибли! Потеряно {exp_loss} опыта.", reply_markup=main_menu_keyboard())
            return
    else:
        # PvP: ход оппонента (автоматическая атака)
        opponent_id = state.get('opponent_id')
        if opponent_id:
            opp_player = get_player(opponent_id)
            if opp_player:
                opp_total = get_total_stats(opp_player)
                crit = random.random() < 0.15
                miss = random.random() < 0.10
                if miss:
                    damage = 0
                    monster_msg = f"😵 {opp_player['name']} промахнулся!"
                else:
                    base = max(1, opp_total['attack'] - df + random.randint(-2, 2))
                    if crit:
                        damage = int(base * 2)
                        monster_msg = f"💥 КРИТ от {opp_player['name']}! Урон {damage}."
                    else:
                        damage = base
                        monster_msg = f"⚔️ {opp_player['name']} атакует! Урон {damage}."
                player['hp'] -= damage
                save_player(user_id, hp=player['hp'])
                bot.reply_to(message, monster_msg)
                if player['hp'] <= 0:
                    if user_id in battle_states:
                        del battle_states[user_id]
                    exp_loss = int(player['exp'] * 0.1)
                    new_exp = max(0, player['exp'] - exp_loss)
                    save_player(user_id, hp=max_hp, exp=new_exp, location='start')
                    bot.reply_to(message, f"💀 Вы погибли! Потеряно {exp_loss} опыта.", reply_markup=main_menu_keyboard())
                    return

    if user_id in battle_states:
        bot.reply_to(message,
                     f"{battle_status_text(player, monster, total, is_pvp)}\n\nВаш ход.",
                     reply_markup=battle_keyboard())

# ========== ОБРАБОТЧИК ВЫБОРА СПОСОБНОСТИ ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith('use_ability_'))
def use_ability_callback(call):
    user_id = call.message.chat.id
    ability_id = int(call.data.split('_')[2])
    if user_id not in battle_states:
        bot.answer_callback_query(call.id, "Вы не в бою.")
        return
    state = battle_states[user_id]
    monster = state['monster']
    player = get_player(user_id)
    if not player:
        return
    abilities = get_player_abilities(user_id)
    chosen = None
    for ab in abilities:
        if ab[0] == ability_id:
            chosen = ab
            break
    if not chosen:
        bot.answer_callback_query(call.id, "Способность не найдена.")
        return
    ab_id, name, nation, desc, base_dmg, base_heal, cost, unlock, mult, level = chosen
    if level is None:
        level = 1
    dmg = get_ability_damage(chosen, player['level']) if base_dmg > 0 else 0
    heal = get_ability_heal(chosen, player['level']) if base_heal > 0 else 0
    energy_cost = cost
    if player['energy'] < energy_cost:
        bot.answer_callback_query(call.id, f"Недостаточно энергии! Нужно {energy_cost}.")
        return
    if dmg > 0:
        monster['hp'] -= dmg
        player_msg = f"✨ {name}! Урон {dmg}."
    elif heal > 0:
        new_hp = min(player['hp'] + heal, player['max_hp'])
        save_player(user_id, hp=new_hp)
        player['hp'] = new_hp
        player_msg = f"✨ {name}! Лечение {heal} HP."
    else:
        player_msg = f"✨ {name} (эффект не реализован)"
    save_player(user_id, energy=player['energy'] - energy_cost)
    player['energy'] -= energy_cost
    bot.answer_callback_query(call.id, f"Использовано {name}.")
    bot.edit_message_text(player_msg, chat_id=call.message.chat.id, message_id=call.message.message_id)

    if monster['hp'] <= 0:
        if user_id in battle_states:
            del battle_states[user_id]
        bot.reply_to(call.message, f"🎉 Вы победили {monster['name']}!", reply_markup=main_menu_keyboard())
        return
    total = get_total_stats(player)
    is_pvp = state.get('is_pvp', False)
    bot.send_message(user_id,
                     f"{battle_status_text(player, monster, total, is_pvp)}\n\nВаш ход.",
                     reply_markup=battle_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_battle')
def back_to_battle_callback(call):
    user_id = call.message.chat.id
    if user_id not in battle_states:
        bot.answer_callback_query(call.id, "Бой окончен.")
        return
    player = get_player(user_id)
    if not player:
        return
    monster = battle_states[user_id]['monster']
    total = get_total_stats(player)
    is_pvp = battle_states[user_id].get('is_pvp', False)
    bot.edit_message_text(f"{battle_status_text(player, monster, total, is_pvp)}\n\nВаш ход.",
                          chat_id=call.message.chat.id, message_id=call.message.message_id,
                          reply_markup=battle_keyboard())
    bot.answer_callback_query(call.id)

# ========== РЕГИСТРАЦИЯ ==========
@bot.message_handler(func=lambda msg: msg.chat.id in registration_states)
def registration_handler(message):
    user_id = message.chat.id
    state = registration_states[user_id]
    if state['step'] == 0:
        name = message.text.strip()
        if len(name) < 2 or len(name) > 20 or not re.match(r'^[a-zA-Zа-яА-ЯёЁ\s]+$', name):
            bot.reply_to(message, "Имя 2–20 символов, только буквы и пробелы.")
            return
        state['name'] = name
        state['step'] = 1
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        for nation in ['💧 Вода', '🌍 Земля', '🔥 Огонь', '🌪️ Воздух']:
            keyboard.add(telebot.types.InlineKeyboardButton(nation, callback_data=f"nation_{nation}"))
        bot.reply_to(message, f"Отлично, {name}! Выберите нацию:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('nation_'))
def nation_callback(call):
    user_id = call.message.chat.id
    if user_id not in registration_states:
        bot.answer_callback_query(call.id, "Ошибка.")
        return
    state = registration_states[user_id]
    full = call.data.split('_', 1)[1]
    nation = full.split(' ', 1)[1] if ' ' in full else full
    name = state['name']
    create_player(user_id, name, nation)
    del registration_states[user_id]
    bot.edit_message_text(f"Поздравляю, {name} из народа {nation}!",
                          chat_id=call.message.chat.id, message_id=call.message.message_id)
    bot.send_message(user_id, "Используйте кнопки:", reply_markup=main_menu_keyboard())
    bot.answer_callback_query(call.id)

# ========== Flask-сервер для Render ==========
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

@app.route('/health')
def health():
    return "OK"

# ========== Запуск бота в отдельном потоке ==========
def run_bot():
    print("Бот запущен и слушает сообщения...")
    bot.infinity_polling()

if __name__ == '__main__':
    # Запускаем бота в фоновом потоке
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    # Запускаем Flask-сервер на порту, который выдаст Render
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)