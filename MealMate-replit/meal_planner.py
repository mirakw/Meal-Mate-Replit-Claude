import os
import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
import google.generativeai as genai
from dotenv import load_dotenv
import re # Import regex for cleaning up JSON response

# --- Pydantic Models for Data Transfer and Parsing ---
class Recipe(BaseModel):
    name: str = Field(description="The name of the recipe.")
    serving_size: Optional[str] = Field(None, description="The serving size of the recipe, e.g., '4 servings' or '6 people'.")
    ingredients: List[str] = Field(description="A list of ingredients for the recipe.")
    instructions: List[str] = Field(description="A list of step-by-step instructions for the recipe.")

class ParsedIngredient(BaseModel):
    quantity: Optional[float] = Field(None, description="The numeric quantity. Convert fractions (e.g., '1/2') to decimals (0.5). If no quantity, use None.")
    unit: Optional[str] = Field(None, description="The standardized unit (e.g., 'cup', 'pound', 'ounce', 'tablespoon', 'teaspoon', 'each', 'gram', 'ml'). If no unit, use None.")
    item: str = Field(description="The standardized, clean name of the ingredient (e.g., 'unsalted butter', 'extra-large eggs', 'all-purpose flour'). Remove descriptors like 'at room temperature', 'chopped', 'minced', 'packed'.")
    notes: Optional[str] = Field(None, description="Any additional descriptive text that can't be removed (e.g., 'at room temperature', 'for garnish').")


# --- Configure Gemini API ---
load_dotenv()

try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    print("Error: GEMINI_API_KEY not found in environment variables or .env file.")
    print("Please make sure you have a .env file in the same directory with GEMINI_API_KEY='your_api_key'")
    exit()

parsing_model = genai.GenerativeModel('gemini-1.5-pro')


def load_recipes_from_directory(directory="saved_recipes") -> Dict[str, Recipe]:
    """Loads all Recipe objects from JSON files in the specified directory."""
    recipes = {}
    if not os.path.exists(directory):
        print(f"Warning: Directory '{directory}' not found. No recipes to load.")
        return recipes

    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    recipe = Recipe.model_validate(data)
                    recipes[recipe.name] = recipe
            except Exception as e:
                print(f"Error loading recipe from {filename}: {e}")
    return recipes

def parse_ingredient_line_with_gemini(ingredient_text: str) -> Optional[ParsedIngredient]:
    """
    Uses Gemini API to parse a single ingredient string into structured data.
    This version is compatible with google-generativeai 0.8.5 by asking Gemini
    to output JSON as text and then parsing it.
    """
    prompt = f"""
    Parse the following raw ingredient text into its quantity, standardized unit, standardized item name, and any remaining notes.

    - Convert all fractions (e.g., '1/2', '1 1/4') to decimals (e.g., 0.5, 1.25).
    - If no explicit quantity is specified, output null for quantity.
    - Standardize units: Use common singular forms (e.g., 'cup', 'pound', 'ounce', 'tablespoon', 'teaspoon', 'each', 'gram', 'ml'). If no clear unit, output null for unit.
    - Standardize item name: **Preserve key descriptors that change ingredient meaning** (e.g., 'unsalted', 'salted', 'brown', 'white', 'grated', 'shredded'). Only remove general prep words like 'chopped', 'diced', 'minced', 'peeled'.
    - Capture any remaining notes (e.g., "at room temperature", "for garnish") in the 'notes' field. If none, use null.

    Examples:
    "1 1/2 cups chopped walnuts" → quantity: 1.5, unit: "cup", item: "walnuts", notes: null  
    "12 extra-large eggs" → quantity: 12.0, unit: "each", item: "eggs", notes: null  
    "1/2 pound unsalted butter, at room temperature" → quantity: 0.5, unit: "pound", item: "unsalted butter", notes: "at room temperature"  
    "Kosher salt and freshly ground black pepper" → quantity: null, unit: null, item: "salt and black pepper", notes: null  
    "1 red onion, 1 1/2-inch-diced" → quantity: 1.0, unit: "each", item: "red onion", notes: "1 1/2-inch-diced"  
    "1 cup half-and-half" → quantity: 1.0, unit: "cup", item: "half and half", notes: null

    Raw ingredient text: "{ingredient_text}"

    Output the result as a JSON object with keys: "quantity", "unit", "item", "notes". No markdown or formatting outside the JSON.
    """

    try:
        response = parsing_model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="text/plain"
            )
        )
        
        json_str = response.text.strip()
        
        if json_str.startswith('```json') and json_str.endswith('```'):
            json_str = json_str[len('```json'):-len('```')].strip()
        elif json_str.startswith('```') and json_str.endswith('```'):
            json_str = json_str[len('```'):-len('```')].strip()

        parsed_data = json.loads(json_str)
        parsed_ingredient = ParsedIngredient.model_validate(parsed_data)
        return parsed_ingredient
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from Gemini response for '{ingredient_text}': {e}")
        # print(f"Gemini raw response (failed JSON): {response.text}") # Uncomment for debugging
        return None
    except Exception as e:
        print(f"Error parsing ingredient '{ingredient_text}' with Gemini (general error): {e}")
        return None

