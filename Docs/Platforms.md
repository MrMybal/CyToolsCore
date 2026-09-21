# Plateformes

Les niveaux Tool, Operation, Backend et Model peuvent déclarer des plateformes.
Une entrée contient os, architecture, status, et éventuellement minimumOSVersion,
computeBackends, notes, tested. OS et architectures restent des strings extensibles.
Conventions initiales : Windows/Linux/macOS, x64/ARM64 ; compute : CPU, CUDA, ROCm,
DirectML, Vulkan, Metal, MPS et valeurs personnalisées.

Status est Supported, Experimental, Unsupported ou Unknown. Unknown n'autorise jamais
une exécution comme si elle était Supported. Le Tool doit avoir au moins une entrée
admissible pour la machine. Une restriction supplémentaire d'opération/backend/modèle
doit également être satisfaite. Sans restriction à ces niveaux, celle du Tool s'applique.

Experimental autorise l'exécution tout en restant explicitement signalé par CanRun.
Une entrée tested documente osVersion/device/driver/runtime/date/status ; elle ne doit
être ajoutée que si le test a réellement été exécuté.

Dans cette V1, minimumOSVersion est traité conservativement par correspondance exacte
avec osVersion détectée. Ne pas utiliser une version marketing ambiguë pour autoriser
implicitement toutes les versions futures. La comparaison propre à chaque OS peut
être ajoutée dans un provider de compatibilité.

Windows x64 est la plateforme locale de validation. Linux x64 est une cible déclarée
et macOS ARM64 une cible expérimentale. La CI fournit la matrice nécessaire ; ses
résultats devront être observés avant de remplir tested pour ces systèmes.
