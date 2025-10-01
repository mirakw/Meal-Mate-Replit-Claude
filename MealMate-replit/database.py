"""
Database configuration for MealMate application
"""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Initialize the database
db = SQLAlchemy(model_class=Base)