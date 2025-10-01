import os
import requests
from bs4 import BeautifulSoup
from recipe_scrapers import scrape_me
from pydantic import BaseModel, Field
from typing import List, Optional
from dotenv import load_dotenv
import json

# --- Pydantic Models for Structured Output ---
class Recipe(BaseModel):
    name: str = Field(description="The name of the recipe.")
    serving_size: Optional[str] = Field(None, description="The serving size of the recipe, e.g., '4 servings' or '6 people'.")
    ingredients: List[str] = Field(description="A list of ingredients for the recipe.")
    instructions: List[str] = Field(description="A list of step-by-step instructions for the recipe.")

def save_recipe_to_file(recipe: Recipe, directory="saved_recipes", folder_id="uncategorized"):
    """Saves a Recipe object to a JSON file in the specified folder."""
    # Use the directory path as-is to prevent duplication
    recipe_dir = os.path.join(directory, folder_id)
    os.makedirs(recipe_dir, exist_ok=True)
    
    # Create a safe filename from the recipe name
    safe_name = "".join(c for c in recipe.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_name = safe_name.replace(' ', '_')
    filename = f"{safe_name}.json"
    filepath = os.path.join(recipe_dir, filename)
    
    # Save recipe as JSON
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(recipe.model_dump(), f, indent=2, ensure_ascii=False)
    
    print(f"Recipe saved to: {filepath}")
    return filepath

def extract_recipe_from_url(url: str) -> Optional[Recipe]:
    """
    Attempts to extract recipe information from a URL using recipe-scrapers.
    """
    print(f"Attempting to extract recipe from: {url}")
    
    # 1. Try recipe-scrapers first
    try:
        scraper = scrape_me(url)
        
        recipe_name = None
        ingredients = []
        instructions = []
        serving_size = None
        
        try:
            recipe_name = scraper.title()
        except AttributeError:
            pass
        except Exception as e:
            pass
        
        try:
            ingredients = scraper.ingredients()
        except AttributeError:
            pass
        except Exception as e:
            pass
        
        try:
            instructions = scraper.instructions_list()
        except AttributeError:
            pass
        except Exception as e:
            pass
        
        try:
            serving_size = scraper.yields()
        except AttributeError:
            pass
        except Exception as e:
            pass

        if recipe_name and ingredients and instructions:
            print("Successfully extracted with recipe-scrapers!")
            return Recipe(
                name=recipe_name,
                serving_size=serving_size,
                ingredients=ingredients,
                instructions=[inst.strip() for inst in instructions if inst.strip()]
            )
        else:
            print("recipe-scrapers returned incomplete data.")
            return None

    except Exception as e:
        print(f"recipe-scrapers failed: {e}")
        return None

def create_manual_recipe() -> Optional[Recipe]:
    """Allows user to manually input a recipe."""
    print("\n=== Manual Recipe Entry ===")
    
    name = input("Enter recipe name: ").strip()
    if not name:
        print("Recipe name is required.")
        return None
    
    serving_size = input("Enter serving size (optional, e.g., '4 servings'): ").strip()
    if not serving_size:
        serving_size = None
    
    print("\nEnter ingredients (one per line, press Enter twice when done):")
    ingredients = []
    while True:
        ingredient = input().strip()
        if not ingredient:
            if ingredients:  # If we have at least one ingredient and user pressed enter
                break
            continue
        ingredients.append(ingredient)
    
    if not ingredients:
        print("At least one ingredient is required.")
        return None
    
    print("\nEnter instructions (one per line, press Enter twice when done):")
    instructions = []
    while True:
        instruction = input().strip()
        if not instruction:
            if instructions:  # If we have at least one instruction and user pressed enter
                break
            continue
        instructions.append(instruction)
    
    if not instructions:
        print("At least one instruction is required.")
        return None
    
    recipe = Recipe(
        name=name,
        serving_size=serving_size,
        ingredients=ingredients,
        instructions=instructions
    )
    
    print(f"\nRecipe '{name}' created successfully!")
    return recipe