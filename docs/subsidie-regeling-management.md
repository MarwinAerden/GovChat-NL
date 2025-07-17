# Subsidie Regeling Management

Dit systeem maakt het mogelijk om meerdere standaard subsidiereglingen beschikbaar te stellen voor gebruikers.

## Functionaliteit

### Voor Admins (Subsidie Admin Paneel):
- **Regeling selecteren**: Kies uit beschikbare standaard regelingen
- **Eigen regelingen maken**: Upload of typ een regeling om criteria te extraheren
- **Opslaan als regeling**: Bewaar gemaakte criteria als herbruikbare regeling voor alle gebruikers
- **Regeling management**: Bekijk, selecteer en beheer alle beschikbare regelingen

### Voor Normale Gebruikers (Subsidie Beoordeling):
- **Regeling kiezen**: Selecteer uit beschikbare regelingen via dropdown
- **Automatisch laden**: Krijg de geselecteerde criteria uit deel 1
- **Eenvoudige beoordeling**: Beoordeel aanvragen tegen de gekozen criteria

## Gebruik

### 1. Admin: Regelingen Beheren
1. Ga naar **Subsidie Admin Paneel** (`/app-launcher/subsidies`)
2. Kies een bestaande regeling uit de dropdown OF upload/typ een nieuwe regeling
3. Gebruik "Sla Op Als Regeling..." om criteria beschikbaar te maken voor iedereen
4. Geef een duidelijke naam en beschrijving

### 2. Gebruiker: Regeling Selecteren
1. Ga naar **Subsidie Beoordeling** (`/app-launcher/subsidies2`)
2. Als er geen criteria zijn geladen, kies een regeling uit de dropdown
3. Klik "Laad" om de criteria te laden
4. Voer je subsidieaanvraag in en laat beoordelen

### 3. Wissel van Regeling
- In beide delen kan je een andere regeling kiezen via de dropdown
- Klik "Laad" of "Wissel" om over te schakelen
- Je huidige werk blijft bewaard

## Standaard Regelingen

Er zijn voorbeeldreglingen beschikbaar:
- **Gemeente Evenementen Subsidie**: Voor lokale evenementen (max €5.000)
- **Sportvereniging Subsidie**: Voor sportverenigingen (max €2.500)
- **MKB Digitalisering Subsidie**: Voor MKB digitalisering (max €25.000)

## Technical Details

### API Endpoints
```
GET  /api/subsidies/regulations          # Lijst alle regelingen
GET  /api/subsidies/regulations/{id}     # Haal specifieke regeling op
POST /api/subsidies/regulations          # Maak nieuwe regeling aan
DELETE /api/subsidies/regulations/{id}   # Verwijder regeling
```

### Bestandsstructuur
```
backend/data/subsidies/
├── regulations/                 # Standaard regelingen
│   ├── regulation_*.json       # Regelingbestanden
└── subsidy_*.json              # Gebruiker-specifieke opgeslagen criteria
```

### Data Format
```json
{
  "id": "uuid",
  "name": "Regeling Naam",
  "description": "Beschrijving van de regeling",
  "timestamp": "2025-01-17T...",
  "criteria": [
    {"id": 1, "text": "Criterium 1"},
    {"id": 2, "text": "Criterium 2"}
  ],
  "summary": "Korte samenvatting van de regeling",
  "type": "regulation"
}
```

## Voordelen

✅ **Eenvoudig**: Gebruikers hoeven niet zelf criteria te maken  
✅ **Consistent**: Iedereen gebruikt dezelfde standaard criteria  
✅ **Flexibel**: Admins kunnen eenvoudig nieuwe regelingen toevoegen  
✅ **Herbruikbaar**: Één keer instellen, door iedereen te gebruiken  
✅ **Schaalbaar**: Geen limiet aan aantal regelingen  

## Workflow

```
1. Admin maakt/uploadt regeling → Criteria extractie → Opslaan als standaard regeling
2. Gebruiker kiest regeling → Criteria automatisch geladen → Aanvraag beoordelen
3. Resultaat: Professionele beoordeling met rapport
```
