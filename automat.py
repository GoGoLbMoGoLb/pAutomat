import dearpygui.dearpygui as dpg
import dearpygui.demo as demo
import gitWork as git
import workWithFiles as uFile
from datetime import datetime

dpg.create_context()
dpg.create_viewport(title='Custom Title', width=600, height=800)
selected_source_dir =''
selected_docs_dir =''
selected_branch =''
selected_label =''

def select_source_directory_callback(sender, app_data):
	global selected_source_dir
	selected_source_dir= app_data['file_path_name']  # Сохранение пути к выбранной директории
	print(f"Selected directory: {selected_source_dir}")
    
    # Обновляем список веток в ComboBox
	branches = git.get_branches(selected_source_dir)
	if branches:
		default_branch = "main" if "main" in branches else branches[0]  # Определяем дефолтную ветку
		dpg.configure_item("branch_combo", items=branches, default_value=default_branch)
		uFile.select_dir_withSource_files(selected_source_dir)
		if default_branch:
			# Установка значения по умолчанию и вызов callback вручную
			dpg.set_value("branch_combo", default_branch)
			branches_combo_callback("branch_combo", default_branch)  # Вызов callback вручную
	else:
		dpg.configure_item("branch_combo", items=["No branches found or not a Git repository."], default_value="")

def select_docs_directory_callback(sender, app_data):
	global selected_docs_dir
	selected_docs_dir = app_data['file_path_name']  # Сохранение пути к выбранной директории
	print(f"Selected documentation directory: {selected_docs_dir}")
	path_readme = uFile.find_readme_file(selected_docs_dir)
	if path_readme:
		print(f"path_readme {path_readme}")
		labels = uFile.extract_labels(path_readme)
		if labels:
			default_label = "main" if "main" in labels else labels[0]  # Определяем дефолтную ветку
			dpg.configure_item("labels_combo", items=labels, default_value=default_label)
			if default_label:
				# Установка значения по умолчанию и вызов callback вручную
				dpg.set_value("labels_combo", default_label)
				lables_combo_callback("labels_combo", default_label)  # Вызов callback вручную
	else:
		print("No README.md path found.")

def branches_combo_callback(sender, app_data):
	global selected_branch
	selected_branch = app_data
	print(f"Selected item: {selected_branch}")

def lables_combo_callback(sender, app_data):
	global selected_label
	selected_label = app_data
	print(f"Selected item: {selected_label}")

def input_callback(sender, app_data):
	print(app_data)

def callback_apply_btn():
	global selected_source_dir
	global selected_docs_dir
	# selected_source_dir = r'C:\Users\User\Documents\Forpost\Outdoor_prjs\OUTDOOR_Release'
	# selected_docs_dir = r'C:\Users\User\Documents\Forpost\Documentation\OutdoorFirmwareVersions'
	# selected_label = 'TAGER_NETRONIC'
	path_copy_files = uFile.select_dir_withSource_files(selected_source_dir)
	newest_files = uFile.get_newest_files(path_copy_files, top_n=2)
	latest_commit_hash = git.get_latest_commit_hash(selected_source_dir)
	if latest_commit_hash:
		print(f"Latest commit hash: {latest_commit_hash}")
	else:
		print("Failed to get the latest commit hash.")
	print("Newest files:")
	for file in newest_files:
		print(file)
	path_info_file = uFile.find_info_file(selected_source_dir)
	if path_info_file:
		# print(f"path_info_file: {path_info_file}")
		parsed_data = uFile.extract_info_of_build(path_info_file)
		for item in parsed_data:
			print(f"Type: {item['data_type']}, Variable: {item['variable_name']}, Value: {item['value']}")
	else:
		print(f"path_info_file not found")

	result_dirs = uFile.find_docs_dir_by_lable(selected_label.strip(), selected_docs_dir)	
	build_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

	for dirs in result_dirs:
		print(dirs)
		if(dirs['file_history']):
			file_item = newest_files[0]
			uFile.add_entry_to_file(dirs['file_history'], file_item.split('.')[0],build_time)
	

with dpg.file_dialog(
    directory_selector=True, show=False, callback=select_source_directory_callback, id="dir_select_source",
    width=700 ,height=400):
    dpg.add_file_extension(".*", color=(0, 255, 0, 255))
with dpg.file_dialog(
    directory_selector=True, show=False, callback=select_docs_directory_callback, id="dir_select_docs",
    width=700 ,height=400):
    dpg.add_file_extension(".*", color=(0, 255, 0, 255))

# Указываем путь к шрифту с поддержкой кириллицы
font_path = "C:/Windows/Fonts/arial.ttf"

with dpg.window(tag="Primary Window"):
	dpg.add_button(label="Directory source Selector", callback=lambda: dpg.show_item("dir_select_source"))
	dpg.add_combo(label="Select Branch", items=[], id="branch_combo", default_value="", callback=branches_combo_callback)  # Пустой ComboBox для списка веток
	
	dpg.add_button(label="Directory documentation Selector", callback=lambda: dpg.show_item("dir_select_docs"))
	dpg.add_combo(label="Select Lable", items=[], id="labels_combo", default_value="", callback=lables_combo_callback)  # Пустой ComboBox для списка меток
	# input_text = dpg.add_input_text(label="input text", multiline=True, hint="enter text here", height=100, callback=input_callback, tab_input=True)
	input_text = dpg.add_input_text(label="Введите текст")
	dpg.add_button(label="Apply", callback=callback_apply_btn, width=300)
# Загружаем шрифт
with dpg.font_registry():
	if dpg.does_item_exist(input_text):
		font = dpg.add_font(font_path, 20)
		dpg.bind_item_font(input_text, font)

# demo.show_demo()
# dpg.show_documentation()
# dpg.show_style_editor()
# dpg.show_debug()
# dpg.show_about()
# dpg.show_metrics()
# dpg.show_font_manager()

# Применение шрифта
dpg.bind_font(font)
# dpg.show_item_registry()
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("Primary Window", True)
dpg.start_dearpygui()
dpg.destroy_context()