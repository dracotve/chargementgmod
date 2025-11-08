import os
import json
import hashlib
import subprocess
import shutil
import eel
from pathlib import Path
from datetime import datetime
from tkinter import filedialog
import tkinter as tk

# Chemins
LAUNCHER_DIR = Path(__file__).parent
CONFIG_FILE = LAUNCHER_DIR / "config.json"
MODS_DIR = LAUNCHER_DIR / "mods"
MODS_CACHE_FILE = LAUNCHER_DIR / "mods_cache.json"

# Créer le dossier mods s'il n'existe pas
MODS_DIR.mkdir(exist_ok=True)

# Initialiser Eel avec le dossier web
eel.init(str(LAUNCHER_DIR))

def load_config():
    """Charge la configuration"""
    default_config = {
        "minecraft_dir": "",
        "java_path": "java",
        "ram_min": "2G",
        "ram_max": "4G",
        "last_check": "",
        "auto_sync": True
    }
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        except:
            pass
    return default_config

def save_config(config):
    """Sauvegarde la configuration"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

def get_file_hash(filepath):
    """Calcule le hash MD5 d'un fichier"""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def load_mods_cache():
    """Charge le cache des mods"""
    if MODS_CACHE_FILE.exists():
        try:
            with open(MODS_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_mods_cache(cache):
    """Sauvegarde le cache des mods"""
    with open(MODS_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=4)

def scan_mods():
    """Scanne le dossier mods et retourne la liste des mods"""
    mods = []
    if MODS_DIR.exists():
        for mod_file in MODS_DIR.glob("*.jar"):
            size_bytes = mod_file.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            
            mods.append({
                'name': mod_file.name,
                'size': f"{size_mb:.2f} MB",
                'size_bytes': size_bytes,
                'hash': get_file_hash(mod_file),
                'modified': datetime.fromtimestamp(mod_file.stat().st_mtime).isoformat()
            })
    
    mods.sort(key=lambda x: x['name'].lower())
    return mods

def sync_mods_to_minecraft(config):
    """Synchronise les mods vers le dossier Minecraft"""
    minecraft_dir = config.get('minecraft_dir', '')
    if not minecraft_dir or not os.path.exists(minecraft_dir):
        return False, "Dossier Minecraft non configure"
    
    mods_dir = Path(minecraft_dir) / "mods"
    mods_dir.mkdir(exist_ok=True)
    
    for mod_file in mods_dir.glob("*.jar"):
        try:
            mod_file.unlink()
        except Exception as e:
            print(f"Erreur: {e}")
    
    copied = 0
    for mod_file in MODS_DIR.glob("*.jar"):
        try:
            dst = mods_dir / mod_file.name
            shutil.copy2(mod_file, dst)
            copied += 1
        except Exception as e:
            print(f"Erreur: {e}")
    
    return True, f"{copied} mod(s) synchronise(s)"

def check_mods_updates_internal():
    """Version interne de check_updates"""
    old_cache = load_mods_cache()
    current_mods_list = scan_mods()
    current_mods = {mod['name']: mod for mod in current_mods_list}
    save_mods_cache(current_mods)
    
    config = load_config()
    if config.get('auto_sync', True):
        sync_mods_to_minecraft(config)

# Exposer les fonctions à JavaScript
@eel.expose
def get_config():
    """Récupère la configuration"""
    return load_config()

@eel.expose
def update_config(config):
    """Met à jour la configuration"""
    save_config(config)
    return {'success': True, 'message': 'Configuration sauvegardee'}

@eel.expose
def get_mods():
    """Récupère la liste des mods"""
    mods = scan_mods()
    return {'mods': mods, 'count': len(mods)}

@eel.expose
def browse_directory():
    """Ouvre un dialogue pour sélectionner le dossier Minecraft"""
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        directory = filedialog.askdirectory(title="Selectionner le dossier Minecraft")
        root.destroy()
        
        if directory:
            return {'path': directory}
        return {'path': None}
    except Exception as e:
        return {'error': str(e)}

@eel.expose
def add_mod():
    """Ouvre un dialogue pour ajouter des mods"""
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        files = filedialog.askopenfilenames(
            title="Selectionner des mods",
            filetypes=[("Fichiers JAR", "*.jar"), ("Tous les fichiers", "*.*")]
        )
        root.destroy()
        
        if files:
            added = 0
            for file in files:
                try:
                    src = Path(file)
                    dst = MODS_DIR / src.name
                    shutil.copy2(src, dst)
                    added += 1
                except Exception as e:
                    print(f"Erreur: {e}")
            
            check_mods_updates_internal()
            return {'success': True, 'added': added, 'message': f'{added} mod(s) ajoute(s)'}
        
        return {'success': False, 'message': 'Aucun fichier selectionne'}
    except Exception as e:
        return {'error': str(e)}

@eel.expose
def remove_mod(mods_to_remove):
    """Retire des mods"""
    try:
        removed = 0
        for mod_name in mods_to_remove:
            mod_path = MODS_DIR / mod_name
            if mod_path.exists():
                try:
                    mod_path.unlink()
                    removed += 1
                except Exception as e:
                    print(f"Erreur: {e}")
        
        check_mods_updates_internal()
        return {'success': True, 'removed': removed, 'message': f'{removed} mod(s) retire(s)'}
    except Exception as e:
        return {'error': str(e)}

@eel.expose
def check_updates():
    """Vérifie les mises à jour des mods"""
    try:
        old_cache = load_mods_cache()
        current_mods_list = scan_mods()
        current_mods = {mod['name']: mod for mod in current_mods_list}
        
        added_mods = []
        removed_mods = []
        modified_mods = []
        
        for mod_name, mod_info in current_mods.items():
            if mod_name not in old_cache:
                added_mods.append(mod_name)
            elif old_cache[mod_name]['hash'] != mod_info['hash']:
                modified_mods.append(mod_name)
        
        for mod_name in old_cache:
            if mod_name not in current_mods:
                removed_mods.append(mod_name)
        
        save_mods_cache(current_mods)
        
        config = load_config()
        sync_message = ""
        if config.get('auto_sync', True):
            success, msg = sync_mods_to_minecraft(config)
            if success:
                sync_message = f" | {msg}"
        
        changes = []
        if added_mods:
            changes.append(f"{len(added_mods)} ajoute(s)")
        if removed_mods:
            changes.append(f"{len(removed_mods)} retire(s)")
        if modified_mods:
            changes.append(f"{len(modified_mods)} modifie(s)")
        
        if changes:
            message = " | ".join(changes) + sync_message
        else:
            message = "Aucun changement detecte"
        
        config['last_check'] = datetime.now().isoformat()
        save_config(config)
        
        return {
            'success': True,
            'message': message,
            'added': len(added_mods),
            'removed': len(removed_mods),
            'modified': len(modified_mods)
        }
    except Exception as e:
        return {'error': str(e)}

@eel.expose
def launch_minecraft():
    """Lance Minecraft"""
    try:
        config = load_config()
        minecraft_dir = config.get('minecraft_dir', '')
        
        if not minecraft_dir or not os.path.exists(minecraft_dir):
            return {'error': 'Dossier Minecraft non configure'}
        
        if config.get('auto_sync', True):
            sync_mods_to_minecraft(config)
        
        minecraft_launcher = None
        possible_paths = [
            Path(minecraft_dir) / "MinecraftLauncher.exe",
            Path(os.environ.get('APPDATA', '')) / ".minecraft" / "MinecraftLauncher.exe",
            "C:\\Program Files (x86)\\Minecraft Launcher\\MinecraftLauncher.exe",
            "C:\\Program Files\\Minecraft Launcher\\MinecraftLauncher.exe"
        ]
        
        for path in possible_paths:
            if path.exists():
                minecraft_launcher = path
                break
        
        if minecraft_launcher:
            subprocess.Popen([str(minecraft_launcher)])
            return {'success': True, 'message': 'Minecraft lance'}
        else:
            return {
                'success': True,
                'message': 'Mods synchronises. Lancez Minecraft manuellement.'
            }
    except Exception as e:
        return {'error': str(e)}

def main():
    # Lancer l'application avec Eel
    import random
    port = random.randint(8000, 9000)
    eel.start('launcher_eel.html', size=(1000, 700), port=port)

if __name__ == "__main__":
    main()
