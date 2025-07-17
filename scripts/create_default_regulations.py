#!/usr/bin/env python3
"""
Script om enkele standaard subsidiereglingen aan te maken voor de GovChat-NL applicatie.
Dit script kan gebruikt worden door admins om voorbeeldregels beschikbaar te maken.
"""

import sys
import os
import json
from datetime import datetime

# Voeg het backend pad toe zodat we imports kunnen doen
backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend')
sys.path.insert(0, backend_path)

from open_webui.utils.subsidy_storage import SubsidyFileStorage

def create_example_regulations():
    """Maak enkele voorbeeldreglingen aan"""
    
    storage = SubsidyFileStorage()
    
    # Regeling 1: Gemeente Evenementen Subsidie
    regeling1 = {
        "criteria": [
            {"id": 1, "text": "Artikel 2.1: De aanvrager moet een rechtspersoon zijn gevestigd binnen de gemeente"},
            {"id": 2, "text": "Artikel 3.1: Het evenement moet plaatsvinden binnen de gemeentegrenzen"},
            {"id": 3, "text": "Artikel 3.2: Het evenement moet minimaal 100 bezoekers verwachten"},
            {"id": 4, "text": "Artikel 4.1: Het evenement moet bijdragen aan de sociale cohesie of culturele ontwikkeling"},
            {"id": 5, "text": "Artikel 5.1: De subsidieaanvraag moet minimaal 8 weken voor het evenement worden ingediend"},
            {"id": 6, "text": "Artikel 6.1: De maximale subsidie bedraagt €5.000 per evenement"},
            {"id": 7, "text": "Artikel 6.2: De subsidie bedraagt maximaal 50% van de totale kosten"},
            {"id": 8, "text": "Artikel 7.1: De aanvrager moet een sluitende begroting overleggen"},
            {"id": 9, "text": "Artikel 8.1: Het evenement mag geen commercieel doel hebben"},
            {"id": 10, "text": "Artikel 9.1: De aanvrager mag per kalenderjaar maximaal 1 subsidie aanvragen"}
        ],
        "summary": "Subsidieregeling voor lokale evenementen ter bevordering van sociale cohesie en culturele ontwikkeling. Maximaal €5.000 per evenement, 50% van totale kosten."
    }
    
    # Regeling 2: Sportvereniging Subsidie
    regeling2 = {
        "criteria": [
            {"id": 1, "text": "Artikel 2.1: De aanvrager moet een sportvereniging zijn met rechtspersoonlijkheid"},
            {"id": 2, "text": "Artikel 2.2: De vereniging moet minimaal 2 jaar actief zijn"},
            {"id": 3, "text": "Artikel 3.1: De vereniging moet minimaal 50 leden hebben"},
            {"id": 4, "text": "Artikel 3.2: Minimaal 60% van de leden moet woonachtig zijn in de gemeente"},
            {"id": 5, "text": "Artikel 4.1: De subsidie is bedoeld voor materialen, accommodatie of training"},
            {"id": 6, "text": "Artikel 5.1: De maximale subsidie bedraagt €2.500 per vereniging per jaar"},
            {"id": 7, "text": "Artikel 5.2: De subsidie bedraagt maximaal 40% van de totale kosten"},
            {"id": 8, "text": "Artikel 6.1: De vereniging moet jeugdleden actief betrekken (onder 18 jaar)"},
            {"id": 9, "text": "Artikel 7.1: Een activiteitenplan voor het komende jaar moet worden overgelegd"},
            {"id": 10, "text": "Artikel 8.1: De aanvraag moet vóór 1 maart van het betreffende jaar zijn ingediend"}
        ],
        "summary": "Subsidieregeling voor geregistreerde sportverenigingen. Maximaal €2.500 per jaar, 40% van kosten. Focus op jeugd en lokale betrokkenheid."
    }
    
    # Regeling 3: MKB Digitalisering Subsidie
    regeling3 = {
        "criteria": [
            {"id": 1, "text": "Artikel 2.1: De aanvrager moet een MKB-onderneming zijn (minder dan 250 medewerkers)"},
            {"id": 2, "text": "Artikel 2.2: Het bedrijf moet gevestigd zijn in de gemeente"},
            {"id": 3, "text": "Artikel 3.1: De subsidie is voor digitalisering en automatiseringsprojecten"},
            {"id": 4, "text": "Artikel 3.2: Het project moet leiden tot efficiëntiewinst of innovatie"},
            {"id": 5, "text": "Artikel 4.1: Minimale investering van €10.000 is vereist"},
            {"id": 6, "text": "Artikel 5.1: De maximale subsidie bedraagt €25.000 per onderneming"},
            {"id": 7, "text": "Artikel 5.2: De subsidie bedraagt maximaal 30% van de totale investering"},
            {"id": 8, "text": "Artikel 6.1: Het project moet binnen 12 maanden worden afgerond"},
            {"id": 9, "text": "Artikel 7.1: Er moet een business case worden overgelegd"},
            {"id": 10, "text": "Artikel 8.1: Het bedrijf mag maximaal 1 keer per 3 jaar subsidie aanvragen"}
        ],
        "summary": "Subsidieregeling voor digitalisering van MKB-ondernemingen. Maximaal €25.000, 30% van investering. Minimum investering €10.000."
    }
    
    try:
        # Maak de regelingen aan
        id1 = storage.save_regulation(
            "Gemeente Evenementen Subsidie",
            regeling1,
            "Subsidieregeling voor het ondersteunen van lokale evenementen die bijdragen aan sociale cohesie en culturele ontwikkeling binnen de gemeente."
        )
        print(f"✓ Regeling 1 aangemaakt: Gemeente Evenementen Subsidie (ID: {id1})")
        
        id2 = storage.save_regulation(
            "Sportvereniging Subsidie",
            regeling2,
            "Subsidieregeling voor sportverenigingen om materialen, accommodatie en training te ondersteunen, met focus op jeugdparticipatie."
        )
        print(f"✓ Regeling 2 aangemaakt: Sportvereniging Subsidie (ID: {id2})")
        
        id3 = storage.save_regulation(
            "MKB Digitalisering Subsidie",
            regeling3,
            "Subsidieregeling voor het midden- en kleinbedrijf om digitalisering- en automatiseringsprojecten te stimuleren."
        )
        print(f"✓ Regeling 3 aangemaakt: MKB Digitalisering Subsidie (ID: {id3})")
        
        print(f"\n🎉 Alle {len([id1, id2, id3])} voorbeeldreglingen succesvol aangemaakt!")
        print("Deze zijn nu beschikbaar in de dropdown voor alle gebruikers.")
        
    except Exception as e:
        print(f"❌ Fout bij aanmaken regelingen: {e}")
        raise

