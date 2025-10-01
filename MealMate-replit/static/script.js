// Global variables
let recipes = [];
let folders = [];
let selectedRecipes = [];
let startDate = null;
let endDate = null;
let groceryListState = {};
let currentFolder = null;
let currentGroceryListData = null; // Store current grocery list for saving

// Modal Functions for New Design
function showExtractModal() {
    loadFolderSelects();
    const modal = new bootstrap.Modal(document.getElementById('extractRecipeModal'));
    modal.show();
}

function showManualModal() {
    loadFolderSelects();
    const modal = new bootstrap.Modal(document.getElementById('manualRecipeModal'));
    modal.show();
}

function showSavedGroceryListsModal() {
    loadSavedGroceryLists();
    const modal = new bootstrap.Modal(document.getElementById('groceryListsModal'));
    modal.show();
}

function showMealPlanModal() {
    loadRecipeSelection();
    initializeDateInputs();
    
    // Add event listeners for date inputs
    const startInput = document.getElementById('startDate');
    const endInput = document.getElementById('endDate');
    
    startInput.addEventListener('change', updateDateRange);
    endInput.addEventListener('change', updateDateRange);
    
    const modal = new bootstrap.Modal(document.getElementById('mealPlanModal'));
    modal.show();
}

function showCreateFolderModal() {
    const modal = new bootstrap.Modal(document.getElementById('createFolderModal'));
    modal.show();
}

function showRenameFolderModal() {
    loadFolderSelects();
    // Clear the new folder name field
    document.getElementById('newFolderName').value = '';
    
    // Add event listener to populate current name when folder is selected
    const selectRenameFolder = document.getElementById('selectRenameFolder');
    selectRenameFolder.onchange = function() {
        const selectedFolderId = this.value;
        if (selectedFolderId) {
            const selectedFolder = folders.find(f => f.id === selectedFolderId);
            if (selectedFolder) {
                document.getElementById('newFolderName').value = selectedFolder.name;
            }
        } else {
            document.getElementById('newFolderName').value = '';
        }
    };
    
    const modal = new bootstrap.Modal(document.getElementById('renameFolderModal'));
    modal.show();
}

function showDeleteFolderModal() {
    loadFolderSelects();
    const modal = new bootstrap.Modal(document.getElementById('deleteFolderModal'));
    modal.show();
}

