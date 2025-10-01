import os
import json
import glob
import re
from dotenv import load_dotenv
from typing import List, Optional
import google.generativeai as genai
from dataclasses import dataclass, asdict

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Please set your GEMINI_API_KEY in a .env file.")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

@dataclass
class SearchRecipe:
    name: str
    ingredients: List[str]
    instructions: List[str]
    serving_size: Optional[str] = ""
    url: str = ""
    match_score: float = 0.0

def search_local_recipes(description: str, user_id: str) -> List[SearchRecipe]:
    """Search through user's saved recipes."""
    keywords = set(description.lower().split())
    matches = []
    
    # Search in user-specific directory structure
    user_recipe_dir = f"user_data/{user_id}/saved_recipes"
    if not os.path.exists(user_recipe_dir):
        return []
    
    # Search through all folders
    for root, dirs, files in os.walk(user_recipe_dir):
        for filename in files:
            if filename.endswith('.json'):
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        recipe = SearchRecipe(
                            name=data.get('name', ''),
                            ingredients=data.get('ingredients', []),
                            instructions=data.get('instructions', []),
                            serving_size=data.get('serving_size', ''),
                            url=data.get('url', '')
                        )
                        
                        # Calculate match score
                        combined_text = (
                            recipe.name + ' ' + 
                            ' '.join(recipe.ingredients) + ' ' + 
                            ' '.join(recipe.instructions)
                        ).lower()
                        
                        score = sum(1 for kw in keywords if kw in combined_text)
                        if score > 0:
                            recipe.match_score = score / len(keywords)
                            matches.append(recipe)
                            
                except Exception as e:
                    print(f"Error reading recipe file {filepath}: {e}")
                    continue
    
    # Sort by match score and return top 5
    matches.sort(key=lambda x: x.match_score, reverse=True)
    return matches[:5]

def search_web_recipes_simple(description: str) -> List[SearchRecipe]:
    """AI-powered recipe search - generates authentic recipes matching user description."""
    try:
        # Skip web scraping entirely since most sites block it
        # Generate authentic recipes directly from AI
        print(f"Generating authentic recipes for: {description}")
        return generate_complete_recipes(description)
        
    except Exception as e:
        print(f"Error in recipe search: {e}")
        return []

def generate_complete_recipes(description: str) -> List[SearchRecipe]:
    """Generate complete recipes using Gemini when URL extraction fails."""
    try:
        query_prompt = f"""
Based on the user request: "{description}"

Create 4 complete, detailed, authentic recipes that match this request. These should be real recipes that work in practice.
Include specific measurements, cooking times, and step-by-step instructions.
Focus on popular, well-tested recipes that people actually cook.

Return ONLY a valid JSON array where each item contains: name, ingredients (list), instructions (list), serving_size.

Format example:
[
  {{
    "name": "Classic Chocolate Chip Cookies",
    "ingredients": ["2 1/4 cups all-purpose flour", "1 teaspoon baking soda", "1 cup butter, softened", "3/4 cup granulated sugar", "3/4 cup packed brown sugar", "2 large eggs", "2 teaspoons vanilla extract", "2 cups chocolate chips"],
    "instructions": ["Preheat oven to 375°F (190°C)", "Mix flour and baking soda in bowl", "Cream butter and sugars until fluffy", "Beat in eggs and vanilla", "Gradually add flour mixture", "Stir in chocolate chips", "Drop rounded tablespoons on ungreased baking sheet", "Bake 9-11 minutes until golden brown"],
    "serving_size": "48 cookies"
  }}
]

Respond with ONLY the JSON array, no additional text."""

        response = model.generate_content(query_prompt)
        return format_multiple_recipes(response.text)
        
    except Exception as e:
        print(f"Error generating complete recipes: {e}")
        return []

def format_multiple_recipes(raw_text):
    """Parse multiple recipes from Gemini response."""
    try:
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
            
        parsed = json.loads(cleaned)
        recipes = []
        
        for item in parsed:
            allowed_keys = {'name', 'ingredients', 'instructions', 'serving_size', 'url'}
            filtered = {k: v for k, v in item.items() if k in allowed_keys}
            
            recipe = SearchRecipe(
                name=filtered.get('name', ''),
                ingredients=filtered.get('ingredients', []),
                instructions=filtered.get('instructions', []),
                serving_size=filtered.get('serving_size', ''),
                url="ai-generated"  # Mark as AI-generated to show proper buttons
            )
            recipes.append(recipe)
            
        return recipes[:5]
        
    except Exception as e:
        print(f"Error parsing multiple recipes: {e}\nRaw Output:\n{raw_text}")
        return []

def save_search_result_to_file(recipe_data: dict, folder_id: str, user_id: str) -> bool:
    """Save a recipe from search results to user's collection by extracting from URL."""
    try:
        from recipe_extractor import extract_recipe_from_url, save_recipe_to_file
        
        # Get the URL from recipe data
        recipe_url = recipe_data.get('url', '')
        
        if not recipe_url:
            # If no URL, create recipe from provided data
            from recipe_extractor import Recipe
            recipe = Recipe(
                name=recipe_data.get('name', ''),
                serving_size=recipe_data.get('serving_size'),
                ingredients=recipe_data.get('ingredients', []),
                instructions=recipe_data.get('instructions', [])
            )
        else:
            # Extract recipe from URL using the same logic as recipe extractor
            recipe = extract_recipe_from_url(recipe_url)
            if not recipe:
                # If extraction fails, create from provided data
                from recipe_extractor import Recipe
                recipe = Recipe(
                    name=recipe_data.get('name', ''),
                    serving_size=recipe_data.get('serving_size'),
                    ingredients=recipe_data.get('ingredients', []),
                    instructions=recipe_data.get('instructions', [])
                )
        
        # Create user-specific directory
        user_recipe_dir = f"user_data/{user_id}/saved_recipes"
        save_recipe_to_file(recipe, user_recipe_dir, folder_id)
        return True
        
    except Exception as e:
        print(f"Error saving search result: {e}")
        return False