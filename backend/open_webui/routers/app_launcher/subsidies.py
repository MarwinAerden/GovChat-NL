import json # Import json module
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Any, Optional, List, Dict, Union
from datetime import datetime
import json
import hashlib
import traceback
import os
import time

from open_webui.utils.chat import generate_chat_completion
from open_webui.utils.auth import get_current_user
from open_webui.utils.subsidy_storage import SubsidyFileStorage  # Importeer de nieuwe helper

# Initialiseer de router
router = APIRouter()

# Initialiseer de storage helper
subsidy_storage = SubsidyFileStorage()

# Model voor subsidiecriteria
class SubsidyCriterion(BaseModel):
    id: int
    text: str

class SubsidyResponse(BaseModel):
    criteria: List[SubsidyCriterion]
    summary: Optional[str] = None
    savedId: Optional[str] = None
    timestamp: Optional[str] = None
    name: Optional[str] = None

class SubsidyQueryInput(BaseModel):
    user_input: str
    model: Optional[str] = None

class SubsidyQueryOutput(BaseModel):
    criteria: List[SubsidyCriterion]
    summary: Optional[str] = None

# --- Modellen voor beoordeling subsidieaanvraag ---
class SubsidyApplicationInput(BaseModel):
    application_text: str
    criteria: List[SubsidyCriterion]
    model: Optional[str] = None

class SubsidyAssessmentItem(BaseModel):
    Criterium: str
    Score: Union[str, int]  # Aanpassen om zowel strings als integers te accepteren
    Toelichting: str

class SubsidyAssessmentOutput(BaseModel):
    assessment: Dict[str, SubsidyAssessmentItem]  # {"1": {...}, "2": {...}, ...}

# --- Aangepaste System Prompt voor JSON Output ---
SYSTEM_PROMPT = """Je bent een expert op het gebied van Nederlandse subsidies en subsidiebeoordelingen. Je taak is het grondig analyseren van subsidiereglementen om alle relevante beoordelingscriteria te identificeren.

**ANALYSEOPDRACHT:**
Analyseer de subsidieregeling systematisch en identificeer:
- Alle formele vereisten (wie kan aanvragen, waar, wanneer)
- Inhoudelijke criteria (waaraan moet het project/evenement voldoen)
- Financiële voorwaarden (budgetlimieten, eigen bijdrage, etc.)
- Procedurele eisen (benodigde documenten, deadlines)
- Uitsluitingsgronden of afwijzingsredenen

**BELANGRIJKE RICHTLIJNEN:**
1. Extraheer ALLE artikelen en subelementen uit de regeling
2. Formuleer elk criterium als concrete beoordelingsvraag
3. Behoud de originele artikelnummering waar mogelijk
4. Splits complexe artikelen op in afzonderlijke criteria
5. Voeg nuances en uitzonderingen toe uit toelichtingen

**VOORBEELDEN VAN GOEDE CRITERIA:**
- "Artikel 3.1: De aanvrager moet een rechtspersoon zijn gevestigd in Nederland"
- "Artikel 4.2: Het evenement moet plaatsvinden binnen de gemeente"
- "Artikel 5.1: Minimaal 50% van de kosten moet gedekt worden door eigen middelen"

**UITVOERFORMAT:**
Geef UITSLUITEND een geldig JSON-object terug:
{
  "criteria": [
    { "id": 1, "text": "Artikel X.Y: [Concreet en toetsbaar criterium]" },
    { "id": 2, "text": "Artikel X.Z: [Concreet en toetsbaar criterium]" }
  ],
  "summary": "Bondige samenvatting van de regeling: doelgroep, doel, belangrijkste voorwaarden en maximale subsidie."
}

**KWALITEITSEISEN:**
- Elk criterium moet toetsbaar en meetbaar zijn
- Gebruik duidelijke, concrete taal
- Vermijd vage termen zoals "redelijk" of "voldoende"
- Neem ALLE relevante bepalingen op
- Nummering moet opeenvolgend zijn (1, 2, 3, ...)

Als geen criteria identificeerbaar zijn: { "criteria": [], "summary": "Geen beoordelingscriteria gevonden in het document." }

Geef ALLEEN het JSON-object terug, geen andere tekst."""

# --- System Prompt voor beoordeling subsidieaanvraag ---
ASSESSMENT_SYSTEM_PROMPT = """Je bent een ervaren subsidiebeoordelaar die aanvragen toetst aan formele reglementen. Je doel is een objectieve, grondige beoordeling per criterium.

**BEOORDELINGSOPDRACHT:**
Voor elk criterium geef je:
1. **Score (0-10)**: Mate waarin het criterium wordt vervuld
2. **Toelichting**: Concrete onderbouwing van de score

**SCORINGSRICHTLIJNEN:**
- **0-2**: Criterium wordt niet of nauwelijks vervuld, ernstige tekortkomingen
- **3-4**: Criterium wordt onvoldoende vervuld, belangrijke tekortkomingen  
- **5-6**: Criterium wordt matig vervuld, verbeteringen nodig
- **7-8**: Criterium wordt goed vervuld, kleine verbeterpunten mogelijk
- **9-10**: Criterium wordt uitstekend/volledig vervuld

**SPECIALE GEVALLEN:**
- **Afwijzingsgronden**: Score 10 = grond NIET van toepassing, Score 0 = grond WEL van toepassing
- **"Onzeker"**: Gebruik alleen bij ontbrekende essentiële informatie

**BEOORDELINGSPRINCIPES:**
1. Beoordeel ALLEEN op basis van de verstrekte aanvraag
2. Maak GEEN aannames over ontbrekende informatie
3. Wees strikt maar fair in je beoordeling
4. Geef concrete, actionable feedback in de toelichting
5. Verwijs naar specifieke onderdelen van de aanvraag

**TOELICHTING KWALITEIT:**
- Citeer relevante passages uit de aanvraag
- Leg uit waarom de score is toegekend
- Geef concrete suggesties voor verbetering (bij lage scores)
- Benoem wat goed gedaan is (bij hoge scores)

**UITVOERFORMAT:**
```json
{
    "1": {
        "Criterium": "[Exacte tekst van het criterium]",
        "Score": "[0-10 of 'Onzeker']",
        "Toelichting": "[Concrete onderbouwing met verwijzing naar aanvraag]"
    },
    "2": {
        "Criterium": "[Exacte tekst van het criterium]", 
        "Score": "[0-10 of 'Onzeker']",
        "Toelichting": "[Concrete onderbouwing met verwijzing naar aanvraag]"
    }
}
```

**VOORBEELD TOELICHTING:**
"Score 6: In de aanvraag wordt vermeld dat het evenement plaatsvindt op [datum], wat binnen de vereiste periode valt. Echter ontbreekt een duidelijke planning van activiteiten, waardoor onduidelijk is of alle geplande onderdelen realiseerbaar zijn binnen de beschikbare tijd."

Beoordeel ALLE criteria systematisch. Geef ALLEEN het JSON-object terug."""

