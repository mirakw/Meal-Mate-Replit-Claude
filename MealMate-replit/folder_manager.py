import os
import json
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class Folder(BaseModel):
    id: str = Field(description="Unique folder identifier")
    name: str = Field(description="Display name of the folder")
    created_at: str = Field(description="Creation timestamp")
    recipe_count: int = Field(default=0, description="Number of recipes in folder")

class FolderManager:
    def __init__(self, folders_file="folders.json", recipes_dir="saved_recipes"):
        self.folders_file = folders_file
        self.recipes_dir = recipes_dir
        self.folders = self._load_folders()
    
    def _load_folders(self) -> Dict[str, Folder]:
        """Load folders from JSON file"""
        if not os.path.exists(self.folders_file):
            # Create default "Uncategorized" folder
            default_folder = Folder(
                id="uncategorized",
                name="Uncategorized",
                created_at=self._get_timestamp()
            )
            folders = {"uncategorized": default_folder}
            self._save_folders(folders)
            return folders
        
        try:
            with open(self.folders_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                folders = {}
                for folder_id, folder_data in data.items():
                    folders[folder_id] = Folder.model_validate(folder_data)
                return folders
        except Exception as e:
            print(f"Error loading folders: {e}")
            return {}
    
    def _save_folders(self, folders: Optional[Dict[str, Folder]] = None):
        """Save folders to JSON file"""
        target_folders = folders if folders is not None else self.folders
        
        data = {}
        for folder_id, folder in target_folders.items():
            data[folder_id] = folder.model_dump()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.folders_file), exist_ok=True)
        with open(self.folders_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _generate_folder_id(self, name: str) -> str:
        """Generate unique folder ID from name"""
        import re
        # Create ID from name, ensure uniqueness
        base_id = re.sub(r'[^a-z0-9]', '_', name.lower())
        folder_id = base_id
        counter = 1
        while folder_id in self.folders:
            folder_id = f"{base_id}_{counter}"
            counter += 1
        return folder_id
    
    def create_folder(self, name: str) -> Folder:
        """Create a new folder"""
        folder_id = self._generate_folder_id(name)
        folder = Folder(
            id=folder_id,
            name=name,
            created_at=self._get_timestamp()
        )
        self.folders[folder_id] = folder
        self._save_folders()
        
        # Create physical directory
        folder_path = os.path.join(self.recipes_dir, folder_id)
        os.makedirs(folder_path, exist_ok=True)
        
        return folder
    
    def delete_folder(self, folder_id: str) -> bool:
        """Delete a folder and move its recipes to Uncategorized"""
        if folder_id == "uncategorized":
            return False  # Cannot delete default folder
        
        if folder_id not in self.folders:
            return False
        
        # Ensure uncategorized folder exists
        uncategorized_path = os.path.join(self.recipes_dir, "uncategorized")
        os.makedirs(uncategorized_path, exist_ok=True)
        
        # Move recipes to uncategorized folder
        folder_path = os.path.join(self.recipes_dir, folder_id)
        
        if os.path.exists(folder_path):
            # Move all JSON files to uncategorized
            for filename in os.listdir(folder_path):
                if filename.endswith('.json'):
                    src = os.path.join(folder_path, filename)
                    dst = os.path.join(uncategorized_path, filename)
                    # Handle filename conflicts by adding a suffix
                    counter = 1
                    original_dst = dst
                    while os.path.exists(dst):
                        name, ext = os.path.splitext(original_dst)
                        dst = f"{name}_{counter}{ext}"
                        counter += 1
                    os.rename(src, dst)
            
            # Remove empty folder
            os.rmdir(folder_path)
        
        # Remove from folders dict
        del self.folders[folder_id]
        self._save_folders()
        self._update_recipe_counts()
        
        return True
    
    def rename_folder(self, folder_id: str, new_name: str) -> bool:
        """Rename a folder"""
        if folder_id not in self.folders:
            return False
        
        self.folders[folder_id].name = new_name
        self._save_folders()
        return True
    
    def get_all_folders(self) -> List[Folder]:
        """Get all folders with updated recipe counts"""
        # Ensure uncategorized folder always exists
        if "uncategorized" not in self.folders:
            self.folders["uncategorized"] = Folder(
                id="uncategorized",
                name="Uncategorized",
                created_at=self._get_timestamp()
            )
            self._save_folders()
            
            # Create physical directory
            uncategorized_path = os.path.join(self.recipes_dir, "uncategorized")
            os.makedirs(uncategorized_path, exist_ok=True)
        
        self._update_recipe_counts()
        return list(self.folders.values())
    
    def get_folder(self, folder_id: str) -> Optional[Folder]:
        """Get a specific folder"""
        return self.folders.get(folder_id)
    
    def _update_recipe_counts(self):
        """Update recipe counts for all folders"""
        for folder_id, folder in self.folders.items():
            folder_path = os.path.join(self.recipes_dir, folder_id)
            if os.path.exists(folder_path):
                recipe_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
                folder.recipe_count = len(recipe_files)
            else:
                folder.recipe_count = 0
        self._save_folders()
    
    def move_recipe(self, recipe_filename: str, source_folder: str, target_folder: str) -> bool:
        """Move a recipe from one folder to another"""
        source_path = os.path.join(self.recipes_dir, source_folder, recipe_filename)
        target_path = os.path.join(self.recipes_dir, target_folder, recipe_filename)
        
        if not os.path.exists(source_path):
            return False
        
        # Ensure target folder directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # Move the file
        os.rename(source_path, target_path)
        
        # Update recipe counts
        self._update_recipe_counts()
        
        return True

# Global folder manager instance
folder_manager = FolderManager()