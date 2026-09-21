# Sorties

`outputSchema` définit la valeur exacte renvoyée par le handler ; une sortie invalide
fait échouer le job avec InvalidOutput. `outputs` dans le descripteur d'opération
complète la documentation : id, type, description, optional, mimeType, fileExtension,
metadata. Types conventionnels : Text, JSON, StructuredData, File, Directory, Image,
ImageSet, Audio, Video, Mesh. Les types restent extensibles.

Pour des maps PBR, utiliser un objet avec propriétés baseColor, normal, roughness,
metallic, height, ao et déclarer explicitement required/optional. Le Core n'impose
aucun moteur ni format de modèle 3D.

Créer les fichiers avec `context.path('outputs/result.ext')`. Le chemin est résolu
dans le workspace du job ; une traversée `../` ou un lien pointant hors du workspace
est refusé au moment de la résolution. Ne pas laisser du code tiers modifier cette
arborescence en parallèle. Un accès local au disque sous le même compte OS ne constitue
pas une isolation de sécurité entre comptes système.

Les réponses HTTP exposent des métadonnées et des chemins côté serveur. La V1 ne
télécharge pas automatiquement les artefacts vers une machine cliente distante.
Un adaptateur distant doit fournir un mécanisme de transfert autorisé séparé.