# --- System Prompt voor samenvatting subsidieaanvraag ---
SUMMARY_SYSTEM_PROMPT = """Je bent een gespecialiseerde subsidieadministratie-expert die aanvragen samenvat voor verdere verwerking.

**SAMENVATTINGSOPDRACHT:**
Extraheer systematisch de kerngegevens uit de subsidieaanvraag voor administratieve verwerking.

**TE IDENTIFICEREN GEGEVENS:**
1. **Aanvrager**: Volledige naam organisatie/persoon (inclusief rechtsvorm indien vermeld)
2. **Datum_aanvraag**: Datum van indiening aanvraag (DD-MM-JJJJ formaat)
3. **Datum_evenement**: Datum van het project/evenement waarvoor subsidie wordt aangevraagd
4. **Bedrag**: Het exacte aangevraagde subsidiebedrag (inclusief valuta)
5. **Samenvatting**: Kernachtige beschrijving van doel en aard van de aanvraag

**EXTRACTIERICHTLIJNEN:**
- Zoek naar formele gegevens (NAW-gegevens, datums, bedragen)
- Let op ondertekening, briefhoofd, formuliervelden
- Identificeer het hoofddoel van de subsidieaanvraag
- Zoek naar projectbeschrijvingen, evenementdetails
- Check op totaalbedragen, kostenoverzichten

**DATUMFORMATEN:**
- Converteer naar DD-MM-JJJJ (bijv. 15-06-2024)
- Bij datumbereiken: gebruik startdatum of vermeld "[startdatum] tot [einddatum]"
- Bij onbekende datum: "Onbekend"

**BEDRAGFORMATEN:**
- Gebruik exacte bedragen: "€ 5.000,00" 
- Bij bereiken: "€ 3.000 - € 5.000"
- Bij percentage van totaal: "€ 2.500 (50% van € 5.000 totaal)"

**SAMENVATTING KWALITEIT:**
- Maximaal 2-3 zinnen
- Focus op: WAT (type project/evenement), VOOR WIE (doelgroep), WAAROM (doel)
- Gebruik concrete termen, vermijd jargon

**UITVOERFORMAT:**
```json
{
  "Aanvrager": "[Volledige naam + rechtsvorm indien bekend]",
  "Datum_aanvraag": "[DD-MM-JJJJ of 'Onbekend']",
  "Datum_evenement": "[DD-MM-JJJJ of periode of 'Onbekend']", 
  "Bedrag": "[€ X.XXX,XX of 'Onbekend']",
  "Samenvatting": "[Korte, concrete beschrijving van aanvraag en doel]"
}
```

**VOORBEELDEN:**
- Aanvrager: "Stichting Dorpsfeest Voorbeeld"
- Datum_evenement: "15-07-2024 tot 17-07-2024" 
- Bedrag: "€ 2.500,00"
- Samenvatting: "Organisatie van jaarlijks dorpsfeest met lokale artiesten en activiteiten voor alle leeftijden ter bevordering van sociale cohesie."

Bij ontbrekende informatie: gebruik "Onbekend". Geef ALLEEN het JSON-object terug."""

# --- System Prompt voor eindrapport ---
REPORT_SYSTEM_PROMPT = """Je bent een senior subsidieadviseur die definitieve beslissingen voorbereidt. Je taak is het opstellen van een samenhangend eindadvies.

**RAPPORTAGEOPDRACHT:**
Combineer de aanvraaggegevens en beoordelingsresultaten tot een professioneel advies voor de beslissingsbevoegde instantie.

**ANALYSEKADER:**
1. **Kwantitatieve analyse**: Scores per criterium, gemiddelde scores, kritieke tekortkomingen
2. **Kwalitatieve analyse**: Sterke punten, verbeterpunten, overall kwaliteit aanvraag  
3. **Risicoanalyse**: Wat kan misgaan, welke onderdelen zijn onzeker
4. **Proportionaliteit**: Is gevraagde bedrag passend bij de voorgestelde activiteiten

**BESLISSINGSCATEGORIEËN:**
- **TOEKENNEN**: Alle criteria score ≥7, geen kritieke tekortkomingen
- **GEDEELTELIJK TOEKENNEN**: Meeste criteria voldoende, maar beperkte financiële middelen of kleinere tekortkomingen  
- **VOORWAARDELIJK TOEKENNEN**: Voldoende potentieel, maar aanvullende informatie/verbeteringen nodig
- **AFWIJZEN**: Kritieke criteria onvoldoende (score <5) of fundamentele bezwaren

**BEDRAGADVIES OVERWEGINGEN:**
- Bij gedeeltelijke toekenning: proportioneel verlagen
- Bij hoge risico's: buffer inbouwen  
- Bij uitstekende aanvragen: volledig toekennen
- Motiveer afwijkingen van aangevraagde bedrag

**RAPPORTSTRUCTUUR:**

**Samenvatting** (100-150 woorden):
- Korte schets van de aanvraag en belangrijkste bevindingen
- Vermelding van sterke punten en hoofdkritiekpunten
- Globale indruk van de aanvraagkwaliteit

**Eindoordeel** (150-200 woorden):  
- Duidelijke beslissing: toekennen/gedeeltelijk/voorwaardelijk/afwijzen
- Concrete motivering op basis van criteriumscores
- Specifieke aandachtspunten voor lage scores (<7)
- Eventuele voorwaarden of verbetermaatregelen
- Onderbouwing van proportionaliteit en haalbaarheid

**Bedrag** (exacte financiële specificatie):
- Bij toekenning: "€ [bedrag] (volledig aangevraagde bedrag)"
- Bij gedeeltelijke toekenning: "€ [bedrag] (XX% van aangevraagd bedrag van € [oorspronkelijk])"
- Bij afwijzing: "€ 0,00 (aanvraag niet gehonoreerd)"
- Motivering van bedragkeuze

**UITVOERFORMAT:**
```json
{
  "Samenvatting": "[Beknopte analyse van aanvraag en belangrijkste bevindingen]",
  "Eindoordeel": "[Duidelijke beslissing met uitgebreide motivering en eventuele voorwaarden]", 
  "Bedrag": "[Exact aanbevolen bedrag met specificatie en motivering]"
}
```

**TOONZETTING:**
- Professioneel en objectief
- Constructief bij kritiekpunten  
- Helder en besluitvaardig
- Respectvol naar aanvrager

Geef ALLEEN het JSON-object terug."""

