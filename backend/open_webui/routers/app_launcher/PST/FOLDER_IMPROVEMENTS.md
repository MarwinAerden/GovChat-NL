# Mappenstructuur Verbeteringen PST Parser

## Probleem Geïdentificeerd
Het PST parser laadde niet alle mappen omdat:

1. **Recursieprobleem**: De `parse_folder_structure` functie retourneerde alleen de huidige map in plaats van alle mappen in de hiërarchie
2. **Onvolledige folder parsing**: Sub-mappen werden niet correct toegevoegd aan de hoofdlijst
3. **Beperkte debug informatie**: Geen manier om te zien waarom bepaalde mappen niet geladen werden

## Oplossingen Geïmplementeerd

### 1. Verbeterde `parse_folder_structure` Functie
- **Platte lijst**: Retourneert nu alle mappen in een platte lijst voor eenvoudige toegang
- **Bytes handling**: Gebruikt `safe_bytes_to_string()` voor mapnamen
- **Betere recursie**: Voegt alle sub-mappen toe aan de hoofdlijst
- **Gedetailleerde logging**: Meer context bij fouten

### 2. Nieuwe `parse_folder_structure_hierarchical` Functie
- **Hiërarchische structuur**: Behoudt de originele boom-structuur
- **Beide formaten**: Frontend kan kiezen tussen plat of hiërarchisch

### 3. Nieuw Debug Endpoint `/debug/folders`
- **Diepte-analyse**: Analyseert mappenstructuur tot een bepaalde diepte
- **Error tracking**: Toont exact welke mappen toegankelijk zijn
- **Folder capabilities**: Controleert welke pypff methoden beschikbaar zijn
- **Recursieve debugging**: Gedetailleerde informatie per map

### 4. Verbeterde `count_folders_recursive` Functie
- **Null checking**: Controleert of sub-mappen daadwerkelijk bestaan
- **Debug logging**: Toont aantal sub-mappen per map
- **Betere error handling**: Gaat door ondanks fouten in individuele mappen

## Nieuwe API Response Structuur

```json
{
  "file_info": { ... },
  "folders": [
    // Platte lijst van alle mappen
    {
      "name": "Inbox",
      "path": "/Inbox",
      "message_count": 150,
      "folder_type": "inbox",
      "sub_folders": [
        // Basis info van directe sub-mappen
      ]
    },
    // ... alle andere mappen
  ],
  "folders_hierarchical": {
    // Hiërarchische boom-structuur
    "name": "Root",
    "sub_folders": [
      {
        "name": "Inbox",
        "sub_folders": [ ... ]
      }
    ]
  },
  "total_folders": 25
}
```

## Nieuwe Debug Endpoint

**POST** `/app-launcher/pst/debug/folders`

**Request:**
```json
{
  "file_path": "/path/to/file.pst"
}
```

**Response:**
```json
{
  "file_path": "/path/to/file.pst",
  "file_size": 1048576,
  "root_folder_debug": {
    "name": "Root",
    "depth": 0,
    "num_sub_folders": 5,
    "num_sub_messages": 0,
    "folder_type": "regular",
    "has_get_sub_folder": true,
    "has_get_sub_message": true,
    "sub_folders": [ ... ],
    "errors": []
  },
  "total_folders_count": 25
}
```

## Gebruiksadvies

1. **Voor frontend development**: Gebruik `folders` voor platte lijst of `folders_hierarchical` voor boom-weergave
2. **Voor debugging**: Gebruik `/debug/folders` endpoint om te zien waarom mappen niet laden
3. **Voor performance**: Platte lijst is sneller voor zoeken, hiërarchische voor navigatie

## Verwachte Resultaten

- ✅ Alle mappen worden nu geladen (plat en hiërarchisch)
- ✅ Betere error handling voor ontoegankelijke mappen  
- ✅ Gedetailleerde debug informatie beschikbaar
- ✅ Bytes naar string conversie voor mapnamen
- ✅ Robuustere parsing die doorgaat ondanks fouten
