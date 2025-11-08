import os
import json
import hashlib
import subprocess
import shutil
import webbrowser
import threading
from pathlib import Path
from datetime import datetime
from tkinter import filedialog
import tkinter as tk
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

class MinecraftLauncherWeb:
    def __init__(self):
        # Chemins
        self.launcher_dir = Path(__file__).parent
        self.config_file = self.launcher_dir / "config.json"
        self.mods_dir = self.launcher_dir / "mods"
        self.mods_cache_file = self.launcher_dir / "mods_cache.json"
        
        # Créer le dossier mods s'il n'existe pas
        self.mods_dir.mkdir(exist_ok=True)
        
        # Créer l'application Flask
        self.app = Flask(__name__, static_folder='.', template_folder='.')
        CORS(self.app)
        
        # Configurer les routes
        self.setup_routes()
    
    def load_config(self):
        """Charge la configuration"""
        default_config = {
            "minecraft_dir": "",
            "java_path": "java",
            "ram_min": "2G",
            "ram_max": "4G",
            "last_check": "",
            "auto_sync": True
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
            except:
                pass
        return default_config
    
    def save_config(self, config):
        """Sauvegarde la configuration"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    
    def get_file_hash(self, filepath):
        """Calcule le hash MD5 d'un fichier"""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def load_mods_cache(self):
        """Charge le cache des mods"""
        if self.mods_cache_file.exists():
            try:
                with open(self.mods_cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_mods_cache(self, cache):
        """Sauvegarde le cache des mods"""
        with open(self.mods_cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=4)
    
    def scan_mods(self):
        """Scanne le dossier mods et retourne la liste des mods"""
        mods = []
        if self.mods_dir.exists():
            for mod_file in self.mods_dir.glob("*.jar"):
                size_bytes = mod_file.stat().st_size
                size_mb = size_bytes / (1024 * 1024)
                
                mods.append({
                    'name': mod_file.name,
                    'size': f"{size_mb:.2f} MB",
                    'size_bytes': size_bytes,
                    'hash': self.get_file_hash(mod_file),
                    'modified': datetime.fromtimestamp(mod_file.stat().st_mtime).isoformat()
                })
        
        # Trier par nom
        mods.sort(key=lambda x: x['name'].lower())
        return mods
    
    def sync_mods_to_minecraft(self, config):
        """Synchronise les mods vers le dossier Minecraft"""
        minecraft_dir = config.get('minecraft_dir', '')
        if not minecraft_dir or not os.path.exists(minecraft_dir):
            return False, "Dossier Minecraft non configure"
        
        mods_dir = Path(minecraft_dir) / "mods"
        mods_dir.mkdir(exist_ok=True)
        
        # Supprimer tous les mods existants dans Minecraft
        for mod_file in mods_dir.glob("*.jar"):
            try:
                mod_file.unlink()
            except Exception as e:
                print(f"Erreur lors de la suppression de {mod_file}: {e}")
        
        # Copier tous les mods depuis le dossier mods
        copied = 0
        for mod_file in self.mods_dir.glob("*.jar"):
            try:
                dst = mods_dir / mod_file.name
                shutil.copy2(mod_file, dst)
                copied += 1
            except Exception as e:
                print(f"Erreur lors de la copie de {mod_file.name}: {e}")
        
        return True, f"{copied} mod(s) synchronise(s)"
    
    def check_mods_updates_internal(self):
        """Version interne de check_updates sans retour HTTP"""
        old_cache = self.load_mods_cache()
        current_mods_list = self.scan_mods()
        current_mods = {mod['name']: mod for mod in current_mods_list}
        self.save_mods_cache(current_mods)
        
        config = self.load_config()
        if config.get('auto_sync', True):
            self.sync_mods_to_minecraft(config)
    
    def setup_routes(self):
        """Configure les routes Flask"""
        
        @self.app.route('/')
        def index():
            return send_from_directory('.', 'launcher.html')
        
        @self.app.route('/api/config', methods=['GET'])
        def get_config():
            config = self.load_config()
            return jsonify(config)
        
        @self.app.route('/api/config', methods=['POST'])
        def update_config():
            config = request.json
            self.save_config(config)
            return jsonify({'success': True, 'message': 'Configuration sauvegardee'})
        
        @self.app.route('/api/mods', methods=['GET'])
        def get_mods():
            mods = self.scan_mods()
            return jsonify({'mods': mods, 'count': len(mods)})
        
        @self.app.route('/api/browse', methods=['GET'])
        def browse_directory():
            try:
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                directory = filedialog.askdirectory(title="Selectionner le dossier Minecraft")
                root.destroy()
                
                if directory:
                    return jsonify({'path': directory})
                return jsonify({'path': None})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/add-mod', methods=['POST'])
        def add_mod():
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
                            dst = self.mods_dir / src.name
                            shutil.copy2(src, dst)
                            added += 1
                        except Exception as e:
                            print(f"Erreur lors de l'ajout de {src.name}: {e}")
                    
                    self.check_mods_updates_internal()
                    return jsonify({'success': True, 'added': added, 'message': f'{added} mod(s) ajoute(s)'})
                
                return jsonify({'success': False, 'message': 'Aucun fichier selectionne'})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/remove-mod', methods=['POST'])
        def remove_mod():
            try:
                data = request.json
                mods_to_remove = data.get('mods', [])
                
                removed = 0
                for mod_name in mods_to_remove:
                    mod_path = self.mods_dir / mod_name
                    if mod_path.exists():
                        try:
                            mod_path.unlink()
                            removed += 1
                        except Exception as e:
                            print(f"Erreur lors de la suppression de {mod_name}: {e}")
                
                self.check_mods_updates_internal()
                return jsonify({'success': True, 'removed': removed, 'message': f'{removed} mod(s) retire(s)'})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/check-updates', methods=['POST'])
        def check_updates():
            try:
                old_cache = self.load_mods_cache()
                current_mods_list = self.scan_mods()
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
                
                self.save_mods_cache(current_mods)
                
                config = self.load_config()
                sync_message = ""
                if config.get('auto_sync', True):
                    success, msg = self.sync_mods_to_minecraft(config)
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
                self.save_config(config)
                
                return jsonify({
                    'success': True,
                    'message': message,
                    'added': len(added_mods),
                    'removed': len(removed_mods),
                    'modified': len(modified_mods)
                })
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/launch', methods=['POST'])
        def launch_minecraft():
            try:
                config = self.load_config()
                minecraft_dir = config.get('minecraft_dir', '')
                
                if not minecraft_dir or not os.path.exists(minecraft_dir):
                    return jsonify({'error': 'Dossier Minecraft non configure'}), 400
                
                if config.get('auto_sync', True):
                    self.sync_mods_to_minecraft(config)
                
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
                    return jsonify({'success': True, 'message': 'Minecraft lance'})
                else:
                    return jsonify({
                        'success': True,
                        'message': 'Mods synchronises. Lancez Minecraft manuellement.'
                    })
            except Exception as e:
                return jsonify({'error': str(e)}), 500
    
    def run(self):
        """Lance le serveur et ouvre le navigateur"""
        # Ouvrir le navigateur après un court délai
        def open_browser():
            import time
            time.sleep(1.5)
            webbrowser.open('http://localhost:5000')
        
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        
        # Lancer le serveur
        print("=== Minecraft Launcher Web ===")
        print("Serveur demarre sur http://localhost:5000")
        print("Ouverture du navigateur...")
        print("\nAppuyez sur Ctrl+C pour arreter\n")
        
        self.app.run(debug=False, host='127.0.0.1', port=5000, use_reloader=False)

def main():
    launcher = MinecraftLauncherWeb()
    launcher.run()

if __name__ == "__main__":
    main()
