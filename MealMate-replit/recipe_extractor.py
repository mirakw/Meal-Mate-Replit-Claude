import os
import requests
from bs4 import BeautifulSoup
from recipe_scrapers import scrape_me
from pydantic import BaseModel, Field
from typing import List, Optional
import google.generativeai as genai
from dotenv import load_dotenv
import json

# --- Pydantic Models for Structured Output ---
class Recipe(BaseModel):
    name: str = Field(description="The name of the recipe.")
    serving_size: Optional[str] = Field(None, description="The serving size of the recipe, e.g., '4 servings' or '6 people'.")
    ingredients: List[str] = Field(description="A list of ingredients for the recipe.")
    instructions: List[str] = Field(description="A list of step-by-step instructions for the recipe.")

# --- Configure Gemini API ---
load_dotenv()

try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    print("Error: GEMINI_API_KEY not found in environment variables or .env file.")
    print("Please make sure you have a .env file in the same directory with GEMINI_API_KEY='your_api_key'")
    exit()

model = genai.GenerativeModel('gemini-1.5-flash')

def save_recipe_to_file(recipe: Recipe, directory="saved_recipes", folder_id="uncategorized"):
    """Saves a Recipe object to a JSON file in the specified folder."""
    # Create user-specific directory structure
    user_dir = os.path.join(directory, folder_id)
    os.makedirs(user_dir, exist_ok=True)
    
    # Sanitize name for filename (replace spaces with underscores, remove special chars)
    filename = "".join(c if c.isalnum() else "_" for c in recipe.name).lower()
    filepath = os.path.join(user_dir, f"{filename}.json")

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(recipe.model_dump(), f, ensure_ascii=False, indent=4)
    print(f"Recipe '{recipe.name}' saved to {filepath}")

def extract_recipe_from_url(url: str) -> Optional[Recipe]:
    """
    Attempts to extract recipe information from a URL using recipe-scrapers.
    If that fails or if the output is incomplete, it uses the Gemini API.
    """
    print(f"\nAttempting to extract recipe from: {url}")

    # 1. Try with recipe-scrapers
    try:
        scraper = scrape_me(url)
        recipe_name = scraper.title()
        ingredients = scraper.ingredients()
        instructions = scraper.instructions().split('\n')
        
        serving_size = None
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
            print("recipe-scrapers returned incomplete data. Falling back to Gemini API...")

    except Exception as e:
        print(f"recipe-scrapers failed: {e}. Falling back to Gemini API...")

    # 2. Fallback to Gemini API if recipe-scrapers fails or returns incomplete data
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        full_text = soup.get_text(separator='\n', strip=True)

        print("Sending content to Gemini for extraction...")
        prompt = f"""
        Extract the recipe name, serving size, a list of ingredients, and a list of instructions from the following text.
        The serving size should be a single string (e.g., "4 servings", "6 people").
        Return the result as a JSON object with keys: "name", "serving_size", "ingredients", "instructions".

        Text to parse:
        {full_text[:8000]}
        """
        
        response = model.generate_content(prompt)
        
        try:
            # Clean up the response text
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:].strip()
            if response_text.endswith('```'):
                response_text = response_text[:-3].strip()
            
            recipe_data = json.loads(response_text)
            parsed_recipe = Recipe.model_validate(recipe_data)
            print("Successfully extracted with Gemini API!")
            return parsed_recipe
        except Exception as e:
            print(f"Failed to parse Gemini API response as JSON: {e}")
            print(f"Gemini raw response: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during Gemini API extraction: {e}")
        return None

def create_manual_recipe() -> Optional[Recipe]:
    """Allows user to manually input a recipe."""
    print("\n=== Manual Recipe Entry ===")
    
    name = input("Recipe name: ").strip()
    if not name:
        print("Recipe name is required.")
        return None
    
    serving_size = input("Serving size (optional): ").strip() or None
    
    print("Enter ingredients (one per line, empty line to finish):")
    ingredients = []
    while True:
        ingredient = input("- ").strip()
        if not ingredient:
            break
        ingredients.append(ingredient)
    
    if not ingredients:
        print("At least one ingredient is required.")
        return None
    
    print("Enter instructions (one per line, empty line to finish):")
    instructions = []
    while True:
        instruction = input(f"{len(instructions) + 1}. ").strip()
        if not instruction:
            break
        instructions.append(instruction)
    
    if not instructions:
        print("At least one instruction is required.")
        return None
    
    return Recipe(
        name=name,
        serving_size=serving_size,
        ingredients=ingredients,
        instructions=instructions
    )

# --- Main execution ---
if __name__ == "__main__":
    while True:
        recipe_url = input("Enter a recipe URL (or 'q' to quit): ").strip()
        if recipe_url.lower() == 'q':
            break

        if not recipe_url.startswith(('http://', 'https://')):
            print("Invalid URL. Please enter a URL starting with http:// or https://")
            continue

        recipe_info = extract_recipe_from_url(recipe_url)

        if recipe_info:
            print("\n--- Extracted Recipe ---")
            print(f"Recipe Name: {recipe_info.name}")
            if recipe_info.serving_size:
                print(f"Serving Size: {recipe_info.serving_size}")
            print("\nIngredients:")
            for ingredient in recipe_info.ingredients:
                print(f"- {ingredient}")
            print("\nInstructions:")
            for i, instruction in enumerate(recipe_info.instructions):
                print(f"{i+1}. {instruction}")
            print("-" * 30)

            # Save the recipe
            save_recipe_to_file(recipe_info)
        else:
            print("Could not extract recipe information from the provided URL.")