#!/usr/bin/env python3
import json
import os
import datetime
import requests
from typing import List, Dict

# Configuración de filtros para Ranuk IT Solutions
TARGET_STACK = ["Python", "Node.js", "Automation", "AI", "Machine Learning"]

def fetch_bounties() -> List[Dict]:
    # Aquí integraríamos la lógica de scraping/API para Algora e IssueHunt
    # Por ahora, simulamos la estructura para el reporte de prueba
    return [
        {"platform": "Algora", "title": "Fix bug in Auth middleware", "amount": "$500", "stack": "Node.js"},
        {"platform": "IssueHunt", "title": "Optimize Python data pipeline", "amount": "$1200", "stack": "Python"}
    ]

def fetch_gigs() -> List[Dict]:
    # Aquí integraríamos la lógica para Upwork/Fiverr usando Camofox si es necesario
    return [
        {"platform": "Upwork", "title": "ML Engineer for automated scraping", "amount": "$50/hr", "stack": "Python, AI"},
        {"platform": "Fiverr", "title": "Custom Trading Bot Development", "amount": "$1000", "stack": "Python"}
    ]

def generate_spec(output_path: str):
    bounties = fetch_bounties()
    gigs = fetch_gigs()
    
    all_opps = bounties + gigs
    
    sections = []
    
    # Sección Bounties
    bounty_items = [f"- {o['platform']}: {o['title']} ({o['amount']}) - {o['stack']}" for o in bounties]
    sections.append({
        "heading": "1. Bounties Activas",
        "bullets": bounty_items
    })
    
    # Sección Gigs
    gig_items = [f"- {o['platform']}: {o['title']} ({o['amount']}) - {o['stack']}" for o in gigs]
    sections.append({
        "heading": "2. Gigs Freelance",
        "bullets": gig_items
    })

    spec = {
        "title": "Oportunidades de Ingresos",
        "subtitle": f"Generado el {datetime.date.today()}",
        "date": str(datetime.date.today()),
        "sections": sections
    }

    with open(output_path, 'w') as f:
        json.dump(spec, f, indent=2)

if __name__ == "__main__":
    spec_file = "spec_temp.json"
    generate_spec(spec_file)
    print(f"Spec generado en {spec_file}")