# --- Unit Conversion and Normalization Data ---
# Define canonical units for different ingredient types
CANONICAL_UNITS = {
    'weight': 'pound',
    'volume': 'cup',
    'count': 'each',
    'spoon': 'tablespoon', # For small quantities
    'other': None # For items with no clear unit, or that are often unitless
}

# Conversion factors to canonical units (e.g., 1 ounce = 1/16 pound)
# Keys are the unit to convert FROM, values are dicts of {TO_UNIT: FACTOR}
UNIT_CONVERSION_FACTORS = {
    'ounce': {'pound': 1/16},
    'gram': {'pound': 1/453.592}, # 1 pound = 453.592 grams
    'tablespoon': {'teaspoon': 3, 'cup': 1/16}, # 1 cup = 16 tablespoons
    'teaspoon': {'tablespoon': 1/3, 'cup': 1/48}, # 1 cup = 48 teaspoons
    'ml': {'cup': 1/236.588}, # 1 cup = 236.588 ml
    'pound': {'ounce': 16}, # For display preference later
    'cup': {'tablespoon': 16}, # For display preference later
}

# Mapping specific units to their 'type' for canonical conversion
UNIT_TYPES_MAP = {
    'pound': 'weight', 'lb': 'weight', 'lbs': 'weight', 'ounce': 'weight', 'oz': 'weight', 'gram': 'weight', 'g': 'weight', 'kg': 'weight',
    'cup': 'volume', 'cups': 'volume', 'ml': 'volume', 'liter': 'volume', 'l': 'volume', 'fl oz': 'volume', 'fluid ounce': 'volume',
    'tablespoon': 'spoon', 'tbsp': 'spoon', 'tbsps': 'spoon',
    'teaspoon': 'spoon', 'tsp': 'spoon', 'tsps': 'spoon',
    'each': 'count', 'ea': 'count', 'clove': 'count', 'cloves': 'count', 'stalk': 'count', 'stalks': 'count', 'sprig': 'count', 'sprigs': 'count', 'head': 'count', 'heads': 'count',
    'slice': 'other', 'package': 'other', 'can': 'other', 'jar': 'other', 'dash': 'other', 'pinch': 'other', 'to taste': 'other',
}


def convert_to_canonical_unit(quantity: float, unit: str) -> tuple[float, str]:
    """
    Converts a quantity and unit to its canonical unit and value.
    Returns (converted_quantity, canonical_unit_name).
    """
    normalized_unit = unit.strip().lower()

    # Find the type of unit (weight, volume, count, spoon)
    unit_type = UNIT_TYPES_MAP.get(normalized_unit)
    if not unit_type:
        return quantity, normalized_unit # Return as is if type unknown

    canonical_unit_name = CANONICAL_UNITS.get(unit_type)
    if not canonical_unit_name:
        return quantity, normalized_unit # No canonical unit for this type

    # If already canonical, return as is
    if normalized_unit == canonical_unit_name:
        return quantity, canonical_unit_name
    
    # Attempt conversion
    # Path 1: Direct conversion from normalized_unit to canonical_unit_name
    if normalized_unit in UNIT_CONVERSION_FACTORS and canonical_unit_name in UNIT_CONVERSION_FACTORS[normalized_unit]:
        return quantity * UNIT_CONVERSION_FACTORS[normalized_unit][canonical_unit_name], canonical_unit_name
    
    # Path 2: Conversion from canonical_unit_name to normalized_unit (then inverse)
    if canonical_unit_name in UNIT_CONVERSION_FACTORS and normalized_unit in UNIT_CONVERSION_FACTORS[canonical_unit_name]:
        # This means we have a conversion factor from canonical to normalized.
        # So to go from normalized to canonical, we divide by that factor.
        return quantity / UNIT_CONVERSION_FACTORS[canonical_unit_name][normalized_unit], canonical_unit_name

    return quantity, normalized_unit # Fallback if no conversion path found


