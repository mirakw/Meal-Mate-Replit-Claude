# app.py  — MealMate (Google-only auth)

import os
import json
import shutil
import logging
from datetime import datetime

from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from database import db
from models import User, PasswordResetToken, GroceryList  # OAuth model not required
from folder_manager import FolderManager
from recipe_extractor import extract_recipe_from_url, create_manual_recipe, save_recipe_to_file, Recipe
from meal_planner import load_recipes_from_directory, parse_ingredient_line_with_gemini, consolidate_ingredients
from smart_recipe_search import search_local_recipes, search_web_recipes_simple, save_search_result_to_file

from flask_login import (LoginManager, login_required, current_user,
                         logout_user, login_user)
from auth import auth_bp
from google_auth import google_auth

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
logging.basicConfig(level=logging.DEBUG)

# ------------------------------------------------------------------------------
# Flask App
# ------------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "your-secret-key-here")

# Ensure proxies / https are handled (Replit)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Cookie hardening + https URL generation
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PREFERRED_URL_SCHEME="https",
    SEND_FILE_MAX_AGE_DEFAULT=0,  # Disable caching for static files
)

# ------------------------------------------------------------------------------
# Database
# ------------------------------------------------------------------------------
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300
}

db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()
    logging.info("Database tables created")

# ------------------------------------------------------------------------------
# Login Manager
# ------------------------------------------------------------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'  # your auth blueprint's login route (renders Google-only page)


@login_manager.user_loader
def load_user(user_id):
    # Using legacy Query.get; fine for now with your SQLAlchemy setup
    return User.query.get(user_id)


CANONICAL_HOST = "c6995661-6fac-468a-bd42-40047c816f22-00-29kqr5fng0b9t.riker.replit.dev"


@app.before_request
def _force_canonical_host():
    if request.host != CANONICAL_HOST:
        return redirect(f"https://{CANONICAL_HOST}{request.full_path}",
                        code=301)


# ------------------------------------------------------------------------------
# Blueprints: your auth UI (renders login page), then Google OAuth
# ------------------------------------------------------------------------------
app.register_blueprint(auth_bp)
app.register_blueprint(google_auth)


# ------------------------------------------------------------------------------
# Basic routes
# ------------------------------------------------------------------------------
@app.route('/')
def index():
    # Template checks current_user.is_authenticated
    return render_template('index.html')


# ------------------------------------------------------------------------------
# Debug helpers (you can keep or remove later)
# ------------------------------------------------------------------------------
@app.route("/_routes")
def _routes():
    return "<pre>" + "\n".join(sorted(
        str(r) for r in app.url_map.iter_rules())) + "</pre>"

@app.route("/_debug_redirect")
def _debug_redirect():
    base = request.url_root.rstrip("/")
    try:
        return base + url_for("google.authorized")
    except Exception:
        return base + "/google_login/callback"


@app.route('/api/folders', methods=['GET'])
@login_required
def get_folders():
    """Get all folders with recipe counts for the current user."""
    # Use user-specific folder manager
    user_folder_manager = FolderManager(
        folders_file=f"user_data/{current_user.id}/folders.json",
        recipes_dir=f"user_data/{current_user.id}/saved_recipes")
    folders = user_folder_manager.get_all_folders()
    folder_list = []
    for folder in folders:
        folder_list.append({
            'id': folder.id,
            'name': folder.name,
            'recipe_count': folder.recipe_count,
            'created_at': folder.created_at
        })
    return jsonify(folder_list)


