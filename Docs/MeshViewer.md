# Visualisation 3D obligatoire pour les Tools de maillage

Tout Tool autonome qui génère, remeshe, texture, déplie ou rigge un mesh fournit
un vrai visualiseur interactif Dear ImGui. Une image fixe ou un bouton qui ouvre
un logiciel externe ne suffit pas. Le résultat terminé s'ouvre automatiquement.

## Interaction

- Orbite par défaut : glisser avec le bouton gauche ; molette pour approcher/éloigner.
- Bouton droit : regarder autour de la position de caméra ; mode Free camera disponible.
- Bouton central ou Maj+gauche : déplacement latéral/vertical de la caméra et du pivot.
- WASD ou ZQSD, ou flèches : avancer/reculer et gauche/droite. Espace/Ctrl : haut/bas.
- Q/E (A/E en AZERTY) : roulis. Maj accélère, Alt affine ; F recadre le mesh.
- Double-clic sur une surface visible : nouveau pivot à cet endroit pour examiner un détail.
- Aucune limite de distance liée à la taille du mesh. Seules subsistent les protections
  numériques ; le plan proche s'adapte. Le mode libre permet de traverser une surface.
- Aucun curseur Rotation/Elevation/Distance requis. Les commandes souris/clavier sont
  limitées au viewport actif et ne détournent pas la saisie des autres champs.

## Scène et matériaux

Scènes studio sombre, studio clair et extérieur ; sol/grille optionnels. Éclairages
studio à trois points, soleil directionnel, lumière de caméra et mode sans éclairage.
Positions/direction, couleurs, intensités et exposition sont réglables. Le fichier
mesh reste intact. Le rendu prend en charge couleur de base, couleurs par sommet,
métal/rugosité, normales, émission, occlusion et modes alpha usuels.

Le shader fournit une prévisualisation PBR avec remplissage ambiant approximatif,
sans HDRI, ombres portées ni validation photométrique. Les rigs sont affichés dans
leur pose stockée ; ce module ne joue pas les animations. La géométrie est
triangulée pour l'affichage, y compris en filaire ; l'export quad n'est pas modifié.

## Intégration fournie

Utiliser `cytools new CHEMIN --name NOM --id ID --desktop --mesh-viewer`.
Le scaffold ajoute `app/mesh_viewer.py`, `app/mesh_viewer_ui.py`, active
`app/mesh-viewer.json` et déclare les dépendances dans le Tool : ModernGL,
trimesh, NumPy et Pillow. Aucun import graphique ou IA dans le runtime du Core.

La façade ui_common installe le panneau sur le runtime de cette interface. Elle
observe uniquement les résultats des appels authentifiés effectués par l'UI et
poll les jobs soumis par cette UI même si l'utilisateur change d'onglet. Elle ne
scanne pas les jobs privés d'autres clients. Ne jamais lire runtime._jobs pour cela.

Sorties reconnues : material_mesh_file, rigged_mesh, mesh_file, mesh, file. Formats
GLB, glTF, OBJ/MTL, PLY, STL et OFF. Pour un contrat différent, adapter mesh_outputs
ou appeler MeshPanel.open(path) explicitement après la fin du job. Ne pas annoncer
FBX ou formats spécifiques sans adaptateur vérifié. Les fichiers distants ne sont
pas chargés ; textures/buffers locaux sont confinés au dossier du mesh.

Les opérations PBR qui n'exportent que des textures doivent quand même produire
un mesh d'aperçu dans le workspace du job, avec les UV réellement utilisés et les
textures produites. Un sidecar `preview.glb` à côté de report_file est reconnu.
Documenter cet artefact privé ; ne pas modifier la signification des sorties publiques.

Le thread de rendu détient son propre contexte OpenGL et le libère à la fermeture.
Le viewer met son rendu en pause lors d'un job de l'UI. Les préférences et le dernier
fichier explicitement ouvert sont dans data/settings/mesh-viewer.json.
Préserver les intégrations existantes et sauvegarder les fichiers avant migration.

## Vérification avant livraison

Tester un vrai résultat de chaque Tool et les variantes de format annoncées, les
couleurs par sommet, les textures/PBR, l'ouverture automatique sur Completed,
le changement de scène/lumières, l'inspection rapprochée, les mouvements/roulis,
le changement de pivot et la fermeture du renderer. Tester aussi échec de fichier,
absence de dépendance et état Cancelled/Failed sans ouverture de faux résultat.
Contrôler visuellement les captures EN/FR. Un test de création de fenêtre seul ne
prouve pas que le mesh est affiché. Les fixtures ne remplacent pas les vrais outputs.

Sources des interfaces de rendu : [ModernGL](https://moderngl.readthedocs.io/en/5.8.2/reference/context.html),
[trimesh](https://trimesh.org/trimesh.html) et [matériaux PBR](https://trimesh.org/trimesh.visual.material.html).
