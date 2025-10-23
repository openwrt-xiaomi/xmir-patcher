#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json

CONFIG_FILE = 'config.json'

def load_config():
    """Load configuration from file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}

def save_config(config):
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False

def get_language():
    """Get current language setting"""
    config = load_config()
    # Return None if no config file exists or no language is set
    # This will trigger the language selection menu
    if not os.path.exists(CONFIG_FILE) or 'language' not in config:
        return None
    return config.get('language', 'en')

def set_language(lang):
    """Set language preference"""
    config = load_config()
    config['language'] = lang
    return save_config(config)

def show_language_menu():
    """Show language selection menu"""
    print()
    print("=" * 58)
    print()
    print("Language / 语言 / Язык")
    print()
    print(" 1 - English")
    print(" 2 - 中文 (Chinese)")
    print(" 3 - Русский (Russian)")
    print()
    
    while True:
        choice = input("Select language [1-English, 2-中文, 3-Русский]: ").strip()
        if choice == '1':
            set_language('en')
            return 'en'
        elif choice == '2':
            set_language('zh')
            return 'zh'
        elif choice == '3':
            set_language('ru')
            return 'ru'
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")