# --- Model voor samenvatting output ---
class SubsidySummaryOutput(BaseModel):
    Aanvrager: str
    Datum_aanvraag: str
    Datum_evenement: str
    Bedrag: str
    Samenvatting: str

# --- Model voor gecombineerd rapport input ---
class SubsidyCombinedReportInput(BaseModel):
    assessment_results: Dict[str, SubsidyAssessmentItem]
    summary_result: SubsidySummaryOutput
    model: Optional[str] = None
    
    class Config:
        # Dit maakt het model flexibeler bij JSON serialisatie/deserialisatie
        arbitrary_types_allowed = True

# --- Model voor rapport output ---
class SubsidyReportOutput(BaseModel):
    Samenvatting: str
    Eindoordeel: str
    Bedrag: str

@router.post("/save", response_model=Dict[str, Any])
async def save_subsidy_data(
    request: Request,
    data: SubsidyResponse,
    user = Depends(get_current_user)
):
    """Sla subsidiecriteria op in een bestand"""
    print(f"save_subsidy_data aangeroepen voor gebruiker {user.id}")
    
    try:
        # Removed deduplication check
        
        # Wanneer criteria in Pydantic model zitten, eerst naar dict converteren
        criteria_list = []
        if data.criteria:
            try:
                # Voor Pydantic v2
                criteria_list = [c.model_dump() for c in data.criteria]
            except AttributeError:
                try:
                    # Voor Pydantic v1
                    criteria_list = [c.dict() for c in data.criteria]
                except AttributeError:
                    # Fallback - Probeer direct als dictionary te gebruiken
                    criteria_list = [{"id": c.id, "text": c.text} for c in data.criteria]
        
        # Bereid criteria voor voor opslag
        criteria_data = {
            "criteria": criteria_list,
            "summary": data.summary,
            "is_selection": getattr(data, 'isSelection', False)  # Behoud is_selection flag
        }
        
        # Als het een selectie is, geef het een speciale naam
        name = data.name
        if getattr(data, 'isSelection', False) and not name.startswith("Selectie:"):
            name = f"Selectie: {name or datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Sla op met de helper
        subsidy_id = subsidy_storage.save_criteria(
            user_id=user.id, 
            criteria=criteria_data,
            name=name
        )
        
        print(f"Succesvol opgeslagen met ID: {subsidy_id}")
        
        return {
            "success": True,
            "id": subsidy_id,
            "message": "Subsidie criteria opgeslagen"
        }
    
    except Exception as e:
        print(f"Error bij opslaan subsidiecriteria: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Kon criteria niet opslaan: {str(e)}")


@router.get("/list", response_model=List[SubsidyResponse])
async def list_subsidy_data(
    request: Request,
    user = Depends(get_current_user)
):
    """Haal alle opgeslagen criteria op voor een gebruiker"""
    print(f"list_subsidy_data called for user {user.id}")
    
    try:
        # Haal de lijst op via de helper
        criteria_list = subsidy_storage.list_criteria_for_user(user_id=user.id)
        
        print(f"Found {len(criteria_list)} items for user {user.id}")
        
        # Converteer naar het response model formaat
        result = []
        for item in criteria_list:
            try:
                criteria_objects = []
                for c in item.get("criteria", []):
                    # Zorg dat criteria de juiste structuur heeft
                    if isinstance(c, dict) and "id" in c and "text" in c:
                        criteria_objects.append(SubsidyCriterion(**c))
                
                result.append(SubsidyResponse(
                    criteria=criteria_objects,
                    summary=item.get("summary"),
                    savedId=item.get("id"),
                    timestamp=item.get("timestamp"),
                    name=item.get("name")
                ))
            except Exception as e:
                print(f"Error converting item: {e}, item: {item}")
                continue
            
        print(f"Returning {len(result)} formatted items")
        return result
        
    except Exception as e:
        print(f"Error in list_subsidy_data: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Kon criteria niet ophalen: {str(e)}")


