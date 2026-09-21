# Journaux, modèles personnalisés, LoRA et périphériques

Ces exigences concernent chaque interface autonome. Le runtime du Core reste sans
import graphique ni import de modèle. Les templates optionnels résident dans le Tool.

## Journal consultable et copiable

Conserver l’onglet Application log, anglais par défaut/français en option. Le champ
multiligne en lecture seule permet sélection souris, Ctrl+C et Ctrl+A. Le bouton
Copy entire log copie le fichier affiché. Pause/Refresh protège une sélection pendant
la réception de nouvelles lignes. Afficher le nom du fichier et une indication explicite
si son affichage est limité à ses derniers 8 Mio. La copie intégrale lit toutefois
tout le fichier sélectionné en arrière-plan, puis le place dans le presse-papiers.

`standalone_log.py` journalise le démarrage, Python logging, stdout/stderr de l’UI,
les exceptions et les événements du runtime obtenus avec le principal authentifié de
cette interface. Ne jamais parcourir les jobs privés des autres clients. Les journaux
des workers appartenant à ses jobs sont proposés dans le sélecteur de fichier.
Le journal principal `data/logs/standalone.log` tourne à 2 Mio, avec trois archives.
Les diagnostics des ProcessWorker terminés sont conservés dans le workspace du job
et publiés comme événements Log. Ne jamais rediriger stdout de la CLI/JSONL/MCP.
Masquer jetons, mots de passe et autorisations avant écriture/affichage/copie.

## Résolution vidéo et périphérique

Afficher les pixels **prévus avant génération**, puis les pixels **réellement encodés**
dans le résultat. Un ratio 16:9 ou une étiquette 480p ne suffit pas. Résoudre avec la
même politique de buckets, grille, taille source et upscaling que le worker ; si une
source manque, l’indiquer. Ne pas bloquer l’interface pour décoder une vidéo.

Proposer CPU / GPU / Auto seulement pour les chemins implémentés. Auto résout un
backend effectivement compatible ; un GPU Vulkan n’est pas un GPU CUDA. La sélection
doit atteindre l’estimateur puis le worker et figurer dans les paramètres sauvegardés.
Le mode CPU réserve de la RAM et aucune VRAM. Le déchargement CPU d’un moteur CUDA
n’est pas une inférence CPU. Expliquer les chemins GPU obligatoires/CPU uniquement.
Ne pas déclarer testé un périphérique sans exécution réelle.

## Bibliothèque locale et LoRA

Le template `model_options.py` étend le Runtime existant sans réécrire son scheduler.
`model-capabilities.json` déclare, par opération, les formats de modèles, formats de
LoRA, périphériques et éventuelles correspondances backend. Une capacité absente
reste indisponible ; ne pas ajouter un bouton qui ne modifie pas l’exécution.

`data/settings/model-library.json` suit `model-library.schema.json` : ID stable,
nom, chemin local, format, modèle de base, licence, source et niveau de validation.
Les fichiers sont référencés sur place. Aucun poids n’entre dans une sauvegarde JSON.
La structure du fichier peut être validée sans prouver sa qualité ni sa compatibilité
complète : le chargeur du moteur doit aussi refuser les tenseurs incompatibles.

Ajouter les champs `model_profile` et `loras` à l’inputSchema dans le générateur du
manifeste. Utiliser `extend_manifest` au build et les classes Runtime/ProcessWorker
du template dans l’adaptateur concerné. La sélection reste propre au job, y compris
avec un thread de surveillance ; aucune mutation globale de l’environnement pendant
une génération. Les wrappers de chemins doivent viser explicitement les fonctions
de configuration du moteur, jamais modifier ses poids officiels ou leurs reçus.
Pour une chaîne de composants, fournir le pack complet et conserver l’architecture,
la variante et la tâche compatibles. Ajuster RAM/VRAM pour les dérivés et les LoRA.

L’UI Models / compute ajoute et sélectionne les références locales. Elle configure
les intensités des LoRA compatibles. Save/Load/Autosave conserve la sélection réellement
soumise ; `outputs/model-selection.json` enregistre le détail du job. Pour une IA :

```text
python app/model_options.py capabilities
python app/model_options.py list
python app/model_options.py add --name MonDerive --path CHEMIN --format FORMAT --base BASE --license LICENCE
```

L’ID retourné s’utilise comme `model_profile` dans la CLI ou le MCP ; un LoRA devient
`loras: [{"id": "ID_RETOURNE", "strength": 0.8}]`. Le catalogue officiel reste
distinct du catalogue utilisateur, qui survit aux mises à jour de `app/`.

Une LoRA « quatre étapes » exige la bonne famille de modèle, les poids distillés,
la guidance, le scheduler et parfois deux réseaux high/low noise. Ne jamais appliquer
automatiquement une LoRA Wan à Hunyuan ou LTX. Un preset d’accélération doit déclarer
et appliquer l’ensemble de ces choix, avec un test réel. Réduire seulement steps à 4
ne constitue pas une prise en charge de la distillation.

Sources vérifiées : [LoRA Diffusers](https://huggingface.co/docs/diffusers/api/loaders/lora),
[LoRA LTX](https://docs.ltx.io/open-source-model/usage-guides/lo-ra),
[distillation LightX2V/Wan](https://lightx2v-en.readthedocs.io/en/latest/method_tutorials/step_distill.html).

## Validation

Vérifier copie intégrale et sélection native, masquage des secrets (y compris écritures
fragmentées), journalisation d’un worker défaillant, persistance et limites de taille.
Comparer la résolution affichée au calcul du moteur et au fichier final.
Tester les chemins CPU/GPU disponibles, les modèles dérivés et les LoRA sur le vrai
chargeur, ainsi que le rejet d’une famille incompatible. Un test de tenseurs réduit
valide le chargement/pondération d’un LoRA, pas la qualité d’une génération complète.