// Simple working search function
function searchRecipes() {
    const searchInput = document.getElementById('discoverSearchInput');
    const searchType = document.querySelector('input[name="searchType"]:checked');
    const query = searchInput.value.trim();
    
    if (!query) {
        alert('Please enter a search query');
        return;
    }
    
    if (searchType.value === 'saved') {
        // Search saved recipes
        if (recipes.length === 0) {
            displaySearchResults(`
                <div class="text-center py-3">
                    <i class="fas fa-search fa-2x text-muted mb-2"></i>
                    <p class="text-muted">No saved recipes found for "${query}"</p>
                    <p class="text-muted small">Try switching to "Discover New Recipes" to find recipes online</p>
                </div>
            `);
        } else {
            // Enhanced fuzzy search with similarity scoring
            const searchWords = query.toLowerCase().split(/\s+/).filter(word => word.length > 0);
            
            const recipesWithScores = recipes.map(recipe => {
                if (!recipe.name) return null;
                
                const recipeName = recipe.name.toLowerCase();
                let score = 0;
                
                // Exact phrase match (80-100% similarity)
                if (recipeName.includes(query.toLowerCase())) {
                    const matchLength = query.length;
                    const nameLength = recipe.name.length;
                    score = Math.min(100, Math.round((matchLength / nameLength) * 100) + 30);
                }
                // Multi-word matching
                else if (searchWords.length > 1) {
                    const wordsFound = searchWords.filter(word => recipeName.includes(word)).length;
                    const wordMatchRatio = wordsFound / searchWords.length;
                    score = Math.round(wordMatchRatio * 70); // 0-70% based on word coverage
                }
                // Partial word matching
                else {
                    const searchWord = searchWords[0];
                    let bestMatch = 0;
                    
                    recipeName.split(/\s+/).forEach(recipeWord => {
                        if (recipeWord.includes(searchWord)) {
                            const matchRatio = searchWord.length / recipeWord.length;
                            bestMatch = Math.max(bestMatch, matchRatio);
                        } else if (searchWord.includes(recipeWord)) {
                            const matchRatio = recipeWord.length / searchWord.length;
                            bestMatch = Math.max(bestMatch, matchRatio * 0.8); // Slightly lower for reverse match
                        }
                    });
                    
                    score = Math.round(bestMatch * 60); // 0-60% for partial matches
                }
                
                return score > 0 ? { ...recipe, similarityScore: score } : null;
            }).filter(recipe => recipe !== null)
            .sort((a, b) => b.similarityScore - a.similarityScore); // Sort by highest similarity first
            
            const filtered = recipesWithScores;
            
            if (filtered.length > 0) {
                displaySearchResults(`
                    <h6 class="fw-semibold mb-3">Found ${filtered.length} saved recipe(s)</h6>
                    <div class="d-grid gap-2">
                        ${filtered.map(recipe => `
                            <div class="card mb-2 recipe-card" onclick="showRecipeDetails('${recipe.folder_id}', '${recipe.name}')">
                                <div class="card-body">
                                    <div class="d-flex justify-content-between align-items-start mb-1">
                                        <h6 class="card-title mb-0">${recipe.name}</h6>
                                        <span class="badge bg-primary ms-2">${recipe.similarityScore}% match</span>
                                    </div>
                                    <div class="recipe-meta">
                                        ${recipe.serving_size ? `<span class="me-3"><i class="fas fa-users me-1"></i>${recipe.serving_size}</span>` : ''}
                                        <span class="me-3"><i class="fas fa-list me-1"></i>${recipe.ingredients_count} ingredients</span>
                                        <span><i class="fas fa-tasks me-1"></i>${recipe.instructions_count} steps</span>
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                `);
            } else {
                displaySearchResults(`
                    <div class="text-center py-3">
                        <i class="fas fa-search fa-2x text-muted mb-2"></i>
                        <p class="text-muted">No saved recipes found for "${query}"</p>
                    </div>
                `);
            }
        }
    } else {
        // Search web recipes
        searchWebRecipes(query);
    }
}

function displaySearchResults(html) {
    const searchResults = document.getElementById('searchResults');
    const searchResultsContent = document.getElementById('searchResultsContent');
    
    if (searchResults && searchResultsContent) {
        searchResultsContent.innerHTML = html;
        searchResults.style.display = 'block';
    }
}

async function searchWebRecipes(query) {
    displaySearchResults(`
        <div class="text-center py-3">
            <div class="loading-spinner me-2"></div>
            Searching the web for recipes...
        </div>
    `);
    
    try {
        const response = await fetch('/api/recipe-search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                description: query,
                search_type: 'web'
            })
        });
        
        const data = await response.json();
        
        // Store recipes globally for access
        window.searchResults = data.recipes || [];
        
        if (data.recipes && data.recipes.length > 0) {
            displaySearchResults(`
                <h6 class="fw-semibold mb-3">Found ${data.recipes.length} web recipe(s)</h6>
                <div class="d-grid gap-2">
                    ${data.recipes.map((recipe, index) => `
                        <div class="mm-tile" onclick="showWebRecipeDetails(${index})">
                            <div class="mm-icon">🌐</div>
                            <div>
                                <div class="fw-medium">${recipe.name}</div>
                                <div class="text-muted small">${recipe.serving_size || 'Click to view details'}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `);
        } else {
            displaySearchResults(`
                <div class="text-center py-3">
                    <i class="fas fa-search fa-2x text-muted mb-2"></i>
                    <p class="text-muted">No recipes found for "${query}"</p>
                </div>
            `);
        }
    } catch (error) {
        console.error('Search error:', error);
        displaySearchResults(`
            <div class="text-center py-3">
                <i class="fas fa-exclamation-triangle fa-2x text-warning mb-2"></i>
                <p class="text-muted">Error searching for recipes. Please try again.</p>
            </div>
        `);
    }
}

function openExtractModal(url) {
    if (url) {
        document.getElementById('recipeUrl').value = url;
    }
    showExtractModal();
}

function showWebRecipeDetails(recipeIndex) {
    const recipe = window.searchResults[recipeIndex];
    if (!recipe) {
        showAlert('Recipe not found', 'danger');
        return;
    }
    
    // Create recipe details modal
    const ingredientsList = recipe.ingredients.map(ingredient => 
        `<li class="list-group-item">${ingredient}</li>`
    ).join('');
    
    const instructionsList = recipe.instructions.map((instruction, index) => 
        `<li class="list-group-item"><strong>Step ${index + 1}:</strong> ${instruction}</li>`
    ).join('');
    
    const modalContent = `
        <div class="modal fade" id="webRecipeModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${recipe.name}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        ${recipe.serving_size ? `<p class="text-muted mb-3"><i class="fas fa-users me-2"></i>Serves: ${recipe.serving_size}</p>` : ''}
                        
                        <h6 class="text-success mb-3">
                            <i class="fas fa-list-ul me-2"></i>Ingredients (${recipe.ingredients.length})
                        </h6>
                        <ul class="list-group list-group-flush mb-4">
                            ${ingredientsList}
                        </ul>
                        
                        <h6 class="text-primary mb-3">
                            <i class="fas fa-clipboard-list me-2"></i>Instructions (${recipe.instructions.length} steps)
                        </h6>
                        <ol class="list-group list-group-numbered mb-4">
                            ${instructionsList}
                        </ol>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-success" onclick="saveWebRecipeFromSearch(${recipeIndex})">
                            <i class="fas fa-save me-1"></i>Save Recipe
                        </button>
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('webRecipeModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body and show
    document.body.insertAdjacentHTML('beforeend', modalContent);
    const modal = new bootstrap.Modal(document.getElementById('webRecipeModal'));
    modal.show();
}

function saveWebRecipeFromSearch(recipeIndex) {
    const recipe = window.searchResults[recipeIndex];
    if (!recipe) {
        showAlert('Recipe not found', 'danger');
        return;
    }
    
    // Close the recipe details modal first
    const modal = bootstrap.Modal.getInstance(document.getElementById('webRecipeModal'));
    if (modal) {
        modal.hide();
    }
    
    // Show folder selection modal
    showSaveToFolderModalWithRecipe(recipe);
}

// Global variable to store the current recipe being saved
let currentRecipeToSave = null;

function showSaveToFolderModalWithRecipe(recipe) {
    // Store the recipe globally so we can access it from the modal
    currentRecipeToSave = recipe;
    
    const folderOptions = folders.map(folder => 
        `<option value="${folder.id}">${folder.name}</option>`
    ).join('');
    
    const modalContent = `
        <div class="modal fade" id="saveRecipeModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Save Recipe: ${recipe.name}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <label for="saveToFolder" class="form-label">Choose folder:</label>
                            <select class="form-select" id="saveToFolder">
                                ${folderOptions}
                            </select>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-success" onclick="confirmSaveRecipeFromModal()">
                            <i class="fas fa-save me-1"></i>Save Recipe
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('saveRecipeModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body and show
    document.body.insertAdjacentHTML('beforeend', modalContent);
    const modal = new bootstrap.Modal(document.getElementById('saveRecipeModal'));
    modal.show();
}

function confirmSaveRecipeFromModal() {
    if (currentRecipeToSave) {
        confirmSaveRecipe(currentRecipeToSave);
    } else {
        showAlert('No recipe selected to save', 'danger');
    }
}

async function confirmSaveRecipe(recipe) {
    const folderId = document.getElementById('saveToFolder').value;
    
    try {
        const response = await fetch('/api/save-search-result', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                recipe: recipe,
                folder_id: folderId
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert('Recipe saved successfully!', 'success');
            
            // Close the save modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('saveRecipeModal'));
            if (modal) {
                modal.hide();
            }
            
            // Refresh the data
            await loadFolders();
            await loadRecipes();
            await loadAllRecipesList();
        } else {
            throw new Error(result.error || 'Failed to save recipe');
        }
    } catch (error) {
        console.error('Error saving recipe:', error);
        showAlert('Error saving recipe: ' + error.message, 'danger');
    }
}

// Missing helper functions
function loadRecipeSelection() {
    const recipeSelection = document.getElementById('recipeSelection');
    if (!recipes || recipes.length === 0) {
        recipeSelection.innerHTML = '<p class="text-muted">No recipes available. Add some recipes first!</p>';
        return;
    }
    
    const recipesHtml = recipes.map(recipe => `
        <div class="form-check">
            <input class="form-check-input" type="checkbox" value="${recipe.name}" id="recipe_${recipe.name}">
            <label class="form-check-label" for="recipe_${recipe.name}">
                ${recipe.name}
            </label>
        </div>
    `).join('');
    
    recipeSelection.innerHTML = recipesHtml;
}

function setDefaultDates() {
    const today = new Date();
    const nextWeek = new Date(today);
    nextWeek.setDate(today.getDate() + 7);
    
    document.getElementById('startDate').value = today.toISOString().split('T')[0];
    document.getElementById('endDate').value = nextWeek.toISOString().split('T')[0];
}

function initializeDateInputs() {
    setDefaultDates();
}


async function createMealPlan() {
    const name = document.getElementById('mealPlanName').value.trim();
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;
    
    const selectedRecipeInputs = document.querySelectorAll('#recipeSelection input:checked');
    const selectedRecipeNames = Array.from(selectedRecipeInputs).map(input => input.value);
    
    if (!name || !startDate || !endDate || selectedRecipeNames.length === 0) {
        showAlert('Please fill in all fields and select at least one recipe', 'warning');
        return;
    }
    
    try {
        showLoading('Creating meal plan...', 'Generating grocery list from your recipes...');
        const response = await fetch('/api/create-meal-plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                name: name,
                start_date: startDate,
                end_date: endDate,
                recipes: selectedRecipeNames
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            cleanupAllModals();
            
            // Display the grocery list immediately
            if (result.grocery_list) {
                // First save the grocery list
                try {
                    const saveResponse = await fetch('/api/grocery-lists', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify({
                            name: `${result.meal_plan.join(', ')} (${result.date_range.start})`,
                            groceryList: result.grocery_list,
                            mealPlan: result.meal_plan,
                            dateRange: result.date_range
                        })
                    });
                    
                    if (saveResponse.ok) {
                        showAlert('Meal plan created and saved successfully! Click "View Lists" to see it.', 'success');
                        
                        // Simple confirmation with the grocery list
                        const groceryText = result.grocery_list.join('\n• ');
                        const confirmText = `✅ MEAL PLAN CREATED!\n\n📅 ${result.meal_plan.join(', ')}\n📍 ${result.date_range.start} to ${result.date_range.end}\n\n🛒 GROCERY LIST (${result.grocery_list.length} items):\n• ${groceryText}\n\n✨ Your meal plan has been saved! Click "View Lists" to access it anytime.`;
                        
                        // Show in a proper alert that can't fail
                        if (confirm(confirmText + '\n\nClick OK to continue, or Cancel to copy this list to clipboard.')) {
                            // User clicked OK - just continue
                        } else {
                            // User clicked Cancel - copy to clipboard
                            try {
                                navigator.clipboard.writeText(confirmText);
                                showAlert('Grocery list copied to clipboard!', 'info');
                            } catch (e) {
                                // Fallback if clipboard doesn't work
                                prompt('Copy this grocery list:', confirmText);
                            }
                        }
                    } else {
                        showAlert('Meal plan created but failed to save. Try again.', 'warning');
                    }
                } catch (error) {
                    showAlert('Error saving meal plan: ' + error.message, 'danger');
                }
            }
            
            await loadFolders();
            await loadRecipes();
        } else {
            cleanupAllModals();
            throw new Error(result.error || 'Failed to create meal plan');
        }
    } catch (error) {
        cleanupAllModals();
        showAlert('Error creating meal plan: ' + error.message, 'danger');
    }
}

async function loadSavedGroceryLists() {
    try {
        const response = await fetch('/api/grocery-lists');
        const lists = await response.json();
        
        const content = document.getElementById('groceryListsContent');
        if (!lists || lists.length === 0) {
            content.innerHTML = '<p class="text-muted">No saved grocery lists yet.</p>';
            return;
        }
        
        const listsHtml = lists.map(list => `
            <div class="card mb-3">
                <div class="card-body">
                    <h6 class="card-title">${list.name}</h6>
                    <p class="text-muted small">Created: ${new Date(list.created_at).toLocaleDateString()}</p>
                    <button class="btn btn-outline-primary btn-sm" onclick="viewGroceryList('${list.id}')">
                        View List
                    </button>
                    <button class="btn btn-outline-danger btn-sm" onclick="deleteGroceryList('${list.id}')">
                        Delete
                    </button>
                </div>
            </div>
        `).join('');
        
        content.innerHTML = listsHtml;
    } catch (error) {
        console.error('Error loading grocery lists:', error);
        document.getElementById('groceryListsContent').innerHTML = '<p class="text-danger">Error loading grocery lists</p>';
    }
}

// Global modal cleanup function
function cleanupAllModals() {
    // Remove all modal backdrops
    const backdrops = document.querySelectorAll('.modal-backdrop');
    backdrops.forEach(backdrop => backdrop.remove());
    
    // Reset body state
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    document.body.style.paddingRight = '';
    
    // Hide all modals
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        const modalInstance = bootstrap.Modal.getInstance(modal);
        if (modalInstance) {
            modalInstance.dispose();
        }
        modal.style.display = 'none';
        modal.classList.remove('show');
        modal.setAttribute('aria-hidden', 'true');
        modal.removeAttribute('aria-modal');
        modal.removeAttribute('role');
    });
}


// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
    
    // Only load data if user is authenticated
    if (window.isAuthenticated) {
        loadFolders();
        loadRecipes();
        loadAllRecipesList();
    }
    initializeDateInputs();
    
    // Add periodic refresh to ensure folders stay loaded
    setInterval(() => {
        if (document.querySelector('#folderGrid')) {
            loadFolders();
        }
    }, 30000); // Refresh every 30 seconds
});

// Check if user is authenticated by looking for auth-specific elements
function isUserAuthenticated() {
    // Check for authenticated content indicators
    return document.querySelector('[data-authenticated]') !== null || 
           document.querySelector('.mm-safe') !== null || 
           window.location.pathname !== '/auth/login';
}

function setupEventListeners() {
    // Add smooth scrolling and enhanced interactions
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('hover-lift')) {
            e.target.style.transform = 'translateY(-4px)';
            setTimeout(() => {
                e.target.style.transform = '';
            }, 200);
        }
    });

    // Tab change events
    document.querySelectorAll('button[data-bs-toggle="tab"]').forEach(tab => {
        tab.addEventListener('shown.bs.tab', function(e) {
            if (e.target.id === 'planner-tab') {
                loadRecipeSelection();
            } else if (e.target.id === 'extract-tab') {
                loadFolderSelects();
            }
        });
    });
}

