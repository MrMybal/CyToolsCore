# Vue d'ensemble

Un CyTool est une application autonome. Il décrit ses opérations avec `CyTool.json`
et les exécute au moyen de CyToolsCore. Les clients découvrent le Tool, valident les
paramètres, créent une session et soumettent des jobs. Le même runtime sert toutes
les façades d'un processus.

Le socle accepte une opération Python, un wrapper de programme, un runtime IA local,
une API distante ou un worker natif. Il ne contient aucun modèle IA ni interface graphique.
Le modèle logique est Tool → Operation → Backend → Model/Runtime ; les deux derniers
niveaux sont facultatifs pour un outil simple.

Commencer par [CreatingYourFirstCyTool](CreatingYourFirstCyTool.md), ou donner
[AgentGuide](AgentGuide.md) à une IA. Pour intégrer un client d'un autre langage,
lire [Protocol](Protocol.md). L'état des fonctions est dans
[ImplementationStatus](ImplementationStatus.md).