@router.delete("/{subsidy_id}", response_model=Dict[str, Any])
async def delete_subsidy_data(
    request: Request,
    subsidy_id: str,
    user = Depends(get_current_user)
):
    """Verwijder opgeslagen criteria"""
    try:
        # Verwijder via de helper
        success = subsidy_storage.delete_criteria(
            subsidy_id=subsidy_id,
            user_id=user.id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Subsidiecriteria niet gevonden")
            
        return {
            "success": True,
            "message": "Subsidiecriteria verwijderd"
        }
        
    except HTTPException:
        raise
        
    except Exception as e:
        print(f"Error bij verwijderen subsidiecriteria: {e}")
        raise HTTPException(status_code=500, detail=f"Kon criteria niet verwijderen: {str(e)}")

@router.post("/query", response_model=SubsidyQueryOutput)
async def handle_subsidy_query(
    request: Request,
    query_input: SubsidyQueryInput,
    user = Depends(get_current_user)
):
    """
    Neemt een subsidieregeling, extraheert criteria via LLM als JSON,
    slaat het resultaat op en retourneert de gestructureerde data.
    """
    if not query_input.user_input:
        raise HTTPException(status_code=400, detail="Input mag niet leeg zijn.")

    # Removed deduplication check using input_hash
    
    # --- Model Selectie ---
    DEFAULT_MODEL_FALLBACK = "openai/gpt-4o" # Pas aan indien nodig
    model_to_use = query_input.model or DEFAULT_MODEL_FALLBACK
    if not model_to_use:
         raise HTTPException(status_code=400, detail="Model niet gespecificeerd.")

    DEFAULT_TEMPERATURE = 0.5 # Lagere temperatuur voor consistentere JSON

    form_data = {
        "model": model_to_use,
        "stream": False,
        "temperature": DEFAULT_TEMPERATURE,
        "response_format": { "type": "json_object" }, # Vraag expliciet om JSON (indien ondersteund door LLM/API)
        "messages": [
            { "role": "system", "content": SYSTEM_PROMPT },
            { "role": "user", "content": query_input.user_input }
        ]
    }

    try:
        completion_result = await generate_chat_completion(
            request=request, form_data=form_data, user=user
        )

        raw_response_content = ""
        if completion_result and "choices" in completion_result and len(completion_result["choices"]) > 0:
            message = completion_result["choices"][0].get("message", {})
            raw_response_content = message.get("content", "").strip()

        if not raw_response_content:
            raise HTTPException(status_code=500, detail="Lege response van LLM.")

        # --- Parse de JSON response van de LLM ---
        try:
            # Soms zit de JSON in een code block, probeer dat te strippen
            if raw_response_content.startswith("```json"):
                raw_response_content = raw_response_content[7:]
                
            if raw_response_content.endswith("```"):
                raw_response_content = raw_response_content[:-3]
                
            raw_response_content = raw_response_content.strip()

            parsed_data = json.loads(raw_response_content)

            # Valideer de structuur (basis check)
            if "criteria" not in parsed_data or not isinstance(parsed_data["criteria"], list):
                raise ValueError("Ongeldige JSON structuur: 'criteria' lijst ontbreekt of is geen lijst.")

            # Creëer het output object
            output_data = SubsidyQueryOutput(
                criteria=[SubsidyCriterion(**item) for item in parsed_data.get("criteria", [])],
                summary=parsed_data.get("summary")
            )

            # NIET automatisch opslaan - alleen wanneer gebruiker expliciet op "Sla Resultaat Op" klikt
            # De save gebeurt nu via de /save endpoint wanneer gebruiker bewust opslaat

            return output_data

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"Fout bij parsen LLM JSON response: {e}")
            print(f"Ontvangen raw response:\n{raw_response_content}")
            raise HTTPException(status_code=500, detail=f"Kon de LLM response niet correct verwerken: {e}")

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error calling generate_chat_completion or processing: {e}")
        raise HTTPException(status_code=500, detail=f"Interne serverfout: {str(e)}")

@router.post("/assess", response_model=SubsidyAssessmentOutput)
async def handle_subsidy_assessment(
    request: Request,
    assessment_input: SubsidyApplicationInput,
    user = Depends(get_current_user),
):
    """
    Beoordeelt een subsidieaanvraag tegen een set van eerder geëxtraheerde criteria 
    m.b.v. een LLM en geeft een gestructureerde beoordeling terug.
    """
    if not assessment_input.application_text:
        raise HTTPException(status_code=400, detail="Subsidieaanvraag tekst mag niet leeg zijn.")
    if not assessment_input.criteria or len(assessment_input.criteria) == 0:
        raise HTTPException(status_code=400, detail="Er zijn geen criteria opgegeven om te beoordelen.")

    # Model Selectie met betere foutafhandeling
    DEFAULT_MODEL_FALLBACK = "openai/gpt-4o"
    model_to_use = None
    
    # Probeer een model te krijgen, met uitgebreide foutafhandeling
    try:
        model_to_use = assessment_input.model
        # Als model leeg is of None, gebruik fallback
        if not model_to_use:
            model_to_use = DEFAULT_MODEL_FALLBACK
            
        # Log het gebruikte model voor debugging
        print(f"Model dat gebruikt wordt voor beoordeling: {model_to_use}")
    except Exception as e:
        print(f"Fout bij het selecteren van het model: {e}")
        model_to_use = DEFAULT_MODEL_FALLBACK
        
    if not model_to_use:
        raise HTTPException(status_code=400, detail="Kon geen geldig model selecteren voor de beoordeling.")

    DEFAULT_TEMPERATURE = 0.2  # Lagere temperatuur voor meer consistente beoordelingen

    # Bereid criteria voor in een genummerde lijst voor de LLM
    criteria_context = []
    for criterion in assessment_input.criteria:
        criteria_context.append(f"Criterium {criterion.id}: {criterion.text}")
    
    criteria_text = "\n".join(criteria_context)

    user_message_content = f"""Beoordeel de volgende subsidieaanvraag:
--- START SUBSIDIEAANVRAAG ---
{assessment_input.application_text}
--- EINDE SUBSIDIEAANVRAAG ---

Aan de hand van de volgende criteria uit de subsidieregeling:
--- START CRITERIA SUBSIDIEREGELING ---
{criteria_text}
--- EINDE CRITERIA SUBSIDIEREGELING ---

Volg de instructies in de system prompt nauwkeurig voor de beoordeling en de outputstructuur.
Zorg ervoor dat elk criterium uit de lijst hierboven wordt beoordeeld.
Het "Criterium" veld in je JSON output MOET de volledige tekst van het beoordeelde criterium bevatten.
De output moet een JSON-object zijn waarbij de sleutels genummerd zijn (als strings, "1", "2", etc.) overeenkomend met de nummering van de criteria hierboven.
"""

    form_data = {
        "model": model_to_use,
        "stream": False,
        "temperature": DEFAULT_TEMPERATURE,
        "response_format": { "type": "json_object" },
        "messages": [
            { "role": "system", "content": ASSESSMENT_SYSTEM_PROMPT },
            { "role": "user", "content": user_message_content }
        ]
    }

    try:
        completion_result = await generate_chat_completion(
            request=request, form_data=form_data, user=user
        )

        raw_response_content = ""
        if completion_result and "choices" in completion_result and len(completion_result["choices"]) > 0:
            message = completion_result["choices"][0].get("message", {})
            raw_response_content = message.get("content", "").strip()

        if not raw_response_content:
            raise HTTPException(status_code=500, detail="Lege response van LLM.")

        # Parse de JSON response van de LLM
        try:
            # Soms zit de JSON in een code block, probeer dat te strippen
            if raw_response_content.startswith("```json"):
                raw_response_content = raw_response_content[7:]
                
            if raw_response_content.endswith("```"):
                raw_response_content = raw_response_content[:-3]
                
            raw_response_content = raw_response_content.strip()

            parsed_data = json.loads(raw_response_content)
            
            # Valideer de structuur (basis check)
            if not parsed_data or not isinstance(parsed_data, dict):
                raise ValueError("Ongeldige JSON structuur: verwacht een dictionary met assessment items.")

            # Converteer scores naar string indien nodig
            for key, value in parsed_data.items():
                if isinstance(value, dict) and "Score" in value:
                    parsed_data[key]["Score"] = str(parsed_data[key]["Score"])

            assessment_output = SubsidyAssessmentOutput(assessment=parsed_data)
            return assessment_output

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"Fout bij parsen LLM JSON response: {e}")
            print(f"Ontvangen raw response:\n{raw_response_content}")
            raise HTTPException(status_code=500, detail=f"Kon de LLM response niet correct verwerken: {e}")

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in handle_subsidy_assessment: {e}")
        raise HTTPException(status_code=500, detail=f"Interne serverfout bij beoordeling: {str(e)}")

