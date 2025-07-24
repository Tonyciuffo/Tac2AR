# main.py (Orchestrator)
import os
import sys
import subprocess
import config
# import io

print("DEBUG: main.py avviato (prima del logging).")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file_path = os.path.join(script_dir, 'pipeline.log')
    # Salva i riferimenti a stdout e stderr originali prima di qualsiasi reindirizzamento
    original_stdout = sys.stdout
    original_stderr = sys.stderr

   # original_stdout_buffer = sys.stdout.buffer
    #original_stderr_buffer = sys.stderr.buffer

    #sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    #sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    # Stampa un messaggio sulla console originale prima di reindirizzare
    print(f"L'output completo verra salvato in: {log_file_path}")

    try:
        # Apri il file di log in modalita' scrittura, sovrascrivendo il contenuto precedente
        with open(log_file_path, 'w') as log_file:
            # Reindirizza stdout e stderr al file di log
            sys.stdout = log_file
            sys.stderr = log_file
            print(f"DEBUG: Logging reindirizzato al file {log_file_path}")

            print("\n--- Avvio Pipeline ---\n")
            # --- 1. ESEGUI LA PIPELINE DI SEGMENTAZIONE ---
            print("--- FASE 1: Avvio Pipeline di Segmentazione ---")
            segmentation_script_path = os.path.join(script_dir, "segmentator_pipeline.py")
            python_executable = os.path.join(sys.prefix, 'Scripts', 'python.exe')
            if not os.path.exists(python_executable):
                print(f"Errore: Eseguibile Python (della VENV) non trovato in '{python_executable}'.")
                sys.exit(1)
            
            try:
                print(f"DEBUG: Esecuzione di {python_executable} {segmentation_script_path}")
                result = subprocess.run(
                    [python_executable, segmentation_script_path],
                    check=True,
                    text=True,
                    capture_output=True,
                    #encoding=config.TOTAL_SEGMENTATOR_SNOMED_ENCODING
                    )
                print("Pipeline di segmentazione completata con successo.\n")
                print("--- SEGMENTATION STDOUT (catturato) ---")
                print(result.stdout)
                if result.stderr:
                    print("--- SEGMENTATION STDERR (catturato) ---")
                    print(result.stderr)
            except subprocess.CalledProcessError as e:
                print(f"ERRORE CRITICO durante la pipeline di segmentazione. Codice di uscita: {e.returncode}")
                print(f"--- SEGMENTATION STDOUT (catturato) ---")
                print(e.stdout)
                if e.stderr:
                    print(f"--- SEGMENTATION STDERR (catturato) ---")
                    print(e.stderr)
                sys.exit(1)
            except FileNotFoundError:
                print(f"ERRORE: Lo script di segmentazione non e' stato trovato in '{segmentation_script_path}'.")
                sys.exit(1)
            except Exception as e:
                print(f"ERRORE INATTESO durante il lancio della segmentazione: {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)

            # --- 2. ESEGUI LA PIPELINE DI BLENDER ---
            print("\n--- FASE 2: Avvio della Pipeline di Blender ---")
            blender_pipeline_script_path = os.path.join(script_dir, "blender_pipeline.py")
            blender_executable = config.BLENDER_EXECUTABLE
            if not os.path.exists(blender_pipeline_script_path):
                print(f"ERRORE: Script Blender Pipeline non trovato in: '{blender_pipeline_script_path}'.")
                sys.exit(1)
            if not os.path.exists(blender_executable):
                print(f"Errore: Eseguibile di Blender non trovato in '{blender_executable}'.")
                sys.exit(1)

            # Comando esecuzione Blender con --background e --factory-startup
            command = [
                blender_executable,
                "--factory-startup",
                "--background",
                "--python", blender_pipeline_script_path
                # TODO -- rebake
                ]
            try:
                print(f"DEBUG: Esecuzione di: {' '.join(command)}")
                result = subprocess.run(
                    command,
                    check=True,
                    text=True,
                    capture_output=True,
                    #encoding=config.TOTAL_SEGMENTATOR_SNOMED_ENCODING
                    )

                print("--- BLENDER STDOUT (catturato) ---")
                print (result.stdout)
                if result.stderr:
                    print("\n--- OUTPUT PIPELINE BLENDER (stderr catturato) ---")
                    print(result.stderr)
                
                print("\n--- FASE 2: Pipeline Blender COMPLETATA con successo. ---")

            except subprocess.CalledProcessError as e: # Cattura il fallimento di Blender
                print(f"ERRORE CRITICO durante la pipeline di Blender. Codice di uscita: {e.returncode}")
                print(f"--- BLENDER STDOUT (catturato) ---")
                print(e.stdout)
                if e.stderr:
                    print(f"--- BLENDER STDERR (catturato) ---")
                    print(e.stderr)
                sys.exit(1)
            except FileNotFoundError: # Aggiunto per un controllo piu' specifico se lo script non e' trovato
                print(f"ERRORE: L'eseguibile di Blender o lo script della pipeline non sono stati trovati.")
                sys.exit(1)
            except Exception as e:
                print(f"ERRORE INATTESO durante il lancio di Blender: {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)

            print("\n--- Pipeline TAC 2 AR Terminata con Successo ---")

    except Exception as main_e:
        # Questo blocco cattura errori che si verificano prima o durante la configurazione del logging
        # o errori non catturati dai blocchi interni.
        # Stampa l'errore sulla console originale e poi tenta di scriverlo nel log se possibile.
        print(f"ERRORE FATALE in main.py: {main_e}", file=original_stderr)
        traceback.print_exc(file=original_stderr)
        
        # Se il log_file e' aperto, prova a scrivere anche li'
        if 'log_file' in locals() and not log_file.closed:
            print(f"ERRORE FATALE in main.py: {main_e}", file=log_file)
            traceback.print_exc(file=log_file)
        sys.exit(1)

    finally:
        # Ripristina stdout e stderr originali
        #sys.stdout = io.TextIOWrapper(original_stdout_buffer, encoding='utf-8', errors='replace')
        #sys.stderr = io.TextIOWrapper(original_stderr_buffer, encoding='utf-8', errors='replace')
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        print("Esecuzione terminata. Controlla pipeline.log per i dettagli.")
