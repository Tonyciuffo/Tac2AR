# config.py
import os
import sys

# --- IMPOSTAZIONI GENERALI DEL PROGETTO ---

# ID del cliente corrente. Usato per la strutturazione delle directory e i nomi dei file.
CLIENT_ID = "HUVANT_TEST"

# ID della sessione del progetto corrente (es. ID scansione paziente). Usato per la strutturazione delle directory e i nomi dei file.
PROJECT_SESSION_ID = "CASE_001_SCAN_01"

# --- IMPOSTAZIONI SEGMENTATOR ---

# Task/s di segmentazione da eseguire (es. ['total'], ['lung_vessels'], ['tissue_types'], etc.)
# La libreria TotalSegmentator verra' chiamata direttamente per ogni task nella lista.
TOTAL_SEGMENTATOR_TASKS = ['total']

# Device da usare per la segmentazione ('gpu' o 'cpu').
TOTAL_SEGMENTATOR_DEVICE = "gpu"

# --- IMPOSTAZIONI DEL MODELLO E DEL BAKING ---

# Distanza massima per la fusione dei vertici (Merge by Distance).
MERGE_DISTANCE = 0.0001

# Limite massimo di facce per mesh dopo la decimazione.
MAX_FACES_PER_MESH = 10000

# Metodo di smoothing delle normali ('WEIGHTED' o 'AVERAGE').
NORMAL_SMOOTHING_METHOD = 'WEIGHTED'

# Dimensione delle texture generate (larghezza e altezza in pixel).
TEXTURE_SIZE = 512

# Device da usare per il bake ('gpu' o 'cpu').
BLENDER_DEVICE="gpu"

# Fattore di scala per convertire le unita' del file STL (tipicamente mm) nelle unita' di Blender (m).
# Default: 0.001 (per conversione da millimetri a metri).
# Per pollici a metri, usare 0.0254.
WORLD_SCALE_FACTOR = 0.001

# Base per il nome dell'oggetto root generato da Blender (e.g., "GeneratedModel").
ROOT_NAME_BASE = PROJECT_SESSION_ID
ROOT_WORLD_POSITION = (0.0, 0.0, 0.0)

# --- STRUTTURA DIRECTORY E FILE ---

INPUT_DIR_NAME = "Input"
NII_RAW_DIR_NAME = "nii_raw"
NII_SEGMENTED_DIR_NAME = "nii_segmented"
TMP_DIR_NAME="Tmp"
INPUT_MESH_DIR_NAME = "mesh_intermediate"
SHADERS_DIR_NAME = "Shaders"
TEXTURES_DIR_NAME = "Textures"
OUTPUT_DIR_NAME = "Output"
SEGMENT_MAPPINGS_FILE_NAME = "segmentMappings.yaml"
BLENDER_SHADER_REGISTRY_FILE_NAME = "blender_shader_registry.yaml"
SEGMENTS_DATA_FILE_NAME = "segments_data_manifest.json"
OUTPUT_SUFFIX = "_processed"
EXTENSION_PBR = "glb"
EXTENSION_URP = "fbx"

# --- PERCORSI RICAVATI ---

# Directory radice del progetto. Tutte le altre directory saranno relative a questa.
PROJECT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = PROJECT_ROOT_DIR
INPUT_DIR = os.path.join(PROJECT_ROOT_DIR, INPUT_DIR_NAME, CLIENT_ID, PROJECT_SESSION_ID)
TMP_DIR = os.path.join(PROJECT_ROOT_DIR, TMP_DIR_NAME)
NII_RAW_DIR = os.path.join(TMP_DIR, CLIENT_ID, PROJECT_SESSION_ID, NII_RAW_DIR_NAME)
NII_SEGMENTED_DIR = os.path.join(TMP_DIR, CLIENT_ID, PROJECT_SESSION_ID, NII_SEGMENTED_DIR_NAME)
INPUT_MESH_DIR = os.path.join(TMP_DIR, CLIENT_ID, PROJECT_SESSION_ID, INPUT_MESH_DIR_NAME)
SHADERS_DIR = os.path.join(PROJECT_ROOT_DIR, SHADERS_DIR_NAME)

# Make OUTPUT_DIR and TEXTURES_DIR absolute paths
OUTPUT_BASE_DIR = os.path.join(PROJECT_ROOT_DIR, OUTPUT_DIR_NAME) # New base for output
OUTPUT_DIR = os.path.join(PROJECT_ROOT_DIR, OUTPUT_DIR_NAME, CLIENT_ID, PROJECT_SESSION_ID)
TEXTURES_DIR = os.path.join(OUTPUT_DIR, TEXTURES_DIR_NAME)
SEGMENT_MAPPINGS_FILE = os.path.join(PROJECT_ROOT_DIR, SEGMENT_MAPPINGS_FILE_NAME)
BLENDER_SHADER_REGISTRY_FILE = os.path.join(PROJECT_ROOT_DIR, BLENDER_SHADER_REGISTRY_FILE_NAME)
SEGMENTS_DATA_MANIFEST_FILE = os.path.join(OUTPUT_DIR, SEGMENTS_DATA_FILE_NAME)
# Nomi dei file di output finali
PBR_FILENAME = f"{PROJECT_SESSION_ID}{OUTPUT_SUFFIX}.{EXTENSION_PBR}" # Esempio: CASE_001_SCAN_01_processed.glb
URP_FILENAME = f"{PROJECT_SESSION_ID}{OUTPUT_SUFFIX}.{EXTENSION_URP}" # Esempio: CASE_001_SCAN_01_processed.fbx

# --- PERCORSI BLENDER ---

BLENDER_INSTALL_ROOT = os.path.join(PROJECT_ROOT_DIR, "Blender") # QUESTA DEVE ESSERE LA CARTELLA CHE CONTIENE DIRETTAMENTE "blender.exe"
BLENDER_EXECUTABLE = os.path.join(BLENDER_INSTALL_ROOT, "blender.exe")
BLENDER_PYTHON_DIR = "4.5\\python\\bin"
BLENDER_DEVICE = "GPU" # Device for baking ('CPU', 'CUDA', 'OPTIX')

# --- PERCORSI TOTAL SEGMENTATOR ---

TOTAL_SEGMENTATOR_INSTALL_DIR = os.path.join(os.path.dirname(sys.executable), "..", "Lib", "site-packages", "totalsegmentator") # Se installato tramite pip
TOTAL_SEGMENTATOR_SCRIPT_PATH = os.path.join(TOTAL_SEGMENTATOR_INSTALL_DIR, "bin", "TotalSegmentator.py")
# File contenente TUTTE le definizioni dei segmenti costruisce il registro fisso
TOTAL_SEGMENTATOR_SNOMED_MAPPING = os.path.join(TOTAL_SEGMENTATOR_INSTALL_DIR, "resources", "totalsegmentator_snomed_mapping.csv")
TOTAL_SEGMENTATOR_SNOMED_KEY = 'Structure'
TOTAL_SEGMENTATOR_SNOMED_ENCODING = 'utf-8'