@router.post("/summarize", response_model=SubsidySummaryOutput)
async def handle_subsidy_summary(
    request: Request,
    assessment_input: SubsidyApplicationInput,
    user = Depends(get_current_user),
):
    """
    Genereert een beknopte samenvatting van een subsidieaanvraag
    met gestructureerde informatie zoals aanvrager, data en bedrag.
    """
    if not assessment_input.application_text:
        raise HTTPException(status_code=400, detail="Subsidieaanvraag tekst mag niet leeg zijn.")

    # Model Selectie met betere foutafhandeling
    DEFAULT_MODEL_FALLBACK = "openai/gpt-4o"
    model_to_use = assessment_input.model or DEFAULT_MODEL_FALLBACK
    
    if not model_to_use:
        print(f"Geen model gespecificeerd, gebruik fallback: {DEFAULT_MODEL_FALLBACK}")
        model_to_use = DEFAULT_MODEL_FALLBACK
        
    print(f"Model dat gebruikt wordt voor samenvatting: {model_to_use}")

    DEFAULT_TEMPERATURE = 0.3  # Temperatuur voor de samenvatting

    user_message_content = f"""Maak een samenvatting van de volgende subsidieaanvraag:
--- START SUBSIDIEAANVRAAG ---
{assessment_input.application_text}
--- EINDE SUBSIDIEAANVRAAG ---

Identificeer de aanvrager, datums, bedrag en maak een beknopte samenvatting.
Zorg ervoor dat je de JSON output structuur volgt zoals beschreven in de systeemprompt.
"""

    form_data = {
        "model": model_to_use,
        "stream": False,
        "temperature": DEFAULT_TEMPERATURE,
        "response_format": { "type": "json_object" },
        "messages": [
            { "role": "system", "content": SUMMARY_SYSTEM_PROMPT },
            { "role": "user", "content": user_message_content }
        ]
    }

    try:
        completion_result = await generate_chat_completion(
            request=request, form_data=form_data, user=user
        )

        raw_response_content = ""
        if completion_result and "choices" in completion_result and len(completion_result["choices"]) > 0:
            message = completion_result["choices"][0].get("message", {})
            raw_response_content = message.get("content", "").strip()

        if not raw_response_content:
            raise HTTPException(status_code=500, detail="Lege response van LLM bij samenvatting.")

        # Parse de JSON response van de LLM
        try:
            # Verwijder eventuele markdown code block markering
            if raw_response_content.startswith("```json"):
                raw_response_content = raw_response_content[7:]
                
            if raw_response_content.endswith("```"):
                raw_response_content = raw_response_content[:-3]
                
            raw_response_content = raw_response_content.strip()

            parsed_data = json.loads(raw_response_content)
            summary_output = SubsidySummaryOutput(**parsed_data)
            return summary_output

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"Fout bij parsen LLM JSON response voor samenvatting: {e}")
            print(f"Ontvangen raw response:\n{raw_response_content}")
            raise HTTPException(status_code=500, detail=f"Kon de LLM samenvattingsresponse niet correct verwerken: {e}")

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in handle_subsidy_summary: {e}")
        raise HTTPException(status_code=500, detail=f"Interne serverfout bij samenvatting: {str(e)}")

