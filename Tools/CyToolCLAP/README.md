# CyToolCLAP — identifier le contenu d'un son ou d'une musique

Prototype CLI/MCP de démonstration utilisant CyToolsCore avec un modèle local.
Il ne constitue pas un modèle de livraison standalone pour les nouveaux Tools.
**CLAP compare l'audio à des descriptions** : aboiement, pluie, piano, trompette, parole,
orchestre, etc. Il ne recherche pas le titre/artiste d'un enregistrement comme Shazam.

Le modèle est `laion/clap-htsat-unfused`, révision immuable
`8fa0f1c6d0433df6e97c127f64b2a1d6c0dcda8a`. Les poids officiels (~615 Mo) ont été
téléchargés et vérifiés par SHA256. L'inférence utilise CPU, 4 threads, sans requête
réseau ni envoi de l'audio. Les dépendances du modèle sont dans une venv propre au Tool.

## Essayer maintenant

Après avoir créé la venv du Tool, installé requirements.txt et CyToolsCore,
puis exécuté install_model.py et download_samples.py, depuis la racine de CyToolsCore :

```powershell
.\Tools\CyToolCLAP\Test-CLAP.ps1 -AudioFile dog.wav
.\Tools\CyToolCLAP\Test-CLAP.ps1 -AudioFile rain.wav
.\Tools\CyToolCLAP\Test-CLAP.ps1 -AudioFile trumpet.ogg -Preset music
.\Tools\CyToolCLAP\Test-CLAP.ps1 -AudioFile pistachio.ogg -Preset music
```

Alternative Python sans script PowerShell :

```powershell
.\Tools\CyToolCLAP\.venv\Scripts\python Tools/CyToolCLAP/tool.py invoke classify_audio --params-file Tools/CyToolCLAP/params.json --timeout 600
```

Le JSON contient le job, ses candidats classés et le chemin `outputs.report_file`.
Un rapport JSON est écrit dans le workspace privé du job. Le modèle est arrêté avec
son worker avant le passage du job à Completed et la libération de sa réservation.

## Analyser son propre fichier

Copier le fichier dans `Tools/CyToolCLAP/audio/`, puis passer son nom à Test-CLAP.ps1.
On peut aussi définir `CYTOOLS_CLAP_AUDIO_ROOT` sur un dossier choisi avant le lancement.
Le Tool refuse les fichiers en dehors de ce dossier, y compris via `../` ou un lien
résolu à l'extérieur. Le dossier autorisé est partagé entre les clients du service :
ne pas y placer de fichiers qu'ils ne doivent pas pouvoir analyser.

Créer un fichier de paramètres, par exemple :

```json
{
  "audio_file": "mon-extrait.wav",
  "preset": "general",
  "top_k": 5,
  "max_seconds": 30
}
```

Presets : general (28 descriptions), sounds (16), music (12). Les labels sont en
français et les descriptions comparées au modèle en anglais. Pour une classification
personnalisée, ajouter `candidate_labels`, liste de 2 à 128 descriptions **en anglais** :
elle remplace le preset. Exemples : `A recording of jazz music`, `A recording of heavy
metal music`, `A recording of classical orchestral music`. Les textes sont limités à
256 caractères et tokenisés au maximum sur 77 tokens.

WAV/FLAC/OGG/MP3 sont transmis à libsndfile ; un codec non décodable donne une erreur.
WAV et OGG ont été vérifiés ici. Maximum 256 Mio par fichier, mono/stéréo, 8 à 192 kHz.
L'audio est converti en mono 48 kHz et traité par fenêtres de 10 secondes. Seules les
premières max_seconds sont analysées (30 par défaut, 120 maximum). Un avertissement
signale la troncature. La moyenne des similarités est pondérée par la durée des fenêtres.

`relative_score` est un softmax parmi les candidats proposés, **pas une probabilité
de vérité**. `cosine_similarity` est la similarité audio/texte. Une classe absente de
la liste ne peut pas être détectée ; des sons mixtes ou inconnus peuvent être mal classés.
Le silence est refusé. Ce Tool ne produit ni transcription, ni BPM, ni titre de chanson.

## Installation reproductible

Depuis la racine du SDK, Python 3.11 :

