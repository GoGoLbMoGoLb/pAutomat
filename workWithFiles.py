import os
from datetime import datetime
import re
import chardet
import shutil
import subprocess
import requests
import win32clipboard

CONFIG_FILE = "config.json"

def choose_existing_path(path1, path2, path3):
    if os.path.exists(path1):
        return path1
    elif os.path.exists(path2):
        return path2
    elif os.path.exists(path3):
        return path3
    else:
        return None

def get_file_modification_time(file_path):
    return os.path.getmtime(file_path)

def sort_files_by_date(directory):
    files = [f for f in os.listdir(directory) if f.endswith('.bin') or f.endswith('.hex')]
    files_with_dates = []

    for file in files:
        file_path = os.path.join(directory, file)
        modification_time = get_file_modification_time(file_path)
        files_with_dates.append((file, modification_time))

    files_with_dates.sort(key=lambda x: x[1], reverse=True)
    return [file for file, _ in files_with_dates]

def get_newest_files(directory, top_n=1):
    sorted_files = sort_files_by_date(directory)
    return sorted_files[:top_n]

def clean_firmware_version(filename):
    """
    Правка 2: Извлекает чистый номер версии из имени файла.
    Пример: 'TAGER_OUTDOOR_BLE_20_214_1A72F73E.hex' -> '20_214_1A72F73E'
    """
    base_name = filename.split('.')[0]
    # Ищем паттерн с цифрами, подчеркиваниями и хешем в конце
    match = re.search(r'(\d+_\d+_[0-9A-Fa-f]+)', base_name)
    if match:
        return match.group(1)
    return base_name

def select_dir_withSource_files(dir_path):
    sub_folder_old = r"MDK-ARM\Release"
    sub_folder_new = r"Main\MDK-ARM\Release"
    sub_folder_addit_devs = r"MS_main_proto\MDK-ARM\Release"
    
    full_path_old = os.path.join(dir_path, sub_folder_old)
    full_path_new = os.path.join(dir_path, sub_folder_new)
    full_path_addit = os.path.join(dir_path, sub_folder_addit_devs)
    
    chosen_path = choose_existing_path(full_path_old, full_path_new, full_path_addit)
    if chosen_path:
        return chosen_path
    else:
        return dir_path

def find_readme_files_map(src_dir):
    """
    Правка 1: Ищет все lable.md в поддиректориях документации 
    и сопоставляет текстовые МЕТКИ из них с реальным ПУТЕМ к папке (например, 'BLE_Tager').
    Возвращает словарь: {'TAGER_BLE': 'C:/.../BLE_Tager'}
    """
    label_to_dir_map = {}
    for root, dirs, files in os.walk(src_dir):
        if 'lable.md' in files:
            readme_path = os.path.join(root, 'lable.md')
            extracted_labels = extract_labels(readme_path)
            for lbl in extracted_labels:
                label_to_dir_map[lbl.strip()] = root
    return label_to_dir_map

def find_info_file(dir_path):
    for root, dirs, files in os.walk(dir_path):
        if 'Info.h' in files:
            return os.path.join(root, 'Info.h')
    return None  

def find_docs_dir_by_path(folder_path):
    """
    Правка 1: Ищет структуры Release/HEX/BIN/History внутри конкретной папки устройства.
    """
    release_pattern = re.compile(r'[Rr][Ee][Ll][Ee][Aa][Ss][Ee]')
    hex_pattern = re.compile(r'[Hh][Ee][Xx]$')
    bin_pattern = re.compile(r'[Bb][Ii][Nn]$')
    hist_pattern = re.compile(r'(?i)(History\s+of\s+changes|Description\s+of\s+firmware\s+changes|change\s+history)\s*\.txt$')
    
    result_dirs = []
    if not os.path.exists(folder_path):
        return result_dirs

    for item in os.listdir(folder_path):
        relative_path = os.path.join(folder_path, item)
        if os.path.isdir(relative_path) and release_pattern.match(item):
            for sub_item in os.listdir(relative_path):
                sub_path = os.path.join(relative_path, sub_item)
                if os.path.isdir(sub_path) and re.match(r'[Hh][Ee][Xx]$', sub_item):
                    result_dirs.append({'dir_hex': sub_path})
                if os.path.isdir(sub_path) and re.match(r'[Bb][Ii][Nn]$', sub_item):
                    result_dirs.append({'dir_bin': sub_path})
                if re.match(hist_pattern, sub_item):
                    result_dirs.append({'file_history': sub_path})
        if os.path.isdir(relative_path) and hex_pattern.match(item):
            result_dirs.append({'dir_hex': relative_path})
        if os.path.isdir(relative_path) and bin_pattern.match(item):
            result_dirs.append({'dir_bin': relative_path})
        if hist_pattern.match(item):
            result_dirs.append({'file_history': relative_path})
            
    return result_dirs