@router.post("/generate_report", response_model=SubsidyReportOutput)
async def handle_subsidy_report(
    request: Request,
    report_input: SubsidyCombinedReportInput,
    user = Depends(get_current_user),
):
    """
    Genereert een eindrapport door de samenvatting en beoordelingsresultaten te combineren.
    """
    print(f"DEBUG: handle_subsidy_report aangeroepen")
    print(f"DEBUG: assessment_results type: {type(report_input.assessment_results)}")
    print(f"DEBUG: assessment_results inhoud: {report_input.assessment_results}")
    print(f"DEBUG: summary_result type: {type(report_input.summary_result)}")
    
    if not report_input.assessment_results:
        raise HTTPException(status_code=400, detail="Beoordelingsresultaten zijn vereist voor het rapport.")
    if not report_input.summary_result:
        raise HTTPException(status_code=400, detail="Samenvattingsresultaat is vereist voor het rapport.")

    # Model Selectie
    DEFAULT_MODEL_FALLBACK = "openai/gpt-4o"
    model_to_use = report_input.model or DEFAULT_MODEL_FALLBACK
    
    if not model_to_use:
        print(f"Geen model gespecificeerd, gebruik fallback: {DEFAULT_MODEL_FALLBACK}")
        model_to_use = DEFAULT_MODEL_FALLBACK
        
    print(f"Model dat gebruikt wordt voor eindrapport: {model_to_use}")

    DEFAULT_TEMPERATURE = 0.4  # Iets hogere temperatuur voor meer creativiteit in het rapport    # Bereid de JSON input voor de LLM prompt voor - Met betere foutafhandeling
    summary_formatted = ""
    assessment_formatted = ""
    
    try:
        print(f"DEBUG: Type van summary_result: {type(report_input.summary_result)}")
        print(f"DEBUG: Type van assessment_results: {type(report_input.assessment_results)}")
        
        # Probeer eerst de summary_result als een Python dict te krijgen
        try:
            # In Pydantic v2+ gebruik je model_dump() in plaats van dict()
            summary_dict = report_input.summary_result.model_dump()
        except AttributeError:
            try:
                summary_dict = report_input.summary_result.dict()
            except AttributeError:
                summary_dict = dict(report_input.summary_result)
                
        print(f"DEBUG: Summary dict: {summary_dict}")
        summary_formatted = json.dumps(summary_dict, ensure_ascii=False)
        
        # Nu de assessment results - Met betere foutafhandeling
        try:
            # Assessment results moet een dict zijn van SubsidyAssessmentItem objecten
            assessment_dict = {}
            for key, value in report_input.assessment_results.items():
                if hasattr(value, 'model_dump'):
                    assessment_dict[key] = value.model_dump()
                elif hasattr(value, 'dict'):
                    assessment_dict[key] = value.dict()
                elif isinstance(value, dict):
                    assessment_dict[key] = value
                else:
                    # Fallback voor onbekende types
                    assessment_dict[key] = {
                        "Criterium": getattr(value, 'Criterium', str(value)),
                        "Score": getattr(value, 'Score', 'Onbekend'),
                        "Toelichting": getattr(value, 'Toelichting', 'Geen toelichting')
                    }
            
            print(f"DEBUG: Assessment dict: {assessment_dict}")
            assessment_formatted = json.dumps(assessment_dict, ensure_ascii=False)
        except Exception as e:
            print(f"Fout bij formatteren assessment: {e}")
            print(f"DEBUG: Assessment results inhoud: {report_input.assessment_results}")
            raise HTTPException(status_code=500, detail=f"Kon de beoordelingsresultaten niet formatteren: {str(e)}")
        
    except Exception as e:
        print(f"Algemene fout bij het voorbereiden van input data: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Kon de input data niet correct voorbereiden voor het rapport: {str(e)}")

    if not summary_formatted or not assessment_formatted:
        raise HTTPException(status_code=500, detail="Kon de input data niet formatteren voor het rapport.")

    user_message_content = f"""Maak een eindrapport voor de volgende subsidieaanvraag.

Informatie over de aanvraag (samenvatting):
```json
{summary_formatted}
```

Beoordeling van de subsidieaanvraag:
```json
{assessment_formatted}
```

Analyseer de samenvatting en beoordeling, en genereer een eindrapport volgens de structuur in de system prompt.
Focus specifiek op criteria die niet (volledig) aan de eisen voldoen (scores lager dan 8), 
en leg uit of deze nog verbeterd kunnen worden.
"""

    form_data = {
        "model": model_to_use,
        "stream": False,
        "temperature": DEFAULT_TEMPERATURE,
        "response_format": { "type": "json_object" },
        "messages": [
            { "role": "system", "content": REPORT_SYSTEM_PROMPT },
            { "role": "user", "content": user_message_content }
        ]
    }

    try:
        completion_result = await generate_chat_completion(
            request=request, form_data=form_data, user=user
        )

        raw_response_content = ""
        if completion_result and "choices" in completion_result and len(completion_result["choices"]) > 0:
            message = completion_result["choices"][0].get("message", {})
            raw_response_content = message.get("content", "").strip()

        if not raw_response_content:
            raise HTTPException(status_code=500, detail="Lege response van LLM bij het genereren van het rapport.")

        # Parse de JSON response van de LLM
        try:
            # Verwijder eventuele markdown code block markering
            if raw_response_content.startswith("```json"):
                raw_response_content = raw_response_content[7:]
            if raw_response_content.endswith("```"):
                raw_response_content = raw_response_content[:-3]
            raw_response_content = raw_response_content.strip()

            parsed_data = json.loads(raw_response_content)
            
            # Validatie via Pydantic model
            report_output = SubsidyReportOutput(**parsed_data)
            return report_output

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"Fout bij parsen LLM JSON response voor rapport: {e}")
            print(f"Ontvangen raw response LLM (rapport):\n{raw_response_content}")
            raise HTTPException(status_code=500, detail=f"Kon de LLM rapportresponse niet correct verwerken: {e}")

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in handle_subsidy_report: {e}")
        raise HTTPException(status_code=500, detail=f"Interne serverfout bij het genereren van het rapport: {str(e)}")

