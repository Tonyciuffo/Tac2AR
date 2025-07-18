TactoAR
Software per la segmentazione di immagini mediche e la creazione di modelli 3D.

Prerequisiti: Python 3.10
Python 3.10 o versioni successive sono necessarie per far girare il progetto.
Puoi scaricare l'ultima versione dal sito ufficiale di Python: https://www.python.org/downloads/

Installazione:

1) Crea un ambiente virtuale con venv:

Windows: python -m venv venv
Linux/MacOs: python3 -m venv venv

2) Attiva l'ambiente virtuale:

Windows: venv\Scripts\activate
Linux/macOS: source venv/bin/activate

3) Per abilitare l'accelerazione GPU installa PyTorch con CUDA (scegli la versione adatta alla tua scheda video):

RTX serie 30/40:
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

RTX serie 50 e superiori:
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

4) Scarica Blender 4.2 LTS da qui e copia la cartella nella directory "Blender" del progetto:

Windows: https://download.blender.org/release/Blender4.2/blender-4.2.9-windows-x64.zip
Linux: https://download.blender.org/release/Blender4.2/blender-4.2.9-linux-x64.tar.xz
MacOs (x64 - Intel): https://download.blender.org/release/Blender4.2/blender-4.2.9-macos-x64.dmg
MacOs (arm64 -AMD): https://download.blender.org/release/Blender4.2/blender-4.2.9-macos-arm64.dmg

5) Modifica i percorsi in config.py a seconda delle necessità

6) Metti uno stack di DICOM nella directory Input ed esegui con:
python Main.py


7) E' possibile lanciare i processi di segmentazione e di fix delle geometrie indipendentemente con:
python execute_segmentator_pipeline.py
python execute_blender_pipeline-py // da testare bene