def update_file_with_template(file_path, firmware_version, description):
    """
    Правка 3: Заменяет название метки на 'MAIN'.
    Формат: Firmware version MAIN: 20_214_1A72F73E(29.08.26)
    """
    original_content = ""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            original_content = file.read()
    
    date_str = datetime.now().strftime("%d.%m.%y")
    template = f"Firmware version MAIN: {firmware_version}({date_str})\n{description}\n\n"
    
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(template + original_content)
def format_desc_for_file(raw_desc: str) -> str:
    """Форматирует многострочный текст с ТАБОМ и ТИРЕ для файла истории."""
    lines = [line.strip() for line in raw_desc.splitlines() if line.strip()]
    if not lines:
        return "\t- (Без описания)"
    return "\n".join([f"\t- {line}" for line in lines])


def format_desc_for_telegram(raw_desc: str) -> tuple[str, str]:
    """Форматирует текст ТОЛЬКО С ТИРЕ (без табов) для публикации в Telegram."""
    lines = [line.strip() for line in raw_desc.splitlines() if line.strip()]
    if not lines:
        return "- (Без описания)", "- (Без описания)"

    # Для Plain Text
    plain_text = "\n".join([f"- {line}" for line in lines])

    # Для HTML (обычные пробелы без nbsp и без табуляции)
    html_text = "<br>".join([f"- {line}" for line in lines])

    return plain_text, html_text
        
def delete_similar_hex_files(destination_dir, filename_pattern):
    """
    Удаляет файлы .hex в целевой папке, имена которых совпадают с базовым именем устройства.
    Пример: 'TAGER_OUTDOOR_BLE_20_214_1A72F73E.hex' -> base_name = 'TAGER_OUTDOOR_BLE'
    """
    if not os.path.exists(destination_dir):
        return

    # Отрезаем расширение .hex
    clean_name = filename_pattern.rsplit('.', 1)[0]
    
    # Регулярка ищет подчёркивание, за которым следуют цифры версии (например, _20_, _21_, _1_ и т.д.)
    match = re.search(r'^(.*?)(?=_\d+)', clean_name)
    
    if match:
        base_name = match.group(1)
    else:
        # Если цифр версии в имени не найдено, убираем последнюю секцию после последнего '_'
        base_name = clean_name.rsplit('_', 1)[0] if '_' in clean_name else clean_name

    for f in os.listdir(destination_dir):
        if f.endswith('.hex') and f.startswith(base_name):
            file_path = os.path.join(destination_dir, f)
            try:
                os.remove(file_path)
                print(f"Удален старый .hex: {file_path}")
            except Exception as e:
                print(f"Ошибка при удалении {file_path}: {e}")

def process_bin_and_run_skiff(file_bin_path, source_dir, firmware_version, raw_bin_filename):
    """
    2) Обработка BIN папки, вызов run.bat и генерация update_*.skif
    """
    fw_bin_dir = os.path.join(file_bin_path, "Firmware_BIN")
    builder_dir = os.path.join(file_bin_path, "Skiff_update_builder")
    bat_path = os.path.join(builder_dir, "run.bat")

    os.makedirs(fw_bin_dir, exist_ok=True)

    # 1. Очищаем *.bin в Firmware_BIN
    for f in os.listdir(fw_bin_dir):
        if f.endswith('.bin'):
            os.remove(os.path.join(fw_bin_dir, f))

    # 2. Копируем новый .bin из исходников в Firmware_BIN
    src_bin_file = os.path.join(source_dir, raw_bin_filename)
    dst_bin_file = os.path.join(fw_bin_dir, raw_bin_filename)
    shutil.copy2(src_bin_file, dst_bin_file)

    # 3. Вызываем run.bat из папки Skiff_update_builder
    if os.path.exists(bat_path):
        try:
            subprocess.run("run.bat", cwd=builder_dir, shell=True, check=True)
            print("Skiff_update_builder/run.bat успешно выполнен.")
        except subprocess.CalledProcessError as e:
            print(f"Ошибка выполнения run.bat: {e}")
            return
    else:
        print(f"Файл не найден: {bat_path}")
        return

    # 4. В корне BIN папки удаляем старый файл с меткой 'update_'
    for f in os.listdir(file_bin_path):
        if f.startswith("update_") and f.endswith(".skif"):
            os.remove(os.path.join(file_bin_path, f))
            print(f"Удален старый update-файл: {f}")

    # 5. Находим вновь сгенерированный .skif файл без метки 'update_' и переименовываем
    for f in os.listdir(file_bin_path):
        if f.endswith(".skif") and not f.startswith("update_") and not f.startswith("default_"):
            old_skif_path = os.path.join(file_bin_path, f)
            # Формируем новое имя: update_<ОРИГИНАЛЬНОЕ_ИМЯ_ИЛИ_ВЕРСИЯ>.skif
            new_skif_name = f"update_{f}" if not f.startswith("update_") else f
            new_skif_path = os.path.join(file_bin_path, new_skif_name)
            
            os.rename(old_skif_path, new_skif_path)
            print(f"Переименован .skif файл в: {new_skif_name}")
            break
        
