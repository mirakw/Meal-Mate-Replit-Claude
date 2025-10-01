#!/usr/bin/env python3
"""
Main entry point for the Meal Planning Application.
Provides a simple menu to choose between recipe extraction and meal planning.
"""

import sys
import os
from recipe_extractor import extract_recipe_from_url, create_manual_recipe, save_recipe_to_file
from meal_planner import load_recipes_from_directory, create_meal_plan

def display_main_menu():
    """Display the main application menu."""
    print("\n" + "="*50)
    print("MEAL PLANNING APPLICATION")
    print("="*50)
    print("1. Extract Recipe from URL")
    print("2. Manually Enter Recipe")
    print("3. Create Meal Plan & Grocery List")
    print("4. View Saved Recipes")
    print("5. Quit")
    print("-"*50)

def view_saved_recipes():
    """Display all saved recipes."""
    recipes = load_recipes_from_directory()
    
    if not recipes:
        print("\nNo saved recipes found.")
        print("Use option 1 or 2 to add some recipes first.")
        return
    
    print(f"\n--- Saved Recipes ({len(recipes)} total) ---")
    for i, (name, recipe) in enumerate(recipes.items(), 1):
        print(f"{i}. {name}")
        if recipe.serving_size:
            print(f"   Serving Size: {recipe.serving_size}")
        print(f"   Ingredients: {len(recipe.ingredients)} items")
        print(f"   Instructions: {len(recipe.instructions)} steps")
        print()

def handle_recipe_extraction():
    """Handle recipe extraction from URL."""
    recipe_url = input("Enter a recipe URL: ").strip()
    
    if not recipe_url.startswith(('http://', 'https://')):
        print("Invalid URL. Please enter a URL starting with http:// or https://")
        return
    
    recipe_info = extract_recipe_from_url(recipe_url)
    
    if recipe_info:
        display_recipe_info(recipe_info)
        save_recipe_to_file(recipe_info)
    else:
        print("Could not extract recipe information from the provided URL.")

def handle_manual_recipe():
    """Handle manual recipe entry."""
    recipe_info = create_manual_recipe()
    
    if recipe_info:
        display_recipe_info(recipe_info)
        save_recipe_to_file(recipe_info)
    else:
        print("Recipe creation cancelled.")

def display_recipe_info(recipe):
    """Display recipe information in a formatted way."""
    print("\n" + "-"*50)
    print("RECIPE DETAILS")
    print("-"*50)
    print(f"Name: {recipe.name}")
    if recipe.serving_size:
        print(f"Serving Size: {recipe.serving_size}")
    
    print(f"\nIngredients ({len(recipe.ingredients)}):")
    for ingredient in recipe.ingredients:
        print(f"  • {ingredient}")
    
    print(f"\nInstructions ({len(recipe.instructions)}):")
    for i, instruction in enumerate(recipe.instructions, 1):
        print(f"  {i}. {instruction}")
    print("-"*50)

def main():
    """Main application loop."""
    print("Welcome to the Meal Planning Application!")
    print("This tool helps you extract recipes and plan meals with automated grocery lists.")
    
    while True:
        display_main_menu()
        
        try:
            choice = input("Choose an option (1-5): ").strip()
            
            if choice == "1":
                handle_recipe_extraction()
                
            elif choice == "2":
                handle_manual_recipe()
                
            elif choice == "3":
                print("\nLoading saved recipes...")
                recipes = load_recipes_from_directory()
                if recipes:
                    create_meal_plan(recipes)
                else:
                    print("No recipes found. Please add some recipes first using options 1 or 2.")
                
            elif choice == "4":
                view_saved_recipes()
                
            elif choice == "5":
                print("\nThank you for using the Meal Planning Application!")
                break
                
            else:
                print("Invalid choice. Please select a number between 1 and 5.")
                
        except KeyboardInterrupt:
            print("\n\nApplication interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")
            print("Please try again.")

if __name__ == "__main__":
    main()