// Date handling functions
function initializeDateInputs() {
    // Check if date input elements exist before trying to access them
    const startDateEl = document.getElementById('startDate');
    const endDateEl = document.getElementById('endDate');
    
    if (!startDateEl || !endDateEl) {
        return; // Exit if elements don't exist (user not authenticated)
    }
    
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const weekFromNow = new Date(today);
    weekFromNow.setDate(weekFromNow.getDate() + 7);
    
    startDateEl.value = tomorrow.toISOString().split('T')[0];
    endDateEl.value = weekFromNow.toISOString().split('T')[0];
    
    updateDateRange();
}

function updateDateRange() {
    const startInput = document.getElementById('startDate');
    const endInput = document.getElementById('endDate');
    
    if (!startInput || !endInput) return;
    
    startDate = startInput.value;
    endDate = endInput.value;
    
    // Optional: Update info element if it exists
    const infoElement = document.getElementById('dateRangeInfo');
    if (infoElement && startDate && endDate) {
        const start = new Date(startDate);
        const end = new Date(endDate);
        const diffTime = Math.abs(end - start);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
        
        if (start > end) {
            infoElement.innerHTML = '<span class="text-danger"><i class="fas fa-exclamation-triangle me-1"></i>End date must be after start date</span>';
            return;
        }
        
        infoElement.innerHTML = `<span class="text-info"><i class="fas fa-calendar-check me-1"></i>Planning meals for ${diffDays} days (${start.toLocaleDateString()} - ${end.toLocaleDateString()})</span>`;
        infoElement.className = 'mt-2 date-range-info';
    }
    
    updateSelectedRecipes();
}