def consolidate_ingredients(parsed_ingredients: List[ParsedIngredient]) -> List[str]:
    """Aggregates parsed ingredients by item and its canonical unit."""
    from collections import defaultdict
    aggregated: Dict[tuple[str, Optional[str]], Dict[str, Any]] = defaultdict(lambda: {'quantity': 0.0, 'notes': set()})
    non_quantified_items: List[str] = []

    # Define a set of ingredients for which quantities should generally be omitted if small
    ITEMS_TO_OMIT_QUANTITY_FOR_SMALL_AMOUNTS = {
        'garlic', 'salt', 'pepper', 'baking soda', 'baking powder', 'vanilla extract',
        'cinnamon', 'nutmeg', 'oregano', 'thyme', 'rosemary', 'paprika', 'cumin',
        'chili powder', 'cayenne pepper', 'ginger', 'allspice', 'cloves', 'bay leaf',
        'dill', 'parsley', 'cilantro', 'scallion', 'chives', 'lemon zest', 'lime zest',
        'kosher salt', 'sea salt', 'black pepper', 'pure vanilla extract',
        'sugar', # Review if you want to always omit small sugar quantities
        'olive oil',
        'vegetable oil', 'canola oil', 'water', 'vinegar'
    }

    # Define density-based conversions for specific ingredients
    # Add more ingredients and their conversion factors here!
    # Format: 'base_ingredient_name': {'unit_to_convert_FROM': {'preferred_unit_TO': conversion_factor}}
    INGREDIENT_DENSITY_CONVERSIONS = {
        'butter': {
            'tablespoon': {'ounce': 0.5}, # 1 tbsp butter is approx 0.5 oz
            'cup': {'ounce': 8}          # 1 cup butter is approx 8 oz
        },
        'all-purpose flour': {
            'cup': {'ounce': 4.25},      # 1 cup all-purpose flour is approx 4.25 oz (standard, unsifted)
            'tablespoon': {'ounce': 4.25 / 16} # 1 tbsp flour is 1/16th of a cup
        },
        'granulated sugar': {
            'cup': {'ounce': 7.05},      # 1 cup granulated sugar is approx 7.05 oz
            'tablespoon': {'ounce': 7.05 / 16}
        },
        'brown sugar': {
            'cup': {'ounce': 7.5},       # 1 cup packed brown sugar is approx 7.5 oz
            'tablespoon': {'ounce': 7.5 / 16}
        },
        'powdered sugar': {
            'cup': {'ounce': 4},         # 1 cup powdered sugar is approx 4 oz (sifted)
            'tablespoon': {'ounce': 4 / 16}
        },
        'olive oil': {
            'cup': {'ounce': 7.6},       # 1 cup olive oil is approx 7.6 oz
            'tablespoon': {'ounce': 0.475} # 1 tbsp olive oil is approx 0.475 oz
        },
        # Add more here as you encounter them!
        # Example for something like 'chicken broth' if you ever get it by weight
        # 'chicken broth': {
        #     'cup': {'ounce': 8.35} # 1 cup water/broth is approx 8.35 oz
        # }
    }


    for p_ing in parsed_ingredients:
        if not p_ing or not p_ing.item:
            continue

        item = p_ing.item.strip().lower().replace("  ", " ")
        quantity = p_ing.quantity
        unit = p_ing.unit.strip().lower() if p_ing.unit else None

        # --- IMPORTANT: Standardize item name for conversion lookup ---
        # This part is crucial. You need to strip common descriptors so that
        # 'unsalted butter', 'salted butter' both map to 'butter' for conversion,
        # 'all-purpose flour' maps to 'all-purpose flour', etc.
        # It's best to have a robust way to get the 'base' ingredient name here.
        # For now, let's refine the `base_item_for_conversion` to handle more cases.

        base_item_for_conversion = item # Start with the parsed item name

        # A more generic way to get the 'base' item for conversion lookup
        if item in INGREDIENT_DENSITY_CONVERSIONS:
            base_item_for_conversion = item
        else:
            # Try stripping common descriptors
            for base_key in INGREDIENT_DENSITY_CONVERSIONS:
                if base_key in item:
                    base_item_for_conversion = base_key
                    break

        # --- Density-based conversion for specific ingredients ---
        if base_item_for_conversion in INGREDIENT_DENSITY_CONVERSIONS and unit and quantity is not None:
            conversions = INGREDIENT_DENSITY_CONVERSIONS[base_item_for_conversion]
            if unit in conversions:
                # Convert using density
                for target_unit, factor in conversions[unit].items():
                    quantity = quantity * factor
                    unit = target_unit
                    break # Use the first available conversion

        # --- Apply canonical unit conversion ---
        if quantity is not None and unit:
            quantity, unit = convert_to_canonical_unit(quantity, unit)

        # --- Aggregate ingredients ---
        if quantity is None or unit is None:
            # Handle non-quantified items
            if item not in [ni.lower() for ni in non_quantified_items]:
                non_quantified_items.append(item)
        else:
            # Check if we should omit the quantity for small amounts
            omit_small_quantity = any(keyword in item for keyword in ITEMS_TO_OMIT_QUANTITY_FOR_SMALL_AMOUNTS)
            
            key = (item, unit)
            aggregated[key]['quantity'] += quantity
            if p_ing.notes:
                aggregated[key]['notes'].add(p_ing.notes)

    # --- Format the final grocery list ---
    grocery_list = []

    # Add quantified items
    for (item, unit), data in aggregated.items():
        quantity = data['quantity']
        notes = data['notes']
        
        # Check if we should omit the quantity
        omit_small_quantity = any(keyword in item for keyword in ITEMS_TO_OMIT_QUANTITY_FOR_SMALL_AMOUNTS)
        
        # Format quantity
        if omit_small_quantity and quantity <= 1.0:
            # Omit quantity for small amounts of spices, seasonings, etc.
            formatted_item = item
        else:
            # Include quantity
            if quantity == int(quantity):
                quantity_str = str(int(quantity))
            else:
                quantity_str = f"{quantity:.3g}" # Use 3 significant digits
            formatted_item = f"{quantity_str} {unit} {item}"
        
        # Add notes if any
        if notes:
            notes_str = ", ".join(notes)
            formatted_item += f" ({notes_str})"
        
        grocery_list.append(formatted_item)

    # Add non-quantified items
    for item in non_quantified_items:
        grocery_list.append(item)

    return sorted(grocery_list)

