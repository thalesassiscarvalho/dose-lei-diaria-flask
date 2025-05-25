# -*- coding: utf-8 -*-
import os
import sys

# Add project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.main import app, db # Import app and db from main
from src.models.user import Achievement # Import Achievement model

# List of achievements to add
achievements_data = [
    {"name": "Primeiro Passo", "description": "Parabéns! Você começou sua jornada.", "laws_completed_threshold": 5, "icon": "fas fa-shoe-prints"},
    {"name": "Estudante Dedicado", "description": "O esforço já é visível. Parabéns pela constância!", "laws_completed_threshold": 10, "icon": "fas fa-book-reader"},
    {"name": "Leitor de Leis", "description": "Agora você é um verdadeiro decifrador de artigos.", "laws_completed_threshold": 20, "icon": "fas fa-glasses"},
    {"name": "Operador do Saber", "description": "Seu conhecimento começa a operar mudanças.", "laws_completed_threshold": 30, "icon": "fas fa-cogs"},
    {"name": "Mestre em Formação", "description": "Sua bagagem está cada vez mais robusta.", "laws_completed_threshold": 50, "icon": "fas fa-graduation-cap"},
    {"name": "Mestre das Normas", "description": "Padrões, princípios e regras não têm segredos pra você.", "laws_completed_threshold": 75, "icon": "fas fa-balance-scale"},
    {"name": "Guardião das Leis", "description": "Sua dedicação é digna de uma toga.", "laws_completed_threshold": 100, "icon": "fas fa-gavel"},
    {"name": "Mentor da Lei", "description": "Você inspira outros estudantes a seguirem seu exemplo.", "laws_completed_threshold": 150, "icon": "fas fa-chalkboard-teacher"},
    {"name": "Uma lenda!", "description": "Um verdadeiro mito entre os estudiosos.", "laws_completed_threshold": 200, "icon": "fas fa-crown"}
]

def add_achievements():
    with app.app_context():
        print("Adding achievements to the database...")
        for data in achievements_data:
            existing_achievement = Achievement.query.filter_by(name=data["name"]).first()
            if not existing_achievement:
                achievement = Achievement(
                    name=data["name"],
                    description=data["description"],
                    laws_completed_threshold=data["laws_completed_threshold"],
                    icon=data.get("icon") # Use get for optional icon
                )
                db.session.add(achievement)
                print(f"Added achievement: {data['name']}")
            else:
                print(f"Achievement '{data['name']}' already exists. Skipping.")
        
        try:
            db.session.commit()
            print("Achievements successfully added/updated.")
        except Exception as e:
            db.session.rollback()
            print(f"Error adding achievements: {e}")

if __name__ == "__main__":
    add_achievements()