def list_existing_regulations():
    """Toon bestaande regelingen"""
    storage = SubsidyFileStorage()
    regulations = storage.list_available_regulations()
    
    if not regulations:
        print("Geen bestaande regelingen gevonden.")
        return
        
    print(f"Bestaande regelingen ({len(regulations)}):")
    for reg in regulations:
        print(f"  - {reg['name']} (ID: {reg['id'][:8]}..., {reg['criteria_count']} criteria)")

if __name__ == "__main__":
    print("🏛️  GovChat-NL Standaard Regelingen Setup")
    print("=" * 50)
    
    # Toon bestaande regelingen
    print("\n📋 Huidige situatie:")
    list_existing_regulations()
    
    # Vraag bevestiging
    print(f"\n🔧 Wilt u 3 voorbeeldreglingen aanmaken?")
    print("   1. Gemeente Evenementen Subsidie")
    print("   2. Sportvereniging Subsidie") 
    print("   3. MKB Digitalisering Subsidie")
    
    response = input("\nDoorgaan? (j/N): ").lower().strip()
    
    if response in ['j', 'ja', 'yes', 'y']:
        print("\n⚙️  Regelingen aanmaken...")
        create_example_regulations()
        
        print("\n📋 Nieuwe situatie:")
        list_existing_regulations()
        
    else:
        print("❌ Geannuleerd.")
