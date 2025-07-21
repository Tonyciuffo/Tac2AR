# blender_pipeline.py
import os
import sys

print("--- blender_pipeline.py: Inizio esecuzione ---")

# Aggiungi la directory dello script al path per trovare i moduli custom
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)
print(f"DEBUG: Aggiunto al sys.path: {script_dir}")

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

# Aggiungi il percorso degli add-on di Blender al sys.path DOPO l'import di config
# if config.BLENDER_STL_ADDON_DIR not in sys.path:
#    sys.path.append(config.BLENDER_STL_ADDON_DIR)
# print(f"DEBUG: Aggiunto al sys.path: {config.BLENDER_STL_ADDON_DIR}")

def execute_blender_pipeline():
    """
    Orchestra l'intera pipeline di elaborazione 3D all'interno di Blender.
    """
    print("\n*** AVVIO PIPELINE BLENDER ***")

    # Ensure output directories exist
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.TEXTURES_DIR, exist_ok=True)
    print(f"  Output directory ensured: {config.OUTPUT_DIR}")
    print(f"  Textures directory ensured: {config.TEXTURES_DIR}")

    # Enable STL add-on
#    addon_name = config.BLENDER_STL_ADDON_NAME
#    if not bpy.context.preferences.addons.get(addon_name) or not bpy.context.preferences.addons[addon_name].bl_info.get('enabled'):
#        print(f"  Attempting to enable add-on '{addon_name}'...")
#        try:
#            bpy.ops.preferences.addon_enable(module=addon_name)
#            print(f"  Add-on '{addon_name}' enabled.")
#        except Exception as e:
#            print(f"  Error enabling add-on '{addon_name}': {e}")
#            return

    # --- 1. Setup Iniziale ---
    print("\n--- Fase 1: Setup Ambiente e Scena ---")
    blender_ops.setup_blender_environment()
    blender_ops.clear_blender_scene()
    all_nodes_to_clean_up = [] # tutti i nodi da pulire (nomi)

    # --- 2. Caricamento delle Regole e del Manifest ---
    print("\n--- Fase 2: Caricamento delle Regole e del Manifest ---")
    try:
        blender_shader_registry = utils.read_yaml(config.BLENDER_SHADER_REGISTRY_FILE)
        print(f"  Registro degli asset caricato da: {config.BLENDER_SHADER_REGISTRY_FILE}")
        
        segments_manifest = utils.read_json(config.SEGMENTS_DATA_MANIFEST_FILE)
        print(f"  Manifest dei segmenti caricato da: {config.SEGMENTS_DATA_MANIFEST_FILE}")

    except FileNotFoundError as e:
        print(f"ERRORE: File fondamentale non trovato: {e}. Assicurati che la pipeline di segmentazione sia stata eseguita correttamente.")
        return
    except Exception as e:
        print(f"ERRORE: Impossibile caricare i file di configurazione. Dettagli: {e}")
        return

    # --- 3. Arricchimento del Manifest con i Dati dei Materiali ---
    print("\n--- Fase 3: Arricchimento del Manifest con i Dati dei Materiali ---")
    enriched_manifest = blender_ops.enrich_segment_data_with_materials(segments_manifest, blender_shader_registry)
    # Salva il manifest arricchito per il debug
    enriched_manifest_path = os.path.join(config.OUTPUT_DIR, "enriched_manifest.json")
    utils.write_json(enriched_manifest, enriched_manifest_path)
    print(f"  Manifest arricchito salvato per debug in: {enriched_manifest_path}")


    # --- 4. Importazione delle Mesh ---
    print(f"\n--- Fase 4: Importazione dei Mesh da '{config.INPUT_MESH_DIR}' ---")
    if not os.path.exists(config.INPUT_MESH_DIR) or not os.listdir(config.INPUT_MESH_DIR):
        print(f"ERRORE: La directory di input '{config.INPUT_MESH_DIR}' non esiste o e' vuota. Nessun mesh da processare.")
        return
        
    imported_meshes = blender_ops.import_meshes_into_blender_scene(config.INPUT_MESH_DIR)
    if not imported_meshes:
        print("ERRORE: Nessun mesh e' stato importato. Interruzione della pipeline.")
        return
    print(f"  Importati {len(imported_meshes)} mesh.")

    # --- 5. Applicazione dei Materiali ---
    print("\n--- Fase 5: Applicazione dei Materiali ---")
    blender_ops.apply_materials_from_manifest(imported_meshes, enriched_manifest)
   
    # --- 6. Ottimizzazione dei Mesh ---
    print("\n--- Fase 6: Ottimizzazione dei Mesh ---")
    blender_ops.fix_normal_orientation(imported_meshes)
    blender_ops.merge_vertices_by_distance(imported_meshes, config.MERGE_DISTANCE)
    blender_ops.delete_small_features(imported_meshes)
    blender_ops.decimate_mesh_objects(imported_meshes, config.MAX_FACES_PER_MESH)
    blender_ops.apply_smoothing_normals(imported_meshes, config.NORMAL_SMOOTHING_METHOD)

    # --- 7. Centratura e Gerarchia ---
    print("\n--- Fase 7: Centratura e Creazione Gerarchia ---")
    # Create a single root for all imported meshes
    scene_root = blender_ops.create_single_scene_root(imported_meshes, bpy.context.scene.cursor.location, config.ROOT_NAME_BASE)
    if not scene_root:
        print("ERRORE: Impossibile creare l'oggetto Root della scena. Interruzione della pipeline.")
        return
    print(f"  Creato un singolo oggetto Root: '{scene_root.name}'.")

    # Creata le mappe UV
    print("\n--- Phase: UV Mapping and Texture Bake ---")
    blender_ops.uv_map(imported_meshes, config.TEXTURE_SIZE)

    # --- SALVA LA SCENA PRIMA DEL BAKE --- (per interventi sul materiale)
    blender_ops.save_blender_scene(config.OUTPUT_DIR, f"{config.PROJECT_SESSION_ID}_01_procedural_materials.blend")

    # Appica i modificatori alle mesh (freeze history)
    blender_ops.apply_all_modifiers(imported_meshes)

    # Setup bake parameters
    print("\n--- Phase: Bake Setup ---")
    blender_ops.bake_setup(config.BLENDER_DEVICE)

    # --- 8. Baking delle Texture ---
    print("\n--- Fase 8: Baking delle Texture ---")
    bake_nodes_created = blender_ops.bake_textures(imported_meshes, config.TEXTURES_DIR, config.TEXTURE_SIZE, config.BLENDER_DEVICE)
    all_nodes_to_clean_up.extend(bake_nodes_created)

    # Link baked texture back to the material (Metallic/Riughness Adobe PBR Standard)
    pbr_link_nodes_created = blender_ops.link_baked_textures(imported_meshes, config.TEXTURES_DIR)
    all_nodes_to_clean_up.extend(pbr_link_nodes_created)

    # --- SAVE SCENE BEFORE EXPORT --- (piu' per debug)
    blender_ops.save_blender_scene(config.OUTPUT_DIR, f"{config.PROJECT_SESSION_ID}_02_baked_materials.blend")

    # --- 9. Esportazione GLB (PBR Standard) ---
    print("\n--- Fase 9: Esportazione in formato GLB (PBR) ---")
    blender_ops.export_glb(os.path.join(config.OUTPUT_DIR, config.PBR_FILENAME), scene_root)

    # --- 10. Esportazione FBX (Unity URP) ---
    print("\n--- Fase 10: Esportazione in formato FBX (URP) ---")

    # Crea la metalic_smoothnes
    blender_ops.create_metallic_smoothness_map(imported_meshes, config.TEXTURES_DIR, config.TEXTURE_SIZE)
    
    # Modifica i collegamenti delle texture per lo standard URP
    urp_nodes_created = blender_ops.update_shader_nodes_for_unity_export(imported_meshes, config.TEXTURES_DIR)
    all_nodes_to_clean_up.extend(urp_nodes_created)

    # Esporta la geometria
    blender_ops.export_fbx(os.path.join(config.OUTPUT_DIR, config.URP_FILENAME), [scene_root])

    # --- 11. Pulizia Finale ---
    print("\n--- Fase 11: Pulizia Finale ---")
    blender_ops.remove_bake_temp_nodes(all_nodes_to_clean_up)

    print("\n*** PIPELINE BLENDER COMPLETATA CON SUCCESSO ***")

if __name__ == "__main__":
    execute_blender_pipeline()