def create_meal_plan(available_recipes: Dict[str, Recipe]):
    """
    Interactively creates a meal plan and generates a grocery list.
    """
    print("\n=== Meal Planning ===")
    print("Available recipes:")
    recipe_names = list(available_recipes.keys())
    for i, name in enumerate(recipe_names, 1):
        print(f"{i}. {name}")

    selected_recipes = []
    while True:
        choice = input("\nEnter recipe number to add to meal plan (or 'done' to finish): ").strip()
        if choice.lower() == 'done':
            break
        try:
            recipe_index = int(choice) - 1
            if 0 <= recipe_index < len(recipe_names):
                recipe_name = recipe_names[recipe_index]
                selected_recipes.append(available_recipes[recipe_name])
                print(f"Added '{recipe_name}' to meal plan.")
            else:
                print("Invalid recipe number.")
        except ValueError:
            print("Please enter a valid number or 'done'.")

    if not selected_recipes:
        print("No recipes selected for meal plan.")
        return

    print(f"\nMeal plan includes {len(selected_recipes)} recipes:")
    for recipe in selected_recipes:
        print(f"- {recipe.name}")

    # Generate grocery list
    print("\nGenerating consolidated grocery list...")
    grocery_list = generate_grocery_list(selected_recipes)
    
    print("\n=== GROCERY LIST ===")
    for item in grocery_list:
        print(f"• {item}")
    print(f"\nTotal items: {len(grocery_list)}")

def generate_grocery_list(recipes: List[Recipe]):
    """Generates a consolidated and aggregated grocery list."""
    all_ingredients = []
    
    for recipe in recipes:
        print(f"Processing ingredients from '{recipe.name}'...")
        for ingredient in recipe.ingredients:
            parsed = parse_ingredient_line_with_gemini(ingredient)
            if parsed:
                all_ingredients.append(parsed)
            else:
                # If parsing fails, add the raw ingredient as-is
                all_ingredients.append(ParsedIngredient(
                    quantity=None,
                    unit=None,
                    item=ingredient,
                    notes=None
                ))
    
    return consolidate_ingredients(all_ingredients)

if __name__ == "__main__":
    # Load all available recipes
    recipes = load_recipes_from_directory()
    
    if not recipes:
        print("No recipes found in the saved_recipes directory.")
        print("Please add some recipes first using the recipe extractor.")
    else:
        create_meal_plan(recipes)