@router.post("/complete_assessment", response_model=Dict[str, Any])
async def handle_complete_assessment(
    request: Request,
    assessment_input: SubsidyApplicationInput,
    user = Depends(get_current_user),
):
    """
    Voert alle drie de stappen uit: beoordeling, samenvatting en eindrapport, in één API-call.
    """
    if not assessment_input.application_text:
        raise HTTPException(status_code=400, detail="Subsidieaanvraag tekst mag niet leeg zijn.")
    if not assessment_input.criteria or len(assessment_input.criteria) == 0:
        raise HTTPException(status_code=400, detail="Er zijn geen criteria opgegeven om te beoordelen.")

    # Model Selectie
    DEFAULT_MODEL_FALLBACK = "openai/gpt-4o"
    model_to_use = assessment_input.model or DEFAULT_MODEL_FALLBACK
    
    if not model_to_use:
        print(f"Geen model gespecificeerd, gebruik fallback: {DEFAULT_MODEL_FALLBACK}")
        model_to_use = DEFAULT_MODEL_FALLBACK
    
    print(f"Complete assessment gestart met model: {model_to_use}")
    
    try:
        # Stap 1: Beoordeling maken
        assessment_result = await handle_subsidy_assessment(
            request=request, 
            assessment_input=assessment_input,
            user=user
        )
        
        # Stap 2: Samenvatting maken
        summary_result = await handle_subsidy_summary(
            request=request, 
            assessment_input=assessment_input,
            user=user
        )
        
        # Stap 3: Eindrapport maken
        report_input = SubsidyCombinedReportInput(
            assessment_results=assessment_result.assessment,
            summary_result=summary_result,
            model=model_to_use
        )
        
        report_result = await handle_subsidy_report(
            request=request, 
            report_input=report_input,
            user=user
        )
          # Combineer alle resultaten in één response
        return {
            "assessment": assessment_result.assessment,
            "summary": summary_result.model_dump() if hasattr(summary_result, 'model_dump') else summary_result.dict(),
            "report": report_result.model_dump() if hasattr(report_result, 'model_dump') else report_result.dict()
        }
        
    except Exception as e:
        print(f"Error in handle_complete_assessment: {e}")
        raise HTTPException(status_code=500, detail=f"Fout bij complete beoordeling: {str(e)}")

