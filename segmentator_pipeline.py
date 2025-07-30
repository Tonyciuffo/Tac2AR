# coding: utf-8
# segmentator_pipeline.py
import sys
import os

try:
    import config
    print("DEBUG: config importato.")
    import segmentator_ops
    print("DEBUG: segmentator_ops importato.")
    import utils
    print("DEBUG: utils importato.")
except ImportError as e:
    print(f"ERRORE CRITICO: Impossibile importare i moduli necessari. Assicurati che tutte le dipendenze siano installate (pip install -r requirements.txt). Dettagli: {e}")
    sys.exit(1)
except Exception as e:
    print(f"ERRORE INATTESO durante l'importazione dei moduli: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

def execute_segmentator_pipeline():
    print("DEBUG: segmentator_pipeline.py in esecuzione .")
    try:
        """
        Orchestra l'intera pipeline di segmentazione, dalla lettura dell'input
        all'esportazione dei file STL e del manifest.
        """
        print(f"--- Avvio Pipeline di Segmentazione per: {config.CLIENT_ID}, CASO: {config.PROJECT_SESSION_ID} ---")

        # --- Fase 0: Pulizia Opzionale delle Directory ---
        if config.CLEAN_SESSION_ON_START:
            print("\n--- Fase 0: Pulizia delle Directory della Sessione Precedente ---")
            utils.clean_session_directories()
        else:
            print("\n--- Fase 0: Pulizia saltata come da configurazione (CLEAN_SESSION_ON_START=False) ---")

        # --- 1. Trova e Prepara i File di Input ---
        print("\n--- Fase 1: Ricerca e Preparazione dei File di Input ---")
        input_nifti_file = segmentator_ops.fetch_input_files(config.INPUT_DIR)
        if not input_nifti_file:
            print("ERRORE: Nessun file di input valido trovato. Interruzione della pipeline.")
            return

        # --- 2. Esegui TotalSegmentator ---
        print("\n--- Fase 2: Esecuzione di TotalSegmentator ---")
        # L'output di TotalSegmentator con --ml e' un singolo file NIfTI multi-etichetta
        # nella directory specificata da -o.
        segmented_nii_path = segmentator_ops.run_total_segmentator(
            input_nifti_file,
            config.NII_SEGMENTED_DIR,
            config.TOTAL_SEGMENTATOR_TASKS
        )
        
        if segmented_nii_path:
            print(f"\nDEBUG: File NIfTI segmentato disponibile in: {segmented_nii_path}")
            print(f"DEBUG: Caricamento della Class Map")
            # 1. Importa le classi dei segmenti disponibili da TotalSegmentator (map_to_binary)
            # Questa e' la mappa ID numerico -> Nome stringa del segmento
            segment_id_to_name_map = segmentator_ops.get_total_segmentator_class_map(
                config.TOTAL_SEGMENTATOR_INSTALL_DIR,
                config.TOTAL_SEGMENTATOR_TASKS[0]
            )
            print(f"DEBUG: Class Map (Segment ID to Name Table) caricata: {len(segment_id_to_name_map)} entries.")

            # 1.5 Determina quali segmenti hanno un volume effettivo nel NIfTI
            valid_segment_ids = segmentator_ops.get_present_segment_ids(
                segmented_nii_path,
                segment_id_to_name_map # Passiamo questa mappa per i nomi nel debug
            )
            print(f"DEBUG: Segmenti con volume effettivo presenti: {sorted(list(valid_segment_ids))}")

            # 2. Inizializza la struttura dati centrale per tutti i segmenti *presenti*
            print("\nDEBUG: Inizializzazione struttura 'all_segment_data'")
            all_segment_data = {}
            for seg_id, seg_name in segment_id_to_name_map.items():
                if seg_id in valid_segment_ids:
                    all_segment_data[seg_name] = {
                        "id": seg_id,
                        "snomed_details": { # Inizializza con chiavi esplicite e valori None per consistenza
                            "category": None, # Anatomical, Tissue...
                            "type": None, # Spleen, Adrenal gland...
                            "type_modifier": None, # Left, Anterior
                            "region": None, # Kidney, Lung
                            "type_code": None, # 23451007... Usato per interrogare un database snomed esterno
                        },
                        "custom_parameters": {
                            "display_name": None, # Nice name o snomed type
                            "export_as_individual_mesh": None, # definito in segmentMappings.yaml
                            "biological_category": None, # categoria per trovare corrispondenza con il materiale
                            "shader_ref": None, # dizionario interno di materiali e "hook" tra segmentMappings e blender_shader_registry
                            "blend_file": None, # nome file .blend contentente il materiale
                            "blend_material": None, # nome del materiale per convenzione nomeFile_mat
                            "color_override": None # per discriminare vene-arterie e colori specifici
                        }
                    }
                #else:
                    # print(f"DEBUG: Segmento '{seg_name}' (ID: {seg_id}) escluso da 'all_segment_data' perche' ha volume zero.")
            print("DEBUG: Struttura 'all_segment_data' inizializzata")

            # 3. Carica i dati SNOMED dal CSV per utilizzatli come lookup table, utili ad identificare il segmento.
            # Vengono generati 4 dizionari ordinati per 'Structure' (indice principale), type, region, category.
            snomed_data_indices = segmentator_ops.load_snomed_mappings(
                config.TOTAL_SEGMENTATOR_SNOMED_MAPPING,
                encoding=config.FILE_ENCODING
            )
            if snomed_data_indices is None:
                raise Exception("Impossibile caricare i dati di mappatura SNOMED.")

            # 4. Popola all_segment_data con gli snomed_details
            segmentator_ops.populate_snomed_details_for_segments(
                all_segment_data,
                snomed_data_indices["by_structure"],
                snomed_data_indices["by_type"],
                snomed_data_indices["by_region"],
                snomed_data_indices["by_category"]
            )

            # 5. Carica le mappature dal file YAML (per le regole di export/combinazione)
            print(f"\nDEBUG: Caricamento dei dati SNOMED\n")
            segment_mappings_yaml = utils.read_yaml(config.SEGMENT_MAPPINGS_FILE)
            if not segment_mappings_yaml:
                print("Nessuna mappatura caricata o file non trovato.")
            else:
                print(f"DEBUG: YAML Mappings caricato da {config.SEGMENT_MAPPINGS_FILE}: {len(segment_mappings_yaml)} entries.\n")

            # --- Fase di Popolamento dei Custom Parameters per l'Export STL ---
            # Carica la 
            print("\nDEBUG:--- Fase: Popolamento dei Custom Parameters per l'export individuale / combinato ---")
            individual_mesh_rules = segment_mappings_yaml.get('individual_mesh_export', {})
            combined_mesh_rules = segment_mappings_yaml.get('combined_mesh_export', {})
            
            segmentator_ops.populate_custom_details_for_segments(all_segment_data, individual_mesh_rules, combined_mesh_rules)
            print("\nDEBUG:--- Popolamento Custom Parameters per l'export completato. ---")

            # --- Fase di Esportazione STL ---
            print(f"\n--- Esportazione STL ---")
            segmentator_ops.export_stl_from_multilabel_nii(
                nii_filepath=segmented_nii_path,
                all_segment_data=all_segment_data,
                combined_mesh_rules=combined_mesh_rules,
                output_dir=config.INPUT_MESH_DIR
            )

            # --- Fase di Scrittura del Manifest ---
            print(f"\nDEBUG:--- Scrittura del Manifest dei Segmenti ---")
            # Assicurati che la directory di output esista prima di scrivere il file
            output_dir = os.path.dirname(config.SEGMENTS_DATA_MANIFEST_FILE)
            os.makedirs(output_dir, exist_ok=True)
            
            utils.write_json(all_segment_data, config.SEGMENTS_DATA_MANIFEST_FILE)
            print(f"Manifest salvato in: {config.SEGMENTS_DATA_MANIFEST_FILE}")
            
            print("\n--- Pipeline di Segmentazione e Creazione Mesh STL completata con successo. ---")

        else: # segmented_nii_path e' None
            print("AVVISO: La segmentazione NIfTI non ha prodotto un file valido. La pipeline di esportazione STL verra' saltata.")

    except Exception as e:
        print(f"ERRORE CRITICO durante la pipeline di segmentazione: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    execute_segmentator_pipeline()