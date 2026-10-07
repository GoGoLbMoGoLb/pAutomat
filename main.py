import customtkinter as ctk
from tkinter import filedialog, messagebox, Menu
import gitWork as git
import workWithFiles as uFile
import pyperclip
import os
import re
import sys
import threading

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("Автоматизация оформления документации")
app.geometry("620x780")

path_source_dir = ctk.StringVar()
path_docs_dir = ctk.StringVar()

# Глобальный словарь для связи "Метка" -> "Путь к папке"
label_to_path_map = {}
last_generated_url = ''
last_firmware_version = ''

def get_resource_path(relative_path):
    """Получает абсолютный путь к ресурсам (работает и для dev, и для PyInstaller)"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

icon_path = get_resource_path("app_icon.ico")
if os.path.exists(icon_path):
    try:
        app.wm_iconbitmap(icon_path)
    except Exception as e:
        print(f"Не удалось загрузить иконку окна: {e}")

		
def select_path(button_id, entry, label):
    global label_to_path_map
    path = filedialog.askdirectory()
    if not path:
        return
    
    entry.set(path)
    label.configure(text=path)
    
    # 1. Сканирование веток исходников в фоновом потоке
    if button_id == 1:
        combo_branches.configure(state="disabled")
        combo_branches.set("Сканирование веток...")
        
        def _fetch_branches_thread():
            branches = git.get_branches(path)
            # Возвращаем результат в UI-поток
            app.after(0, lambda: _update_branches_ui(branches))

        threading.Thread(target=_fetch_branches_thread, daemon=True).start()
            
    # 2. Поиск lable.md документации в фоновом потоке
    elif button_id == 2:
        combo_lables.configure(state="disabled")
        combo_lables.set("Поиск lable.md...")
        
        def _fetch_readme_thread():
            global label_to_path_map
            readme_map = uFile.find_readme_files_map(path)
            # Возвращаем результат в UI-поток
            app.after(0, lambda: _update_readme_ui(readme_map))

        threading.Thread(target=_fetch_readme_thread, daemon=True).start()

# --- Вспомогательные функции обновления интерфейса ---
def _update_branches_ui(branches):
    combo_branches.configure(state="normal")
    if branches:
        default_branch = "master" if "master" in branches else branches[0]
        combo_branches.configure(values=branches)
        combo_branches.set(default_branch)
    else:
        combo_branches.configure(values=["No branches found"])
        combo_branches.set("No branches found")

def _update_readme_ui(readme_map):
    global label_to_path_map
    label_to_path_map = readme_map
    combo_lables.configure(state="normal")
    if label_to_path_map:
        labels_list = list(label_to_path_map.keys())
        combo_lables.configure(values=labels_list)
        combo_lables.set(labels_list[0])
    else:
        combo_lables.configure(values=["No lable.md found"])
        combo_lables.set("No lable.md found")

def format_description(raw_desc: str) -> tuple[str, str]:
    """Форматирует многострочный текст описания.
    Возвращает кортеж из двух строк: (plain_text_desc, html_desc).
    """
    lines = [line.strip() for line in raw_desc.splitlines() if line.strip()]
    if not lines:
        return "\t- (Без описания)", "&nbsp;&nbsp;&nbsp;&nbsp;- (Без описания)"

    # Для обычного текста
    plain_lines = [f"\t- {line}" for line in lines]
    plain_text = "\n".join(plain_lines)

    # Для HTML-текста (с неразрывными пробелами для сохранения отступа в Telegram)
    html_lines = [f"&nbsp;&nbsp;&nbsp;&nbsp;- {line}" for line in lines]
    html_text = "<br>".join(html_lines)

    return plain_text, html_text

def copy_to_clipboard():
    if not last_generated_url or not last_firmware_version:
        messagebox.showwarning("Предупреждение", "Сначала выполните выгрузку (Apply & Deploy)!")
        return

    label = combo_lables.get()
    desc_raw = description.get("1.0", "end-1c")

    # Форматирование списка изменений (только с тире, без табов)
    desc_plain, desc_html = uFile.format_desc_for_telegram(desc_raw)

    # 1. Plain text fallback
    text_plain = f"{label} MAIN: {last_firmware_version} ({last_generated_url})\n{desc_plain}"
    
    # 2. HTML text для кликабельной ссылки в Telegram (Ctrl + V)
    text_html = f'{label} MAIN: <a href="{last_generated_url}">{last_firmware_version}</a><br>{desc_html}'

    try:
        uFile.copy_html_to_clipboard(text_plain, text_html)
        messagebox.showinfo("Буфер обмена", "Скопировано в буфер обмена!")
    except Exception as e:
        pyperclip.copy(text_plain)
        messagebox.showwarning("Предупреждение", f"Скопирован обычный текст: {e}")

def apply_button_clicked():
    # Блокируем кнопку на время выполнения
    apply_button.configure(state="disabled", text="Выполняется выгрузка...")
    
    # Запускаем тяжелую логику в отдельном потоке
    threading.Thread(target=_async_deploy_process, daemon=True).start()

def _async_deploy_process():
    global last_generated_url
    folder_url = ""

    try:
        source_path = path_source_dir.get()
        docs_path = path_docs_dir.get()
        source_branch = combo_branches.get()
        docs_branch = "master"
        label = combo_lables.get()
        desc_raw = description.get("1.0", "end-1c")

        if not source_path or not docs_path or not desc_raw.strip():
            app.after(0, lambda: messagebox.showerror("Ошибка", "Заполните все необходимые поля!"))
            return

        target_device_folder = label_to_path_map.get(label)
        if not target_device_folder or not os.path.exists(target_device_folder):
            app.after(0, lambda: messagebox.showerror("Ошибка", f"Папка для метки '{label}' не найдена!"))
            return

        source_commit_sha = git.get_latest_commit_hash(source_path, source_branch)

        path_copy_files = uFile.select_dir_withSource_files(source_path)
        newest_files = uFile.get_newest_files(path_copy_files, top_n=2)
        
        if not newest_files:
            app.after(0, lambda: messagebox.showerror("Ошибка", "Файлы прошивки не найдены!"))
            return

        firmware_version = uFile.clean_firmware_version(newest_files[0])
        result_dirs = uFile.find_docs_dir_by_path(target_device_folder)

        hex_processed = False
        bin_processed = False

        # Форматируем текст С ОТСТУПОМ специально для записи в файл
        formatted_desc_for_file = uFile.format_desc_for_file(desc_raw)

        for dirs in result_dirs:
            file_history_path = dirs.get('file_history')
            if file_history_path:
                # В файл уходит вариант с табуляцией (\t- ...)
                uFile.update_file_with_template(file_history_path, firmware_version, formatted_desc_for_file)

            file_hex_path = dirs.get('dir_hex')
            file_bin_path = dirs.get('dir_bin')

            for file_str in newest_files:
                if file_hex_path and not hex_processed and file_str.endswith('.hex'):
                    extended_hex_path = os.path.join(file_hex_path, "FirmwareSeparately")
                    uFile.delete_similar_hex_files(extended_hex_path, file_str)
                    uFile.copy_single_file(path_copy_files, extended_hex_path, file_str)
                    uFile.execute_commands_from_file(os.path.join(file_hex_path, "MakeTotal"))
                    hex_processed = True

                if file_bin_path and not bin_processed and file_str.endswith('.bin'):
                    uFile.process_bin_and_run_skiff(
                        file_bin_path=file_bin_path,
                        source_dir=path_copy_files,
                        firmware_version=firmware_version,
                        raw_bin_filename=file_str
                    )
                    bin_processed = True

        commit_summary = f"{label} : {firmware_version}"
        commit_description = f"LABEL : {label}\nBRANCH : {source_branch}\nSHA: {source_commit_sha}"

        git_success = git.git_commit_and_push(docs_path, docs_branch, commit_summary, commit_description)

        if git_success:
            docs_commit_sha = git.get_latest_commit_hash(docs_path)
            folder_url = git.get_folder_commit_url(docs_path, target_device_folder, docs_commit_sha)
            firmware_version = uFile.clean_firmware_version(newest_files[0])
        
            # Формируем имя тега (например, QA_v20_214_1AF6C5AE или QA_v1.0.0)
            tag_name = f"QA_v{firmware_version}"

            # Создаем и пушим тег в репозиторий ИСХОДНИКОВ на выбранную ветку (source_branch)
            tag_success = git.create_and_push_tag(source_path, source_branch, tag_name)
            if not tag_success:
               print(f"Предупреждение: Не удалось создать тег {tag_name} в репозитории исходников.")

            last_generated_url = folder_url
            app.after(0, lambda: _on_deploy_success(label, firmware_version, folder_url, desc_raw))
        else:
            app.after(0, lambda: messagebox.showwarning("Ошибка Git", "Не удалось выполнить push в репозиторий документации."))

    except Exception as e:
        app.after(0, lambda err=e: messagebox.showerror("Ошибка", f"Сбой процесса: {err}"))
    finally:
        app.after(0, lambda: apply_button.configure(state="normal", text="Apply & Push"))


def _on_deploy_success(label, firmware_version, folder_url, desc_raw):
    global last_generated_url, last_firmware_version
    
    last_generated_url = folder_url
    last_firmware_version = firmware_version
    
    messagebox.showinfo("Успех", "Выгрузка завершена! Нажмите 'Скопировать', чтобы получить текст для Telegram.")

def paste_text(event=None):
    # Если событие вызвано нажатием клавиши, проверяем keycode (86 = V)
    if event and hasattr(event, 'keycode'):
        # 86 — виртуальный код клавиши V в Windows
        if event.keycode != 86 and event.keysym.lower() != 'v':
            return

    try:
        text_to_paste = app.clipboard_get()
        # Удаляем выделенный текст перед вставкой, если он есть
        try:
            if description.tag_ranges("sel"):
                description.delete("sel.first", "sel.last")
        except Exception:
            pass
            
        description.insert("insert", text_to_paste)
    except Exception:
        pass
        
    return "break"  # Блокирует стандартную обработку Tkinter, исключая дублирование

def show_context_menu(event):
    desc_menu.tk_popup(event.x_root, event.y_root)

# --- UI Элементы ---
btn_source = ctk.CTkButton(app, text="Выбрать путь исходников", command=lambda: select_path(1, path_source_dir, label_source_path))
btn_source.pack(pady=(10,0), padx=10, anchor="w")
label_source_path = ctk.CTkLabel(app, text="", wraplength=550)
label_source_path.pack(pady=2, padx=10, anchor="w")

label_branch = ctk.CTkLabel(app, text="Ветка исходников:")
label_branch.pack(padx=10, anchor="w")
combo_branches = ctk.CTkComboBox(app, values=["---------"], width=200)
combo_branches.pack(pady=(0,10), padx=10, anchor="w")

btn_docs = ctk.CTkButton(app, text="Выбрать путь документации", command=lambda: select_path(2, path_docs_dir, label_docs_path))
btn_docs.pack(pady=(10,0), padx=10, anchor="w")
label_docs_path = ctk.CTkLabel(app, text="", wraplength=550)
label_docs_path.pack(pady=2, padx=10, anchor="w")

label_lbl = ctk.CTkLabel(app, text="Метка (Label из label.md):")
label_lbl.pack(padx=10, anchor="w")
combo_lables = ctk.CTkComboBox(app, values=["---------"], width=200)
combo_lables.pack(pady=(0,10), padx=10, anchor="w")

label_desc = ctk.CTkLabel(app, text="Описание изменений (Description):")
label_desc.pack(padx=10, anchor="w")
description = ctk.CTkTextbox(app, height=150)
description.pack(pady=(0,10), padx=10, fill="x")
desc_menu = Menu(app, tearoff=0)
desc_menu.add_command(label="Вставить", command=paste_text)
# Перехватываем ВСЕ нажатия клавиш с зажатым Control
description.bind("<Control-Key>", paste_text)
description.bind("<Shift-Insert>", paste_text)
description.bind("<Button-3>", show_context_menu)
apply_button = ctk.CTkButton(app, text="Apply & Push", command=apply_button_clicked, fg_color="green", height=40)
apply_button.pack(pady=15, padx=10, fill="x")

btn_copy = ctk.CTkButton(app, text="📋 Скопировать текст для Telegram", command=copy_to_clipboard, height=35)
btn_copy.pack(pady=(10, 20), padx=10, fill="x")

app.mainloop()