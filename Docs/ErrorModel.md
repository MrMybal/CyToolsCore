# Erreurs

CyToolError sérialise code, message, technicalDetails, recoverable et suggestedAction.
Les codes restent des strings extensibles ; un client doit conserver un code inconnu.
Les exceptions métier attendues ne doivent pas devenir des retours de succès ambigus.

Codes courants : InvalidDescriptor, IncompatibleVersion, InvalidParameters, InvalidOutput,
MissingImplementation, UnknownOperation, MissingDependency, MissingRuntime, MissingModel,
UnsupportedPlatform, UnsupportedBackend, InsufficientRAM, InsufficientVRAM,
InsufficientDisk, UnsupportedCPU, AccessDenied, AuthenticationRequired, Busy, Timeout,
Cancelled, Interrupted, WorkerCrashed, ProtocolError, DownloadFailed, IntegrityFailure,
LicenseAcceptanceRequired, InternalError.

SubmitJob refusé retourne une erreur sans créer un job. Un handler qui échoue donne
un job Failed avec error. Une lecture GetJob réussie d'un job Failed ne transforme
pas l'opération en succès. Une exception inattendue du handler est InternalError.

Les détails d'erreur ou logs métier peuvent contenir des données utilisateur : le
backend doit expurger les secrets avant context.log ou technicalDetails. Le Core ne
prétend pas détecter tous les secrets arbitraires. L'API HTTP masque les exceptions
internes du dispatcher en dehors des erreurs structurées connues.
