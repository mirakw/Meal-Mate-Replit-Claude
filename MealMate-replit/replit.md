# MealMate - AI Recipe & Meal Planning Application

## Overview

MealMate is a Flask-based web application that helps users organize recipes, plan meals, and generate grocery lists with AI assistance. The application leverages Google's Gemini AI for intelligent recipe extraction and meal planning, while providing a user-friendly interface for recipe management and meal organization.

## System Architecture

### Frontend Architecture
- **Framework**: Bootstrap 5 with custom CSS for modern, responsive design
- **JavaScript**: Vanilla JS for interactive features and modal management
- **UI/UX**: Clean, gradient-based design with Inter font family
- **Templates**: Jinja2 templating with modular HTML structure

### Backend Architecture
- **Framework**: Flask web framework with SQLAlchemy ORM
- **Authentication**: Replit Auth integration with OAuth2 via Flask-Dance
- **API Integration**: Google Gemini AI for recipe parsing and meal planning
- **Data Models**: Pydantic models for structured data validation
- **Session Management**: Flask sessions with user-specific data storage

### Data Storage
- **Primary Database**: PostgreSQL (configurable via DATABASE_URL)
- **File Storage**: JSON-based recipe storage in organized folder structure
- **User Data**: Separated by user directories (`user_data/{user_id}/`)
- **Folder Management**: JSON-based folder organization system

## Key Components

### Recipe Management
- **Recipe Extraction**: Automated extraction from URLs using recipe-scrapers library
- **AI Fallback**: Gemini AI processes raw HTML when scrapers fail
- **Manual Entry**: Direct recipe input with structured validation
- **Folder Organization**: User-defined categories for recipe organization

### Meal Planning System
- **AI-Powered Planning**: Gemini generates meal plans based on selected recipes
- **Date Range Planning**: Flexible planning periods with calendar integration
- **Ingredient Parsing**: Smart ingredient parsing with quantity standardization
- **Grocery List Generation**: Consolidated shopping lists with duplicate elimination

### User Authentication
- **Replit Auth**: Integrated OAuth authentication system
- **User Sessions**: Persistent user sessions with browser-specific storage
- **Profile Management**: User profile data storage and management

### Folder Management
- **Dynamic Folders**: User-created recipe categories
- **Recipe Counts**: Automatic tracking of recipes per folder
- **Default Categories**: System-provided "Uncategorized" folder

## Data Flow

1. **User Authentication**: OAuth flow via Replit Auth → User session creation
2. **Recipe Addition**: URL extraction or manual entry → AI processing → JSON storage
3. **Folder Organization**: Recipe categorization → Folder metadata updates
4. **Meal Planning**: Recipe selection → AI meal plan generation → Grocery list creation
5. **Data Persistence**: User-specific directory structure → JSON file storage

## External Dependencies

### AI Services
- **Google Gemini AI**: Recipe extraction, ingredient parsing, meal planning
- **API Keys**: Stored in environment variables (.env file)

### Web Scraping
- **recipe-scrapers**: Primary recipe extraction library
- **BeautifulSoup4**: HTML parsing for fallback extraction
- **requests**: HTTP client for web scraping

### Authentication
- **Flask-Dance**: OAuth2 integration for Replit Auth
- **Flask-Login**: User session management

### Database
- **SQLAlchemy**: ORM for database operations
- **psycopg2**: PostgreSQL adapter

## Deployment Strategy

### Development Environment
- **Replit Integration**: Configured for Replit hosting platform
- **Auto-install Dependencies**: Package installation via workflow configuration
- **Port Configuration**: Flask app on port 5000, external port 80

### Production Considerations
- **Environment Variables**: API keys and database URLs via environment
- **Static Assets**: CSS/JS served via Flask static file handling
- **Database Migration**: SQLAlchemy model creation on startup
- **User Data Isolation**: Separate directories per user for data security

## Changelog

- June 22, 2025: **ENHANCEMENT** - Fixed recipe discovery to always return multiple recipes by combining scraped + AI-generated recipes when websites block scraping
- June 22, 2025: **MAJOR FIX** - Resolved JavaScript syntax errors preventing recipe save/view functionality by replacing inline handlers with event listeners
- June 22, 2025: **MAJOR FIX** - Completely overhauled web recipe search to extract real, complete recipes instead of placeholder URLs
- June 22, 2025: Fixed web recipe saving to use full recipe extractor with Gemini AI fallback for authentic recipe details
- June 22, 2025: Resolved all JavaScript authentication errors preventing recipe details from displaying properly
- June 22, 2025: Major cleanup - removed all broken overlapping scripts and replaced with working versions
- June 22, 2025: Enhanced web recipe search to properly scrape URLs and extract complete recipe details
- June 22, 2025: Added recipe move functionality - users can now move recipes between folders with automatic refresh
- June 22, 2025: Fixed automatic UI refresh after recipe saves - all recipe operations now update folders and recipe lists immediately
- June 22, 2025: Implemented smart recipe discovery feature with search functionality for saved recipes and web discovery using Gemini AI
- June 22, 2025: Fixed recipe extraction path duplication issue causing recipes not to appear in folders
- June 22, 2025: Added intelligent error handling for websites that block scraping
- June 15, 2025: Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.