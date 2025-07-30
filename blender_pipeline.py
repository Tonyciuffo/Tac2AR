# coding: utf-8
# blender_pipeline.py
import os
import sys
import subprocess

def execute_blender_pipeline():
    """
    Orchestra l'intera pipeline di elaborazione 3D all'interno di Blender.
    """
    # Importa i moduli custom e di configurazione
    try:
        print("DEBUG: Tentativo di importare i moduli: bpy, config, utils, blender_ops...")
        import bpy
        import config
        import utils
        import blender_ops
        print("DEBUG: Moduli importati con successo.")
    except ImportError as e:
        print(f"ERRORE CRITICO: Impossibile importare un modulo fondamentale. Controlla che le librerie necessarie (es. PyYAML) siano installate nell'ambiente Python di Blender. Dettagli: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERRORE INATTESO durante l'importazione: {e}")
        sys.exit(1)

    (f"--- Avvio Pipeline di Blender per: {config.CLIENT_ID}, CASO: {config.PROJECT_SESSION_ID} ---")

    # Ensure output directories exist
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.TEXTURES_DIR, exist_ok=True)
    print(f"  Output directory ensured: {config.OUTPUT_DIR}")
    print(f"  Textures directory ensured: {config.TEXTURES_DIR}")

    # --- 1. Setup Iniziale ---
    print("\n--- Fase 1: Setup Ambiente e Scena ---")
    blender_ops.setup_blender_environment()
    blender_ops.clear_blender_scene()
    all_nodes_to_clean_up = [] # tutti i nodi e oggetti temporanei da pulire (nomi)

    # --- 2. Caricamento Shader Registry e Manifest ---
    print("\n--- Fase 2: Caricamento delle Regole dallo Shader Registry e del Manifest dei Segmenti ---")
    try:

        blender_shader_registry = utils.read_json(config.BLENDER_SHADER_REGISTRY_TMP)
        print(f"  Registro degli asset (da JSON) caricato da: {config.BLENDER_SHADER_REGISTRY_TMP}")
        segments_manifest = utils.read_json(config.SEGMENTS_DATA_MANIFEST_FILE)
        print(f"  Manifest dei segmenti caricato da: {config.SEGMENTS_DATA_MANIFEST_FILE}")

    except FileNotFoundError as e:
        print(f"ERRORE: File fondamentale non trovato: {e}. Assicurati che la pipeline di segmentazione sia stata eseguita correttamente.")
        return
    except Exception as e:
        print(f"ERRORE: Impossibile caricare i file di configurazione. Dettagli: {e}")
        return

    # --- 3. Matcha i materiali dal manifest ---
    print("\n--- Fase 3: Match dei materiali in bse alle regole del Manifest ---")
    enriched_manifest = blender_ops.match_materials_on_manifest(segments_manifest, blender_shader_registry)
    # Salva il manifest arricchito per il debug
    enriched_manifest_path = os.path.join(config.OUTPUT_DIR, "enriched_manifest.json")
    utils.write_json(enriched_manifest, enriched_manifest_path)
    print(f"  Manifest arricchito e salvato per debug in: {enriched_manifest_path}")


    # --- 4. Importazione delle Mesh ---
    print(f"\n--- Fase 4: Importazione dei Mesh da '{config.INPUT_MESH_DIR}' ---")
    if not os.path.exists(config.INPUT_MESH_DIR) or not os.listdir(config.INPUT_MESH_DIR):
        print(f"ERRORE: La directory di input '{config.INPUT_MESH_DIR}' non esiste o e' vuota. Nessun mesh da processare.")
        return
        
    imported_meshes = blender_ops.import_meshes_into_blender_scene(config.INPUT_MESH_DIR)
    if not imported_meshes:
        print("ERRORE: Nessun mesh e' stato importato. Interruzione della pipeline.")
        return
    print(f"  Importate {len(imported_meshes)} mesh.")

    # --- 5. Applicazione Scala Globale ---
    print(f"\n--- Fase 5: Applicazione unita' in scala reale, fattore di conversione: '{config.WORLD_SCALE_FACTOR}' ---")
    blender_ops.apply_world_scale(imported_meshes, config.WORLD_SCALE_FACTOR)

    # --- 6. Centratura e Gerarchia ---
    print("\n--- Fase 6: Centratura e Creazione Gerarchia ---")
    # Create a single root for all imported meshes
    scene_root = blender_ops.create_single_scene_root(imported_meshes, config.ROOT_NAME_BASE)
    if not scene_root:
        print("ERRORE: Impossibile creare l'oggetto Root della scena. Interruzione della pipeline.")
        return
    print(f"  Geometrie parentate sotto unico Root: '{scene_root.name}'.")

    # --- 7. Ottimizzazione dei Mesh ---
    print("\n--- Fase 7: Ottimizzazione dei Mesh ---")
    blender_ops.fix_normal_orientation(imported_meshes) # all normals out
    blender_ops.merge_vertices_by_distance(imported_meshes, config.MERGE_DISTANCE) # disconnected faces
    polycount, poly_removed = blender_ops.decimate_mesh_objects(imported_meshes, config.MAX_FACES_PER_MESH, segments_manifest) # decimation
    print (f"RECAP DECIMATION: Total: '{polycount}', Removed: '{poly_removed}'")
    blender_ops.delete_small_features(imported_meshes, config.MERGE_DISTANCE) # dissolve_degenerate to fix potential decimation leftovers
    blender_ops.apply_smoothing_normals(imported_meshes, config.NORMAL_SMOOTHING_METHOD) # smoth

    # --- 8. Creata le mappe UV
    print("\n--- Fase 8: UV Mapping  ---")
    blender_ops.uv_map(imported_meshes, config.TEXTURE_SIZE)

    # --- 9. Applicazione dei Materiali ---
    print("\n--- Fase 9: Applicazione dei Materiali ---")
    template_nodes = blender_ops.apply_materials_from_manifest(imported_meshes, enriched_manifest)
    # blender_ops.apply_materials_from_manifest(imported_meshes, enriched_manifest)
    all_nodes_to_clean_up.extend(template_nodes) # Template materials and projectors

    # --- 10 SALVA LA SCENA PRIMA DEL BAKE --- (per interventi sul materiale)
    print("\n--- Fase 10: Salvataggio scena con history  ---")
    blender_ops.save_blender_scene(config.OUTPUT_DIR, f"{config.PROJECT_SESSION_ID}_01_history.blend")

    # --- 11 Applica i modificatori alle mesh (freeze history)
    print("\n--- Fase 11: Baking dei modificatori e deformatori ---")
    blender_ops.apply_all_modifiers(imported_meshes)

    # --- 12 Baking delle Texture ---
    print("\n--- Fase 12: Baking delle Texture ---")
    blender_ops.bake_textures(imported_meshes, config.TEXTURES_DIR, config.TEXTURE_SIZE, config.BLENDER_DEVICE)

    # --- 13 Crea la mappa metalness per lo standard Adobe PBR
    print("\n--- Fase 13: Creazione Mappa di Metalness in standard PBR ---")
    blender_ops.create_base_metalness_map(imported_meshes, config.TEXTURES_DIR, config.TEXTURE_SIZE)

    # --- 14 Collega le texture al materiale (Metallic/Roughness Adobe PBR Standard)
    print("\n--- Fase 14: Collegamento nodi texture in standard PBR")
    blender_ops.link_baked_textures(imported_meshes, config.TEXTURES_DIR)
    # all_nodes_to_clean_up.extend(temp_pbr_nodes_created)

    # --- 15 Pulizia Nodi ---
    print("\n--- Fase 15: Pulizia Nodi ---")
    blender_ops.remove_bake_temp_nodes(all_nodes_to_clean_up) # FOLLIA QUI ?

    # --- 16 SALVA LA SCENA DOPO DEL BAKE --- (per debug PBR)
    print("\n--- Fase 16: Salvataggio scena con i bake PBR applicati ---")
    blender_ops.save_blender_scene(config.OUTPUT_DIR, f"{config.PROJECT_SESSION_ID}_02_baked_PBR.blend")

    # --- 17 Esportazione GLB (PBR Standard) ---
    print("\n--- Fase 17: Esportazione in formato GLB (PBR) ---")
    blender_ops.export_glb(os.path.join(config.OUTPUT_DIR, config.PBR_FILENAME), scene_root)

    # --- 18 Crea la metalic_smoothnes ---
    print("\n--- Fase 18: Creazione Mappa di Metalness in standard URP ---")
    blender_ops.create_metallic_smoothness_map(imported_meshes, config.TEXTURES_DIR, config.TEXTURE_SIZE)
    
    # --- 19 Collega le texture al materiale (Unity URP Standard)
    print("\n--- Fase 19: Collegamento nodi texture in standard URP")
    urp_nodes_created = blender_ops.update_shader_nodes_for_unity_export(imported_meshes, config.TEXTURES_DIR)
    all_nodes_to_clean_up.extend(urp_nodes_created)

    # --- 20. Pulizia Finale ---
    print("\n--- Fase 20: Pulizia Finale ---")
    blender_ops.remove_bake_temp_nodes(all_nodes_to_clean_up)

    # --- 21 SALVA LA SCENA DOPO DEL BAKE --- (per debug URP)
    print("\n--- Fase 21: Salvataggio scena con i bake URP applicati ---")
    blender_ops.save_blender_scene(config.OUTPUT_DIR, f"{config.PROJECT_SESSION_ID}_02_baked_URP.blend")

    # --- 22 # Esporta la geometria in Fbx
    print("\n--- Fase 22: Esportazione in formato FBX (URP) ---")
    blender_ops.export_fbx(os.path.join(config.OUTPUT_DIR, config.URP_FILENAME), [scene_root])

    print("\n*** PIPELINE BLENDER COMPLETATA CON SUCCESSO ***")

