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

# ========== ИМПОРТ ДАННЫХ ==========
from data import locations, monster_templates, items_data, raid_boss, daily_quests_pool, nation_info

# ========== ТОКЕН ==========
TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("Токен не найден! Установите переменную TELEGRAM_TOKEN")

bot = telebot.TeleBot(TOKEN)

# ========== ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ ==========
conn = sqlite3.connect('game.db', check_same_thread=False)

# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==========
def init_db():
    c = conn.cursor()
    c.execute('''
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
        daily_quest_target TEXT,
        daily_quest_count INTEGER DEFAULT 0,
        daily_quest_reward_exp INTEGER DEFAULT 0,
        daily_quest_reward_gold INTEGER DEFAULT 0,
        last_raid TIMESTAMP,
        pvp_wins INTEGER DEFAULT 0,
        pvp_losses INTEGER DEFAULT 0,
        total_kills INTEGER DEFAULT 0,
        total_duels INTEGER DEFAULT 0,
        total_quests INTEGER DEFAULT 0,
        total_gold_earned INTEGER DEFAULT 0
    )
    ''')
    c.execute("PRAGMA table_info(players)")
    existing_cols = [col[1] for col in c.fetchall()]
    for col in ['last_daily_quest', 'daily_quest', 'daily_quest_progress', 'daily_quest_target',
                'daily_quest_count', 'daily_quest_reward_exp', 'daily_quest_reward_gold',
                'last_raid', 'pvp_wins', 'pvp_losses', 'total_kills', 'total_duels',
                'total_quests', 'total_gold_earned']:
        if col not in existing_cols:
            c.execute(f"ALTER TABLE players ADD COLUMN {col} DEFAULT NULL")
    conn.commit()

    c.execute('''
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
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
    c.execute("PRAGMA table_info(items)")
    item_cols = [col[1] for col in c.fetchall()]
    for col in ['attack_bonus', 'defense_bonus', 'hp_bonus', 'energy_bonus', 'effect_percent']:
        if col not in item_cols:
            c.execute(f"ALTER TABLE items ADD COLUMN {col} INTEGER DEFAULT 0")
    conn.commit()

    c.execute('''
    CREATE TABLE IF NOT EXISTS inventory (
        user_id INTEGER,
        item_id INTEGER,
        quantity INTEGER DEFAULT 1,
        PRIMARY KEY (user_id, item_id)
    )
    ''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS player_abilities (
        user_id INTEGER,
        ability_id INTEGER,
        level INTEGER DEFAULT 1,
        PRIMARY KEY (user_id, ability_id)
    )
    ''')
    c.execute('''
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
    c.execute("SELECT COUNT(*) FROM abilities")
    if c.fetchone()[0] == 0:
        abilities_data = [
            ('❄️ Ледяная стрела', 'Вода', 'Выпускает ледяной снаряд.', 15, 0, 10, 5, 1.15),
            ('💧 Исцеление', 'Вода', 'Восстанавливает часть здоровья.', 0, 20, 15, 10, 1.2),
            ('🛡️ Ледяной щит', 'Вода', 'Создаёт ледяную защиту.', 0, 0, 10, 15, 1.0),
            ('🌊 Цунами', 'Вода', 'Огромная волна.', 30, 0, 20, 20, 1.1),
            ('👻 Призыв духа', 'Вода', 'Дух воды атакует и лечит.', 10, 15, 25, 25, 1.15),
            ('🌀 Ледяная буря', 'Вода', 'Ледяной вихрь.', 45, 0, 30, 30, 1.1),
            ('🗿 Каменный кулак', 'Земля', 'Мощный удар.', 18, 0, 10, 5, 1.15),
            ('🪨 Земляная броня', 'Земля', 'Увеличивает защиту.', 0, 0, 15, 10, 1.0),
            ('🌍 Дрожь земли', 'Земля', 'Землетрясение.', 25, 0, 15, 15, 1.1),
            ('🧱 Каменная стена', 'Земля', 'Стена, уменьшающая урон.', 0, 0, 20, 20, 1.0),
            ('💢 Гнев земли', 'Земля', 'Разрушительная атака.', 35, 0, 20, 20, 1.15),
            ('🌋 Землетрясение', 'Земля', 'Огромный урон.', 55, 0, 30, 30, 1.1),
            ('🔥 Огненный шар', 'Огонь', 'Огненный снаряд.', 20, 0, 10, 5, 1.15),
            ('🛡️ Огненный щит', 'Огонь', 'Повышает атаку.', 0, 0, 15, 10, 1.0),
            ('🔥 Пламя', 'Огонь', 'Поджигает врага.', 28, 0, 15, 15, 1.1),
            ('☄️ Огненный дождь', 'Огонь', 'Град огненных шаров.', 35, 0, 20, 20, 1.15),
            ('💥 Вспышка', 'Огонь', 'Критическая атака.', 40, 0, 25, 25, 1.1),
            ('🌪️ Пепельный вихрь', 'Огонь', 'Огненный смерч.', 60, 0, 30, 30, 1.1),
            ('💨 Воздушный удар', 'Воздух', 'Удар воздухом.', 15, 0, 8, 5, 1.15),
            ('🍃 Ветряной щит', 'Воздух', 'Увеличивает уклонение.', 0, 0, 12, 10, 1.0),
            ('🌪️ Ураган', 'Воздух', 'Мощный ураган.', 25, 0, 15, 15, 1.1),
            ('🌬️ Порыв ветра', 'Воздух', 'Ослабляет защиту врага.', 30, 0, 20, 20, 1.15),
            ('⛈️ Шторм', 'Воздух', 'Грозовой шторм.', 40, 0, 25, 25, 1.1),
            ('🌀 Ветряной смерч', 'Воздух', 'Огромный смерч.', 55, 0, 30, 30, 1.1),
        ]
        for ab in abilities_data:
            c.execute('''
            INSERT INTO abilities (name, nation, description, base_damage, base_heal, energy_cost, unlock_level, upgrade_multiplier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', ab)
        conn.commit()
    c.execute("SELECT COUNT(*) FROM items")
    if c.fetchone()[0] == 0 and items_data:
        for item in items_data:
            c.execute('''
            INSERT INTO items (name, type, rarity, description, attack_bonus, defense_bonus, hp_bonus, energy_bonus, effect_percent, price_buy, price_sell)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', item)
        conn.commit()
    c.close()

init_db()

# ========== СОСТОЯНИЯ ==========
registration_states = {}
battle_states = {}
pvp_duels = {}
restore_cooldowns = {}
pending_monsters = {}

# ========== СПИСОК РАЗРАБОТЧИКОВ (по user_id) ==========
# Замените 123456789 на ваш реальный user_id (узнайте через /myid)
DEVELOPER_IDS = [402629657]  # <-- СЮДА ВСТАВЬТЕ СВОЙ ID, КОТОРЫЙ ВЫ УЗНАЕТЕ ЧЕРЕЗ /myid

def is_developer(user_id):
    """Проверяет, является ли пользователь разработчиком."""
    return user_id in DEVELOPER_IDS

# ========== КОМАНДА ДЛЯ УЗНАВАНИЯ СВОЕГО USER_ID ==========
@bot.message_handler(commands=['myid'])
def myid_cmd(message):
    user_id = message.from_user.id
    bot.reply_to(message, f"Ваш user_id: `{user_id}`", parse_mode='Markdown')

# ========== ФУНКЦИИ РАБОТЫ С БД (локальные курсоры) ==========
def get_player(user_id):
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    c.close()
    if row:
        columns = ['user_id','name','nation','level','exp','hp','max_hp','attack','defense','location','energy','max_energy',
                   'skill_points','stat_points','gold','weapon_slot','armor_slot','helmet_slot','accessory_slot',
                   'last_daily_quest','daily_quest','daily_quest_progress','daily_quest_target','daily_quest_count',
                   'daily_quest_reward_exp','daily_quest_reward_gold',
                   'last_raid','pvp_wins','pvp_losses','total_kills','total_duels','total_quests','total_gold_earned']
        return dict(zip(columns, row))
    return None

def create_player(user_id, name, nation):
    stats = nation_info.get(nation, {'attack': 10, 'defense': 5})
    atk = stats['attack']
    df = stats['defense']
    c = conn.cursor()
    c.execute('''
    INSERT INTO players (user_id, name, nation, attack, defense, skill_points, stat_points, gold,
                         total_kills, total_duels, total_quests, total_gold_earned)
    VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0)
    ''', (user_id, name, nation, atk, df))
    conn.commit()
    c.close()

def save_player(user_id, **kwargs):
    if not kwargs:
        return
    c = conn.cursor()
    for key, value in kwargs.items():
        c.execute(f"UPDATE players SET {key} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    c.close()

def add_item_to_inventory(user_id, item_name, quantity=1):
    c = conn.cursor()
    c.execute("SELECT id FROM items WHERE name = ?", (item_name,))
    row = c.fetchone()
    if not row:
        c.close()
        return False
    item_id = row[0]
    c.execute("INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, ?) "
              "ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = quantity + ?",
              (user_id, item_id, quantity, quantity))
    conn.commit()
    c.close()
    return True

def get_inventory(user_id):
    c = conn.cursor()
    c.execute('''
    SELECT items.id, items.name, items.type, items.rarity, items.description,
           items.attack_bonus, items.defense_bonus, items.hp_bonus, items.energy_bonus,
           items.effect_percent, inventory.quantity
    FROM inventory
    JOIN items ON inventory.item_id = items.id
    WHERE inventory.user_id = ?
    ''', (user_id,))
    result = c.fetchall()
    c.close()
    return result

def get_item_info(item_id):
    c = conn.cursor()
    c.execute('''
    SELECT id, name, type, rarity, description, attack_bonus, defense_bonus, hp_bonus, energy_bonus, effect_percent, price_buy, price_sell
    FROM items WHERE id = ?
    ''', (item_id,))
    row = c.fetchone()
    c.close()
    return row

def get_player_abilities(user_id):
    c = conn.cursor()
    c.execute('''
    SELECT a.id, a.name, a.nation, a.description, a.base_damage, a.base_heal, a.energy_cost, a.unlock_level, a.upgrade_multiplier, p.level
    FROM abilities a
    LEFT JOIN player_abilities p ON a.id = p.ability_id AND p.user_id = ?
    WHERE a.nation = (SELECT nation FROM players WHERE user_id = ?)
    AND a.unlock_level <= (SELECT level FROM players WHERE user_id = ?)
    ''', (user_id, user_id, user_id))
    result = c.fetchall()
    c.close()
    return result

def upgrade_ability(user_id, ability_id):
    c = conn.cursor()
    c.execute("SELECT level FROM player_abilities WHERE user_id = ? AND ability_id = ?", (user_id, ability_id))
    row = c.fetchone()
    if row:
        new_level = row[0] + 1
        c.execute("UPDATE player_abilities SET level = ? WHERE user_id = ? AND ability_id = ?", (new_level, user_id, ability_id))
    else:
        new_level = 2
        c.execute("INSERT INTO player_abilities (user_id, ability_id, level) VALUES (?, ?, ?)", (user_id, ability_id, 2))
    conn.commit()
    c.close()
    return new_level

def get_monster_for_location(location_id):
    possible = [m for m in monster_templates.values() if location_id in m.get('locations', [])]
    if not possible:
        return {
            'name': '👾 Дикое создание',
            'desc': 'Неизвестное существо.',
            'hp': 30, 'attack': 10, 'defense': 3, 'exp': 15,
            'ability': '💢 Дикий рывок',
            'ability_damage': 15,
            'rank': 'Обычный',
            'loot': [{'item_name': '🧪 Малое зелье лечения', 'chance': 0.1}],
            'gold_min': 2, 'gold_max': 8
        }
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
    monster['gold_min'] = int(monster['gold_min'] * mult)
    monster['gold_max'] = int(monster['gold_max'] * mult)
    monster['rank'] = rank
    return monster

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
    c = conn.cursor()
    if old > 0:
        c.execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND item_id = ?", (user_id, old))
    c.execute("UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    c.execute("DELETE FROM inventory WHERE user_id = ? AND item_id = ? AND quantity <= 0", (user_id, item_id))
    conn.commit()
    c.close()
    save_player(user_id, **{slot: item_id})
    return True, f"✅ Экипировано {item[1]}"

def unequip_item(user_id, slot):
    slot_map = {'weapon':'weapon_slot','armor':'armor_slot','helmet':'helmet_slot','accessory':'accessory_slot'}
    db_slot = slot_map.get(slot)
    if not db_slot:
        return False, "Неверный слот."
    player = get_player(user_id)
    item_id = player[db_slot]
    if item_id == 0:
        return False, "Слот пуст."
    c = conn.cursor()
    c.execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    conn.commit()
    c.close()
    save_player(user_id, **{db_slot: 0})
    item = get_item_info(item_id)
    return True, f"✅ Снято {item[1]}"

def generate_daily_quest():
    quest = random.choice(daily_quests_pool)
    return {
        'desc': quest['desc'],
        'target': quest['target'],
        'count': quest['count'],
        'reward_exp': quest['reward_exp'],
        'reward_gold': quest['reward_gold']
    }

def check_daily_quest(user_id):
    player = get_player(user_id)
    if not player:
        return None
    now = datetime.now()
    if player['last_daily_quest']:
        last = datetime.strptime(player['last_daily_quest'], '%Y-%m-%d %H:%M:%S')
        if (now - last).days >= 1:
            quest = generate_daily_quest()
            save_player(user_id,
                        daily_quest=quest['desc'],
                        daily_quest_progress=0,
                        daily_quest_target=quest['target'],
                        daily_quest_count=quest['count'],
                        daily_quest_reward_exp=quest['reward_exp'],
                        daily_quest_reward_gold=quest['reward_gold'],
                        last_daily_quest=now.strftime('%Y-%m-%d %H:%M:%S'))
            return quest
        else:
            if player['daily_quest']:
                return {
                    'desc': player['daily_quest'],
                    'target': player['daily_quest_target'],
                    'count': player['daily_quest_count'],
                    'progress': player['daily_quest_progress'],
                    'reward_exp': player['daily_quest_reward_exp'],
                    'reward_gold': player['daily_quest_reward_gold']
                }
            else:
                quest = generate_daily_quest()
                save_player(user_id,
                            daily_quest=quest['desc'],
                            daily_quest_progress=0,
                            daily_quest_target=quest['target'],
                            daily_quest_count=quest['count'],
                            daily_quest_reward_exp=quest['reward_exp'],
                            daily_quest_reward_gold=quest['reward_gold'],
                            last_daily_quest=now.strftime('%Y-%m-%d %H:%M:%S'))
                return quest
    else:
        quest = generate_daily_quest()
        save_player(user_id,
                    daily_quest=quest['desc'],
                    daily_quest_progress=0,
                    daily_quest_target=quest['target'],
                    daily_quest_count=quest['count'],
                    daily_quest_reward_exp=quest['reward_exp'],
                    daily_quest_reward_gold=quest['reward_gold'],
                    last_daily_quest=now.strftime('%Y-%m-%d %H:%M:%S'))
        return quest

def update_daily_quest(user_id, location_id):
    player = get_player(user_id)
    if not player or not player['daily_quest'] or not player['daily_quest_target']:
        return False, None
    if player['daily_quest_target'] != location_id:
        return False, None
    new_progress = player['daily_quest_progress'] + 1
    save_player(user_id, daily_quest_progress=new_progress)
    if new_progress >= player['daily_quest_count']:
        reward_exp = player['daily_quest_reward_exp']
        reward_gold = player['daily_quest_reward_gold']
        gain_exp(user_id, reward_exp)
        player2 = get_player(user_id)
        save_player(user_id, gold=player2['gold'] + reward_gold, total_quests=player2['total_quests'] + 1)
        save_player(user_id,
                    daily_quest=None,
                    daily_quest_progress=0,
                    daily_quest_target=None,
                    daily_quest_count=0,
                    daily_quest_reward_exp=0,
                    daily_quest_reward_gold=0)
        return True, f"✅ **Квест выполнен!**\nПолучено {reward_exp} опыта и {reward_gold} золота."
    else:
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
    kb.add('👤 Профиль', '🗺️ Карта', '📍 Локация', '⚔️ Охота', '🚀 Переместиться')
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

# ========== МЕНЮ (inline-клавиатуры) ==========
def abilities_menu(user_id):
    abilities = get_player_abilities(user_id)
    if not abilities:
        return "📚 У вас пока нет доступных способностей. Повышайте уровень!", None
    text = "⚡ **Ваши способности:**\n\n"
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    for ab in abilities:
        ab_id, name, nation, desc, base_dmg, base_heal, cost, unlock, mult, level = ab
        if level is None:
            level = 1
        text += f"**{name}** (ур. {level})\n"
        text += f"_{desc}_\n"
        if base_dmg > 0:
            dmg = get_ability_damage(ab, 0)
            text += f"  ⚔️ Урон: {dmg}, ⚡ Стоимость: {cost} энергии\n"
        if base_heal > 0:
            heal = get_ability_heal(ab, 0)
            text += f"  💚 Лечение: {heal}, ⚡ Стоимость: {cost} энергии\n"
        player = get_player(user_id)
        if player and player['skill_points'] > 0:
            keyboard.add(telebot.types.InlineKeyboardButton(f"⬆️ Улучшить {name} (1 очко)", callback_data=f"upg_ability_{ab_id}"))
    keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    return text, keyboard

def shop_menu(user_id, category=None):
    player = get_player(user_id)
    if not player:
        return None
    categories = {
        'weapon': '⚔️ Оружие',
        'armor': '🛡️ Броня',
        'helmet': '⛑️ Шлемы',
        'accessory': '💍 Аксессуары',
        'potion_hp': '🧪 Зелья HP',
        'potion_energy': '🧪 Зелья энергии'
    }
    if category is None:
        text = "🏪 **Выберите категорию товаров:**"
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        for key, label in categories.items():
            keyboard.add(telebot.types.InlineKeyboardButton(label, callback_data=f"shop_cat_{key}"))
        keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
        return text, keyboard
    else:
        c = conn.cursor()
        c.execute('''
        SELECT id, name, type, rarity, description, attack_bonus, defense_bonus, hp_bonus, energy_bonus, price_buy
        FROM items WHERE type = ? AND price_buy > 0
        ''', (category,))
        items = c.fetchall()
        c.close()
        if not items:
            return "📭 В этой категории нет товаров.", None
        text = f"🛒 **Категория:** {categories.get(category, category)}\n💰 **Ваше золото:** {player['gold']}\n\n"
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
        for item in items:
            item_id, name, typ, rarity, desc, atk, df, hp, en, price = item
            text += f"**{name}** ({rarity})\n"
            text += f"_{desc}_\n"
            if atk>0 or df>0 or hp>0 or en>0:
                text += f"  ⚔️{atk} 🛡️{df} ❤️{hp} ⚡{en}\n"
            text += f"  💰 Цена: {price} золота\n\n"
            keyboard.add(telebot.types.InlineKeyboardButton(f"Купить {name} ({price} золота)", callback_data=f"buy_{item_id}"))
        keyboard.add(telebot.types.InlineKeyboardButton("📤 Продать предмет", callback_data="sell_menu"))
        keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="shop_back"))
        return text, keyboard

def stats_menu(user_id):
    player = get_player(user_id)
    if not player:
        return None
    text = (f"📈 **Развитие персонажа**\n"
            f"🔹 Очки навыков: {player['skill_points']}\n"
            f"🔹 Очки характеристик: {player['stat_points']}\n\n"
            f"**Текущие характеристики:**\n"
            f"⚔️ Атака: {player['attack']}\n"
            f"🛡️ Защита: {player['defense']}\n"
            f"❤️ Макс. HP: {player['max_hp']}\n"
            f"⚡ Макс. энергия: {player['max_energy']}")
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
    text = "🎒 **Ваш инвентарь:**\n\n"
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    for item in items:
        item_id, name, typ, rarity, desc, atk, df, hp, en, effect, qty = item
        text += f"**{name}** x{qty} ({rarity})\n"
        text += f"_{desc}_\n"
        if atk>0 or df>0 or hp>0 or en>0:
            text += f"  ⚔️{atk} 🛡️{df} ❤️{hp} ⚡{en}\n"
        text += "\n"
        if typ in ['weapon','armor','helmet','accessory']:
            keyboard.add(telebot.types.InlineKeyboardButton(f"✅ Экипировать {name}", callback_data=f"equip_{item_id}"))
        elif typ in ['potion_hp','potion_energy']:
            keyboard.add(telebot.types.InlineKeyboardButton(f"🧪 Использовать {name}", callback_data=f"use_item_{item_id}"))
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
    text = "⚔️ **Ваша экипировка:**\n\n"
    slot_names = {'weapon':'Оружие','armor':'Броня','helmet':'Шлем','accessory':'Аксессуар'}
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    for slot_key, slot_name in slot_names.items():
        if slot_key in equipped:
            item = equipped[slot_key]
            text += f"**{slot_name}:** {item[1]} ({item[3]})\n"
            text += f"_{item[4]}_\n"
            if item[5]>0 or item[6]>0 or item[7]>0 or item[8]>0:
                text += f"  ⚔️{item[5]} 🛡️{item[6]} ❤️{item[7]} ⚡{item[8]}\n"
            text += "\n"
            keyboard.add(telebot.types.InlineKeyboardButton(f"❌ Снять {item[1]}", callback_data=f"unequip_{slot_key}"))
        else:
            text += f"**{slot_name}:** пусто\n\n"
    text += f"**Итоговые статы с учётом экипировки:**\n"
    text += f"⚔️ Атака: {total['attack']} (база {player['attack']} + {total['bonus_attack']})\n"
    text += f"🛡️ Защита: {total['defense']} (база {player['defense']} + {total['bonus_defense']})\n"
    text += f"❤️ Макс. HP: {total['max_hp']} (база {player['max_hp']} + {total['bonus_hp']})\n"
    text += f"⚡ Макс. энергия: {total['max_energy']} (база {player['max_energy']} + {total['bonus_energy']})"
    keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    return text, keyboard

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ СПОСОБНОСТЕЙ ==========
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

# ========== СКРЫТЫЕ КОМАНДЫ ДЛЯ РАЗРАБОТЧИКА ==========
@bot.message_handler(commands=['dev_help'])
def dev_help(message):
    if not is_developer(message.from_user.id):
        return
    help_text = "🔧 **Команды разработчика:**\n\n"
    help_text += "/dev_add_exp <количество> - добавить опыт\n"
    help_text += "/dev_set_level <уровень> - установить уровень\n"
    help_text += "/dev_add_gold <количество> - добавить золото\n"
    help_text += "/dev_add_item <название> [количество] - добавить предмет\n"
    help_text += "/dev_teleport <id_локации> - телепорт\n"
    help_text += "/dev_reset_quest - сбросить квест\n"
    help_text += "/dev_heal - полное восстановление\n"
    help_text += "/dev_give_all_items - выдать все предметы\n"
    help_text += "/dev_spawn <имя_монстра> - спавн монстра для боя\n"
    help_text += "/dev_kill - убить текущего монстра\n"
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['dev_add_exp'])
def dev_add_exp(message):
    if not is_developer(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Использование: /dev_add_exp <количество>")
        return
    try:
        amount = int(args[1])
        gain_exp(message.from_user.id, amount)
        bot.reply_to(message, f"✅ Добавлено {amount} опыта.")
    except ValueError:
        bot.reply_to(message, "❌ Введите число.")

@bot.message_handler(commands=['dev_set_level'])
def dev_set_level(message):
    if not is_developer(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Использование: /dev_set_level <уровень>")
        return
    try:
        new_level = int(args[1])
        player = get_player(message.from_user.id)
        if not player:
            bot.reply_to(message, "❌ Персонаж не найден.")
            return
        save_player(message.from_user.id, level=new_level)
        bot.reply_to(message, f"✅ Уровень установлен на {new_level}.")
    except ValueError:
        bot.reply_to(message, "❌ Введите число.")

@bot.message_handler(commands=['dev_add_gold'])
def dev_add_gold(message):
    if not is_developer(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Использование: /dev_add_gold <количество>")
        return
    try:
        amount = int(args[1])
        player = get_player(message.from_user.id)
        if not player:
            bot.reply_to(message, "❌ Персонаж не найден.")
            return
        save_player(message.from_user.id, gold=player['gold'] + amount)
        bot.reply_to(message, f"✅ Добавлено {amount} золота.")
    except ValueError:
        bot.reply_to(message, "❌ Введите число.")

@bot.message_handler(commands=['dev_add_item'])
def dev_add_item(message):
    if not is_developer(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Использование: /dev_add_item <название> [количество]")
        return
    item_name = ' '.join(args[1:])
    quantity = 1
    if args[-1].isdigit():
        quantity = int(args[-1])
        item_name = ' '.join(args[1:-1])
    c = conn.cursor()
    c.execute("SELECT id FROM items WHERE name = ?", (item_name,))
    if not c.fetchone():
        bot.reply_to(message, f"❌ Предмет '{item_name}' не найден.")
        c.close()
        return
    c.close()
    add_item_to_inventory(message.from_user.id, item_name, quantity)
    bot.reply_to(message, f"✅ Добавлено {quantity} шт. {item_name}.")

@bot.message_handler(commands=['dev_teleport'])
def dev_teleport(message):
    if not is_developer(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Использование: /dev_teleport <id_локации>")
        return
    loc_id = args[1]
    if loc_id not in locations:
        bot.reply_to(message, f"❌ Локация '{loc_id}' не найдена.")
        return
    save_player(message.from_user.id, location=loc_id)
    loc = locations[loc_id]
    bot.reply_to(message, f"🚀 Телепорт в {loc['name']}.")

@bot.message_handler(commands=['dev_reset_quest'])
def dev_reset_quest(message):
    if not is_developer(message.from_user.id):
        return
    save_player(message.from_user.id,
                daily_quest=None,
                daily_quest_progress=0,
                daily_quest_target=None,
                daily_quest_count=0,
                daily_quest_reward_exp=0,
                daily_quest_reward_gold=0)
    bot.reply_to(message, "✅ Квест сброшен.")

@bot.message_handler(commands=['dev_heal'])
def dev_heal(message):
    if not is_developer(message.from_user.id):
        return
    player = get_player(message.from_user.id)
    if not player:
        bot.reply_to(message, "❌ Персонаж не найден.")
        return
    save_player(message.from_user.id, hp=player['max_hp'], energy=player['max_energy'])
    bot.reply_to(message, "❤️ Здоровье и энергия полностью восстановлены.")

@bot.message_handler(commands=['dev_give_all_items'])
def dev_give_all_items(message):
    if not is_developer(message.from_user.id):
        return
    c = conn.cursor()
    c.execute("SELECT name FROM items")
    all_items = c.fetchall()
    c.close()
    for item in all_items:
        add_item_to_inventory(message.from_user.id, item[0], 1)
    bot.reply_to(message, "✅ Выданы все предметы (по 1 шт).")

@bot.message_handler(commands=['dev_spawn'])
def dev_spawn(message):
    if not is_developer(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Использование: /dev_spawn <имя_монстра>")
        return
    monster_name = ' '.join(args[1:])
    found = None
    for m in monster_templates.values():
        if m['name'] == monster_name:
            found = m.copy()
            break
    if not found:
        bot.reply_to(message, f"❌ Монстр '{monster_name}' не найден.")
        return
    battle_states[message.from_user.id] = {
        'monster': found,
        'defending': False,
        'restore_used': False,
        'turn': 'player'
    }
    player = get_player(message.from_user.id)
    total = get_total_stats(player)
    bot.send_message(message.chat.id,
                     f"⚔️ **Спавн монстра {found['name']}**\n\n"
                     f"_{found['desc']}_\n\n"
                     f"❤️ HP: {found['hp']}\n⚔️ Атака: {found['attack']}\n🛡️ Защита: {found['defense']}\n"
                     f"💥 Способность: {found['ability']} (урон {found['ability_damage']})\n\n"
                     f"{battle_status_text(player, found, total)}\n\n"
                     "⚔️ Ваш ход!",
                     reply_markup=battle_keyboard(), parse_mode='Markdown')
    bot.reply_to(message, "✅ Монстр создан.")

@bot.message_handler(commands=['dev_kill'])
def dev_kill(message):
    if not is_developer(message.from_user.id):
        return
    if message.from_user.id not in battle_states:
        bot.reply_to(message, "❌ Вы не в бою.")
        return
    battle_states[message.from_user.id]['monster']['hp'] = 0
    bot.reply_to(message, "💀 Монстр убит (dev-команда). Бой завершён.")
    if message.from_user.id in battle_states:
        del battle_states[message.from_user.id]
    bot.reply_to(message, "Бой завершён.", reply_markup=main_menu_keyboard())

# ========== ОБРАБОТЧИКИ КОМАНД (основные) ==========
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.chat.id
    player = get_player(user_id)
    if player:
        bot.send_message(user_id, f"🌟 С возвращением, {player['name']}!", reply_markup=main_menu_keyboard())
    else:
        bot.reply_to(message, "🌟 Добро пожаловать в мир «Аватар: 150 лет до Аанга»!\nСоздайте персонажа командой /newgame")

@bot.message_handler(commands=['newgame'])
def new_game_cmd(message):
    user_id = message.chat.id
    if get_player(user_id):
        bot.reply_to(message, "У вас уже есть персонаж!")
        return
    registration_states[user_id] = {'step': 0, 'name': ''}
    bot.reply_to(message, "📝 Введите имя вашего героя (2–20 букв и пробелов):")

@bot.message_handler(commands=['profile'])
def profile_cmd(message):
    user_id = message.chat.id
    player = get_player(user_id)
    if not player:
        return
    total = get_total_stats(player)
    text = (f"👤 **{player['name']}** ({player['nation']})\n"
            f"📈 Уровень: {player['level']}\n"
            f"⭐ Опыт: {player['exp']} / {100 * player['level']}\n"
            f"❤️ HP: {player['hp']}/{total['max_hp']}\n"
            f"⚔️ Атака: {total['attack']} (база {player['attack']} + {total['bonus_attack']})\n"
            f"🛡️ Защита: {total['defense']} (база {player['defense']} + {total['bonus_defense']})\n"
            f"⚡ Энергия: {player['energy']}/{total['max_energy']}\n"
            f"💰 Золото: {player['gold']}\n"
            f"🗺️ Локация: {locations.get(player['location'], {}).get('name', player['location'])}\n"
            f"📊 Очки навыков: {player['skill_points']}, Очки характеристик: {player['stat_points']}\n"
            f"🏆 PvP: побед {player['pvp_wins']}, поражений {player['pvp_losses']}\n"
            f"💀 Убито монстров: {player['total_kills']}\n"
            f"⚔️ Дуэлей проведено: {player['total_duels']}\n"
            f"📋 Квестов выполнено: {player['total_quests']}\n"
            f"💰 Всего заработано золота: {player['total_gold_earned']}")
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['map'])
def map_cmd(message):
    user_id = message.chat.id
    player = get_player(user_id)
    if not player:
        bot.reply_to(message, "Сначала создайте персонажа.")
        return
    current = player['location']
    text = "🗺️ **Карта мира**\n\n"
    for loc_id, loc_data in locations.items():
        marker = "📍" if loc_id == current else "▪️"
        level_info = f"(треб. ур. {loc_data['min_level']})"
        text += f"{marker} **{loc_data['name']}** {level_info}\n"
        if loc_data['exits']:
            exits = [locations[eid]['name'] for eid in loc_data['exits'] if eid in locations]
            text += f"   → {', '.join(exits)}\n"
        text += "\n"
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['location'])
def location_cmd(message):
    user_id = message.chat.id
    player = get_player(user_id)
    if not player:
        return
    loc_data = locations.get(player['location'], locations['start'])
    text = f"🏠 **{loc_data['name']}**\n\n{loc_data['desc']}\n"
    text += f"🎯 Требуемый уровень: {loc_data['min_level']}\n"
    if loc_data.get('has_shop'):
        text += "\n🛒 Здесь есть магазин!"
    if loc_data.get('has_npc'):
        text += f"\n👤 Здесь вы можете поговорить с {loc_data['npc_name']}."
    if loc_data['exits']:
        exits_names = [locations[eid]['name'] for eid in loc_data['exits'] if eid in locations]
        text += "\n\n🚪 Выходы: " + ", ".join(exits_names)
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def stats_cmd(message):
    user_id = message.chat.id
    if not get_player(user_id):
        return
    result = stats_menu(user_id)
    if result:
        text, keyboard = result
        bot.reply_to(message, text, reply_markup=keyboard, parse_mode='Markdown')

@bot.message_handler(commands=['reset'])
def reset_cmd(message):
    user_id = message.chat.id
    if not get_player(user_id):
        return
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton("❌ Да, удалить", callback_data="confirm_reset"))
    keyboard.add(telebot.types.InlineKeyboardButton("↩️ Отмена", callback_data="cancel_reset"))
    bot.reply_to(message, "⚠️ Вы уверены, что хотите удалить персонажа? Это необратимо!", reply_markup=keyboard)

@bot.message_handler(commands=['inventory'])
def inventory_cmd(message):
    user_id = message.chat.id
    if not get_player(user_id):
        return
    result = inventory_menu(user_id)
    if result:
        text, keyboard = result
        bot.reply_to(message, text, reply_markup=keyboard, parse_mode='Markdown')

@bot.message_handler(commands=['equip'])
def equip_cmd(message):
    user_id = message.chat.id
    if not get_player(user_id):
        return
    result = equipment_menu(user_id)
    if result:
        text, keyboard = result
        bot.reply_to(message, text, reply_markup=keyboard, parse_mode='Markdown')

@bot.message_handler(commands=['abilities'])
def abilities_cmd(message):
    user_id = message.chat.id
    if not get_player(user_id):
        return
    result = abilities_menu(user_id)
    if result:
        text, keyboard = result
        bot.reply_to(message, text, reply_markup=keyboard, parse_mode='Markdown')

@bot.message_handler(commands=['duel'])
def duel_cmd(message):
    user_id = message.chat.id
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Использование: /duel @username")
        return
    target_name = args[1].lstrip('@')
    c = conn.cursor()
    c.execute("SELECT user_id, name FROM players WHERE name LIKE ?", (target_name,))
    row = c.fetchone()
    c.close()
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
    keyboard.add(telebot.types.InlineKeyboardButton("⚔️ Принять дуэль", callback_data=f"accept_duel_{user_id}"))
    keyboard.add(telebot.types.InlineKeyboardButton("❌ Отказаться", callback_data="decline_duel"))
    bot.send_message(target_id, f"⚔️ Игрок {get_player(user_id)['name']} вызывает вас на дуэль! Принять?", reply_markup=keyboard)
    bot.reply_to(message, "✅ Вызов отправлен.")

@bot.message_handler(commands=['daily'])
def daily_cmd(message):
    user_id = message.chat.id
    quest = check_daily_quest(user_id)
    if isinstance(quest, dict) and 'desc' in quest:
        progress = quest.get('progress', 0)
        count = quest.get('count', 0)
        bot.reply_to(message, f"📋 **Ежедневный квест:**\n{quest['desc']}\n📊 Прогресс: {progress}/{count}", parse_mode='Markdown')
    else:
        bot.reply_to(message, "Не удалось получить квест.")

@bot.message_handler(commands=['raid'])
def raid_cmd(message):
    user_id = message.chat.id
    if not can_raid(user_id):
        bot.reply_to(message, "🐉 Вы уже сражались с рейдовым боссом сегодня. Возвращайтесь завтра.")
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
    bot.send_message(user_id, f"🐉 **Рейдовый босс: {raid_boss['name']}**\n\n{raid_boss['desc']}\n\n"
                              f"❤️ HP: {raid_boss['hp']}\n⚔️ Атака: {raid_boss['attack']}\n🛡️ Защита: {raid_boss['defense']}\n"
                              f"💥 Способность: {raid_boss['ability']} (урон {raid_boss['ability_damage']})\n\n"
                              f"{battle_status_text(player, raid_boss, total)}\n\n"
                              "⚔️ Ваш ход!",
                     reply_markup=battle_keyboard(), parse_mode='Markdown')

# ========== ОБРАБОТЧИКИ ТЕКСТОВЫХ КНОПОК ==========
@bot.message_handler(func=lambda msg: msg.text == '👤 Профиль')
def profile_text(message): profile_cmd(message)
@bot.message_handler(func=lambda msg: msg.text == '🗺️ Карта')
def map_text(message): map_cmd(message)
@bot.message_handler(func=lambda msg: msg.text == '📍 Локация')
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
        bot.reply_to(message, text, reply_markup=keyboard, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == '⚔️ Охота')
def hunt_text(message):
    user_id = message.chat.id
    player = get_player(user_id)
    if not player:
        return
    if user_id in battle_states:
        bot.reply_to(message, "Вы уже в бою!")
        return
    monster = get_monster_for_location(player['location'])
    pending_monsters[user_id] = monster
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(telebot.types.InlineKeyboardButton("⚔️ Сражаться!", callback_data="fight_confirm"))
    keyboard.add(telebot.types.InlineKeyboardButton("🏃 Убежать", callback_data="flee_encounter"))
    bot.send_message(user_id, f"⚔️ **Вы встретили {monster['rank']} монстра {monster['name']}**\n\n"
                              f"_{monster['desc']}_\n\n"
                              f"❤️ HP: {monster['hp']}\n⚔️ Атака: {monster['attack']}\n🛡️ Защита: {monster['defense']}\n"
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
    loc_data = locations.get(player['location'])
    if not loc_data or not loc_data['exits']:
        bot.reply_to(message, "🚫 Отсюда никуда не уйти.")
        return
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    for eid in loc_data['exits']:
        exit_loc = locations.get(eid)
        if exit_loc:
            level_req = exit_loc.get('min_level', 1)
            label = f"🚶 {exit_loc['name']} (ур. {level_req})"
            if player['level'] < level_req:
                label = "🔒 " + label
            keyboard.add(telebot.types.InlineKeyboardButton(label, callback_data=f"go_to_{eid}"))
    keyboard.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_go"))
    bot.reply_to(message, "🗺️ **Выберите направление:**", reply_markup=keyboard, parse_mode='Markdown')

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
    bot.edit_message_text("🔙 Возврат в главное меню.", chat_id=call.message.chat.id, message_id=call.message.message_id)
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
        msg = "⚔️ Атака +1"
    elif call.data == 'stat_defense':
        save_player(user_id, defense=player['defense']+1, stat_points=player['stat_points']-1)
        msg = "🛡️ Защита +1"
    elif call.data == 'stat_hp':
        save_player(user_id, max_hp=player['max_hp']+10, hp=player['max_hp']+10, stat_points=player['stat_points']-1)
        msg = "❤️ HP +10, восстановлено"
    elif call.data == 'stat_energy':
        save_player(user_id, max_energy=player['max_energy']+5, energy=player['max_energy']+5, stat_points=player['stat_points']-1)
        msg = "⚡ Энергия +5, восстановлена"
    else:
        return
    bot.answer_callback_query(call.id, msg)
    result = stats_menu(user_id)
    if result:
        text, keyboard = result
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'fight_confirm')
def fight_confirm_callback(call):
    user_id = call.message.chat.id
    player = get_player(user_id)
    if not player:
        bot.answer_callback_query(call.id, "Ошибка персонажа.")
        return
    if user_id not in pending_monsters:
        bot.answer_callback_query(call.id, "Монстр не найден. Начните охоту заново.")
        return
    monster = pending_monsters.pop(user_id)
    battle_states[user_id] = {'monster': monster, 'defending': False, 'restore_used': False, 'turn': 'player'}
    total = get_total_stats(player)
    bot.send_message(user_id, f"⚔️ **Вы вступаете в бой с {monster['rank']} монстром {monster['name']}**\n\n"
                              f"{battle_status_text(player, monster, total)}\n\n"
                              "⚔️ Ваш ход!",
                     reply_markup=battle_keyboard(), parse_mode='Markdown')
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
        bot.edit_message_text("❌ Отмена.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    target = call.data.split('_', 2)[2]
    if target not in locations:
        bot.answer_callback_query(call.id, "Нет такой локации.")
        return
    target_loc = locations[target]
    if target not in locations.get(player['location'], {}).get('exits', []):
        bot.answer_callback_query(call.id, "Нет пути.")
        return
    if player['level'] < target_loc.get('min_level', 1):
        bot.answer_callback_query(call.id, f"⚠️ Требуется уровень {target_loc['min_level']} для безопасного входа. Будьте осторожны!")
    save_player(user_id, location=target)
    loc = locations[target]
    bot.edit_message_text(f"🚶 Вы переместились в **{loc['name']}**.\n\n{loc['desc']}",
                          chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='Markdown')
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
            bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

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
            bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

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
        c = conn.cursor()
        c.execute("UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_id = ?", (user_id, item_id))
        c.execute("DELETE FROM inventory WHERE user_id = ? AND item_id = ? AND quantity <= 0", (user_id, item_id))
        conn.commit()
        c.close()
        bot.answer_callback_query(call.id, f"🧪 Вы восстановили {new_hp - player['hp']} HP.")
    elif typ == 'potion_energy':
        heal_percent = item[9] / 100.0
        energy_heal = int(player['max_energy'] * heal_percent)
        new_energy = min(player['energy'] + energy_heal, player['max_energy'])
        save_player(user_id, energy=new_energy)
        c = conn.cursor()
        c.execute("UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_id = ?", (user_id, item_id))
        c.execute("DELETE FROM inventory WHERE user_id = ? AND item_id = ? AND quantity <= 0", (user_id, item_id))
        conn.commit()
        c.close()
        bot.answer_callback_query(call.id, f"🧪 Вы восстановили {new_energy - player['energy']} энергии.")
    else:
        bot.answer_callback_query(call.id, "Этот предмет нельзя использовать.")
        return
    result = inventory_menu(user_id)
    if result:
        text, keyboard = result
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

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
    bot.answer_callback_query(call.id, f"✅ Куплено {name} за {price} золота.")
    result = shop_menu(user_id)
    if result:
        text, keyboard = result
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('shop_cat_'))
def shop_category_callback(call):
    user_id = call.message.chat.id
    category = call.data.split('_')[2]
    result = shop_menu(user_id, category)
    if result:
        text, keyboard = result
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'shop_back')
def shop_back_callback(call):
    user_id = call.message.chat.id
    result = shop_menu(user_id)
    if result:
        text, keyboard = result
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'sell_menu')
def sell_menu_callback(call):
    user_id = call.message.chat.id
    items = get_inventory(user_id)
    if not items:
        bot.answer_callback_query(call.id, "Нет предметов для продажи.")
        return
    text = "📤 **Выберите предмет для продажи:**\n"
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    for item in items:
        item_id, name, typ, rarity, desc, atk, df, hp, en, effect, qty = item
        c = conn.cursor()
        c.execute("SELECT price_sell FROM items WHERE id = ?", (item_id,))
        price = c.fetchone()[0]
        c.close()
        text += f"**{name}** x{qty} — {price} золота за шт.\n"
        keyboard.add(telebot.types.InlineKeyboardButton(f"💰 Продать {name} (x{qty})", callback_data=f"sell_{item_id}"))
    keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="shop_back"))
    bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sell_'))