@app.route('/api/folders', methods=['POST'])
@login_required
def create_folder():
    """Create a new folder for the current user."""
    data = request.get_json()
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': 'Folder name is required'}), 400

    try:
        user_folder_manager = FolderManager(
            folders_file=f"user_data/{current_user.id}/folders.json",
            recipes_dir=f"user_data/{current_user.id}/saved_recipes")
        folder = user_folder_manager.create_folder(name)
        return jsonify({
            'success': True,
            'folder': {
                'id': folder.id,
                'name': folder.name,
                'recipe_count': folder.recipe_count,
                'created_at': folder.created_at
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/folders/<folder_id>', methods=['PUT'])
@login_required
def rename_folder(folder_id):
    """Rename a folder for the current user."""
    data = request.get_json()
    new_name = data.get('name', '').strip()

    if not new_name:
        return jsonify({'error': 'Folder name is required'}), 400

    try:
        user_folder_manager = FolderManager(
            folders_file=f"user_data/{current_user.id}/folders.json",
            recipes_dir=f"user_data/{current_user.id}/saved_recipes")
        success = user_folder_manager.rename_folder(folder_id, new_name)
        if success:
            return jsonify({
                'success': True,
                'message': 'Folder renamed successfully'
            })
        else:
            return jsonify({'error': 'Folder not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/folders/<folder_id>', methods=['DELETE'])
@login_required
def delete_folder(folder_id):
    """Delete a folder for the current user."""
    try:
        user_folder_manager = FolderManager(
            folders_file=f"user_data/{current_user.id}/folders.json",
            recipes_dir=f"user_data/{current_user.id}/saved_recipes")
        success = user_folder_manager.delete_folder(folder_id)
        if success:
            return jsonify({
                'success': True,
                'message': 'Folder deleted successfully'
            })
        else:
            return jsonify(
                {'error': 'Cannot delete folder or folder not found'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/folders/<folder_id>/recipes', methods=['GET'])
@login_required
def get_folder_recipes(folder_id):
    """Get all recipes in a specific folder for the current user."""
    try:
        folder_path = os.path.join(
            f"user_data/{current_user.id}/saved_recipes", folder_id)
        if not os.path.exists(folder_path):
            return jsonify([])

        recipes = []
        for filename in os.listdir(folder_path):
            if filename.endswith('.json'):
                filepath = os.path.join(folder_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        recipe = Recipe.model_validate(data)
                        recipes.append({
                            'name':
                            recipe.name,
                            'serving_size':
                            recipe.serving_size,
                            'ingredients_count':
                            len(recipe.ingredients),
                            'instructions_count':
                            len(recipe.instructions),
                            'folder_id':
                            folder_id
                        })
                except Exception as e:
                    print(f"Error loading recipe from {filename}: {e}")

        return jsonify(recipes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recipes', methods=['GET'])
@login_required
def get_recipes():
    """Get all saved recipes organized by folders for the current user."""
    try:
        user_folder_manager = FolderManager(
            folders_file=f"user_data/{current_user.id}/folders.json",
            recipes_dir=f"user_data/{current_user.id}/saved_recipes")
        folders = user_folder_manager.get_all_folders()
        all_recipes = []

        for folder in folders:
            folder_path = os.path.join(
                f"user_data/{current_user.id}/saved_recipes", folder.id)
            if os.path.exists(folder_path):
                for filename in os.listdir(folder_path):
                    if filename.endswith('.json'):
                        filepath = os.path.join(folder_path, filename)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                recipe = Recipe.model_validate(data)
                                all_recipes.append({
                                    'name':
                                    recipe.name,
                                    'serving_size':
                                    recipe.serving_size,
                                    'ingredients_count':
                                    len(recipe.ingredients),
                                    'instructions_count':
                                    len(recipe.instructions),
                                    'folder_id':
                                    folder.id,
                                    'folder_name':
                                    folder.name
                                })
                        except Exception as e:
                            print(f"Error loading recipe from {filename}: {e}")

        return jsonify(all_recipes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recipe/<folder_id>/<recipe_name>', methods=['GET'])
@login_required
def get_recipe_details(folder_id, recipe_name):
    """Get details for a specific recipe in a folder for the current user."""
    try:
        folder_path = os.path.join(
            f"user_data/{current_user.id}/saved_recipes", folder_id)

        # Use consistent filename generation (same as in recipe_extractor.py)
        filename = "".join(c if c.isalnum() else "_"
                           for c in recipe_name).lower()
        filepath = os.path.join(folder_path, f"{filename}.json")

        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                recipe = Recipe.model_validate(data)
                return jsonify(recipe.model_dump())

        # If not found, try to find any file in the folder that matches
        if os.path.exists(folder_path):
            for file in os.listdir(folder_path):
                if file.endswith('.json'):
                    with open(os.path.join(folder_path, file),
                              'r',
                              encoding='utf-8') as f:
                        try:
                            data = json.load(f)
                            recipe = Recipe.model_validate(data)
                            if recipe.name == recipe_name:
                                return jsonify(recipe.model_dump())
                        except:
                            continue

        return jsonify({'error': 'Recipe not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/extract-recipe', methods=['POST'])
@login_required
def extract_recipe():
    """Extract recipe from URL for the current user."""
    data = request.get_json()
    url = data.get('url')
    folder_id = data.get('folder_id', 'uncategorized')

    if not url or not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL'}), 400

    try:
        recipe = extract_recipe_from_url(url)
        if recipe:
            # Ensure user directory exists
            user_dir = f"user_data/{current_user.id}/saved_recipes"
            os.makedirs(user_dir, exist_ok=True)
            filepath = save_recipe_to_file(
                recipe,
                directory=f"user_data/{current_user.id}/saved_recipes",
                folder_id=folder_id)
            # Update folder recipe count
            user_folder_manager = FolderManager(
                folders_file=f"user_data/{current_user.id}/folders.json",
                recipes_dir=f"user_data/{current_user.id}/saved_recipes")
            user_folder_manager._update_recipe_counts()
            return jsonify({
                'success':
                True,
                'recipe':
                recipe.model_dump(),
                'message':
                f'Recipe saved successfully to {filepath}'
            })
        else:
            return jsonify({
                'error':
                'Website blocked scraping. Try a different recipe URL or enter the recipe manually.'
            }), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/save-manual-recipe', methods=['POST'])
@login_required
def save_manual_recipe():
    """Save a manually entered recipe for the current user."""
    data = request.get_json()
    folder_id = data.get('folder_id', 'uncategorized')

    try:
        recipe = Recipe(name=data['name'],
                        serving_size=data.get('serving_size'),
                        ingredients=data['ingredients'],
                        instructions=data['instructions'])
        # Ensure user directory exists
        user_dir = f"user_data/{current_user.id}/saved_recipes"
        os.makedirs(user_dir, exist_ok=True)
        filepath = save_recipe_to_file(
            recipe,
            directory=f"user_data/{current_user.id}/saved_recipes",
            folder_id=folder_id)
        # Update folder recipe count
        user_folder_manager = FolderManager(
            folders_file=f"user_data/{current_user.id}/folders.json",
            recipes_dir=f"user_data/{current_user.id}/saved_recipes")
        user_folder_manager._update_recipe_counts()
        return jsonify({
            'success': True,
            'recipe': recipe.model_dump(),
            'message': f'Recipe saved successfully to {filepath}'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/create-meal-plan', methods=['POST'])
@login_required
def create_meal_plan_api():
    """Create a meal plan and generate grocery list for the current user."""
    data = request.get_json()
    recipe_names = data.get('recipes', [])
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not recipe_names:
        return jsonify({'error': 'No recipes selected'}), 400

    if not start_date or not end_date:
        return jsonify({'error': 'Start date and end date are required'}), 400

    try:
        from datetime import datetime

        # Validate and parse dates
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')

        if start_dt > end_dt:
            return jsonify({'error': 'End date must be after start date'}), 400

        # Calculate number of days
        date_diff = (end_dt - start_dt).days + 1

        # Load recipes from all user folders
        all_recipes = {}
        user_folder_manager = FolderManager(
            folders_file=f"user_data/{current_user.id}/folders.json",
            recipes_dir=f"user_data/{current_user.id}/saved_recipes")
        folders = user_folder_manager.get_all_folders()

        for folder in folders:
            folder_path = os.path.join(
                f"user_data/{current_user.id}/saved_recipes", folder.id)
            if os.path.exists(folder_path):
                for filename in os.listdir(folder_path):
                    if filename.endswith('.json'):
                        filepath = os.path.join(folder_path, filename)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                recipe = Recipe.model_validate(data)
                                all_recipes[recipe.name] = recipe
                        except Exception as e:
                            print(f"Error loading recipe from {filename}: {e}")

        selected_recipes = []
        for recipe_name in recipe_names:
            if recipe_name in all_recipes:
                selected_recipes.append(all_recipes[recipe_name])
            else:
                return jsonify({'error':
                                f'Recipe "{recipe_name}" not found'}), 400

        # Parse ingredients and generate grocery list
        all_parsed_ingredients = []
        for recipe in selected_recipes:
            for ingredient_text in recipe.ingredients:
                parsed = parse_ingredient_line_with_gemini(ingredient_text)
                if parsed:
                    all_parsed_ingredients.append(parsed)

        grocery_list = consolidate_ingredients(all_parsed_ingredients)

        return jsonify({
            'success': True,
            'meal_plan': recipe_names,
            'grocery_list': grocery_list,
            'date_range': {
                'start': start_dt.strftime('%B %d, %Y'),
                'end': end_dt.strftime('%B %d, %Y'),
                'days': date_diff
            }
        })
    except ValueError as e:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete-recipe/<folder_id>/<recipe_name>', methods=['DELETE'])
@login_required
def delete_recipe(folder_id, recipe_name):
    """Delete a saved recipe from a specific folder for the current user."""
    try:
        folder_path = os.path.join(
            f"user_data/{current_user.id}/saved_recipes", folder_id)

        # Try consistent filename generation first
        filename = "".join(c if c.isalnum() else "_"
                           for c in recipe_name).lower()
        filepath = os.path.join(folder_path, f"{filename}.json")

        if os.path.exists(filepath):
            os.remove(filepath)
        else:
            # If not found, search by recipe name in all files in the folder
            found = False
            if os.path.exists(folder_path):
                for file in os.listdir(folder_path):
                    if file.endswith('.json'):
                        full_path = os.path.join(folder_path, file)
                        try:
                            with open(full_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                recipe = Recipe.model_validate(data)
                                if recipe.name == recipe_name:
                                    os.remove(full_path)
                                    found = True
                                    break
                        except:
                            continue

            if not found:
                return jsonify({'error': 'Recipe file not found'}), 404

        # Update folder recipe counts
        user_folder_manager = FolderManager(
            folders_file=f"user_data/{current_user.id}/folders.json",
            recipes_dir=f"user_data/{current_user.id}/saved_recipes")
        user_folder_manager._update_recipe_counts()
        return jsonify({
            'success':
            True,
            'message':
            f'Recipe "{recipe_name}" deleted successfully'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/move-recipe', methods=['POST'])
@login_required
def move_recipe():
    """Move a recipe from one folder to another for the current user."""
    data = request.get_json()
    recipe_name = data.get('recipe_name')
    current_folder = data.get('current_folder')
    target_folder = data.get('target_folder')

    if not recipe_name or not current_folder or not target_folder:
        return jsonify({'error': 'Missing required parameters'}), 400

    if current_folder == target_folder:
        return jsonify({'error':
                        'Recipe is already in the target folder'}), 400

    try:
        # Find the actual recipe file by searching for the recipe name in the folder
        source_folder_path = os.path.join(
            f"user_data/{current_user.id}/saved_recipes", current_folder)

        if not os.path.exists(source_folder_path):
            return jsonify({'error': 'Source folder not found'}), 404

        # Find the file that contains this recipe
        recipe_file = None
        for filename in os.listdir(source_folder_path):
            if filename.endswith('.json'):
                filepath = os.path.join(source_folder_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data.get('name') == recipe_name:
                            recipe_file = filename
                            break
                except Exception:
                    continue

        if not recipe_file:
            return jsonify({'error': 'Recipe not found in source folder'}), 404

        # Define paths using the found filename
        source_path = os.path.join(source_folder_path, recipe_file)
        target_dir = os.path.join(f"user_data/{current_user.id}/saved_recipes",
                                  target_folder)
        target_path = os.path.join(target_dir, recipe_file)

        # Create target directory if it doesn't exist
        os.makedirs(target_dir, exist_ok=True)

        # Move the file
        shutil.move(source_path, target_path)

        # Update folder recipe counts
        user_folder_manager = FolderManager(
            folders_file=f"user_data/{current_user.id}/folders.json",
            recipes_dir=f"user_data/{current_user.id}/saved_recipes")
        user_folder_manager._update_recipe_counts()

        return jsonify({
            'success':
            True,
            'message':
            f'Recipe "{recipe_name}" moved successfully from {current_folder} to {target_folder}'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/grocery-lists', methods=['GET'])
@login_required
def get_grocery_lists():
    """Get all saved grocery lists for the current user."""
    try:
        grocery_lists = GroceryList.query.filter_by(
            user_id=current_user.id).order_by(
                GroceryList.created_at.desc()).all()

        result = []
        for grocery_list in grocery_lists:
            result.append({
                'id': grocery_list.id,
                'grocery_list': grocery_list.grocery_list,
                'meal_plan': grocery_list.meal_plan,
                'date_range': grocery_list.date_range,
                'created_at': grocery_list.created_at.isoformat(),
                'updated_at': grocery_list.updated_at.isoformat()
            })

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/grocery-lists', methods=['POST'])
@login_required
def save_grocery_list():
    """Save a new grocery list for the current user."""
    try:
        data = request.json

        if not data or 'groceryList' not in data or 'mealPlan' not in data:
            return jsonify(
                {'error':
                 'Missing required data: groceryList and mealPlan'}), 400

        grocery_list = GroceryList(user_id=current_user.id,
                                   grocery_list=data['groceryList'],
                                   meal_plan=data['mealPlan'],
                                   date_range=data.get('dateRange'))

        db.session.add(grocery_list)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Grocery list saved successfully',
            'id': grocery_list.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/grocery-lists/<grocery_list_id>', methods=['GET'])
@login_required
def get_grocery_list(grocery_list_id):
    """Get a specific grocery list for the current user."""
    try:
        grocery_list = GroceryList.query.filter_by(
            id=grocery_list_id, user_id=current_user.id).first()

        if not grocery_list:
            return jsonify({'error': 'Grocery list not found'}), 404

        return jsonify({
            'id': grocery_list.id,
            'grocery_list': grocery_list.grocery_list,
            'meal_plan': grocery_list.meal_plan,
            'date_range': grocery_list.date_range,
            'created_at': grocery_list.created_at.isoformat(),
            'updated_at': grocery_list.updated_at.isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/grocery-lists/<grocery_list_id>', methods=['DELETE'])
@login_required
def delete_grocery_list(grocery_list_id):
    """Delete a specific grocery list for the current user."""
    try:
        grocery_list = GroceryList.query.filter_by(
            id=grocery_list_id, user_id=current_user.id).first()

        if not grocery_list:
            return jsonify({'error': 'Grocery list not found'}), 404

        db.session.delete(grocery_list)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Grocery list deleted successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/recipe-search', methods=['POST'])
@login_required
def recipe_search():
    """Smart recipe search - searches saved recipes or web based on user description."""
    try:
        data = request.get_json()
        search_term = data.get('description', '').strip() or data.get(
            'search_term', '').strip()
        search_type = data.get('search_type', 'saved')  # 'saved' or 'web'

        if not search_term:
            return jsonify({'error': 'Search term is required'}), 400

        recipes = []

        if search_type == 'saved':
            # Search through user's saved recipes
            search_results = search_local_recipes(search_term, current_user.id)
            recipes = [{
                'name': recipe.name,
                'ingredients': recipe.ingredients,
                'instructions': recipe.instructions,
                'serving_size': recipe.serving_size,
                'url': recipe.url,
                'match_score': recipe.match_score
            } for recipe in search_results]
        elif search_type == 'web':
            # Search web for new recipes (simplified version without AI)
            search_results = search_web_recipes_simple(search_term)
            recipes = [{
                'name': recipe.name,
                'ingredients': recipe.ingredients,
                'instructions': recipe.instructions,
                'serving_size': recipe.serving_size,
                'url': recipe.url
            } for recipe in search_results]

        return jsonify({
            'recipes': recipes,
            'search_term': search_term,
            'search_type': search_type
        })

    except Exception as e:
        logging.error(f"Error in recipe search: {e}")
        return jsonify({'error': 'Recipe search failed'}), 500


@app.route('/api/save-search-result', methods=['POST'])
@login_required
def save_search_result():
    """Save a recipe from search results to user's collection."""
    try:
        data = request.get_json()

        # Handle both formats: complete recipe object or recipe_name/recipe_url
        recipe_data = data.get('recipe')
        if recipe_data:
            # Use the complete recipe data directly (from search results)
            print(
                f"Saving complete recipe data: {recipe_data.get('name')} with {len(recipe_data.get('ingredients', []))} ingredients"
            )
        else:
            # Handle legacy format with recipe_name and recipe_url (URL-based extraction)
            recipe_name = data.get('recipe_name', '').strip()
            recipe_url = data.get('recipe_url', '').strip()

            if not recipe_name:
                return jsonify({'error': 'Recipe name is required'}), 400

            # Try to extract full recipe from URL using full extractor with Gemini AI fallback
            from recipe_extractor import extract_recipe_from_url

            try:
                # Attempt to extract full recipe content
                extracted_recipe = extract_recipe_from_url(recipe_url)
                if extracted_recipe and extracted_recipe.ingredients:
                    recipe_data = {
                        'name':
                        extracted_recipe.name,
                        'url':
                        recipe_url,
                        'ingredients':
                        extracted_recipe.ingredients,
                        'instructions':
                        extracted_recipe.instructions,
                        'serving_size':
                        extracted_recipe.serving_size or 'See original recipe'
                    }
                else:
                    raise Exception("Extraction failed")
            except Exception:
                # Fallback to basic content with URL reference
                recipe_data = {
                    'name':
                    recipe_name,
                    'url':
                    recipe_url,
                    'ingredients': [
                        "See original recipe for full ingredient list",
                        f"Visit: {recipe_url}"
                    ],
                    'instructions': [
                        "This recipe was saved from search results",
                        f"View full instructions at: {recipe_url}",
                        "Use the recipe URL above for complete details"
                    ],
                    'serving_size':
                    'See original recipe'
                }

        folder_id = data.get('folder_id', 'uncategorized')

        # Create Recipe object from the data and save it directly
        from recipe_extractor import Recipe, save_recipe_to_file
        recipe = Recipe(name=recipe_data.get('name', ''),
                        serving_size=recipe_data.get('serving_size'),
                        ingredients=recipe_data.get('ingredients', []),
                        instructions=recipe_data.get('instructions', []))

        # Ensure user directory exists
        user_dir = f"user_data/{current_user.id}/saved_recipes"
        os.makedirs(user_dir, exist_ok=True)

        # Save recipe directly using the recipe_extractor function
        save_recipe_to_file(recipe, directory=user_dir, folder_id=folder_id)

        # Update folder recipe counts
        user_folder_manager = FolderManager(
            folders_file=f"user_data/{current_user.id}/folders.json",
            recipes_dir=f"user_data/{current_user.id}/saved_recipes")
        user_folder_manager._update_recipe_counts()

        return jsonify({'message': 'Recipe saved successfully'})

    except Exception as e:
        logging.error(f"Error saving search result: {e}")
        return jsonify({'error': 'Failed to save recipe'}), 500


if __name__ == '__main__':
    # Ensure user_data directory exists
    os.makedirs('user_data', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