if __name__ == "__main__":
    # Questo blocco gestisce il caso in cui lo script venga eseguito direttamente
    # (es. "python blender_pipeline.py") invece che da main.py.

    # Aggiungi la directory dello script al path di Python per trovare i moduli custom
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.append(script_dir)
        print(f"DEBUG: Aggiunto al sys.path: {script_dir}")

    # Discrimina l'ambiente
    try:
        import bpy
        is_inside_blender = True
    except ImportError:
        is_inside_blender = False

    # --- Logica di Esecuzione ---
    if is_inside_blender:
        execute_blender_pipeline()
    else:
        print("--- Esecuzione Stand-Alone Rilevata ---")

        # Importa i moduli necessari per la preparazione
        import config
        import utils

        # --- 1. Preparazione dell'Ambiente ---
        print("1. Preparazione dell'ambiente e delle directory...")
        try:
            # La pipeline di Blender ha bisogno che la directory di sessione in Tmp
            # esista per il file JSON, e la directory di Output per i suoi risultati.
            tmp_session_dir = os.path.dirname(config.BLENDER_SHADER_REGISTRY_TMP)
            os.makedirs(tmp_session_dir, exist_ok=True)
            os.makedirs(config.OUTPUT_DIR, exist_ok=True)
            print(f"  Directory assicurata: {tmp_session_dir}")
            print(f"  Directory assicurata: {config.OUTPUT_DIR}")
        except Exception as e:
            print(f"ERRORE CRITICO: Impossibile creare le directory necessarie. Dettagli: {e}")
            sys.exit(1)

        # --- 2. Conversione del Registro Shader in JSON ---
        print("2. Conversione del registro shader in formato JSON...")
        try:
            utils.yaml_to_json(
                config.BLENDER_SHADER_REGISTRY_FILE,
                config.BLENDER_SHADER_REGISTRY_TMP
            )
        except Exception as e:
            print(f"ERRORE CRITICO: Impossibile creare il file di registro JSON. Interruzione. Dettagli: {e}")
            sys.exit(1)

        # --- 3. Lancio del Sottoprocesso Blender ---
        print("3. Avvio di Blender in background...")
        blender_pipeline_script_path = os.path.join(script_dir, "blender_pipeline.py")
        blender_executable = config.BLENDER_EXECUTABLE
        command = [
            blender_executable,
            "--factory-startup",
            "--background",
            "--python", blender_pipeline_script_path
        ]

        try:
            result = subprocess.run(
                command,
                check=True,
                text=True,
                capture_output=True,
                encoding=config.FILE_ENCODING
            )
            print("\n--- BLENDER STDOUT (catturato) ---")
            print(result.stdout)
            if result.stderr:
                print("\n--- BLENDER STDERR (catturato) ---")
                print(result.stderr)
            print("\n--- Esecuzione Stand-Alone di Blender completata. ---")
        except subprocess.CalledProcessError as e:
            print(f"\nERRORE CRITICO durante l'esecuzione di Blender. Codice di uscita: {e.returncode}")
            print(f"--- BLENDER STDOUT (catturato) ---\n{e.stdout}")
            if e.stderr:
                print(f"--- BLENDER STDERR (catturato) ---\n{e.stderr}")
            sys.exit(1)
        except FileNotFoundError:
            print(f"ERRORE: L'eseguibile di Blender non è stato trovato in '{blender_executable}'. Controlla il percorso in config.py.")
            sys.exit(1)

