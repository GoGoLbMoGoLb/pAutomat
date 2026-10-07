import subprocess
import os
import re
import git  # GitPython

def get_branches(repository_path):
    """Получает список всех локальных и удаленных веток."""
    if os.path.isdir(repository_path):
        try:
            result = subprocess.run(
                ["git", "branch", "-a"], 
                cwd=repository_path,
                capture_output=True, 
                text=True, 
                check=True
            )
            branches = result.stdout.splitlines()
            cleaned_branches = []
            for b in branches:
                clean = b.strip().replace('* ', '').replace('remotes/origin/', '')
                if clean not in cleaned_branches and 'HEAD' not in clean:
                    cleaned_branches.append(clean)
            return cleaned_branches
        except subprocess.CalledProcessError:
            return []
    return []

def git_commit_and_push(repo_path, branch, summary, description):
    """Оптимизированный commit через библиотеку GitPython (без лишних subprocess)"""
    try:
        repo = git.Repo(repo_path, search_parent_directories=True)
        
        # Переключение ветки если необходимо
        if repo.active_branch.name != branch:
            repo.git.checkout(branch)
            
        # Индексируем изменения и делаем коммит
        repo.git.add(A=True)  # Аналог 'git add .'
        commit_message = f"{summary}\n\n{description}"
        repo.index.commit(commit_message)
        
        # Пуш на сервер
        # repo.remotes.origin.push(branch)
        
        print("Git commit completed instantly.")
        return True
    except Exception as e:
        print(f"Git operation failed: {e}")
        return False

def get_latest_commit_hash(repo_path, branch_name="HEAD"):
    """Получает SHA последнего коммита через GitPython без задержек subprocess."""
    try:
        repo = git.Repo(repo_path, search_parent_directories=True)
        commit = repo.commit(branch_name)
        return commit.hexsha
    except Exception as e:
        print(f"Error getting commit hash for branch {branch_name}: {e}")
        return "UNKNOWN_SHA"

def get_folder_commit_url(docs_repo_path, target_folder_path, commit_sha):
    """Формирует веб-ссылку на папку коммита через GitPython."""
    try:
        repo = git.Repo(docs_repo_path, search_parent_directories=True)
        repo_root = repo.working_tree_dir
        raw_url = repo.remotes.origin.url

        clean_url = raw_url
        if clean_url.startswith("git@"):
            clean_url = re.sub(r'^git@([^:]+):', r'http://\1/', clean_url)
        clean_url = re.sub(r'\.git$', '', clean_url).rstrip('/')

        abs_target_path = os.path.abspath(target_folder_path)
        rel_path = os.path.relpath(abs_target_path, repo_root).replace('\\', '/')

        if rel_path == '.' or not rel_path:
            return f"{clean_url}/tree/{commit_sha}"
        return f"{clean_url}/tree/{commit_sha}/{rel_path}"
    except Exception as err:
        print(f"[ERROR] GitPython failed: {err}")
        return f"/tree/{commit_sha}"

def create_and_push_tag(repo_path, branch_name, tag_name):
    """Создает тег на указанной ветке и выгружает его на origin."""
    try:
        repo = git.Repo(repo_path, search_parent_directories=True)
        
        # Получаем коммит указанной ветки
        target_commit = repo.commit(branch_name)
        
        # Проверяем, существует ли уже такой тег, чтобы избежать конфликта
        if tag_name in repo.tags:
            print(f"Тег {tag_name} уже существует. Пересоздаем...")
            git.Tag.delete(repo, tag_name)
            
        # Создаем тег на целевом коммите
        new_tag = repo.create_tag(tag_name, ref=target_commit)
        
        # Выполняем push тега на origin
        origin = repo.remote(name='origin')
        origin.push(new_tag)
        print(f"Тег {tag_name} успешно создан и отправлен в origin.")
        return True
    except Exception as e:
        print(f"Ошибка при создании/push тега {tag_name}: {e}")
        return False