def delete_files_with_prefix(destination_dir, prefix):
    if not os.path.exists(destination_dir):
        return
    for filename in os.listdir(destination_dir):
        if filename.startswith(prefix):
            file_path = os.path.join(destination_dir, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)

def copy_files(source_dir, destination_dir, extension):
    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir, exist_ok=True)
    for filename in os.listdir(source_dir):
        if filename.endswith(extension):
            source_file = os.path.join(source_dir, filename)
            destination_file = os.path.join(destination_dir, filename)
            if os.path.isfile(source_file):
                shutil.copy2(source_file, destination_file)
                
def copy_single_file(source_dir, destination_dir, filename):
    """Копирует конкретный файл из source_dir в destination_dir."""
    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir, exist_ok=True)
    
    source_file = os.path.join(source_dir, filename)
    destination_file = os.path.join(destination_dir, filename)
    
    if os.path.isfile(source_file):
        shutil.copy2(source_file, destination_file)
        print(f"Скопирован свежий файл: {filename}")
        
def execute_commands_from_file(working_directory):
    bat_file_path = os.path.join(working_directory, 'make_total_for_sorce.bat')
    if os.path.exists(bat_file_path):
        try:
            subprocess.run(bat_file_path, cwd=working_directory, shell=True, check=True)
            print("Команда .bat выполнена успешно.")
        except subprocess.CalledProcessError as e:
            print(f"Ошибка при выполнении .bat: {e}")

def send_telegram_message(bot_token, chat_id, label, version, description):
    message = f"{label} MAIN: {version} - {description}"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            print("Уведомление в Telegram успешно отправлено!")
        else:
            print(f"Ошибка Telegram API: {res.text}")
    except Exception as e:
        print(f"Не удалось отправить сообщение в Telegram: {e}")

def detect_encoding(file_path):
    with open(file_path, 'rb') as file:
        raw_data = file.read(10000)
        result = chardet.detect(raw_data)
        return result['encoding'] or 'utf-8'

def read_file(file_path, encoding='utf-8'):
    try:
        with open(file_path, 'r', encoding=encoding) as file:
            return file.readlines()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None

pattern_type_1 = re.compile(r'^([A-Z0-9_]+)(?:_([A-Z0-9_]+))?$')
pattern_type_2 = re.compile(r'^\s*-\s*([A-Za-z_]+)\s*\(')

def parse_lables_type_1(line):
    match = pattern_type_1.match(line.strip())
    if match:
        return {'type': 'type_1', 'original': line.strip()}
    return None

def parse_lables_type_2(line):
    match = pattern_type_2.search(line)
    if match:
        return {'type': 'type_2', 'original': match.group(1)}
    return None

def unified_parser(lines):
    results = []
    for line in lines:
        res1 = parse_lables_type_1(line)
        if res1:
            results.append(res1)
            continue
        res2 = parse_lables_type_2(line)
        if res2:
            results.append(res2)
            continue
    return results

def extract_labels(file_path):
    labels = []
    if not os.path.isfile(file_path):
        return labels
    encoding = detect_encoding(file_path)
    lines = read_file(file_path, encoding)
    if not lines:
        return labels

    parsed_results = unified_parser(lines)
    for result in parsed_results:
        labels.append(result['original'])
    return labels

def copy_html_to_clipboard(text_plain, text_html):
    """
    Помещает в буфер обмена Windows одновременно обычный текст и HTML.
    Telegram при вставке (Ctrl+V) подхватит именно HTML с кликабельной ссылкой.
    """
    fragment_start = 105
    fragment_end = fragment_start + len(text_html.encode('utf-8'))
    
    header = (
        "Version:0.9\r\n"
        "StartHTML:0000000000\r\n"
        "EndHTML:0000000000\r\n"
        f"StartFragment:{fragment_start:010d}\r\n"
        f"EndFragment:{fragment_end:010d}\r\n"
    )
    
    html_data = (
        f"{header}"
        "<html><body><!--StartFragment-->"
        f"{text_html}"
        "<!--EndFragment--></body></html>"
    )
    
    # Расчет точных офсетов для заголовка
    start_html = len(header)
    end_html = len(html_data.encode('utf-8'))
    
    header = (
        "Version:0.9\r\n"
        f"StartHTML:{start_html:010d}\r\n"
        f"EndHTML:{end_html:010d}\r\n"
        f"StartFragment:{fragment_start:010d}\r\n"
        f"EndFragment:{fragment_end:010d}\r\n"
    )
    
    final_html = (
        f"{header}"
        "<html><body><!--StartFragment-->"
        f"{text_html}"
        "<!--EndFragment--></body></html>"
    )

    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    
    # Регистрируем формат HTML Format
    cf_html = win32clipboard.RegisterClipboardFormat("HTML Format")
    
    # Записываем обычный текст (как фоллбэк) и HTML
    win32clipboard.SetClipboardText(text_plain, win32clipboard.CF_UNICODETEXT)
    win32clipboard.SetClipboardData(cf_html, final_html.encode('utf-8'))
    
    win32clipboard.CloseClipboard()