```powershell
python -m venv Tools/CyToolCLAP/.venv
.\Tools\CyToolCLAP\.venv\Scripts\python -m pip install --keyring-provider disabled -r Tools/CyToolCLAP/requirements.txt 'dist/cytools_core-0.1.0-py3-none-any.whl[mcp]'
.\Tools\CyToolCLAP\.venv\Scripts\python Tools/CyToolCLAP/install_model.py
.\Tools\CyToolCLAP\.venv\Scripts\python Tools/CyToolCLAP/download_samples.py
```

Sous Linux/macOS, adapter le chemin de l'interpréteur en `.venv/bin/python`.
Le wheel du Core doit être fourni avec le projet ou installé depuis le checkout.
`CYTOOLS_CLAP_MODEL_DIR` permet de choisir le dossier de poids avant installation
et lancement. Relancer install_model.py revérifie les fichiers. Aucun téléchargement
implicite pendant classify_audio ; un modèle absent donne MissingModel.

## CLI, API et MCP

Toutes les façades sont celles du SDK. `describe`, `list-operations`, `diagnose`,
`create-client`, `serve`, `stdio`, `mcp` restent disponibles.
Le MCP expose `op_classify_audio` et les contrôles `cy_get_job`, `cy_cancel_job`, etc.
Commande d'un client MCP : interpréteur de la venv, arguments absolus `tool.py mcp`.
Arguments d'appel : `{"parameters":{"audio_file":"dog.wav","preset":"general"}}`.
La réponse initiale est un job : consulter son état jusqu'à Completed/Failed/Cancelled.

Un service HTTP unique et des ponts `--connect URL mcp` permettent de partager le
scheduler entre clients. La politique est Sequential ; le modèle est rechargé pour
chaque job. Budget conservateur réservé : 6 Gio RAM, 4 threads, 300 Mio disque ; aucun
GPU réservé. Le pic mesuré sur les petits extraits est proche de 1 Gio. Ce n'est pas
une mesure garantie pour tous les fichiers/versions de runtime.

## Validation du 20 septembre 2026

Windows x64 / CPU, quatre fichiers publics, preset general de 28 candidats :

| Extrait | Premier résultat | Temps du job |
|---|---|---|
| ESC-50 : chien | Chien qui aboie | ~5 s |
| ESC-50 : pluie | Pluie | ~5 s |
| Mihai Sorohan : trumpet loop | Trompette | ~5 s |
| Lena Orsa : Pistachio Ice Cream Ragtime | Piano | ~5 s |

Les quatre premières classes correspondent aux annotations publiques. Il s'agit d'un
test fonctionnel réduit, pas d'un taux de précision général : ces données peuvent
recouper l'entraînement de CLAP. Deux clients, isolation et libération des réservations
ont été vérifiés ; une inférence trompette a aussi réussi via le protocole MCP réel.

```powershell
.\Tools\CyToolCLAP\.venv\Scripts\python -m unittest discover -s Tools/CyToolCLAP -p test_tool.py -v
.\Tools\CyToolCLAP\.venv\Scripts\python Tools/CyToolCLAP/validate_public.py
```

Sept tests techniques couvrent manifest/defaults, entrées invalides, chemins autorisés,
modèle absent, jobs privés, audio invalide, candidats personnalisés et annulation avec
arrêt du worker. Rapports détaillés : `reports/public-validation.json` et
`reports/mcp-validation.json`. Linux/macOS restent expérimentaux et non testés ici.

## Sources et attributions

- [Modèle CLAP officiel, Apache-2.0](https://huggingface.co/laion/clap-htsat-unfused).
- [Documentation Transformers CLAP](https://huggingface.co/docs/transformers/model_doc/clap).
- [ESC-50](https://github.com/karolpiczak/ESC-50) : dataset CC BY-NC 3.0, sons Freesound.
- [Exemples librosa](https://librosa.org/doc/main/recordings.html).
- Trompette : Mihai Sorohan, [Freesound 77711](https://freesound.org/s/77711/), CC BY 3.0.
- Piano : The Piano Lady / Lena Orsa, [Freesound 442789](https://freesound.org/people/lena_orsa/sounds/442789/), CC BY-NC 3.0.

`audio/SOURCES.json` conserve URLs, métadonnées, licences et SHA256 des fichiers publics.
Les poids, environnements, échantillons et rapports locaux sont ignorés par Git.
Le Core ne dépend pas de CLAP : ce dossier est un Tool séparé généré avec `cytools new`.