// Folder management functions
async function loadFolders() {
    try {
        const response = await fetch('/api/folders', {
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            if (response.status === 302 || response.status === 401) {
                // User not authenticated, silently return
                return;
            }
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Always ensure folders array is valid
        folders = Array.isArray(data) ? data : [];
        displayFolders(folders);
        
        // Also update folder selects
        loadFolderSelects();
        
    } catch (error) {
        console.log('Error loading folders:', error.message);
        // Ensure folders is at least an empty array on error
        folders = [];
        displayFolders([]);
    }
}

function displayFolders(folderList) {
    const folderGrid = document.getElementById('folderGrid');
    if (!folderGrid) return;
    
    if (folderList.length === 0) {
        folderGrid.innerHTML = `
            <div class="col-12 text-center py-4">
                <i class="fas fa-folder-open fa-3x text-secondary mb-3"></i>
                <h6 class="text-secondary mb-2">No folders yet</h6>
                <p class="text-muted small mb-3">Create your first folder to organize your recipes!</p>
                <button class="btn btn-sm mm-btn mm-btn-primary" onclick="showCreateFolderModal()">
                    <i class="fas fa-plus me-1"></i>Create First Folder
                </button>
            </div>
        `;
        return;
    }
    
    folderGrid.innerHTML = folderList.map(folder => `
        <div class="col-6 col-md-4">
            <div class="card mm-card h-100 folder-card" onclick="showFolderRecipes('${folder.id}', '${folder.name}')" style="cursor: pointer;">
                <div class="card-body text-center p-3">
                    <i class="fas fa-folder fa-2x text-primary mb-2"></i>
                    <h6 class="card-title mb-1">${folder.name}</h6>
                    <p class="text-muted small mb-0">${folder.recipe_count} recipe${folder.recipe_count !== 1 ? 's' : ''}</p>
                </div>
            </div>
        </div>
    `).join('');
}

async function showFolderRecipes(folderId, folderName) {
    try {
        currentFolder = { id: folderId, name: folderName };
        
        showLoading('Loading recipes...', 'Fetching recipes from ' + folderName);
        const response = await fetch(`/api/folders/${folderId}/recipes`, {
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const recipes = await response.json();
        console.log('Fetched recipes:', recipes);
        
        // Complete modal cleanup
        cleanupAllModals();
        
        // Small delay then show folder modal
        setTimeout(() => {
            displayFolderModal(folderName, recipes);
        }, 300);
        
    } catch (error) {
        console.error('Error in showFolderRecipes:', error);
        cleanupAllModals();
        showAlert('Error loading folder recipes: ' + error.message, 'danger');
    }
}

function displayFolderModal(folderName, recipes) {
    console.log('displayFolderModal called with:', folderName, recipes);
    
    const modalTitle = document.getElementById('folderModalTitle');
    const modalBody = document.getElementById('folderModalBody');
    const folderModal = document.getElementById('folderModal');
    
    if (!modalTitle || !modalBody || !folderModal) {
        console.error('Modal elements not found:', { modalTitle, modalBody, folderModal });
        showAlert('Error: Modal elements not found', 'danger');
        return;
    }
    
    modalTitle.textContent = folderName;
    
    if (recipes.length === 0) {
        modalBody.innerHTML = `
            <div class="text-center p-4">
                <i class="fas fa-utensils" style="font-size: 3rem; color: #6c757d;"></i>
                <h5 class="mt-3">No Recipes in This Folder</h5>
                <p class="text-muted">Add recipes to this folder using the "Add Recipe" tab.</p>
            </div>
        `;
    } else {
        const recipeList = recipes.map(recipe => `
            <div class="card mb-2 recipe-card" onclick="showRecipeDetails('${recipe.folder_id}', '${recipe.name}')">
                <div class="card-body">
                    <h6 class="card-title mb-1">${recipe.name}</h6>
                    <div class="recipe-meta">
                        ${recipe.serving_size ? `<span class="me-3"><i class="fas fa-users me-1"></i>${recipe.serving_size}</span>` : ''}
                        <span class="me-3"><i class="fas fa-list me-1"></i>${recipe.ingredients_count} ingredients</span>
                        <span><i class="fas fa-tasks me-1"></i>${recipe.instructions_count} steps</span>
                    </div>
                </div>
            </div>
        `).join('');
        
        modalBody.innerHTML = recipeList;
    }
    
    // Set up folder action buttons
    const renameBtn = document.getElementById('renameFolderBtn');
    const deleteBtn = document.getElementById('deleteFolderBtn');
    
    if (renameBtn) renameBtn.onclick = () => renameCurrentFolder();
    if (deleteBtn) deleteBtn.onclick = () => deleteCurrentFolder();
    
    console.log('About to show modal...');
    try {
        const modal = new bootstrap.Modal(folderModal);
        modal.show();
        console.log('Modal show() called successfully');
    } catch (error) {
        console.error('Error showing modal:', error);
        showAlert('Error displaying folder modal', 'danger');
    }
}

// Current folder action functions
async function renameCurrentFolder() {
    if (!currentFolder) {
        showAlert('No folder selected', 'danger');
        return;
    }
    
    // Cannot rename uncategorized folder
    if (currentFolder.id === 'uncategorized') {
        showAlert('Cannot rename the Uncategorized folder', 'warning');
        return;
    }
    
    const newName = prompt(`Enter new name for "${currentFolder.name}":`, currentFolder.name);
    if (!newName || newName.trim() === '') {
        return; // User cancelled or entered empty name
    }
    
    const trimmedName = newName.trim();
    if (trimmedName === currentFolder.name) {
        return; // No change
    }
    
    try {
        showLoading('Renaming folder...', 'Please wait while we update the folder name.');
        const response = await fetch(`/api/folders/${currentFolder.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ name: trimmedName })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            // Update current folder name
            currentFolder.name = trimmedName;
            
            // Update the modal title
            const modalTitle = document.getElementById('folderModalTitle');
            if (modalTitle) {
                modalTitle.textContent = trimmedName;
            }
            
            cleanupAllModals();
            showAlert('Folder renamed successfully!', 'success');
            await loadFolders();
            loadFolderSelects();
        } else {
            cleanupAllModals();
            throw new Error(result.error || 'Failed to rename folder');
        }
    } catch (error) {
        cleanupAllModals();
        showAlert('Error renaming folder: ' + error.message, 'danger');
    }
}

async function deleteCurrentFolder() {
    if (!currentFolder) {
        showAlert('No folder selected', 'danger');
        return;
    }
    
    // Cannot delete uncategorized folder
    if (currentFolder.id === 'uncategorized') {
        showAlert('Cannot delete the Uncategorized folder', 'warning');
        return;
    }
    
    const confirmMessage = `Are you sure you want to delete the folder "${currentFolder.name}"? All recipes will be moved to "Uncategorized".`;
    if (!confirm(confirmMessage)) {
        return;
    }
    
    try {
        showLoading('Deleting folder...', 'Moving recipes to Uncategorized folder...');
        const response = await fetch(`/api/folders/${currentFolder.id}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            cleanupAllModals();
            showAlert('Folder deleted successfully!', 'success');
            await loadFolders();
            loadFolderSelects();
        } else {
            cleanupAllModals();
            throw new Error(result.error || 'Failed to delete folder');
        }
    } catch (error) {
        cleanupAllModals();
        showAlert('Error deleting folder: ' + error.message, 'danger');
    }
}

// Recipe loading and display functions
async function loadRecipes() {
    try {
        const response = await fetch('/api/recipes', {
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            if (response.status === 302) {
                // User not authenticated, silently return
                return;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        recipes = data;
        displayRecipes(data);
    } catch (error) {
        console.log('Error loading recipes:', error.message);
    }
}

function displayRecipes(recipeList) {
    const recipeGrid = document.getElementById('recipeGrid');
    if (!recipeGrid) return;
    
    if (recipeList.length === 0) {
        recipeGrid.innerHTML = `
            <div class="text-center py-5">
                <i class="fas fa-utensils fa-4x text-secondary mb-3"></i>
                <h4 class="text-secondary">No recipes yet</h4>
                <p class="text-muted">Add your first recipe to get started!</p>
            </div>
        `;
        return;
    }
    
    recipeGrid.innerHTML = recipeList.map(recipe => `
        <div class="recipe-card slide-up" onclick="showRecipeDetails('${recipe.folder_id}', '${recipe.name}')">
            <div class="recipe-card-header">
                <h5 class="recipe-card-title">${recipe.name}</h5>
            </div>
            <div class="recipe-card-body">
                <p class="text-secondary mb-2">
                    <i class="fas fa-folder me-1"></i>${recipe.folder_name || 'Uncategorized'}
                </p>
                <p class="text-secondary mb-2">
                    <i class="fas fa-users me-1"></i>${recipe.serving_size || 'No serving info'}
                </p>
                <div class="recipe-card-actions">
                    <button class="btn btn-outline-primary btn-sm" onclick="event.stopPropagation(); showRecipeDetails('${recipe.folder_id}', '${recipe.name}')">
                        <i class="fas fa-eye me-1"></i>View
                    </button>
                    <button class="btn btn-outline-danger btn-sm" onclick="event.stopPropagation(); deleteRecipe('${recipe.name}', '${recipe.folder_id}')">
                        <i class="fas fa-trash me-1"></i>Delete
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

async function showRecipeDetails(folderId, recipeName) {
    try {
        showLoading('Loading recipe details...', 'Fetching recipe information.');
        const response = await fetch(`/api/recipe/${encodeURIComponent(folderId)}/${encodeURIComponent(recipeName)}`, {
            credentials: 'same-origin'
        });
        const recipe = await response.json();
        
        if (response.ok) {
            cleanupAllModals();
            setTimeout(() => {
                displayRecipeModal(recipe, folderId);
            }, 100);
        } else {
            cleanupAllModals();
            throw new Error(recipe.error || 'Recipe not found');
        }
    } catch (error) {
        cleanupAllModals();
        showAlert('Error loading recipe details: ' + error.message, 'danger');
    }
}

function displayRecipeModal(recipe, folderId) {
    document.getElementById('recipeModalTitle').textContent = recipe.name;
    
    const ingredientsList = recipe.ingredients.map(ingredient => `<li>${ingredient}</li>`).join('');
    const instructionsList = recipe.instructions.map((instruction, index) => 
        `<li><strong>Step ${index + 1}:</strong> ${instruction}</li>`).join('');
    
    document.getElementById('recipeModalBody').innerHTML = `
        ${recipe.serving_size ? `<p><strong>Serving Size:</strong> ${recipe.serving_size}</p>` : ''}
        
        <h6><i class="fas fa-list me-2"></i>Ingredients (${recipe.ingredients.length})</h6>
        <ul class="mb-4">${ingredientsList}</ul>
        
        <h6><i class="fas fa-tasks me-2"></i>Instructions (${recipe.instructions.length})</h6>
        <ol>${instructionsList}</ol>
    `;
    
    // Set up move button
    document.getElementById('moveRecipeBtn').onclick = () => showMoveRecipeModal(recipe.name, folderId);
    
    // Set up delete button
    document.getElementById('deleteRecipeBtn').onclick = () => deleteRecipe(recipe.name, folderId);
    
    new bootstrap.Modal(document.getElementById('recipeModal')).show();
}

// Global variables to store current recipe move context
let currentMoveRecipe = null;
let currentMoveFolder = null;

function showMoveRecipeModal(recipeName, currentFolderId) {
    currentMoveRecipe = recipeName;
    currentMoveFolder = currentFolderId;
    
    // Set recipe name in modal
    document.getElementById('moveRecipeName').textContent = recipeName;
    
    // Populate folder dropdown (exclude current folder)
    const moveTargetFolder = document.getElementById('moveTargetFolder');
    const defaultOption = '<option value="">Choose folder...</option>';
    const options = folders
        .filter(folder => folder.id !== currentFolderId) // Exclude current folder
        .map(folder => `<option value="${folder.id}">${folder.name}</option>`)
        .join('');
    
    moveTargetFolder.innerHTML = defaultOption + options;
    
    // Close recipe modal and show move modal
    const recipeModal = bootstrap.Modal.getInstance(document.getElementById('recipeModal'));
    if (recipeModal) {
        recipeModal.hide();
    }
    
    new bootstrap.Modal(document.getElementById('moveRecipeModal')).show();
}

async function confirmMoveRecipe() {
    const targetFolder = document.getElementById('moveTargetFolder').value;
    
    if (!targetFolder) {
        showAlert('Please select a target folder', 'warning');
        return;
    }
    
    if (!currentMoveRecipe || !currentMoveFolder) {
        showAlert('Recipe information missing', 'danger');
        return;
    }
    
    try {
        showLoading('Moving recipe...', 'Please wait while we move your recipe');
        
        const response = await fetch('/api/move-recipe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                recipe_name: currentMoveRecipe,
                current_folder: currentMoveFolder,
                target_folder: targetFolder
            })
        });
        
        const result = await response.json();
        hideLoading();
        
        if (response.ok) {
            cleanupAllModals();
            showAlert(result.message, 'success');
            loadFolders(); // Refresh folder counts
            loadRecipes(); // Refresh recipe list
            
            // Reset move context
            currentMoveRecipe = null;
            currentMoveFolder = null;
        } else {
            throw new Error(result.error || 'Failed to move recipe');
        }
    } catch (error) {
        hideLoading();
        showAlert('Error moving recipe: ' + error.message, 'danger');
    }
}

async function deleteRecipe(recipeName, folderId) {
    if (!confirm(`Are you sure you want to delete "${recipeName}"?`)) {
        return;
    }
    
    try {
        showLoading('Deleting recipe...', 'Please wait while we remove the recipe.');
        const response = await fetch(`/api/delete-recipe/${encodeURIComponent(folderId)}/${encodeURIComponent(recipeName)}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const result = await response.json();
        
        if (response.ok) {
            cleanupAllModals();
            showAlert(result.message, 'success');
            loadRecipes();
            loadFolders(); // Also reload folders to update recipe counts
        } else {
            cleanupAllModals();
            throw new Error(result.error || 'Failed to delete recipe');
        }
    } catch (error) {
        cleanupAllModals();
        showAlert('Error deleting recipe: ' + error.message, 'danger');
    }
}

// Folder management actions
function showCreateFolderModal() {
    document.getElementById('folderName').value = '';
    new bootstrap.Modal(document.getElementById('createFolderModal')).show();
}

async function createFolder() {
    const name = document.getElementById('folderName').value.trim();
    
    if (!name) {
        showAlert('Please enter a folder name', 'warning');
        return;
    }
    
    try {
        showLoading('Creating folder...', 'Please wait while we create your new folder.');
        const response = await fetch('/api/folders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ name: name })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            // Safely hide the modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('createFolderModal'));
            if (modal) {
                modal.hide();
            }
            cleanupAllModals();
            
            // Clear the input field
            document.getElementById('folderName').value = '';
            
            showAlert('Folder created successfully!', 'success');
            await loadFolders();
            await loadAllRecipesList();
            loadFolderSelects();
        } else {
            cleanupAllModals();
            throw new Error(result.error || 'Failed to create folder');
        }
    } catch (error) {
        cleanupAllModals();
        showAlert('Error creating folder: ' + error.message, 'danger');
    }
}



async function renameFolder() {
    const folderId = document.getElementById('selectRenameFolder').value;
    const newName = document.getElementById('newFolderName').value.trim();
    
    if (!folderId) {
        showAlert('Please select a folder to rename', 'warning');
        return;
    }
    
    if (!newName) {
        showAlert('Please enter a new folder name', 'warning');
        return;
    }
    
    try {
        showLoading('Renaming folder...', 'Please wait while we update the folder name.');
        const response = await fetch(`/api/folders/${folderId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ name: newName })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            cleanupAllModals();
            showAlert('Folder renamed successfully!', 'success');
            loadFolders();
            loadFolderSelects();
        } else {
            cleanupAllModals();
            throw new Error(result.error || 'Failed to rename folder');
        }
    } catch (error) {
        cleanupAllModals();
        showAlert('Error renaming folder: ' + error.message, 'danger');
    }
}

function deleteFolderConfirm() {
    showDeleteFolderModal();
}

async function confirmDeleteFolder() {
    const folderId = document.getElementById('selectDeleteFolder').value;
    
    if (!folderId) {
        showAlert('Please select a folder to delete', 'warning');
        return;
    }
    
    const folderName = folders.find(f => f.id === folderId)?.name || 'Unknown';
    
    if (!confirm(`Are you sure you want to delete the folder "${folderName}"? All recipes will be moved to "Uncategorized".`)) {
        return;
    }
    
    try {
        showLoading('Deleting folder...', 'Moving recipes to Uncategorized folder...');
        const response = await fetch(`/api/folders/${folderId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            cleanupAllModals();
            showAlert('Folder deleted successfully!', 'success');
            loadFolders();
            loadFolderSelects();
        } else {
            cleanupAllModals();
            throw new Error(result.error || 'Failed to delete folder');
        }
    } catch (error) {
        cleanupAllModals();
        showAlert('Error deleting folder: ' + error.message, 'danger');
    }
}

function loadFolderSelects() {
    const extractFolder = document.getElementById('extractFolder');
    const manualFolder = document.getElementById('manualFolder');
    const selectRenameFolder = document.getElementById('selectRenameFolder');
    const selectDeleteFolder = document.getElementById('selectDeleteFolder');
    
    const options = folders.map(folder => 
        `<option value="${folder.id}">${folder.name}</option>`
    ).join('');
    
    // Filter out uncategorized for delete and rename operations
    const deletableOptions = folders
        .filter(folder => folder.id !== 'uncategorized')
        .map(folder => `<option value="${folder.id}">${folder.name}</option>`)
        .join('');
    
    if (extractFolder) {
        const defaultOption = '<option value="">Select a folder...</option>';
        extractFolder.innerHTML = defaultOption + options;
    }
    if (manualFolder) {
        // Set uncategorized as default for manual recipes
        manualFolder.innerHTML = options;
        manualFolder.value = 'uncategorized'; // Set default to uncategorized
    }
    if (selectRenameFolder) {
        selectRenameFolder.innerHTML = '<option value="">Choose folder to rename...</option>' + deletableOptions;
    }
    if (selectDeleteFolder) {
        selectDeleteFolder.innerHTML = '<option value="">Choose folder to delete...</option>' + deletableOptions;
    }
}

// Recipe extraction functions
async function extractRecipe() {
    const url = document.getElementById('recipeUrl').value.trim();
    const folderId = document.getElementById('extractFolder').value;
    
    if (!url) {
        showAlert('Please enter a recipe URL', 'warning');
        return;
    }
    
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        showAlert('Please enter a valid URL starting with http:// or https://', 'warning');
        return;
    }
    
    try {
        showLoading('Extracting recipe...', 'This may take a few moments while we parse the webpage.');
        const response = await fetch('/api/extract-recipe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ url: url, folder_id: folderId })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            cleanupAllModals();
            showAlert(result.message, 'success');
            document.getElementById('recipeUrl').value = '';
            loadFolders();
            loadRecipes();
        } else {
            cleanupAllModals();
            throw new Error(result.error || 'Failed to extract recipe');
        }
    } catch (error) {
        cleanupAllModals();
        showAlert('Error extracting recipe: ' + error.message, 'danger');
    }
}

async function saveManualRecipe() {
    const name = document.getElementById('manualRecipeName').value.trim();
    const servingSize = document.getElementById('manualServingSize').value.trim();
    const ingredientsText = document.getElementById('manualIngredients').value.trim();
    const instructionsText = document.getElementById('manualInstructions').value.trim();
    const folderId = document.getElementById('manualFolder').value;
    
    const ingredients = ingredientsText.split('\n').map(line => line.trim()).filter(line => line);
    const instructions = instructionsText.split('\n').map(line => line.trim()).filter(line => line);
    
    console.log('Manual recipe save data:', {
        name,
        servingSize,
        folderId,
        ingredientsCount: ingredients.length,
        instructionsCount: instructions.length
    });
    
    if (!name || !ingredientsText || !instructionsText) {
        showAlert('Please fill in all required fields', 'warning');
        return;
    }
    
    if (ingredients.length === 0 || instructions.length === 0) {
        showAlert('Please provide at least one ingredient and one instruction', 'warning');
        return;
    }
    
    try {
        showLoading('Saving recipe...', 'Please wait while we save your recipe.');
        const response = await fetch('/api/save-manual-recipe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                name: name,
                serving_size: servingSize || null,
                ingredients: ingredients,
                instructions: instructions,
                folder_id: folderId
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            cleanupAllModals();
            showAlert(result.message, 'success');
            // Clear form fields
            document.getElementById('manualRecipeName').value = '';
            document.getElementById('manualServingSize').value = '';
            document.getElementById('manualIngredients').value = '';
            document.getElementById('manualInstructions').value = '';
            document.getElementById('manualFolder').value = 'uncategorized';
            loadFolders();
            loadRecipes();
        } else {
            cleanupAllModals();
            throw new Error(result.error || 'Failed to save recipe');
        }
    } catch (error) {
        cleanupAllModals();
        showAlert('Error saving recipe: ' + error.message, 'danger');
    }
}

// Meal planning functions
function loadRecipeSelection() {
    const container = document.getElementById('recipeSelection');
    
    if (recipes.length === 0) {
        container.innerHTML = `
            <div class="text-center">
                <p class="text-muted">No recipes available for meal planning.</p>
                <button class="btn btn-primary" onclick="document.getElementById('extract-tab').click()">
                    <i class="fas fa-plus me-2"></i>Add Recipes First
                </button>
            </div>
        `;
        return;
    }
    
    const recipeCheckboxes = recipes.map(recipe => `
        <div class="recipe-selection-item">
            <div class="form-check">
                <input class="form-check-input" type="checkbox" value="${recipe.name}" id="recipe-${recipe.name.replace(/\s+/g, '-')}" onchange="updateSelectedRecipes()">
                <label class="form-check-label" for="recipe-${recipe.name.replace(/\s+/g, '-')}">
                    <strong>${recipe.name}</strong>
                    <div class="recipe-meta">
                        ${recipe.serving_size ? `${recipe.serving_size} • ` : ''}${recipe.ingredients_count} ingredients • ${recipe.instructions_count} steps
                    </div>
                </label>
            </div>
        </div>
    `).join('');
    
    container.innerHTML = recipeCheckboxes;
    updateSelectedRecipes(); // Initialize the button state
}

function updateSelectedRecipes() {
    const checkboxes = document.querySelectorAll('#recipeSelection input[type="checkbox"]:checked');
    selectedRecipes = Array.from(checkboxes).map(cb => cb.value);
    
    // The button doesn't need to be updated here since it uses onclick="generateMealPlan()"
    // Just store the selected recipes for use in generateMealPlan()
}

async function generateMealPlan() {
    if (selectedRecipes.length === 0) {
        showAlert('Please select at least one recipe', 'warning');
        return;
    }
    
    if (!startDate || !endDate || new Date(startDate) > new Date(endDate)) {
        showAlert('Please select valid meal prep dates', 'warning');
        return;
    }
    
    try {
        showLoading('Generating meal plan...', 'This may take a moment while we parse ingredients and create your grocery list.');
        const response = await fetch('/api/create-meal-plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ 
                recipes: selectedRecipes,
                start_date: startDate,
                end_date: endDate
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            cleanupAllModals();
            displayGroceryList(result.grocery_list, result.meal_plan, result.date_range);
            
            // Automatically save the grocery list to the database
            setTimeout(async () => {
                try {
                    const saveResponse = await fetch('/api/grocery-lists', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify({
                            groceryList: result.grocery_list,
                            mealPlan: result.meal_plan,
                            dateRange: result.date_range
                        })
                    });
                    
                    if (saveResponse.ok) {
                        showAlert('Meal plan generated and grocery list saved successfully!', 'success');
                    } else {
                        showAlert('Meal plan generated! Click "Save List" to save for later viewing.', 'info');
                    }
                } catch (error) {
                    showAlert('Meal plan generated! Click "Save List" to save for later viewing.', 'info');
                }
                
                // Update the current plan section on the main page
                updateCurrentPlanDisplay(result.meal_plan, result.grocery_list, result.date_range);
            }, 500);
        } else {
            cleanupAllModals();
            throw new Error(result.error || 'Failed to generate meal plan');
        }
    } catch (error) {
        cleanupAllModals();
        showAlert('Error generating meal plan: ' + error.message, 'danger');
    }
}

function displayGroceryList(groceryList, mealPlan, dateRange) {
    // Store current grocery list data for saving
    currentGroceryListData = {
        groceryList,
        mealPlan,
        dateRange,
        createdAt: new Date().toISOString()
    };
    
    // Clear previous grocery list state for new plan
    groceryListState = {};
    
    const dateInfo = dateRange ? 
        `<div class="mb-3 p-3 bg-light rounded"><i class="fas fa-calendar me-2 text-primary"></i><strong>Meal Planning Period:</strong> ${dateRange.start} to ${dateRange.end}</div>` : '';
    
    const mealPlanDisplay = mealPlan && mealPlan.length > 0 ? 
        `<div class="mb-4">
            <h6 class="mb-2"><i class="fas fa-utensils me-2 text-success"></i>Selected Recipes:</h6>
            ${mealPlan.map(recipe => `<div class="mb-1 ms-3"><i class="fas fa-circle text-success me-2" style="font-size: 0.5rem;"></i>${recipe}</div>`).join('')}
        </div>` : '';
    
    if (!groceryList || groceryList.length === 0) {
        const container = document.getElementById('groceryList');
        if (container) {
            container.innerHTML = `
                ${dateInfo}
                ${mealPlanDisplay}
                <div class="text-center p-4">
                    <i class="fas fa-shopping-cart fa-3x text-muted mb-3"></i>
                    <p class="text-muted">No ingredients found in selected recipes.</p>
                </div>
            `;
        }
        // Show the modal
        const modal = new bootstrap.Modal(document.getElementById('groceryListModal'));
        modal.show();
        return;
    }
    
    const groceryItems = groceryList.map((item, index) => {
        const itemId = `grocery-item-${index}`;
        const isChecked = groceryListState[itemId] || false;
        
        return `
            <div class="d-flex align-items-center p-3 border-bottom grocery-item ${isChecked ? 'completed' : ''}" id="${itemId}" style="cursor: pointer;" onclick="toggleGroceryItem('${itemId}')">
                <input class="form-check-input me-3" type="checkbox" ${isChecked ? 'checked' : ''} onchange="event.stopPropagation(); toggleGroceryItem('${itemId}')" id="check-${itemId}" style="min-width: 18px; height: 18px;">
                <label class="form-check-label grocery-item-text flex-grow-1" for="check-${itemId}" style="font-size: 1rem; line-height: 1.4; ${isChecked ? 'text-decoration: line-through; opacity: 0.6;' : ''}">${item}</label>
            </div>
        `;
    }).join('');
    
    const container = document.getElementById('groceryList');
    if (container) {
        container.innerHTML = `
            ${dateInfo}
            ${mealPlanDisplay}
            
            <div class="grocery-list">
                <h6 class="mb-3"><i class="fas fa-shopping-cart me-2"></i>Grocery List (${groceryList.length} items)</h6>
                <div class="mb-3">
                    <button class="btn btn-outline-secondary btn-sm me-2" onclick="toggleAllItems(true)">
                        <i class="fas fa-check-square me-1"></i>Check All
                    </button>
                    <button class="btn btn-outline-secondary btn-sm" onclick="toggleAllItems(false)">
                        <i class="fas fa-square me-1"></i>Uncheck All
                    </button>
                </div>
                ${groceryItems}
            </div>
        `;
        
        // Show the grocery list modal
        const modal = new bootstrap.Modal(document.getElementById('groceryListModal'));
        modal.show();
    }
}

function copyGroceryList() {
    const groceryItems = document.querySelectorAll('.grocery-item span');
    const listText = Array.from(groceryItems).map(item => `• ${item.textContent}`).join('\n');
    
    navigator.clipboard.writeText(listText).then(() => {
        showAlert('Grocery list copied to clipboard!', 'success');
    }).catch(() => {
        showAlert('Failed to copy grocery list', 'danger');
    });
}

function printGroceryList() {
    const groceryItems = document.querySelectorAll('.grocery-item span');
    const mealPlan = document.querySelector('.meal-plan-display').innerHTML;
    const listText = Array.from(groceryItems).map(item => `• ${item.textContent}`).join('\n');
    
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
        <html>
            <head>
                <title>Grocery List</title>
                <style>
                    body { font-family: Arial, sans-serif; padding: 20px; }
                    h1, h2 { color: #333; }
                    .meal-plan { margin-bottom: 20px; }
                    .grocery-list { white-space: pre-line; }
                </style>
            </head>
            <body>
                <h1>Meal Planning Grocery List</h1>
                <h2>Meal Plan</h2>
                <div class="meal-plan">${mealPlan}</div>
                <h2>Grocery List</h2>
                <div class="grocery-list">${listText}</div>
                <script>window.print();</script>
            </body>
        </html>
    `);
    printWindow.document.close();
}

// Grocery list checkbox functions
function toggleGroceryItem(itemId) {
    const item = document.getElementById(itemId);
    const checkbox = item.querySelector('input[type="checkbox"]');
    const label = item.querySelector('.grocery-item-text');
    
    // Toggle checkbox if called from clicking the item
    if (event.target !== checkbox) {
        checkbox.checked = !checkbox.checked;
    }
    
    const isChecked = checkbox.checked;
    
    // Update visual state with better styling
    if (isChecked) {
        item.classList.add('completed');
        label.style.textDecoration = 'line-through';
        label.style.opacity = '0.6';
        item.style.backgroundColor = '#f8f9fa';
    } else {
        item.classList.remove('completed');
        label.style.textDecoration = 'none';
        label.style.opacity = '1';
        item.style.backgroundColor = '';
    }
    
    // Store state
    groceryListState[itemId] = isChecked;
    
    // Save to localStorage for persistence
    localStorage.setItem('groceryListState', JSON.stringify(groceryListState));
}

// Saved grocery lists functions

async function loadSavedGroceryLists() {
    try {
        const response = await fetch('/api/grocery-lists', {
            credentials: 'same-origin'
        });
        const savedLists = await response.json();
        
        const container = document.getElementById('savedGroceryListsBody');
        
        if (!savedLists || savedLists.length === 0) {
            container.innerHTML = `
                <div class="text-center p-5">
                    <i class="fas fa-shopping-cart fa-3x text-muted mb-3"></i>
                    <h5 class="text-muted">No Saved Grocery Lists</h5>
                    <p class="text-muted">Create a meal plan to generate your first grocery list!</p>
                    <button class="btn btn-primary" onclick="bootstrap.Modal.getInstance(document.getElementById('savedGroceryListsModal')).hide(); showMealPlanModal();">
                        <i class="fas fa-calendar-plus me-2"></i>Create Meal Plan
                    </button>
                </div>
            `;
            return;
        }
        
        const listsHTML = savedLists.map(list => {
            const createdDate = new Date(list.created_at).toLocaleDateString();
            const dateRange = list.date_range ? `${list.date_range.start} to ${list.date_range.end}` : 'No date range';
            
            return `
                <div class="card mb-3">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-0">
                                <i class="fas fa-calendar me-2 text-primary"></i>${dateRange}
                            </h6>
                            <small class="text-muted">Created: ${createdDate}</small>
                        </div>
                        <div>
                            <button class="btn btn-outline-primary btn-sm me-2" onclick="viewSavedGroceryList('${list.id}')">
                                <i class="fas fa-eye me-1"></i>View
                            </button>
                            <button class="btn btn-outline-danger btn-sm" onclick="deleteSavedGroceryList('${list.id}')">
                                <i class="fas fa-trash me-1"></i>Delete
                            </button>
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-6">
                                <h6 class="text-success"><i class="fas fa-utensils me-1"></i>Recipes (${list.meal_plan.length})</h6>
                                <ul class="list-unstyled mb-0">
                                    ${list.meal_plan.slice(0, 3).map(recipe => `<li class="mb-1"><i class="fas fa-circle text-success me-2" style="font-size: 0.5rem;"></i>${recipe}</li>`).join('')}
                                    ${list.meal_plan.length > 3 ? `<li class="text-muted">...and ${list.meal_plan.length - 3} more</li>` : ''}
                                </ul>
                            </div>
                            <div class="col-md-6">
                                <h6 class="text-info"><i class="fas fa-shopping-cart me-1"></i>Grocery Items (${list.grocery_list.length})</h6>
                                <ul class="list-unstyled mb-0">
                                    ${list.grocery_list.slice(0, 4).map(item => `<li class="mb-1"><i class="fas fa-circle text-info me-2" style="font-size: 0.5rem;"></i>${item}</li>`).join('')}
                                    ${list.grocery_list.length > 4 ? `<li class="text-muted">...and ${list.grocery_list.length - 4} more</li>` : ''}
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        container.innerHTML = listsHTML;
        
    } catch (error) {
        document.getElementById('savedGroceryListsBody').innerHTML = `
            <div class="text-center p-4">
                <i class="fas fa-exclamation-triangle fa-2x text-warning mb-3"></i>
                <p class="text-muted">Error loading saved grocery lists</p>
            </div>
        `;
    }
}

async function saveCurrentGroceryList() {
    if (!currentGroceryListData) {
        showAlert('No grocery list to save', 'warning');
        return;
    }
    
    try {
        showLoading('Saving grocery list...', 'Please wait while we save your grocery list.');
        
        const response = await fetch('/api/grocery-lists', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify(currentGroceryListData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            cleanupAllModals();
            showAlert('Grocery list saved successfully!', 'success');
        } else {
            cleanupAllModals();
            throw new Error(result.error || 'Failed to save grocery list');
        }
    } catch (error) {
        cleanupAllModals();
        showAlert('Error saving grocery list: ' + error.message, 'danger');
    }
}

async function viewSavedGroceryList(listId) {
    try {
        const response = await fetch(`/api/grocery-lists/${listId}`, {
            credentials: 'same-origin'
        });
        const savedList = await response.json();
        
        if (response.ok) {
            // Close saved lists modal and show the grocery list
            bootstrap.Modal.getInstance(document.getElementById('savedGroceryListsModal')).hide();
            
            // Display the saved grocery list
            displayGroceryList(savedList.grocery_list, savedList.meal_plan, savedList.date_range);
        } else {
            throw new Error(savedList.error || 'Failed to load grocery list');
        }
    } catch (error) {
        showAlert('Error loading grocery list: ' + error.message, 'danger');
    }
}

async function deleteSavedGroceryList(listId) {
    // Create a more user-friendly confirmation dialog
    const confirmDelete = confirm('Are you sure you want to delete this grocery list? This action cannot be undone.');
    
    if (!confirmDelete) {
        return;
    }
    
    try {
        showLoading('Deleting grocery list...', 'Please wait while we delete your grocery list.');
        
        const response = await fetch(`/api/grocery-lists/${listId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        
        const result = await response.json();
        
        // Always hide loading first
        hideLoading();
        
        if (response.ok) {
            showAlert('Grocery list deleted successfully!', 'success');
            // Add a small delay to ensure the loading modal is fully hidden
            setTimeout(() => {
                loadSavedGroceryLists();
            }, 100);
        } else {
            throw new Error(result.error || 'Failed to delete grocery list');
        }
    } catch (error) {
        hideLoading();
        showAlert('Error deleting grocery list: ' + error.message, 'danger');
    }
}

function toggleAllItems(checkState) {
    const checkboxes = document.querySelectorAll('.grocery-item input[type="checkbox"]');
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = checkState;
        const item = checkbox.closest('.grocery-item');
        const itemId = item.id;
        
        if (checkState) {
            item.classList.add('completed');
        } else {
            item.classList.remove('completed');
        }
        
        groceryListState[itemId] = checkState;
    });
    
    // Save to localStorage
    localStorage.setItem('groceryListState', JSON.stringify(groceryListState));
}

// Utility functions
function showAlert(message, type = 'info') {
    const alertContainer = document.createElement('div');
    alertContainer.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertContainer.style.cssText = 'top: 20px; right: 20px; z-index: 1050; max-width: 400px;';
    alertContainer.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertContainer);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alertContainer.parentNode) {
            alertContainer.remove();
        }
    }, 5000);
}

function showLoading(title = 'Processing...', subtitle = 'Please wait...') {
    // First ensure any existing loading modal is completely cleaned up
    hideLoading();
    
    // Wait a moment for cleanup to complete
    setTimeout(() => {
        const titleElement = document.getElementById('loadingTitle');
        const subtitleElement = document.getElementById('loadingSubtitle');
        
        if (titleElement) titleElement.textContent = title;
        if (subtitleElement) subtitleElement.textContent = subtitle;
        
        const loadingModalElement = document.getElementById('loadingModal');
        if (loadingModalElement) {
            const loadingModal = new bootstrap.Modal(loadingModalElement, {
                backdrop: 'static',
                keyboard: false
            });
            loadingModal.show();
        }
    }, 50);
}

function hideLoading() {
    // Force immediate cleanup of loading modal
    const loadingModalElement = document.getElementById('loadingModal');
    if (loadingModalElement) {
        const loadingModal = bootstrap.Modal.getInstance(loadingModalElement);
        if (loadingModal) {
            loadingModal.dispose();
        }
        loadingModalElement.style.display = 'none';
        loadingModalElement.classList.remove('show');
        loadingModalElement.setAttribute('aria-hidden', 'true');
        loadingModalElement.removeAttribute('aria-modal');
        loadingModalElement.removeAttribute('role');
    }
    
    // Aggressive cleanup of all modal artifacts
    const existingBackdrops = document.querySelectorAll('.modal-backdrop');
    existingBackdrops.forEach(backdrop => backdrop.remove());
    
    // Reset body state
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    document.body.style.paddingRight = '';
    document.body.style.marginRight = '';
}

// Function to update the current meal plan display on main page
function updateCurrentPlanDisplay(mealPlan, groceryList, dateRange) {
    const planSection = document.getElementById('currentPlanSection');
    const mealPlanElement = document.getElementById('currentMealPlan');
    const groceryListElement = document.getElementById('currentGroceryList');
    
    if (!planSection || !mealPlanElement || !groceryListElement) return;
    
    // Show the section
    planSection.style.display = 'block';
    
    // Update meal plan display
    if (mealPlan && mealPlan.length > 0) {
        const dateInfo = dateRange ? 
            `<div class="mb-3 p-2 bg-light rounded">
                <strong><i class="fas fa-calendar me-2"></i>Planning Period:</strong> ${dateRange.start} to ${dateRange.end}
            </div>` : '';
        
        const recipesHTML = mealPlan.map((recipe, index) => `
            <div class="d-flex align-items-center mb-2 p-2 border-left-success recipe-clickable" style="cursor: pointer;" onclick="showRecipeFromMealPlan('${recipe}')">
                <div class="recipe-number bg-success text-white rounded-circle d-flex align-items-center justify-content-center me-3" style="width: 30px; height: 30px; font-size: 0.8rem; font-weight: bold;">
                    ${index + 1}
                </div>
                <div class="flex-grow-1">
                    <span class="fw-medium">${recipe}</span>
                </div>
            </div>
        `).join('');
        
        mealPlanElement.innerHTML = `
            ${dateInfo}
            <div class="recipes-list">
                ${recipesHTML}
            </div>
            <div class="mt-3 text-center">
                <small class="text-muted">${mealPlan.length} recipe${mealPlan.length !== 1 ? 's' : ''} planned</small>
            </div>
        `;
    }
    
    // Update grocery list display
    if (groceryList && groceryList.length > 0) {
        const groceryHTML = groceryList.slice(0, 8).map(item => `
            <div class="d-flex align-items-center mb-1">
                <i class="fas fa-circle text-info me-2" style="font-size: 0.4rem;"></i>
                <small style="color: #0F172A !important;">${item}</small>
            </div>
        `).join('');
        
        const moreItems = groceryList.length > 8 ? 
            `<div class="mt-2 text-center">
                <small class="text-muted">...and ${groceryList.length - 8} more items</small>
            </div>` : '';
        
        groceryListElement.innerHTML = `
            <div class="grocery-preview grocery-clickable" style="color: #0F172A !important; cursor: pointer;" onclick="showFullGroceryList()">
                ${groceryHTML}
                ${moreItems}
            </div>
            <div class="mt-3 text-center">
                <small style="color: #64748B !important;">${groceryList.length} total items</small>
                <div class="mt-2">
                    <small class="text-info">Click to view full list</small>
                </div>
            </div>
        `;
        
        // Force all text elements to be dark after rendering
        setTimeout(() => {
            const allElements = groceryListElement.querySelectorAll('*');
            allElements.forEach(el => {
                if (el.tagName !== 'I') { // Don't change icon colors
                    el.style.color = '#0F172A';
                }
            });
        }, 100);
    }
}

// Function to load and display the most recent meal plan
async function loadCurrentMealPlan() {
    try {
        const response = await fetch('/api/grocery-lists', {
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            if (response.status === 302) {
                // User not authenticated, silently return
                return;
            }
            console.log('Failed to fetch grocery lists:', response.status);
            return;
        }
        
        const savedLists = await response.json();
        console.log('Loaded grocery lists:', savedLists);
        
        if (savedLists && savedLists.length > 0) {
            // Get the most recent grocery list (they're ordered by created_at desc)
            const mostRecent = savedLists[0];
            console.log('Displaying most recent plan:', mostRecent);
            
            // Store the current grocery list data globally for click access
            currentGroceryListData = {
                groceryList: mostRecent.grocery_list,
                mealPlan: mostRecent.meal_plan,
                dateRange: mostRecent.date_range,
                createdAt: mostRecent.created_at
            };
            
            updateCurrentPlanDisplay(mostRecent.meal_plan, mostRecent.grocery_list, mostRecent.date_range);
        } else {
            console.log('No saved grocery lists found');
        }
    } catch (error) {
        console.log('Error loading meal plan:', error);
    }
}

// Function to show recipe details when clicked from meal plan
async function showRecipeFromMealPlan(recipeName) {
    try {
        // Find the recipe in the recipes list
        const response = await fetch('/api/recipes', {
            credentials: 'same-origin'
        });
        const allRecipes = await response.json();
        
        console.log('Looking for recipe:', recipeName);
        
        // Find the recipe by name (each recipe object has folder_id and name)
        for (const recipe of allRecipes) {
            if (recipe.name === recipeName) {
                console.log('Found recipe:', recipe);
                showRecipeDetails(recipe.folder_id, recipeName);
                return;
            }
        }
        
        showAlert('Recipe not found', 'warning');
    } catch (error) {
        console.error('Full error:', error);
        showAlert('Error loading recipe: ' + error.message, 'danger');
    }
}

// Smart Recipe Discovery Functions
function handleCravingSearch(event) {
    if (event.key === 'Enter') {
        performCravingSearch();
    }
}

function performCravingSearch() {
    const searchTerm = document.getElementById('discoverSearchInput').value.trim();
    if (!searchTerm) {
        showAlert('Please enter what you\'re craving to search for recipes', 'warning');
        return;
    }
    
    // Get selected search type
    const searchType = document.querySelector('input[name="searchType"]:checked').value;
    
    if (searchType === 'saved') {
        searchSavedRecipes(searchTerm);
    } else {
        searchWebRecipes(searchTerm);
    }
}

// Search saved recipes function
function searchSavedRecipes(searchTerm) {
    console.log('Searching saved recipes for:', searchTerm);
    
    if (!recipes || recipes.length === 0) {
        displaySearchResults(`
            <div class="text-center py-3">
                <i class="fas fa-search fa-2x text-muted mb-2"></i>
                <p class="text-muted">No saved recipes found for "${searchTerm}"</p>
                <p class="text-muted small">Try switching to "Discover New Recipes" to find recipes online</p>
            </div>
        `);
        return;
    }
    
    // Enhanced fuzzy search with similarity scoring
    const searchWords = searchTerm.toLowerCase().split(/\s+/).filter(word => word.length > 0);
    
    const recipesWithScores = recipes.map(recipe => {
        if (!recipe.name) return null;
        
        const recipeName = recipe.name.toLowerCase();
        let score = 0;
        
        // Exact phrase match (80-100% similarity)
        if (recipeName.includes(searchTerm.toLowerCase())) {
            const matchLength = searchTerm.length;
            const nameLength = recipe.name.length;
            score = Math.min(100, Math.round((matchLength / nameLength) * 100) + 30);
        }
        // Multi-word matching
        else if (searchWords.length > 1) {
            const wordsFound = searchWords.filter(word => recipeName.includes(word)).length;
            const wordMatchRatio = wordsFound / searchWords.length;
            score = Math.round(wordMatchRatio * 70); // 0-70% based on word coverage
        }
        // Partial word matching
        else {
            const searchWord = searchWords[0];
            let bestMatch = 0;
            
            recipeName.split(/\s+/).forEach(recipeWord => {
                if (recipeWord.includes(searchWord)) {
                    const matchRatio = searchWord.length / recipeWord.length;
                    bestMatch = Math.max(bestMatch, matchRatio);
                } else if (searchWord.includes(recipeWord)) {
                    const matchRatio = recipeWord.length / searchWord.length;
                    bestMatch = Math.max(bestMatch, matchRatio * 0.8); // Slightly lower for reverse match
                }
            });
            
            score = Math.round(bestMatch * 60); // 0-60% for partial matches
        }
        
        return score > 0 ? { ...recipe, similarityScore: score } : null;
    }).filter(recipe => recipe !== null)
    .sort((a, b) => b.similarityScore - a.similarityScore); // Sort by highest similarity first
    
    const filtered = recipesWithScores;
    
    if (filtered.length > 0) {
        displaySearchResults(`
            <h6 class="fw-semibold mb-3">Found ${filtered.length} saved recipe(s)</h6>
            <div class="d-grid gap-2">
                ${filtered.map(recipe => `
                    <div class="card mb-2 recipe-card" onclick="showRecipeDetails('${recipe.folder_id}', '${recipe.name}')">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-start mb-1">
                                <h6 class="card-title mb-0">${recipe.name}</h6>
                                <span class="badge bg-primary ms-2">${recipe.similarityScore}% match</span>
                            </div>
                            <div class="recipe-meta">
                                ${recipe.serving_size ? `<span class="me-3"><i class="fas fa-users me-1"></i>${recipe.serving_size}</span>` : ''}
                                <span class="me-3"><i class="fas fa-list me-1"></i>${recipe.ingredients_count || 0} ingredients</span>
                                <span><i class="fas fa-tasks me-1"></i>${recipe.instructions_count || 0} steps</span>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `);
    } else {
        displaySearchResults(`
            <div class="text-center py-3">
                <i class="fas fa-search fa-2x text-muted mb-2"></i>
                <p class="text-muted">No saved recipes found for "${searchTerm}"</p>
                <p class="text-muted small">Try a different search term or switch to "Discover New Recipes"</p>
            </div>
        `);
    }
}

function showSaveToFolderModal(recipeName, recipeUrl) {
    // Create folder selection modal content
    const folderOptions = folders.map(folder => 
        `<option value="${folder.id}">${folder.name}</option>`
    ).join('');
    
    const modalContent = `
        <div class="modal fade" id="saveToFolderModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Save Recipe to Folder</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p><strong>Recipe:</strong> ${recipeName}</p>
                        <div class="mb-3">
                            <label for="selectSaveFolder" class="form-label">Choose folder:</label>
                            <select class="form-select" id="selectSaveFolder">
                                <option value="uncategorized">Uncategorized</option>
                                ${folderOptions}
                            </select>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-success" onclick="confirmSaveWebRecipe('${recipeName}', '${recipeUrl}')">Save Recipe</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('saveToFolderModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalContent);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('saveToFolderModal'));
    modal.show();
}

function showSaveToFolderModalWithData(recipe) {
    // Store recipe data globally to avoid encoding issues
    window.currentSaveRecipe = recipe;
    
    const folderOptions = folders.map(folder => 
        `<option value="${folder.id}">${folder.name}</option>`
    ).join('');
    
    const modalContent = `
        <div class="modal fade" id="saveToFolderModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Save Recipe to Folder</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p><strong>Recipe:</strong> ${recipe.name}</p>
                        <p class="text-muted">Contains ${recipe.ingredients.length} ingredients and ${recipe.instructions.length} instructions</p>
                        <div class="mb-3">
                            <label for="selectSaveFolder" class="form-label">Choose folder:</label>
                            <select class="form-select" id="selectSaveFolder">
                                <option value="uncategorized">Uncategorized</option>
                                ${folderOptions}
                            </select>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-success" id="confirmSaveBtn">Save Recipe</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('saveToFolderModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalContent);
    
    // Add event listener for save button
    document.getElementById('confirmSaveBtn').addEventListener('click', confirmSaveCompleteRecipe);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('saveToFolderModal'));
    modal.show();
}

async function confirmSaveCompleteRecipe() {
    const selectedFolder = document.getElementById('selectSaveFolder').value;
    
    try {
        const recipe = window.currentSaveRecipe;
        
        if (!recipe) {
            throw new Error('Recipe data not found');
        }
        
        // Hide the folder selection modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('saveToFolderModal'));
        modal.hide();
        
        showLoading('Saving recipe...', 'Saving complete recipe details to your collection');
        
        const response = await fetch('/api/save-search-result', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ 
                recipe: recipe,
                folder_id: selectedFolder
            })
        });
        
        const result = await response.json();
        hideLoading();
        
        if (response.ok) {
            showAlert(`Recipe "${recipe.name}" saved successfully to ${selectedFolder === 'uncategorized' ? 'Uncategorized' : folders.find(f => f.id === selectedFolder)?.name || selectedFolder}!`, 'success');
            loadFolders(); // Refresh folder counts
            loadRecipes(); // Refresh the recipes list
            
            // Clean up modal and global data
            setTimeout(() => {
                const modalElement = document.getElementById('saveToFolderModal');
                if (modalElement) {
                    modalElement.remove();
                }
                delete window.currentSaveRecipe;
            }, 500);
        } else {
            throw new Error(result.error || 'Failed to save recipe');
        }
    } catch (error) {
        hideLoading();
        showAlert('Error saving recipe: ' + error.message, 'danger');
    }
}

async function confirmSaveWebRecipe(recipeName, recipeUrl) {
    const selectedFolder = document.getElementById('selectSaveFolder').value;
    
    try {
        // Hide the folder selection modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('saveToFolderModal'));
        modal.hide();
        
        showLoading('Saving recipe...', 'Extracting recipe details and saving to your collection');
        
        const response = await fetch('/api/save-search-result', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ 
                recipe_name: recipeName,
                recipe_url: recipeUrl,
                folder_id: selectedFolder
            })
        });
        
        const result = await response.json();
        hideLoading();
        
        if (response.ok) {
            showAlert(`Recipe "${recipeName}" saved successfully to ${selectedFolder === 'uncategorized' ? 'Uncategorized' : folders.find(f => f.id === selectedFolder)?.name || selectedFolder}!`, 'success');
            loadFolders(); // Refresh folder counts
            loadRecipes(); // Refresh the recipes list
            
            // Clean up modal
            setTimeout(() => {
                const modalElement = document.getElementById('saveToFolderModal');
                if (modalElement) {
                    modalElement.remove();
                }
            }, 500);
        } else {
            throw new Error(result.error || 'Failed to save recipe');
        }
    } catch (error) {
        hideLoading();
        showAlert('Error saving recipe: ' + error.message, 'danger');
    }
}

async function showSavedRecipeDetails(recipeName) {
    // Find the recipe in the recipes list and show its details
    try {
        const response = await fetch('/api/recipes', {
            credentials: 'same-origin'
        });
        const allRecipes = await response.json();
        
        for (const recipe of allRecipes) {
            if (recipe.name === recipeName) {
                showRecipeDetails(recipe.folder_id, recipeName);
                return;
            }
        }
        
        showAlert('Recipe not found', 'warning');
    } catch (error) {
        showAlert('Error loading recipe: ' + error.message, 'danger');
    }
}

function addToMealPlan(recipeName) {
    // For now, just show the meal plan modal and suggest the user select the recipe
    showMealPlanModal();
    showAlert(`Open the meal planner and look for "${recipeName}" in your recipes`, 'info');
}

// Function to show full grocery list when clicked
function showFullGroceryList() {
    if (currentGroceryListData) {
        displayGroceryList(
            currentGroceryListData.groceryList,
            currentGroceryListData.mealPlan,
            currentGroceryListData.dateRange
        );
    } else {
        showAlert('No grocery list available', 'warning');
    }
}

// Add event listeners for recipe action buttons using event delegation
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('view-web-recipe-btn') || e.target.closest('.view-web-recipe-btn')) {
        const button = e.target.classList.contains('view-web-recipe-btn') ? e.target : e.target.closest('.view-web-recipe-btn');
        const url = decodeURIComponent(button.dataset.url);
        viewWebRecipe(url);
    }
    
    if (e.target.classList.contains('save-web-recipe-btn') || e.target.closest('.save-web-recipe-btn')) {
        const button = e.target.classList.contains('save-web-recipe-btn') ? e.target : e.target.closest('.save-web-recipe-btn');
        const name = decodeURIComponent(button.dataset.name);
        const url = decodeURIComponent(button.dataset.url);
        saveWebRecipe(name, url);
    }
    
    if (e.target.classList.contains('view-saved-recipe-btn') || e.target.closest('.view-saved-recipe-btn')) {
        const button = e.target.classList.contains('view-saved-recipe-btn') ? e.target : e.target.closest('.view-saved-recipe-btn');
        const name = decodeURIComponent(button.dataset.name);
        showSavedRecipeDetails(name);
    }
});

