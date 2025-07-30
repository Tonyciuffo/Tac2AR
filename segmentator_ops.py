# coding: utf-8
# segmentator_ops.py
import os
import sys
import subprocess
import shutil
import yaml
import nibabel as nib
import numpy as np
import pyvista as pv
from skimage.measure import marching_cubes
import config
import utils
import SimpleITK as sitk
import csv


def convert_dicom_to_nifti(dicom_folder, output_nifti_path):
    """
    Converte una serie di file DICOM in un singolo file NIfTI.
    """
    print(f"Conversione della directory DICOM: {dicom_folder}")
    reader = sitk.ImageSeriesReader()
    try:
        print("Ricerca dei nomi dei file della serie DICOM...")
        dicom_names = reader.GetGDCMSeriesFileNames(dicom_folder)
        if not dicom_names:
            print(f"Errore: Nessun file DICOM valido trovato in {dicom_folder}. Controlla che la cartella contenga una serie DICOM.")
            return False
        
        print(f"Trovati {len(dicom_names)} file DICOM. Tentativo di caricarli...")
        reader.SetFileNames(dicom_names)
        
        print("Esecuzione della lettura della serie DICOM (potrebbe richiedere tempo)...")
        image = reader.Execute()
        print("Lettura della serie completata.")
        
        print(f"Scrittura del file NIfTI in: {output_nifti_path}")
        sitk.WriteImage(image, output_nifti_path)
        print("File NIfTI salvato con successo.")
        return True
    except Exception as e:
        print(f"ERRORE CRITICO durante la conversione DICOM: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_segment_volume(segment_data):
    return np.count_nonzero(segment_data) > 0

def populate_snomed_details_for_segments(all_segment_data, snomed_by_structure, snomed_by_type, snomed_by_region, snomed_by_category):
    """
    Popola il campo 'snomed_details' per ogni segmento in all_segment_data.
    Usa una strategia di lookup con nomi candidati generati dinamicamente.
    """
    print("\nDEBUG: (segmentator_ops) Inizio popolamento dettagli SNOMED per i segmenti con volume effettivo...")
    snomed_details_found_count = 0
    snomed_details_not_found_count = 0

    for seg_name, segment_info in all_segment_data.items():
        found_snomed_entry = None

        # Genera tutti i nomi candidati per il lookup, dal piu' specifico al piu' generico
        candidate_names = utils.generate_snomed_candidate_names(seg_name)
        print(f"DEBUG: Candidati generati per '{seg_name}': {candidate_names}")
        # ------------------------------------
        
        for candidate_name in candidate_names:
            # Tenta lookup come 'Structure'
            found_snomed_entry = snomed_by_structure.get(candidate_name)
            if found_snomed_entry:
                print(f"DEBUG: Dettagli SNOMED trovati per '{seg_name}' (via '{candidate_name}' come 'Structure').")
                break # Trovato, esci dal loop dei candidati

            # Se non trovato come 'Structure', tenta come 'Type CodeMeaning'
            matching_entries_by_type = snomed_by_type.get(candidate_name)
            if matching_entries_by_type:
                found_snomed_entry = matching_entries_by_type[0] # Prendi la prima corrispondenza
                print(f"DEBUG: Dettagli SNOMED trovati per '{seg_name}' (via '{candidate_name}' come 'Type').")
                break

            # Se non trovato come 'Type', tenta come 'AnatomicRegionSequence.CodeMeaning'
            matching_entries_by_region = snomed_by_region.get(candidate_name)
            if matching_entries_by_region:
                found_snomed_entry = matching_entries_by_region[0]
                print(f"DEBUG: Dettagli SNOMED trovati per '{seg_name}' (via '{candidate_name}' come 'Region').")
                break

        # Popola snomed_details con i dati trovati o con None
        # Questa parte del codice e' fuori dal loop 'for candidate_name in candidate_names',
        # il che significa che 'found_snomed_entry' conterra' l'ultimo match trovato (o None).
        snomed_details = segment_info["snomed_details"]
        if found_snomed_entry:
            snomed_details["category"] = found_snomed_entry.get('SegmentedPropertyCategoryCodeSequence.CodeMeaning')
            snomed_details["type"] = found_snomed_entry.get('SegmentedPropertyTypeCodeSequence.CodeMeaning')
            snomed_details["type_modifier"] = found_snomed_entry.get('SegmentedPropertyTypeModifierCodeSequence.CodeMeaning')
            snomed_details["region"] = found_snomed_entry.get('AnatomicRegionSequence.CodeMeaning')
            snomed_details["type_code"] = found_snomed_entry.get('SegmentedPropertyTypeCodeSequence.CodeValue')
            snomed_details_found_count += 1
        else:
            snomed_details_not_found_count += 1
            print(f"AVVISO: Dettagli SNOMED NON trovati per '{seg_name}' (nessun lookup riuscito dopo normalizzazione).")
            
    print(f"DEBUG: (segmentator_ops) Popolamento SNOMED completato. Trovati: {snomed_details_found_count}, Non trovati: {snomed_details_not_found_count}.")

def load_snomed_mappings(file_path, encoding):
    """
    Carica il CSV di mappatura SNOMED e restituisce un dizionario principale
    (indicizzato per 'Structure') e dizionari secondari per lookup veloci
    per 'CodeMeaning' dei Type e Region.
    """
    snomed_by_structure = {}
    snomed_by_type_meaning = {} # key: CodeMeaning, value: list of matching entries
    snomed_by_region_meaning = {} # key: CodeMeaning, value: list of matching entries
    snomed_by_category_meaning = {} # key: CodeMeaning, value: list of matching entries

    try:
        with open(file_path, mode='r', encoding=encoding) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                structure_name = row['Structure']
                snomed_by_structure[structure_name] = row

                type_meaning = row.get('SegmentedPropertyTypeCodeSequence.CodeMeaning')
                if type_meaning:
                    snomed_by_type_meaning.setdefault(type_meaning, []).append(row)

                region_meaning = row.get('AnatomicRegionSequence.CodeMeaning')
                if region_meaning:
                    snomed_by_region_meaning.setdefault(region_meaning, []).append(row)

                category_meaning = row.get('SegmentedPropertyCategoryCodeSequence.CodeMeaning')
                if category_meaning:
                    snomed_by_category_meaning.setdefault(category_meaning, []).append(row)

        print(f"DEBUG: (segmentator_ops) SNOMED Mappings loaded. Main index by 'Structure': {len(snomed_by_structure)} entries.")
        print(f"DEBUG: (segmentator_ops) Secondary index by 'Type CodeMeaning': {len(snomed_by_type_meaning)} entries.")
        print(f"DEBUG: (segmentator_ops) Secondary index by 'Region CodeMeaning': {len(snomed_by_region_meaning)} entries.")
        print(f"DEBUG: (segmentator_ops) Secondary index by 'Category CodeMeaning': {len(snomed_by_category_meaning)} entries.")

        return {
            "by_structure": snomed_by_structure,
            "by_type": snomed_by_type_meaning,
            "by_region": snomed_by_region_meaning,
            "by_category": snomed_by_category_meaning,
        }

    except FileNotFoundError:
        print(f"ERRORE: (segmentator_ops) File SNOMED mapping non trovato: {file_path}")
        return None
    except Exception as e:
        print(f"ERRORE: (segmentator_ops) durante il caricamento del CSV SNOMED: {e}")
        return None

def get_present_segment_ids(nii_segmented_file_path, segment_id_to_name_map):
    """
    Carica il file NIfTI multi-etichetta, verifica il volume per ciascun segmento
    e restituisce un set di ID dei segmenti che hanno un volume effettivo (> 0 voxel).

    Args:
        nii_segmented_file_path (str): Percorso al file NIfTI segmentato multi-etichetta.
        segment_id_to_name_map (dict): Mappa dagli ID numerici dei segmenti ai loro nomi.

    Returns:
        set: Un set di ID numerici dei segmenti che hanno un volume non nullo nel NIfTI.
             Restituisce un set vuoto se il file non e' trovato o in caso di errore.
    """
    present_segment_ids = set()

    if not os.path.exists(nii_segmented_file_path):
        print(f"Errore: File NIfTI segmentato non trovato in '{nii_segmented_file_path}'.")
        return present_segment_ids

    try:
        # Getta i dati dall nifti
        data = get_nifti_fdata(nii_segmented_file_path)

        print(f"DEBUG: Analizzando i volumi dei segmenti nel file NIfTI multi-etichetta '{nii_segmented_file_path}'...")

        # Per ogni ID di segmento che ci aspettiamo (da TotalSegmentator)
        for seg_id in segment_id_to_name_map.keys():
            # Estrai solo i voxel che corrispondono a questo specifico seg_id
            segment_mask = (data == seg_id)
            if check_segment_volume(segment_mask):
                present_segment_ids.add(seg_id)
                # print(f"DEBUG: Segmento ID {seg_id} ('{segment_id_to_name_map.get(seg_id, 'Sconosciuto')}') presente nel volume.")
            # else:
                # print(f"DEBUG: Segmento ID {seg_id} ('{segment_id_to_name_map.get(seg_id, 'Sconosciuto')}') NON presente nel volume (volume zero).")

        print(f"DEBUG: Trovati {len(present_segment_ids)} segmenti con volume effettivo.")
        return present_segment_ids

    except Exception as e:
        print(f"ERRORE durante l'analisi dei volumi NIfTI: {e}")
        import traceback
        traceback.print_exc()
        return present_segment_ids

def get_nifti_voxel_spacing(nifti_filepath):
    print(f"DEBUG: Caricamento del file NIfTI: {nifti_filepath}")
    nii_img = nib.load(nifti_filepath)
    # --- FIX: Estrai la spaziatura dei voxel dall'header ---
    voxel_spacing = nii_img.header.get_zooms()
    if voxel_spacing:
        print(f"DEBUG: Spaziatura Voxel rilevata (mm): {voxel_spacing}")
        return voxel_spacing
    else:
        return None

def get_nifti_fdata(nifti_filepath):
    print(f"DEBUG: Caricamento del file NIfTI: {nifti_filepath}")
    nii_img = nib.load(nifti_filepath)
    nii_fdata = nii_img.get_fdata()
    if nii_fdata.size > 0:
        print(f"DEBUG: Caricamento dei dati NIfTI riuscito")
        return nii_fdata
    else:
        return None

def export_stl_from_multilabel_nii(nii_filepath, all_segment_data, combined_mesh_rules, output_dir):
    """
    Esporta i file STL da un singolo file NIfTI multi-etichetta, implementando
    una logica di override per i mesh combinati.
    """
    print("\n--- Fase: Esportazione Mesh STL dal NIfTI Multi-Etichetta (con logica di override) ---")
    if not os.path.exists(nii_filepath):
        print(f"ERRORE: File NIfTI non trovato in '{nii_filepath}'. Impossibile esportare mesh.")
        return

    os.makedirs(output_dir, exist_ok=True)
    
    try:
        print(f"DEBUG: Caricamento del file NIfTI: {nii_filepath}")
        nii_data = get_nifti_fdata(nii_filepath)
        voxel_spacing = get_nifti_voxel_spacing(nii_filepath)
        print(f"DEBUG: Spaziatura Voxel rilevata (mm): {voxel_spacing}")
        # ---------------------------------------------------------
    except Exception as e:
        print(f"ERRORE CRITICO nel caricamento del file NIfTI: {e}")
        return
    # voxel_spacing = get_nifti_voxel_spacing(nii_filepath)
    grouped_segments = set()

    # --- 1. Prima Passata: Gestisci le Esportazioni Combinate (Override) ---
    print("\n--- Prima Passata: Esportazioni Combinate (Override) ---")
    if not combined_mesh_rules:
        print("Nessuna regola di esportazione combinata definita.")
    else:
        for group_name, group_rules in combined_mesh_rules.items():
            if group_rules.get('export'):
                included_categories = group_rules.get('biological_category', [])
                if not isinstance(included_categories, list):
                    included_categories = [included_categories]

                print(f"  Processando gruppo combinato: '{group_name}' (Categorie: {', '.join(included_categories)})")
                
                combined_volume = None
                segments_in_this_group = []

                # Trova tutti i segmenti che appartengono a queste categorie
                for seg_name, seg_data in all_segment_data.items():
                    if seg_data['custom_parameters'].get('biological_category') in included_categories:
                        segments_in_this_group.append(seg_data)
                
                if not segments_in_this_group:
                    print(f"    Attenzione: Nessun segmento trovato per le categorie {included_categories} nel gruppo '{group_name}'.")
                    continue

                # Combina i volumi e aggiungi i segmenti al set 'grouped_segments'
                for seg_data in segments_in_this_group:
                    segment_id = seg_data['id']
                    seg_name = next(key for key, value in all_segment_data.items() if value['id'] == segment_id) # Trova il nome del segmento dall'ID
                    
                    volume_mask = (nii_data == segment_id)
                    if combined_volume is None:
                        combined_volume = volume_mask
                    else:
                        combined_volume = np.logical_or(combined_volume, volume_mask)
                    
                    grouped_segments.add(seg_name)
                
                # Esporta il volume combinato
                if combined_volume is not None and np.sum(combined_volume) > 0:
                    output_stl_path = os.path.join(output_dir, f"{group_name}.stl")
                    convert_nii_to_stl(combined_volume.astype(np.uint8), output_stl_path, spacing=voxel_spacing)
                    
                    # Aggiungi una voce per il gruppo combinato al dizionario principale
                    all_segment_data[group_name] = {
                        "id": None, # I gruppi non hanno un ID singolo
                        "snomed_details": {},
                        "custom_parameters": {
                            "display_name": group_rules.get('display_name', group_name),
                            "export_as_individual_mesh": False, # I gruppi sono sempre "non individuali"
                            "biological_category": group_rules.get('biological_category', 'Other')
                        }
                    }
                    print(f"    Segmenti {list(s['custom_parameters']['display_name'] for s in segments_in_this_group)} raggruppati e salvati.")
                else:
                    print(f"    Nessun volume combinato generato per il gruppo '{group_name}'.")

    # --- 2. Seconda Passata: Gestisci le Esportazioni Individuali ---
    print("\n--- Seconda Passata: Esportazioni Individuali ---")
    for seg_name, seg_data in all_segment_data.items():
        # Salta i segmenti che sono stati raggruppati E che non sono essi stessi una regola di combinazione
        if seg_name in grouped_segments and seg_name not in combined_mesh_rules:
            print(f"  Segmento '{seg_name}' gia' incluso in un gruppo. Salto l'esportazione individuale.")
            continue

        # Salta le voci che rappresentano le regole di combinazione, non sono segmenti reali da esportare qui
        if seg_name in combined_mesh_rules:
            continue

        if seg_data['custom_parameters'].get('export'):
            segment_id = seg_data['id']
            print(f"  Processando segmento individuale: '{seg_name}' (ID: {segment_id})")
            
            volume_mask = (nii_data == segment_id)
            output_stl_path = os.path.join(output_dir, f"{seg_name}.stl")
            convert_nii_to_stl(volume_mask, output_stl_path, spacing=voxel_spacing)
        else:
             print(f"  Segmento '{seg_name}' contrassegnato per non essere esportato individualmente.")

    print("\n--- Esportazione Mesh STL Completata ---")

def convert_nii_to_stl(volume, output_stl_path, spacing=(1.0, 1.0, 1.0)):
    """
    Converte un volume numpy in un file STL usando marching cubes e PyVista.
    Applica trasformazioni per orientamento, scala e spaziatura voxel.
    """
    if np.sum(volume) == 0:
        print(f"Attenzione: il volume per '{os.path.basename(output_stl_path)}' e' vuoto. Salto la creazione del mesh.")
        return

    # Estrai la superficie usando marching_cubes, tenendo conto della spaziatura
    vertices, faces, _, _ = marching_cubes(volume, level=0.5, spacing=spacing)

    # Converte le facce nel formato compatibile con PyVista
    # Prependi una colonna di '3' (per indicare triangoli) a ogni faccia
    faces_pv = np.hstack([np.full((len(faces), 1), 3), faces])

    # Crea il mesh con PyVista
    mesh = pv.PolyData(vertices, faces_pv)

    # Applica smoothing
    mesh = mesh.smooth(n_iter=80, relaxation_factor=0.2)
    
    # Salva il file STL
    mesh.save(output_stl_path)
    print(f"Mesh salvato in: {output_stl_path}")

def populate_custom_details_for_segments(all_segment_data, segment_rules, combined_mesh_rules):
    """
    Popola i parametri custom per i dati dei segmenti usando una logica di matching euristico.
    Cerca corrispondenze sia per il nome esatto del segmento sia per varianti piu'generiche.
    """
    unmapped_segments = []
    print("\n--- Fase: Popolamento dei Custom Parameters ---")

    for seg_name, segment_data in all_segment_data.items():
        custom_params = segment_data['custom_parameters']
        rule_found = False

        # Genera nomi candidati, dal piu' specifico al piu'generico
        candidate_names = utils.generate_snomed_candidate_names(seg_name)
        
        # Itera sui candidati per trovare una regola corrispondente
        for candidate in candidate_names:
            rule = segment_rules.get(candidate)
            if rule:
                print(f"  Match trovato per '{seg_name}' (via candidato '{candidate}') -> Categoria: {rule.get('biological_category', 'N/A')}")
                custom_params['display_name'] = rule.get('display_name', seg_name.replace("_", " ").title())
                custom_params['export'] = rule.get('export', True)
                custom_params['biological_category'] = rule.get('biological_category', 'Other')
                custom_params['color_override'] = rule.get('color_override', None)
                rule_found = True
                break  # Usa la prima regola trovata (la piu' specifica)

        # Se nessuna regola e' stata trovata dopo aver provato tutti i candidati, applica il fallback
        if not rule_found:
            unmapped_segments.append(seg_name)
            snomed_type = segment_data['snomed_details'].get('type')
            custom_params['display_name'] = snomed_type if snomed_type else seg_name.replace("_", " ").title()
            custom_params['export'] = True  # Default per i non mappati
            snomed_category = segment_data['snomed_details'].get('category')
            custom_params['biological_category'] = snomed_category if snomed_category else "Other"
            print(f"  AVVISO: Nessuna regola trovata per '{seg_name}' o i suoi candidati. Applicati valori di default (Categoria Fallback: {custom_params['biological_category']}).")

    if unmapped_segments:
        print(f"\n--- Riepilogo Segmenti Non Mappati ({len(unmapped_segments)}) ---")
        print("I seguenti segmenti non hanno trovato una corrispondenza diretta o tramite candidati in 'segment_rules':")
        for seg_name in unmapped_segments:
            print(f"  - {seg_name} (Categoria fallback: {all_segment_data[seg_name]['custom_parameters']['biological_category']})")
        print("Sono stati assegnati valori di default. Considera di aggiungere regole piu' generiche al file di mappatura se necessario.")

    return all_segment_data, unmapped_segments

def get_total_segmentator_class_map(ts_install_dir, target_task):
    map_to_binary_path = os.path.join(ts_install_dir, "map_to_binary.py")
    print (f"DEBUG: Using Class map located in in: {map_to_binary_path}")
    if ts_install_dir not in sys.path:
        sys.path.append(ts_install_dir)
    ## Per interrogare la class_map serve il metodo class_map da map_to_binary
    try:
        from map_to_binary import class_map
    except ImportError as e:
        print(f"Errore durante l'importazione di 'map_to_binary' o 'class_map': {e}")
        print("Assicurati che 'map_to_binary.py' si trovi nella directory specificata e che il nome sia corretto.")
        sys.exit(1)
    return class_map.get(target_task)

def run_total_segmentator(input_nifti_path, output_base_dir, tasks):
    """
    Lancia TotalSegmentator come processo esterno per segmentare un file NIfTI usando la modalita' --ml.
    Tutti i task specificati vengono eseguiti in una singola chiamata, e il risultato
    
    
    Restituisce True se la segmentazione ha successo, False altrimenti.
    """
    if not os.path.exists(input_nifti_path):
        print(f"Errore: File NIfTI di input non trovato in '{input_nifti_path}'")
        return None

    # Assicurati che la directory di output esista
    os.makedirs(output_base_dir, exist_ok=True)
    print(f"\nAvvio di TotalSegmentator (come processo esterno) per i task: {', '.join(tasks)}")
    
    # Definisci il percorso completo per il file NIfTI di output
    output_nii_filepath = os.path.join(output_base_dir, f"{config.PROJECT_SESSION_ID}.nii") # Atteso nii_segmented\PROJECT_SESSION_ID.nii
    print(f"DEBUG: Output multi-etichetta previsto in: {output_nii_filepath}")

    # Costruisci il comando. Il flag --ml implica che l'output sara' un singolo file
    # nella directory specificata da -o. L'argomento -ta puo' accettare piu' task.
    command = [
        sys.executable, # Usa l'interprete Python che sta eseguendo questo script
        config.TOTAL_SEGMENTATOR_SCRIPT_PATH,
        "-i", input_nifti_path,
        "-o", output_nii_filepath, # L'output va direttamente nella directory base
        "-ta", " ".join(tasks), # Passa tutti i task come una singola stringa separata da spazi
        "--device", config.TOTAL_SEGMENTATOR_DEVICE,
        "--ml"
    ]

    try:
        print(f"DEBUG: Comando TotalSegmentator: {' '.join(command)}")
        print(f"DEBUG: Esecuzione da directory: {config.TOTAL_SEGMENTATOR_INSTALL_DIR}")
        
        result = subprocess.run(
            command,
            check=True, # Lancia un CalledProcessError se il codice di uscita non e' 0
            capture_output=True,
            text=True,
            cwd=config.TOTAL_SEGMENTATOR_INSTALL_DIR,
            encoding=config.FILE_ENCODING
        )
        print(f"Segmentazione completata. Output salvato in '{output_base_dir}'.\n")
        print("DEBUG: --- TotalSegmentator STDOUT ---")
        print(result.stdout)
        print("DEBUG: ---\n")
        print("\n--- TotalSegmentator STDERR ---")
        print(result.stderr)
        print("---\n")
        return output_nii_filepath # Restituisci il percorso del file in caso di successo
    
    except subprocess.CalledProcessError as e:
        print(f"ERRORE CRITICO durante l'esecuzione di TotalSegmentator. Codice di uscita: {e.returncode}")
        print("\n--- TotalSegmentator STDOUT ---")
        print(e.stdout)
        print("---\n")
        print("\n--- TotalSegmentator STDERR ---")
        print(e.stderr)
        print("---\n")
        return None
    except FileNotFoundError:
        print(f"Errore: L'eseguibile Python o lo script TotalSegmentator non sono stati trovati.")
        print(f"Verifica che '{sys.executable}' e '{config.TOTAL_SEGMENTATOR_SCRIPT_PATH}' esistano.")
        return None
    except Exception as e:
        print(f"ERRORE INATTESO durante l'esecuzione di TotalSegmentator: {e}")
        import traceback
        traceback.print_exc()
        return None

def fetch_input_files(input_dir):
    """
    Cerca un file Nii o uno stack di DICOM da segmentare
    """
    print("--- Importazione NIfTI / Dicom ---")

    # Assicurati che le directory di output esistano
    os.makedirs(config.NII_RAW_DIR, exist_ok=True)
    os.makedirs(config.NII_SEGMENTED_DIR, exist_ok=True)
    os.makedirs(config.INPUT_MESH_DIR, exist_ok=True)

    # --- Logica di ricerca input migliorata ---
    input_nifti_file = None
    dicom_input_dir = None

    # 1. Cerca file NIfTI nella directory di input
    try:
        for item in os.listdir(input_dir):
            if item.endswith((".nii", ".nii.gz")):
                input_nifti_file = os.path.join(config.INPUT_DIR, item)
                print(f"Trovato file NIfTI di input: {input_nifti_file}")
                break
    except FileNotFoundError:
        print(f"Errore: La directory di input non esiste: {config.INPUT_DIR}")
        print("Controlla che le variabili CLIENT_ID e PROJECT_SESSION_ID in config.py corrispondano alla tua struttura di cartelle.")
        return

    # 2. Se non trovi NIfTI, controlla se la cartella stessa contiene file DICOM
    if not input_nifti_file:
        if any(f.lower().endswith(".dcm") for f in os.listdir(config.INPUT_DIR)):
            dicom_input_dir = config.INPUT_DIR
            print(f"Trovati file DICOM direttamente nella cartella di input: {dicom_input_dir}")
        else:
            # 3. Se no, cerca una sottocartella che potrebbe essere la cartella DICOM
            for item in os.listdir(config.INPUT_DIR):
                full_path = os.path.join(config.INPUT_DIR, item)
                if os.path.isdir(full_path):
                    dicom_input_dir = full_path
                    print(f"Trovata potenziale sottocartella DICOM: {dicom_input_dir}")
                    break

    # Se abbiamo una cartella DICOM, convertila
    if dicom_input_dir:
        print("Tentativo di conversione da DICOM a NIfTI.")
        nifti_output_path = os.path.join(config.NII_RAW_DIR, f"{config.PROJECT_SESSION_ID}.nii.gz")
        if not convert_dicom_to_nifti(dicom_input_dir, nifti_output_path):
            print("Conversione DICOM fallita. Interruzione.")
            return
        input_nifti_file = nifti_output_path
    
    # Controllo finale: se a questo punto non abbiamo un file NIfTI, errore.
    if not input_nifti_file:
        print(f"Errore: Nessun file NIfTI o cartella DICOM valida trovata nella directory di input: {config.INPUT_DIR}")
        return
    return input_nifti_file 
