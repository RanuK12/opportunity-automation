#!/usr/bin/env python3
import os
import sys
import datetime
import subprocess
from pathlib import Path

# Rutas base
BASE_DIR = Path("/Users/emilioranucoli/Apps/ranukita-bridge")
SCRAPER_PATH = BASE_DIR / "integrations/opportunity_scraper.py"
REPORT_ENGINE = BASE_DIR / "scripts/ranukita_report.py"
OUTPUT_DIR = Path("/Users/emilioranucoli/Desktop/Oficina_Ranuk")

def run_task():
    # 1. Generar el spec.json usando el scraper
    print("Ejecutando scraper...")
    subprocess.run([str(SCRAPER_PATH)], check=True)
    
    spec_file = "spec_temp.json"
    
    # 2. Generar el PDF usando el motor de Ranukita
    today = datetime.date.today().strftime("%Y-%m-%d")
    pdf_name = f"opportunities-report-{today}.pdf"
    pdf_path = OUTPUT_DIR / pdf_name
    
    print(f"Generando PDF en {pdf_path}...")
    # Usamos el motor existente con el spec generado
    subprocess.run([str(REPORT_ENGINE), spec_file, str(pdf_path)], check=True)
    
    # 3. Generar reporte de prueba solicitado
    test_pdf_path = OUTPUT_DIR / f"opportunities-report-test.pdf"
    print(f"Generando reporte de prueba...")
    subprocess.run([str(REPORT_ENGINE), spec_file, str(test_pdf_path)], check=True)
    
    print("Tarea completada con éxito.")

if __name__ == "__main__":
    run_task()