def sell_callback(call):
    user_id = call.message.chat.id
    item_id = int(call.data.split('_')[1])
    player = get_player(user_id)
    if not player:
        return
    c = conn.cursor()
    c.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    qty_row = c.fetchone()
    if not qty_row or qty_row[0] <= 0:
        c.close()
        bot.answer_callback_query(call.id, "Нет предмета.")
        return
    qty = qty_row[0]
    c.execute("SELECT price_sell FROM items WHERE id = ?", (item_id,))
    price = c.fetchone()[0]
    total_gold = price * qty
    c.close()
    save_player(user_id, gold=player['gold'] + total_gold)
    c = conn.cursor()
    c.execute("DELETE FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    conn.commit()
    c.close()
    bot.answer_callback_query(call.id, f"💰 Продано {qty} шт. за {total_gold} золота.")
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
    bot.answer_callback_query(call.id, f"⬆️ Способность улучшена до уровня {new_level}.")
    result = abilities_menu(user_id)
    if result:
        text, keyboard = result
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

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
    
    save_player(user_id, total_duels=player1['total_duels'] + 1)
    save_player(opponent_id, total_duels=player2['total_duels'] + 1)
    
    bot.send_message(
        user_id,
        f"⚔️ **Дуэль началась! Ваш противник — {player2['name']}**\n\n"
        f"{battle_status_text(player1, monster_for_player1, total1, is_pvp=True)}\n\n"
        "⚔️ Ваш ход!",
        reply_markup=battle_keyboard(),
        parse_mode='Markdown'
    )
    bot.send_message(
        opponent_id,
        f"⚔️ **Дуэль началась! Ваш противник — {player1['name']}**\n\n"
        f"{battle_status_text(player2, monster_for_player2, total2, is_pvp=True)}\n\n"
        "⚔️ Ваш ход!",
        reply_markup=battle_keyboard(),
        parse_mode='Markdown'
    )
    
    bot.edit_message_text(
        "✅ Дуэль принята! Бой начался.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'decline_duel')
def decline_duel_callback(call):
    user_id = call.message.chat.id
    if user_id in pvp_duels:
        del pvp_duels[user_id]
    bot.edit_message_text("❌ Вы отклонили дуэль.", chat_id=call.message.chat.id, message_id=call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data in ['confirm_reset', 'cancel_reset'])
def reset_callback(call):
    user_id = call.message.chat.id
    if call.data == 'confirm_reset':
        c = conn.cursor()
        c.execute("DELETE FROM players WHERE user_id = ?", (user_id,))
        conn.commit()
        c.close()
        if user_id in battle_states:
            del battle_states[user_id]
        if user_id in restore_cooldowns:
            del restore_cooldowns[user_id]
        bot.edit_message_text("✅ Персонаж удалён.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id, "Удалено")
    else:
        bot.edit_message_text("↩️ Отмена.", chat_id=call.message.chat.id, message_id=call.message.message_id)
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
                player_msg = f"💥 **КРИТИЧЕСКИЙ УДАР!** Вы наносите {damage} урона."
            else:
                damage = base
                player_msg = f"⚔️ Вы наносите {damage} урона."
        monster['hp'] -= damage
        state['defending'] = False

    elif action == '🛡️ Защита':
        state['defending'] = True
        player_msg = "🛡️ Вы встаёте в защитную стойку. Следующая атака монстра будет ослаблена."

    elif action == '✨ Способность':
        abilities = get_player_abilities(user_id)
        if not abilities:
            player_msg = "📚 Нет доступных способностей."
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
                    label += f" ⚔️{dmg}"
                if heal > 0:
                    label += f" 💚{heal}"
                label += f" [⚡{cost_energy}]"
                keyboard.add(telebot.types.InlineKeyboardButton(label, callback_data=f"use_ability_{ab_id}"))
            if keyboard.keyboard:
                bot.send_message(user_id, "✨ **Выберите способность:**", reply_markup=keyboard, parse_mode='Markdown')
                return
            else:
                player_msg = "⚠️ Недостаточно энергии для способностей."

    elif action == '💤 Восстановление':
        if state.get('restore_used', False):
            player_msg = "Вы уже использовали восстановление в этом бою."
        else:
            hp_heal, energy_heal, new_hp, new_energy = heal_player(player, 0.2, 0.3)
            state['restore_used'] = True
            state['defending'] = False
            player['hp'] = new_hp
            player['energy'] = new_energy
            player_msg = f"💤 Вы восстановили {hp_heal} HP и {energy_heal} энергии."

    elif action == '🧪 Зелье':
        inventory = get_inventory(user_id)
        potions = [item for item in inventory if item[2] in ['potion_hp','potion_energy']]
        if not potions:
            player_msg = "🧪 Нет зелий."
        else:
            keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
            for item in potions:
                item_id, name, typ, rarity, desc, atk_b, df_b, hp_b, en_b, effect, qty = item
                keyboard.add(telebot.types.InlineKeyboardButton(f"{name} x{qty}", callback_data=f"use_item_{item_id}"))
            keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_battle"))
            bot.send_message(user_id, "🧪 **Выберите зелье:**", reply_markup=keyboard, parse_mode='Markdown')
            return

    elif action == '🏃 Сбежать':
        if random.random() < 0.6:
            if user_id in battle_states:
                del battle_states[user_id]
            bot.reply_to(message, "🏃 Вы сбежали!", reply_markup=main_menu_keyboard())
            return
        else:
            player_msg = "🏃 Не удалось сбежать! Монстр атакует."

    if player_msg:
        bot.reply_to(message, player_msg, parse_mode='Markdown')

    if monster['hp'] <= 0:
        exp_gain = monster.get('exp', 20)
        gold_gain = random.randint(monster.get('gold_min', 2), monster.get('gold_max', 8))
        level_up = gain_exp(user_id, exp_gain)
        save_player(user_id, gold=player['gold'] + gold_gain, total_kills=player['total_kills'] + 1,
                    total_gold_earned=player['total_gold_earned'] + gold_gain)
        loot_msg = ""
        if 'loot' in monster:
            for loot_item in monster['loot']:
                if random.random() < loot_item['chance']:
                    add_item_to_inventory(user_id, loot_item['item_name'], 1)
                    loot_msg += f"\n🎁 **+ {loot_item['item_name']}**"

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
        quest_complete, quest_msg = update_daily_quest(user_id, player_loc)
        if quest_complete and quest_msg:
            bot.send_message(user_id, quest_msg, parse_mode='Markdown')
        if user_id in battle_states:
            del battle_states[user_id]
        msg = f"🎉 **Победа!**\nПолучено опыта: {exp_gain}\n💰 Золота: {gold_gain}" + loot_msg
        if level_up:
            msg += "\n🎊 **Уровень повышен!**"
        bot.reply_to(message, msg, parse_mode='Markdown', reply_markup=main_menu_keyboard())
        return

    is_pvp = state.get('is_pvp', False)
    if not is_pvp:
        uses_ability = random.random() < 0.4
        if uses_ability and 'ability' in monster:
            ability_name = monster['ability']
            ability_damage = monster.get('ability_damage', 15)
            if state['defending']:
                damage = max(1, int(ability_damage * 0.5) + random.randint(-2, 2))
                state['defending'] = False
                monster_msg = f"💥 {monster['name']} использует **{ability_name}**! Вы защищаетесь, урон уменьшен: {damage}."
            else:
                damage = max(1, ability_damage + random.randint(-3, 3))
                monster_msg = f"💥 {monster['name']} использует **{ability_name}**! Урон: {damage}."
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
                    monster_msg = f"💥 **КРИТИЧЕСКИЙ УДАР** от {monster['name']}! Урон: {damage}."
                else:
                    damage = base
                    monster_msg = f"⚔️ {monster['name']} атакует! Урон: {damage}."
        player['hp'] -= damage
        save_player(user_id, hp=player['hp'])
        bot.reply_to(message, monster_msg, parse_mode='Markdown')

        if player['hp'] <= 0:
            if user_id in battle_states:
                del battle_states[user_id]
            exp_loss = int(player['exp'] * 0.1)
            new_exp = max(0, player['exp'] - exp_loss)
            save_player(user_id, hp=max_hp, exp=new_exp, location='start')
            bot.reply_to(message, f"💀 **Вы погибли!** Потеряно {exp_loss} опыта.\n\n🔄 Вы возродились на **Перекрёстке**.", reply_markup=main_menu_keyboard(), parse_mode='Markdown')
            return
    else:
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
                        monster_msg = f"💥 **КРИТИЧЕСКИЙ УДАР** от {opp_player['name']}! Урон: {damage}."
                    else:
                        damage = base
                        monster_msg = f"⚔️ {opp_player['name']} атакует! Урон: {damage}."
                player['hp'] -= damage
                save_player(user_id, hp=player['hp'])
                bot.reply_to(message, monster_msg, parse_mode='Markdown')
                if player['hp'] <= 0:
                    if user_id in battle_states:
                        del battle_states[user_id]
                    exp_loss = int(player['exp'] * 0.1)
                    new_exp = max(0, player['exp'] - exp_loss)
                    save_player(user_id, hp=max_hp, exp=new_exp, location='start')
                    bot.reply_to(message, f"💀 **Вы погибли!** Потеряно {exp_loss} опыта.\n\n🔄 Вы возродились на **Перекрёстке**.", reply_markup=main_menu_keyboard(), parse_mode='Markdown')
                    return

    if user_id in battle_states:
        bot.reply_to(message,
                     f"{battle_status_text(player, monster, total, is_pvp)}\n\n⚔️ **Ваш ход.**",
                     reply_markup=battle_keyboard(), parse_mode='Markdown')

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
        bot.answer_callback_query(call.id, f"⚠️ Недостаточно энергии! Нужно {energy_cost}.")
        return
    if dmg > 0:
        monster['hp'] -= dmg
        player_msg = f"✨ **{name}**! Урон: {dmg}."
    elif heal > 0:
        new_hp = min(player['hp'] + heal, player['max_hp'])
        save_player(user_id, hp=new_hp)
        player['hp'] = new_hp
        player_msg = f"✨ **{name}**! Лечение: {heal} HP."
    else:
        player_msg = f"✨ **{name}** (эффект не реализован)"
    save_player(user_id, energy=player['energy'] - energy_cost)
    player['energy'] -= energy_cost
    bot.answer_callback_query(call.id, f"✅ Использовано {name}.")
    bot.edit_message_text(player_msg, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='Markdown')

    if monster['hp'] <= 0:
        if user_id in battle_states:
            del battle_states[user_id]
        bot.reply_to(call.message, f"🎉 **Вы победили {monster['name']}!**", reply_markup=main_menu_keyboard(), parse_mode='Markdown')
        return
    total = get_total_stats(player)
    is_pvp = state.get('is_pvp', False)
    bot.send_message(user_id,
                     f"{battle_status_text(player, monster, total, is_pvp)}\n\n⚔️ **Ваш ход.**",
                     reply_markup=battle_keyboard(), parse_mode='Markdown')

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
    bot.edit_message_text(f"{battle_status_text(player, monster, total, is_pvp)}\n\n⚔️ **Ваш ход.**",
                          chat_id=call.message.chat.id, message_id=call.message.message_id,
                          reply_markup=battle_keyboard(), parse_mode='Markdown')
    bot.answer_callback_query(call.id)

# ========== РЕГИСТРАЦИЯ (обновлённая, с описанием наций) ==========
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
        text = f"⭐ Отлично, {name}! Теперь выберите вашу нацию:\n\n"
        for n, info in nation_info.items():
            text += f"**{n}** — {info['description']}\n"
            text += f"  ⚔️ Атака: {info['attack']}, 🛡️ Защита: {info['defense']}\n\n"
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        for nation in nation_info.keys():
            keyboard.add(telebot.types.InlineKeyboardButton(nation, callback_data=f"nation_{nation}"))
        bot.reply_to(message, text, reply_markup=keyboard, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('nation_'))
def nation_callback(call):
    user_id = call.message.chat.id
    if user_id not in registration_states:
        bot.answer_callback_query(call.id, "Ошибка.")
        return
    state = registration_states[user_id]
    if state['step'] != 1:
        bot.answer_callback_query(call.id, "Уже выбрано.")
        return
    full = call.data.split('_', 1)[1]
    nation = full
    name = state['name']
    create_player(user_id, name, nation)
    del registration_states[user_id]
    bot.edit_message_text(f"🎉 **Поздравляю, {name} из народа {nation}!**\n\nПерсонаж создан. Добро пожаловать в мир!", 
                          chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='Markdown')
    bot.send_message(user_id, "🌟 Используйте кнопки для навигации:", reply_markup=main_menu_keyboard())
    bot.answer_callback_query(call.id)

# ========== FLASK ==========
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

@app.route('/health')
def health():
    return "OK"

def run_bot():
    print("✅ Бот запущен и слушает сообщения...")
    bot.infinity_polling()

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)