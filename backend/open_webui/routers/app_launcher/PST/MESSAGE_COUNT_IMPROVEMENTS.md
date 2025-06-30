# PST Parser - Berichtentelling en Zoekfunctie Verbeteringen

## Problemen Geïdentificeerd

1. **Onjuiste berichtentelling**: Mappen toonden 0 berichten terwijl ze wel berichten bevatten
2. **Zoekfunctie werkte niet**: Zoeken naar "(Geen onderwerp)" gaf 0 resultaten
3. **Onnauwkeurige totalen**: Totaal aantal berichten klopte niet

## Oplossingen Geïmplementeerd

### 1. Verbeterde Berichtentelling - `safe_get_message_count()`
- **Probleem**: `number_of_sub_messages` eigenschap was onbetrouwbaar
- **Oplossing**: 
  - Eerst proberen met `number_of_sub_messages`
  - Bij falen: handmatig tellen door berichten op te halen
  - Veiligheidslimiet om oneindige loops te voorkomen
  - Graceful fallback naar 0 bij fouten

```python
def safe_get_message_count(folder) -> int:
    # Meerdere methoden om berichtentelling te krijgen
    # Fallback naar handmatig tellen als nodig
    # Veiligheidslimiet van 10.000 berichten
```

### 2. Intelligente Zoekfunctie - `safe_search_match()`
- **Probleem**: Zoeken naar "(Geen onderwerp)" was te letterlijk
- **Oplossing**:
  - Speciale behandeling voor lege onderwerpen
  - Flexibele matching voor haakjes en speciale tekens
  - Normalisatie van zoektermen

```python
def safe_search_match(text: str, query: str) -> bool:
    # Speciale behandeling voor "(Geen onderwerp)"
    # Flexibele matching voor haakjes
    # Case-insensitive normalisatie
```

### 3. Nauwkeurige Totaalberekening - `calculate_total_messages()`
- **Probleem**: Totaal aantal berichten werd niet correct berekend
- **Oplossing**: Recursieve telling door alle mappen en submappen

### 4. Debug Endpoints

#### A. `/debug/search` - Zoek Debug
- Test waarom een specifieke zoekopdracht niet werkt
- Analyseert voorbeeldberichten in relevante mappen
- Toont daadwerkelijke onderwerpen gevonden
- Identificeert parsing errors

#### B. Verbeterde `/debug/folders` 
- Meer gedetailleerde mappenanalyse
- Bericht telling per map
- Error tracking per niveau

## Nieuwe API Endpoints

### POST `/app-launcher/pst/debug/search`
Test zoekfunctionaliteit in specifieke mappen.

**Request:**
```json
{
  "file_path": "/path/to/file.pst",
  "query": "(Geen onderwerp)",
  "search_in": ["subject"]
}
```

**Response:**
```json
{
  "search_query": "(Geen onderwerp)",
  "search_in": ["subject"],
  "folders_analyzed": [
    {
      "folder_name": "Concepten",
      "message_count": 91,
      "messages_analyzed": 10,
      "matches_found": 8,
      "sample_subjects": [
        "(Geen onderwerp)",
        "FW: Your Amazon.nl order...",
        "(Geen onderwerp)"
      ]
    }
  ]
}
```

## Verwachte Verbeteringen

### ✅ **Berichtentelling**
- Mappen tonen nu correcte berichtenaantallen
- Totaal aantal berichten is accuraat
- Handmatige telling als fallback

### ✅ **Zoekfunctie**
- "(Geen onderwerp)" zoeken werkt nu
- Flexibele matching voor verschillende formaten
- Betere behandeling van speciale karakters

### ✅ **Debug Capabilities**
- Specifieke endpoints om problemen te diagnosticeren
- Inzicht in welke berichten daadwerkelijk gevonden worden
- Error tracking per map en bericht

### ✅ **Performance**
- Veiligheidslimiet voorkomt oneindige loops
- Efficiëntere berichtentelling
- Graceful error handling

## Test Aanbevelingen

1. **Test berichtentelling**: Controleer of mappen nu correcte aantallen tonen
2. **Test zoekfunctie**: Zoek naar "(Geen onderwerp)" - zou nu resultaten moeten geven
3. **Test debug endpoints**: Gebruik om specifieke problemen te analyseren
4. **Test performance**: Verificeer dat grote PST bestanden nog steeds goed presteren

## Bekende Verbeteringen

- Concepten map (91 berichten) zou nu correct moeten tellen
- Ongewenste e-mail (39 berichten) correcte telling
- Zoeken naar "(Geen onderwerp)" vindt nu matches
- Totaal bericht telling (390+) accuraat berekend