@router.get("/debug/write-test", response_model=Dict[str, Any])
async def test_write_access(
    request: Request,
    user = Depends(get_current_user)
):
    """Test endpoint om te controleren of de bestandsopslag werkt"""
    try:
        # Test directory creatie en schrijfpermissies
        test_dir = subsidy_storage.base_dir
        os.makedirs(test_dir, exist_ok=True)
        
        # Test bestand aanmaken en schrijven
        test_file = os.path.join(test_dir, f"test_write_{int(time.time())}.txt")
        with open(test_file, 'w') as f:
            f.write(f"Test schrijftoegang voor gebruiker {user.id}")
        
        # Lees het bestand om te verifiëren dat het schrijven is gelukt
        with open(test_file, 'r') as f:
            content = f.read()
        
        # Verwijder het testbestand
        os.remove(test_file)
        
        # Lijst alle bestanden in de directory
        files = os.listdir(test_dir)
        
        return {
            "success": True,
            "message": f"Schrijftest geslaagd in {test_dir}",
            "content": content,
            "test_file": test_file,
            "files_in_directory": files[:10],  # Toon slechts de eerste 10 bestanden
            "directory_exists": os.path.exists(test_dir),
            "is_writable": os.access(test_dir, os.W_OK)
        }
    except Exception as e:
        print(f"Fout bij testen schrijftoegang: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

# Voeg deze nieuwe endpoints toe

@router.post("/select/{subsidy_id}", response_model=Dict[str, Any])
async def select_subsidy_data(
    request: Request,
    subsidy_id: str,
    user = Depends(get_current_user)
):
    """Stel een bepaalde set subsidiecriteria in als geselecteerd voor een gebruiker"""
    try:
        # Controleer of de subsidie bestaat
        subsidy_data = subsidy_storage.get_criteria_by_id(subsidy_id, user.id)
        
        if not subsidy_data:
            raise HTTPException(status_code=404, detail="Subsidiecriteria niet gevonden")
        
        # Sla de selectie op voor deze gebruiker
        user_settings = {
            "user_id": user.id,
            "last_selection_id": subsidy_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # Gebruik een speciale bestandsnaam voor gebruikersinstellingen
        filename = f"user_settings_{user.id}.json"
        filepath = os.path.join(subsidy_storage.base_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(user_settings, f, ensure_ascii=False, indent=2)
        
        return {
            "success": True,
            "message": "Subsidie selectie ingesteld",
            "selection_id": subsidy_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error bij instellen subsidie selectie: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Kon selectie niet instellen: {str(e)}")

@router.get("/selection", response_model=Dict[str, Any])
async def get_current_selection(
    request: Request,
    user = Depends(get_current_user)
):
    """Haal de huidige selectie op voor een gebruiker"""
    try:
        # Zoek de gebruikersinstellingen
        filename = f"user_settings_{user.id}.json"
        filepath = os.path.join(subsidy_storage.base_dir, filename)
        
        if not os.path.exists(filepath):
            return {
                "success": True,
                "has_selection": False,
                "message": "Geen huidige selectie gevonden"
            }
        
        with open(filepath, 'r', encoding='utf-8') as f:
            user_settings = json.load(f)
        
        selection_id = user_settings.get("last_selection_id")
        if not selection_id:
            return {
                "success": True,
                "has_selection": False,
                "message": "Geen huidige selectie gevonden"
            }
            
        # Haal de geselecteerde subsidie op
        subsidy_data = subsidy_storage.get_criteria_by_id(selection_id, user.id)
        
        if not subsidy_data:
            return {
                "success": True,
                "has_selection": False,
                "message": "Geselecteerde subsidie niet meer gevonden"
            }
        
        # Converteer de data naar het juiste formaat
        criteria = []
        for c in subsidy_data.get("criteria", []):
            if isinstance(c, dict) and "id" in c and "text" in c:
                criteria.append({"id": c["id"], "text": c["text"]})
        
        selection = {
            "criteria": criteria,
            "summary": subsidy_data.get("summary"),
            "name": subsidy_data.get("name"),
            "savedId": subsidy_data.get("id"),
            "timestamp": subsidy_data.get("timestamp"),
            "isSelection": True
        }
        
        return {
            "success": True,
            "has_selection": True,
            "selection": selection
        }
        
    except Exception as e:
        print(f"Error bij ophalen subsidie selectie: {e}")
        traceback.print_exc()
        return {
            "success": False,
            "has_selection": False,
            "message": f"Kon selectie niet ophalen: {str(e)}"
        }

# Voeg deze nieuwe endpoints toe aan het einde van het bestand

import os
import json
import traceback
from datetime import datetime

@router.post("/global/set/{subsidy_id}", response_model=Dict[str, Any])
async def set_global_selection(
    request: Request,
    subsidy_id: str,
    user = Depends(get_current_user)
):
    """Stel een bepaalde set subsidiecriteria in als globale standaard voor alle gebruikers"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Alleen beheerders kunnen de globale selectie instellen")
    
    try:
        # Controleer of de subsidie bestaat
        subsidy_data = subsidy_storage.get_criteria_by_id(subsidy_id)
        
        if not subsidy_data:
            raise HTTPException(status_code=404, detail="Subsidiecriteria niet gevonden")
        
        # Sla de globale selectie op
        global_settings = {
            "global_selection_id": subsidy_id,
            "set_by_user_id": user.id,
            "set_by_user_name": user.name,
            "timestamp": datetime.now().isoformat()
        }
        
        # Gebruik een speciale bestandsnaam voor globale instellingen
        filename = "global_subsidy_settings.json"
        filepath = os.path.join(subsidy_storage.base_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(global_settings, f, ensure_ascii=False, indent=2)
        
        return {
            "success": True,
            "message": "Globale subsidie selectie ingesteld voor alle gebruikers",
            "selection_id": subsidy_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error bij instellen globale subsidie selectie: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Kon globale selectie niet instellen: {str(e)}")

@router.get("/global", response_model=Dict[str, Any])
async def get_global_selection(
    request: Request,
    user = Depends(get_current_user)
):
    """Haal de globale selectie op die voor alle gebruikers geldt"""
    try:
        # Zoek de globale instellingen
        filename = "global_subsidy_settings.json"
        filepath = os.path.join(subsidy_storage.base_dir, filename)
        
        if not os.path.exists(filepath):
            return {
                "success": True,
                "has_global_selection": False,
                "message": "Geen globale selectie gevonden"
            }
        
        with open(filepath, 'r', encoding='utf-8') as f:
            global_settings = json.load(f)
        
        selection_id = global_settings.get("global_selection_id")
        if not selection_id:
            return {
                "success": True,
                "has_global_selection": False,
                "message": "Geen globale selectie ID gevonden"
            }
            
        # Haal de geselecteerde subsidie op
        subsidy_data = subsidy_storage.get_criteria_by_id(selection_id)
        
        if not subsidy_data:
            return {
                "success": True, 
                "has_global_selection": False,
                "message": "Globale selectie niet meer gevonden"
            }
        
        # Converteer de data naar het juiste formaat
        criteria = []
        for c in subsidy_data.get("criteria", []):
            if isinstance(c, dict) and "id" in c and "text" in c:
                criteria.append({"id": c["id"], "text": c["text"]})
        
        selection = {
            "criteria": criteria,
            "summary": subsidy_data.get("summary", ""),
            "name": subsidy_data.get("name", "Globale standaard selectie"),
            "savedId": subsidy_data.get("id", ""),
            "timestamp": subsidy_data.get("timestamp", datetime.now().isoformat()),
            "isSelection": True,
            "isGlobalSelection": True
        }
        
        print(f"Returning global selection with {len(criteria)} criteria")
        
        return {
            "success": True,
            "has_global_selection": True,
            "selection": selection,
            "set_by_user_id": global_settings.get("set_by_user_id"),
            "set_by_user_name": global_settings.get("set_by_user_name"),
            "timestamp": global_settings.get("timestamp")
        }
        
    except Exception as e:
        print(f"Error bij ophalen globale subsidie selectie: {e}")
        traceback.print_exc()
        return {
            "success": False,
            "has_global_selection": False,
            "message": f"Kon globale selectie niet ophalen: {str(e)}"
        }

@router.post("/debug/test_report", response_model=Dict[str, Any])
async def test_report_generation(
    request: Request,
    user = Depends(get_current_user)
):
    """Test endpoint om rapportgeneratie te debuggen"""
    try:
        # Maak test data voor de rapportgeneratie
        test_assessment = {
            "1": {
                "Criterium": "Test criterium 1",
                "Score": "8",
                "Toelichting": "Dit is een test toelichting"
            },
            "2": {
                "Criterium": "Test criterium 2", 
                "Score": "5",
                "Toelichting": "Dit criterium heeft een lagere score"
            }
        }
        
        test_summary = SubsidySummaryOutput(
            Aanvrager="Test Aanvrager",
            Datum_aanvraag="2024-01-01",
            Datum_evenement="2024-06-01",
            Bedrag="€10.000",
            Samenvatting="Test samenvatting van de aanvraag"
        )
        
        # Converteer naar SubsidyAssessmentItem objecten
        assessment_items = {}
        for key, value in test_assessment.items():
            assessment_items[key] = SubsidyAssessmentItem(**value)
        
        report_input = SubsidyCombinedReportInput(
            assessment_results=assessment_items,
            summary_result=test_summary,
            model="openai/gpt-4o"
        )
        
        print(f"DEBUG: Test report input created successfully")
        print(f"DEBUG: Assessment results type: {type(report_input.assessment_results)}")
        print(f"DEBUG: Summary result type: {type(report_input.summary_result)}")
        
        # Probeer het rapport te genereren
        report_result = await handle_subsidy_report(
            request=request,
            report_input=report_input,
            user=user
        )
        
        return {
            "success": True,
            "message": "Test rapport succesvol gegenereerd",
            "report": report_result.model_dump() if hasattr(report_result, 'model_dump') else report_result.dict(),
            "test_input": {
                "assessment": test_assessment,
                "summary": test_summary.model_dump() if hasattr(test_summary, 'model_dump') else test_summary.dict()
            }
        }
        
    except Exception as e:
        print(f"Error in test report generation: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }