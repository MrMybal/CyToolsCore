# Manifest du Tool

Source normative : `cytools_core/schemas/tool.schema.json`.
Chargement : `load_manifest(path)` ; validation CLI : `cytools validate CyTool.json`.
Exemple complet exécutable : `cytool_test/CyTool.json`.

Champs obligatoires : schemaVersion, protocolVersion, id, name, version, description,
operations, platforms, concurrency. Un id commence par une lettre puis contient des
lettres ASCII, chiffres, `_`, `.` ou `-`, au maximum 128 caractères.

Champs d'identité optionnels : displayName, vendor, author, categories, tags, executable,
license, documentation, homepage, repository. Le manifest ne lance pas executable :
c'est une indication de découverte et d'installation.

Champs de capacités : capabilities, interfaces, backends, runtimeRequirements,
idleUnloadPolicy. Chaque opération porte ses schémas et ses capacités propres.
Le runtime vérifie l'unicité des IDs et les références aux backends.

Les champs inconnus sont préservés ; `extensions` permet les ajouts propres à un Tool.
Les paramètres métier peuvent au contraire refuser les champs inconnus avec
additionalProperties:false. Version majeure incompatible → IncompatibleVersion.
Ne pas placer de clés API, jetons, comptes utilisateur ou chemins privés de développeur
dans un manifest distribuable.
