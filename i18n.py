#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Language translations for menu system
# Supported languages: en (English), zh (Chinese), ru (Russian)

TRANSLATIONS = {
    'en': {
        'title': 'Xiaomi MiR Patcher',
        'main_menu': [
            'Set IP-address (current value: {})',
            'Connect to device (install exploit)',
            'Read full device info',
            'Create full backup',
            'Install EN/RU/ZH languages',
            'Install permanent SSH',
            'Install firmware (from directory "firmware")',
            '{{{ Other functions }}}',
            'Change language',
            '[[ Reboot device ]]',
            'Exit'
        ],
        'extended_menu': [
            'Set IP-address (current value: {})',
            'Change root password',
            'Read dmesg and syslog',
            'Create a backup of the specified partition',
            'Uninstall EN/RU/ZH languages',
            'Set kernel boot address',
            'Install bootloader (Breed/U-Boot)',
            '__test__',
            '[[ Reboot device ]]',
            'Return to main menu'
        ],
        'prompts': {
            'select': 'Select: ',
            'choice': 'Choice: ',
            'enter_ip': 'Enter device IP-address: ',
            'extended_functions': '(extended functions)',
            'language_menu': 'Language / 语言 / Язык',
            'language_prompt': 'Select language [1-English, 2-中文, 3-Русский]: ',
            'bootloader_choice': 'Select bootloader [1-Breed, 2-U-Boot]: '
        }
    },
    'zh': {
        'title': '小米路由器破解工具',
        'main_menu': [
            '设置IP地址 (当前值: {})',
            '连接设备 (安装漏洞利用)',
            '读取完整设备信息',
            '创建完整备份',
            '安装 英文/俄文/中文 语言包',
            '安装永久SSH',
            '安装固件 (从 "firmware" 目录)',
            '{{{ 其他功能 }}}',
            '更改语言',
            '[[ 重启设备 ]]',
            '退出'
        ],
        'extended_menu': [
            '设置IP地址 (当前值: {})',
            '修改root密码',
            '读取dmesg和系统日志',
            '创建指定分区备份',
            '卸载 英文/俄文/中文 语言包',
            '设置内核启动地址',
            '安装引导程序 (Breed/U-Boot)',
            '__测试__',
            '[[ 重启设备 ]]',
            '返回主菜单'
        ],
        'prompts': {
            'select': '请选择: ',
            'choice': '请选择: ',
            'enter_ip': '请输入设备IP地址: ',
            'extended_functions': '(扩展功能)',
            'language_menu': 'Language / 语言 / Язык',
            'language_prompt': '选择语言 [1-English, 2-中文, 3-Русский]: ',
            'bootloader_choice': '选择引导程序 [1-Breed, 2-U-Boot]: '
        }
    },
    'ru': {
        'title': 'Xiaomi MiR Patcher',
        'main_menu': [
            'Установить IP-адрес (текущее значение: {})',
            'Подключиться к устройству (установить эксплойт)',
            'Читать полную информацию об устройстве',
            'Создать полную резервную копию',
            'Установить языки EN/RU/ZH',
            'Установить постоянный SSH',
            'Установить прошивку (из папки "firmware")',
            '{{{ Другие функции }}}',
            'Изменить язык',
            '[[ Перезагрузить устройство ]]',
            'Выход'
        ],
        'extended_menu': [
            'Установить IP-адрес (текущее значение: {})',
            'Изменить пароль root',
            'Прочитать dmesg и syslog',
            'Создать резервную копию указанного раздела',
            'Удалить языки EN/RU/ZH',
            'Установить адрес загрузки ядра',
            'Установить загрузчик (Breed/U-Boot)',
            '__тест__',
            '[[ Перезагрузить устройство ]]',
            'Вернуться в главное меню'
        ],
        'prompts': {
            'select': 'Выбрать: ',
            'choice': 'Выбор: ',
            'enter_ip': 'Введите IP-адрес устройства: ',
            'extended_functions': '(расширенные функции)',
            'language_menu': 'Language / 语言 / Язык',
            'language_prompt': 'Выберите язык [1-English, 2-中文, 3-Русский]: ',
            'bootloader_choice': 'Выберите загрузчик [1-Breed, 2-U-Boot]: '
        }
    }
}

def get_translation(lang, key, *args):
    """Get translated text for given language and key"""
    if lang not in TRANSLATIONS:
        lang = 'en'  # fallback to English
    
    trans = TRANSLATIONS[lang]
    if key in trans:
        if isinstance(trans[key], list):
            return trans[key]
        elif args:
            return trans[key].format(*args)
        else:
            return trans[key]
    elif key in trans.get('prompts', {}):
        text = trans['prompts'][key]
        if args:
            return text.format(*args)
        return text
    else:
        # fallback to English only if we're not already using English
        if lang != 'en':
            return get_translation('en', key, *args)
        else:
            # If key not found even in English, return a default message
            return f"[Missing translation: {key}]"

def get_supported_languages():
    """Get list of supported language codes"""
    return list(TRANSLATIONS.keys())