// Function to load and display all recipes
async function loadAllRecipesList() {
    try {
        const response = await fetch('/api/recipes', {
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            if (response.status === 302) {
                return; // User not authenticated
            }
            throw new Error(`HTTP ${response.status}`);
        }
        
        const allRecipes = await response.json();
        displayAllRecipes(allRecipes);
    } catch (error) {
        console.log('Error loading all recipes:', error.message);
    }
}

function displayAllRecipes(recipeList) {
    const allRecipesList = document.getElementById('allRecipesList');
    const recipeCount = document.getElementById('recipeCount');
    
    if (!allRecipesList) return;
    
    // Update recipe count
    if (recipeCount) {
        recipeCount.textContent = `${recipeList.length} recipe${recipeList.length !== 1 ? 's' : ''}`;
    }
    
    if (recipeList.length === 0) {
        allRecipesList.innerHTML = `
            <div class="text-center py-4">
                <i class="fas fa-utensils fa-3x text-secondary mb-3"></i>
                <h6 class="text-secondary mb-2">No recipes yet</h6>
                <p class="text-muted small mb-3">Add your first recipe to get started!</p>
            </div>
        `;
        return;
    }
    
    // Group recipes by folder for better organization
    const groupedRecipes = {};
    recipeList.forEach(recipe => {
        const folderName = recipe.folder_name || 'Uncategorized';
        if (!groupedRecipes[folderName]) {
            groupedRecipes[folderName] = [];
        }
        groupedRecipes[folderName].push(recipe);
    });
    
    let html = '';
    Object.keys(groupedRecipes).forEach(folderName => {
        html += `
            <div class="mb-3">
                <h6 class="text-muted fw-semibold mb-2">
                    <i class="fas fa-folder me-1"></i>${folderName}
                </h6>
                <div class="list-group">
        `;
        
        groupedRecipes[folderName].forEach(recipe => {
            html += `
                <a href="#" class="list-group-item list-group-item-action" onclick="showRecipeDetails('${recipe.folder_id}', '${recipe.name}')">
                    <div class="d-flex w-100 justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1">${recipe.name}</h6>
                            <small class="text-muted">
                                ${recipe.ingredients_count} ingredients • ${recipe.instructions_count} steps
                                ${recipe.serving_size ? ` • ${recipe.serving_size}` : ''}
                            </small>
                        </div>
                        <i class="fas fa-chevron-right text-muted"></i>
                    </div>
                </a>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    });
    
    allRecipesList.innerHTML = html;
}

// Initialize the application when DOM is loaded
