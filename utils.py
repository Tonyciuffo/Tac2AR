import os
import yaml
import json
import re
import csv

def read_yaml(file):
    # Carica le mappature dei segmenti
    try:
        with open(file, 'r') as f:
            success = yaml.safe_load(f)
        # print(f"DEBUG: Read Yaml - Mappature caricate da {file}: {len(success)}\n")
        return success
    except FileNotFoundError:
        print(f"Errore: File delle mappature non trovato in {file}")
        return
    except yaml.YAMLError as e:
        print(f"Errore nel parsing del file YAML delle mappature: {e}")
        return

def write_json(data, file_path):
    """Scrive un dizionario in un file JSON con una formattazione leggibile."""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def read_json(file_path):
    """Legge un file JSON e restituisce il suo contenuto."""
    with open(file_path, 'r') as f:
        return json.load(f)

def hex_to_rgb(hex_color):
    """Converte un colore esadecimale (es. #RRGGBB) in un tuple RGB normalizzato (0-1)."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    
def plural_to_singular(s: str) -> str:
    """
    Tenta di convertire una stringa da plurale a singolare.
    Gestisce casi comuni di plurali in inglese.
    """
    # Regole comuni:
    if s.endswith("es"):
        return s[:-2] # es. 'boxes' -> 'box', 'churches' -> 'church'
    elif s.endswith("s") and len(s) > 2 and s[-2] not in 'aeiouy':
        # es. 'ribs' -> 'rib', 'discs' -> 'disc'
        # La condizione 'len(s) > 2 and s[-2] not in 'aeiouy'' serve a evitare casi come 'gas' -> 'ga' o 'bus' -> 'bu'
        return s[:-1]
    elif s.endswith("ae"): # Latino, o per irregolarit� come 'vertebrae' -> 'vertebra'
        return s[:-1]
    return s

def number_to_ordinal(num_str: str) -> str:
    """Converte una stringa numerica ('1', '2', etc.) nella sua forma ordinale inglese ('First', 'Second', etc.)."""
    try:
        num = int(num_str)
        if 10 <= num % 100 <= 20: # Gestisce 11th, 12th, 13th
            return f"{num}th"
        else:
            # Per i numeri 1-9 e altri che terminano con 1, 2, 3 (non 11-13)
            return {1: 'First', 2: 'Second', 3: 'Third', 4: 'Fourth', 5: 'Fifth',
                    6: 'Sixth', 7: 'Seventh', 8: 'Eighth', 9: 'Ninth', 0: f"{num}th"}.get(num % 10, f"{num}th")
            # Aggiunto 0: f"{num}th" per i casi come 10th, 20th, ecc. che non terminano con 1,2,3
    except ValueError:
        return num_str # Ritorna l'originale se non � un numero valido

def generate_snomed_candidate_names(original_seg_name: str) -> list[str]:
    """
    Genera una lista ordinata di nomi candidati per il lookup SNOMED,
    applicando regole di normalizzazione per matchare sia lo stile 'Structure'
    (lowercase, underscore) che lo stile 'CodeMeaning' (Capitalized, space, prefix/ordinal).
    """
    candidates = []

    # --- Candidati in stile 'Structure' (lowercase, underscore) ---
    # 1. Nome originale (massima priorit� per match diretto su Structure)
    candidates.append(original_seg_name)

    # 2. Forma singolare del nome originale (se diversa)
    singular_original = plural_to_singular(original_seg_name)
    if singular_original != original_seg_name and singular_original not in candidates:
        candidates.append(singular_original)

    # 3. Nomi strippati iterativamente (solo qualificatori) per match su Structure
    # Lista di qualificatori da strippare (posizionali, numerici, di grado)

    qualifier_suffixes_to_strip = [
        '_left', '_right',
        '_L5', '_L4', '_L3', '_L2', '_L1',
        '_T12', '_T11', '_T10', '_T9', '_T8', '_T7', '_T6', '_T5', '_T4', '_T3', '_T2', '_T1',
        '_C7', '_C6', '_C5', '_C4', '_C3', '_C2', '_C1',
        '_S1',
        '_1','_2','_3','_4','_5','_6','_7','_8','_9','_10','_11','_12',
        '_lumbar', '_thoracic', '_cervical',
        '_maximus', '_medius', '_minimus',
        '_body' # per 'body_trunc', 'body_extremities' - qualificatori di 'body'
    ]

    current_name_for_stripping = original_seg_name
    for suffix in qualifier_suffixes_to_strip:
        if current_name_for_stripping.endswith(suffix):
            stripped_name = current_name_for_stripping.replace(suffix, '')
            if stripped_name and stripped_name != current_name_for_stripping and stripped_name not in candidates:
                candidates.append(stripped_name)
                # Aggiungi anche la forma singolare di questo nome strippato
                singular_stripped = plural_to_singular(stripped_name)
                if singular_stripped != stripped_name and singular_stripped not in candidates:
                    candidates.append(singular_stripped)
            current_name_for_stripping = stripped_name # Continua a strippare dal nome appena ottenuto

    # --- Candidati in stile 'CodeMeaning' (Capitalized, space, prefix/ordinal) ---

    # Regex per riconoscere pattern specifici
    vertebra_pattern = re.compile(r"^(vertebrae|vertebra)_([LTCMS][0-9]+)$")
    rib_pattern = re.compile(r"^(ribs|rib)_(left|right)_([0-9]+)$")
    # Pattern per organ_side come 'adrenal_gland_left'
    organ_side_pattern = re.compile(r"^([a-z_]+)_(left|right)$")
    # Pattern per lobe_side come 'lung_lower_lobe_left'
    lobe_side_pattern = re.compile(r"^(lung|lobe|segment)_(lower_lobe|upper_lobe|middle_lobe|medial_lobe|lateral_lobe)_(left|right)$")
    # Pattern per nomi composti come 'iliac_artery' -> 'Iliac Artery' o 'Common Iliac Artery'
    # Per semplicit�, inizialmente convertiamo solo underscore a spazio e capitalizziamo.
    # Pattern per nomi tipo 'vessels_portal' -> 'Portal vessels' (es. per il nome in Structure, non nell'esempio fornito)
    compound_pattern = re.compile(r"^([a-z_]+)_([a-z_]+)$") # 'word1_word2'

    # Caso Nomi Composti Generici: es. 'iliac_artery' -> 'Iliac Artery', 'Common Iliac Artery'
    # Per questo, convertiamo semplicemente underscore in spazi e capitalizziamo ogni parola.
    # Questo copre anche casi come 'vertebrae_lumbar' che potrebbe non essere catturato dai pattern specifici sopra
    # se non � una vertebra numerata.
    formatted_generic = ' '.join([plural_to_singular(p).capitalize() for p in original_seg_name.split('_')])
    if formatted_generic not in candidates:
        candidates.append(formatted_generic)

    # 5. Gestione nomi composti con "_and_" (assicura che le singole parti siano candidate)
    if '_and_' in original_seg_name:
        parts_and = original_seg_name.split('_and_')
        for p in parts_and:
            if p not in candidates:
                candidates.append(p)
            singular_p = plural_to_singular(p)
            if singular_p != p and singular_p not in candidates:
                candidates.append(singular_p)
            
            # Aggiungi anche la versione CodeMeaning per le singole parti
            formatted_p = ' '.join([plural_to_singular(word).capitalize() for word in p.split('_')])
            if formatted_p not in candidates:
                candidates.append(formatted_p)


    # Rimuovi duplicati mantenendo l'ordine (importante per la priorita' di lookup)
    final_candidates = []
    seen = set()
    for candidate in candidates:
        if candidate not in seen:
            final_candidates.append(candidate)
            seen.add(candidate)
            
    return final_candidates

def load_csv(csv_path, key_column, encoding):
    """
    Loads a CSV file into a dictionary of dictionaries, using a specified column as the main key.
    Each row of the CSV becomes a dictionary, and these row-dictionaries are stored
    in a larger dictionary, keyed by the value of 'key_column' for that row.

    Args:
        csv_path (str): The path to the CSV file.
        key_column (str): The name of the column whose values will serve as keys
                          for the outer dictionary.
        encoding (str): The encoding to use when reading the CSV file (default: 'utf-8').

    Returns:
        dict: A dictionary where keys are values from 'key_column' and values are
              dictionaries representing the full rows of the CSV.
              Returns an empty dictionary if the file is not found, the key_column
              is missing, or an error occurs.
    """
    data_map = {}
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at '{csv_path}'.")
        return data_map

    try:
        with open(csv_path, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)

            # Validate if the key_column exists in the CSV header
            if key_column not in reader.fieldnames:
                print(f"Error: Key column '{key_column}' not found in the CSV header of '{csv_path}'.")
                print(f"Available columns: {', '.join(reader.fieldnames)}")
                return data_map

            for row in reader:
                key_value = row.get(key_column) # Use .get() for safer access, though KeyError is caught
                if key_value is None or key_value == '':
                    print(f"Warning: Skipping row due to empty or missing value in key column '{key_column}'. Row: {row}")
                    continue
                
                if key_value in data_map:
                    print(f"Warning: Duplicate key '{key_value}' found in column '{key_column}'. Overwriting previous entry.")
                
                data_map[key_value] = row
        
        print(f"DEBUG: Loaded CSV from '{csv_path}' into a dictionary with {len(data_map)} entries, keyed by '{key_column}'.")
        return data_map

    except UnicodeDecodeError as e:
        print(f"Decoding error (UnicodeDecodeError) when reading '{csv_path}': {e}")
        print(f"Hint: The file might not be encoded in '{encoding}'. Try 'windows-1252' or 'latin-1'.")
        return data_map
    except Exception as e:
        print(f"Generic error loading '{csv_path}': {e}")
        return data_map

def hex_to_rgb(hex_color_str):
    """
    Converts a hexadecimal string (e.g., "FF0000") to an RGB tuple (0-1).
    Returns (0.0, 0.0, 0.0) for invalid input.
    """
    if not isinstance(hex_color_str, str) or len(hex_color_str) != 6:
        print(f"Warning: Invalid hexadecimal color: '{hex_color_str}'. Using black.")
        return (0.0, 0.0, 0.0)
    
    try:
        r = int(hex_color_str[0:2], 16) / 255.0
        g = int(hex_color_str[2:4], 16) / 255.0
        b = int(hex_color_str[4:6], 16) / 255.0
        return (r, g, b)
    except ValueError:
        print(f"Warning: Could not convert hexadecimal color '{hex_color_str}'. Using black.")
        return (0.0, 0.0, 0.0)